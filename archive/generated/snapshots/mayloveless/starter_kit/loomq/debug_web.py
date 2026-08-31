"""Thin local HTTP API for the LoomQ debug trace UI."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import unquote, urlsplit

from .backend_selector import (
    Backend,
    BackendConstraints,
    load_backends,
    load_capability_version,
    select_backends,
)
from .debug_cli import build_debug_trace
from .qasm_tools import QASMValidationError, validate_qasm
from .real_hardware import (
    RealHardwareNotConfigured,
    RealHardwareOperationError,
    capability_status,
    get_job,
    submit_bell,
)
from .teaching_explainer import TeachingExplanation, explain_validated_circuit


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
MAX_REQUEST_BYTES = 64 * 1024
DebugBuilder = Callable[[str], tuple[str, Sequence[Any]]]
TeachingExplainer = Callable[
    [str, str, Sequence[Any]], TeachingExplanation | None
]
_BACKEND_CONSTRAINT_FIELDS = {
    "min_qubits",
    "require_qpu",
    "require_no_queue",
    "cost_policy",
    "allow_account_required",
}


def build_debug_payload(
    prompt: str,
    *,
    debug_builder: DebugBuilder = build_debug_trace,
    teaching_explainer: TeachingExplainer = explain_validated_circuit,
) -> dict[str, Any]:
    """复用共享 Trace 入口，并把事件转换成稳定的 JSON 数据。"""
    reply, events = debug_builder(prompt)
    final_qasm = next(
        (
            event.data["qasm"]
            for event in reversed(events)
            if event.layer == "agent"
            and event.stage == "agent_result"
            and isinstance(event.data.get("qasm"), str)
        ),
        None,
    )
    teaching = None
    if final_qasm is not None:
        circuit_events = tuple(event for event in events if event.layer == "circuit")
        # Explainer 只在 Web payload 组装阶段运行；失败不影响 reply/events。
        try:
            teaching = teaching_explainer(prompt, final_qasm, circuit_events)
        except Exception:
            teaching = None
    return {
        "reply": reply,
        "events": [event.as_dict() for event in events],
        "teaching": teaching.as_dict() if teaching is not None else None,
    }


def _repair_request_prompt(goal: str, qasm: str) -> str:
    """集中构造 repair_qasm 用户请求，保持目标与原始程序原样参与判断。"""
    return (
        "请检查并修复下面的 OpenQASM 2.0 程序。\n"
        "保持用户明确声明的目标功能和测量语义不变。\n\n"
        "用户期望：%s\n\n"
        "原始程序：\n%s" % (goal, qasm)
    )


def build_repair_payload(
    goal: str,
    qasm: str,
    *,
    debug_builder: DebugBuilder = build_debug_trace,
) -> dict[str, Any]:
    """检查原始输入，并复用 production L2 Trace 取得真实修复提案。"""
    try:
        validate_qasm(qasm)
    except QASMValidationError as exc:
        input_validation = {
            "status": "error",
            "diagnostic": exc.diagnostic,
        }
    else:
        input_validation = {"status": "ok", "diagnostic": None}

    reply, events = debug_builder(_repair_request_prompt(goal, qasm))
    final_event = next(
        (
            event
            for event in reversed(events)
            if event.layer == "agent" and event.stage == "agent_result"
        ),
        None,
    )
    repaired_qasm = None
    if final_event is not None and final_event.status == "ok":
        candidate = final_event.data.get("qasm")
        if isinstance(candidate, str) and candidate.strip():
            repaired_qasm = candidate

    return {
        "input_validation": input_validation,
        "reply": reply,
        "repaired_qasm": repaired_qasm,
        "events": [event.as_dict() for event in events],
    }


def _backend_payload(backend: Backend) -> dict[str, Any]:
    return {
        "id": backend.id,
        "name": backend.name,
        "kind": backend.kind,
        "max_qubits": backend.max_qubits,
        "queue": backend.queue,
        "cost": backend.cost,
        "requires_account": backend.requires_account,
    }


def _backend_match_reasons(
    backend: Backend, constraints: BackendConstraints
) -> list[str]:
    """只解释 selector 真正使用过的约束，不把未限制字段写成优势。"""
    reasons = []
    if constraints.min_qubits is not None:
        reasons.append(
            "%d qubits ≥ 需要的 %d"
            % (backend.max_qubits, constraints.min_qubits)
        )
    if constraints.require_qpu is True:
        reasons.append("类型为真机 QPU")
    if constraints.require_no_queue:
        reasons.append("能力表队列分类为 none")
    if constraints.cost_policy == "free_only":
        reasons.append("能力表成本分类为 free")
    elif constraints.cost_policy == "free_or_quota":
        reasons.append("成本分类属于 free / free_quota")
    if constraints.allow_account_required is False:
        reasons.append("能力表标记为无需账号")
    return reasons


def _backend_exclusion_reasons(
    backend: Backend, constraints: BackendConstraints
) -> list[str]:
    """逐项镜像 select_backends() 的现有排除条件。"""
    reasons = []
    if (
        constraints.min_qubits is not None
        and backend.max_qubits < constraints.min_qubits
    ):
        reasons.append(
            "只有 %d qubits，不满足至少 %d qubits"
            % (backend.max_qubits, constraints.min_qubits)
        )
    if constraints.require_qpu is True and backend.kind != "qpu":
        reasons.append("类型为 %s，不是真机 QPU" % backend.kind)
    if constraints.require_no_queue and backend.queue != "none":
        reasons.append("能力表队列分类为 %s，不满足零排队" % backend.queue)
    if constraints.cost_policy == "free_only" and backend.cost != "free":
        reasons.append("成本分类为 %s，不满足完全免费" % backend.cost)
    if constraints.cost_policy == "free_or_quota" and backend.cost not in (
        "free",
        "free_quota",
    ):
        reasons.append("成本分类为 %s，不属于免费或免费额度" % backend.cost)
    if constraints.allow_account_required is False and backend.requires_account:
        reasons.append("能力表标记为需要账号")
    return reasons


def _relaxation_categories(constraints: BackendConstraints) -> list[str]:
    categories = []
    if constraints.min_qubits is not None:
        categories.append("比特数")
    if constraints.require_qpu is True:
        categories.append("真机")
    if constraints.require_no_queue:
        categories.append("零排队")
    if constraints.cost_policy in ("free_only", "free_or_quota"):
        categories.append("费用")
    if constraints.allow_account_required is False:
        categories.append("账号")
    return categories or ["当前约束"]


def build_backend_payload(
    prompt: str,
    *,
    debug_builder: DebugBuilder = build_debug_trace,
) -> dict[str, Any]:
    """复用 production Trace，并用本地能力表解释匹配与排除原因。"""
    _, events = debug_builder(prompt)
    constraint_event = next(
        (
            event
            for event in reversed(events)
            if event.layer == "agent" and event.stage == "backend_constraints"
        ),
        None,
    )
    selected_event = next(
        (
            event
            for event in reversed(events)
            if event.layer == "agent" and event.stage == "backend_selected"
        ),
        None,
    )
    if constraint_event is None or selected_event is None:
        raise RuntimeError("backend selection trace is incomplete")
    if not _BACKEND_CONSTRAINT_FIELDS.issubset(constraint_event.data):
        raise RuntimeError("backend constraints trace is incomplete")

    try:
        constraints = BackendConstraints(
            min_qubits=constraint_event.data.get("min_qubits"),
            require_qpu=constraint_event.data.get("require_qpu"),
            require_no_queue=constraint_event.data.get("require_no_queue"),
            cost_policy=constraint_event.data.get("cost_policy"),
            allow_account_required=constraint_event.data.get(
                "allow_account_required"
            ),
        )
    except ValueError:
        raise RuntimeError("backend constraints trace is invalid") from None

    trace_ids = selected_event.data.get("backend_ids")
    if not isinstance(trace_ids, list) or not all(
        isinstance(backend_id, str) for backend_id in trace_ids
    ):
        raise RuntimeError("backend selection trace has invalid backend ids")

    backends = load_backends()
    local_ids = [backend.id for backend in select_backends(constraints)]
    if trace_ids != local_ids:
        raise RuntimeError("backend selection trace does not match local selector")
    raw_no_match = selected_event.data.get("no_match")
    if not isinstance(raw_no_match, bool):
        raise RuntimeError("backend selection trace has invalid no-match state")
    no_match = raw_no_match
    if no_match != (not bool(trace_ids)):
        raise RuntimeError("backend selection trace has inconsistent no-match state")

    matched_ids = set(trace_ids)
    matches = []
    excluded = []
    for backend in backends:
        if backend.id in matched_ids:
            matches.append(
                {
                    **_backend_payload(backend),
                    "match_reasons": _backend_match_reasons(backend, constraints),
                }
            )
        else:
            reasons = _backend_exclusion_reasons(backend, constraints)
            if not reasons:
                raise RuntimeError("backend exclusion does not match local selector")
            excluded.append(
                {**_backend_payload(backend), "exclusion_reasons": reasons}
            )

    return {
        "constraints": {
            "min_qubits": constraints.min_qubits,
            "require_qpu": constraints.require_qpu,
            "require_no_queue": constraints.require_no_queue,
            "cost_policy": constraints.cost_policy,
            "allow_account_required": constraints.allow_account_required,
        },
        "matches": matches,
        "excluded": excluded,
        "no_match": no_match,
        "relaxation_categories": (
            _relaxation_categories(constraints) if no_match else []
        ),
        "capability_version": load_capability_version(),
        "events": [event.as_dict() for event in events],
    }


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class DebugRequestHandler(BaseHTTPRequestHandler):
    """Serve the local Web workspaces through thin production-backed APIs."""

    server_version = "LoomQDebug/1.0"

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_web_asset(self) -> bool:
        """按需托管已构建的前端资源，API 路由始终优先。"""
        web_dist = getattr(self.server, "web_dist", None)
        if not isinstance(web_dist, Path) or not web_dist.is_dir():
            return False

        request_path = unquote(urlsplit(self.path).path)
        relative_path = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        try:
            candidate = (web_dist / relative_path).resolve()
            candidate.relative_to(web_dist.resolve())
        except (OSError, ValueError):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "页面不存在。"})
            return True

        # 前端采用单页应用；非静态资源路径回退到入口页面。
        if not candidate.is_file() and "." not in Path(relative_path).name:
            candidate = web_dist / "index.html"
        if not candidate.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "页面不存在。"})
            return True

        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if candidate.name == "index.html" else "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(body)
        return True

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if self.path == "/api/real-hardware/status":
            self._send_json(HTTPStatus.OK, capability_status())
            return
        job_prefix = "/api/real-hardware/status/"
        if self.path.startswith(job_prefix):
            job_id = self.path[len(job_prefix):]
            if not job_id or "/" in job_id or "?" in job_id:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在。"})
                return
            try:
                payload = get_job(job_id)
            except RealHardwareNotConfigured:
                self._send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error_code": "SPINQ_NOT_CONFIGURED", "message": "真实量子设备未配置"},
                )
                return
            except RealHardwareOperationError:
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {"error_code": "SPINQ_OPERATION_FAILED", "message": "真实量子设备操作未完成"},
                )
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if self._serve_web_asset():
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在。"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path not in (
            "/api/debug", "/api/repair", "/api/backend", "/api/real-hardware/run"
        ):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "接口不存在。"})
            return

        if self.path == "/api/real-hardware/run":
            self._handle_real_hardware_run()
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            # 三个工作区分别保留自己的输入错误文案。
            if self.path == "/api/repair":
                error = "请输入有效的修复目标和 OpenQASM。"
            elif self.path == "/api/backend":
                error = "请输入有效的后端要求。"
            else:
                error = "请输入有效的调试请求。"
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": error},
            )
            return

        try:
            raw_body = self.rfile.read(content_length)
            request = json.loads(raw_body.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("invalid request")
            if self.path in ("/api/debug", "/api/backend"):
                prompt = request.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError("invalid prompt")
                request_args = (prompt.strip(),)
            else:
                goal = request.get("goal")
                qasm = request.get("qasm")
                if (
                    not isinstance(goal, str)
                    or not goal.strip()
                    or not isinstance(qasm, str)
                    or not qasm.strip()
                ):
                    raise ValueError("invalid repair request")
                request_args = (goal.strip(), qasm.strip())
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": (
                        "请输入有效的修复目标和 OpenQASM。"
                        if self.path == "/api/repair"
                        else (
                            "请输入有效的后端要求。"
                            if self.path == "/api/backend"
                            else "请输入有效的调试请求。"
                        )
                    )
                },
            )
            return

        try:
            if self.path == "/api/debug":
                payload = build_debug_payload(*request_args)
            elif self.path == "/api/repair":
                payload = build_repair_payload(*request_args)
            else:
                payload = build_backend_payload(*request_args)
        except Exception:
            # 浏览器只接收固定安全文案，不暴露模型响应、凭证、路径或 traceback。
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": (
                        "这次检查没有完成，请检查模型配置后重试。"
                        if self.path == "/api/repair"
                        else (
                            "这次推荐没有完成，请检查模型配置后重试。"
                            if self.path == "/api/backend"
                            else "这次调试没有完成，请检查模型配置后重试。"
                        )
                    )
                },
            )
            return
        self._send_json(HTTPStatus.OK, payload)

    def _handle_real_hardware_run(self) -> None:
        """处理固定 Bell 真机请求，不接受任意电路或平台参数。"""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length < 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请输入有效的真机实验请求。"})
            return
        try:
            request = (
                json.loads(self.rfile.read(content_length).decode("utf-8"))
                if content_length else {}
            )
            if not isinstance(request, dict):
                raise ValueError("invalid real hardware request")
            # MVP 仅允许 Bell/SpinQ，避免该入口变成通用远程代码执行接口。
            if request.get("circuit", "bell") != "bell" or request.get("platform", "spinq") != "spinq":
                raise ValueError("unsupported real hardware request")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "仅支持提交 SpinQ Bell 实验。"})
            return
        try:
            payload = submit_bell()
        except RealHardwareNotConfigured:
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error_code": "SPINQ_NOT_CONFIGURED", "message": "真实量子设备未配置"},
            )
            return
        except RealHardwareOperationError:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {"error_code": "SPINQ_OPERATION_FAILED", "message": "真实量子设备操作未完成"},
            )
            return
        self._send_json(HTTPStatus.OK, payload)

    def log_message(self, format: str, *args: Any) -> None:
        # 保留简洁请求日志，不记录请求正文和模型信息。
        super().log_message(format, *args)


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    web_dist: Path | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), DebugRequestHandler)
    server.web_dist = web_dist  # type: ignore[attr-defined]
    return server


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoomQ 本地 Quantum DevTools API")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--serve-web",
        action="store_true",
        help="托管已构建的 LoomQ Web 页面（Docker 单容器部署使用）。",
    )
    parser.add_argument(
        "--web-dist",
        type=Path,
        default=DEFAULT_WEB_DIST,
        help="前端构建产物目录；仅与 --serve-web 一起使用。",
    )
    args = parser.parse_args(argv)
    web_dist = args.web_dist if args.serve_web else None
    if web_dist is not None and not web_dist.is_dir():
        parser.error("前端构建产物目录不存在：%s" % web_dist)
    server = create_server(args.host, args.port, web_dist)
    print("LoomQ debug API: http://%s:%d" % server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_backend_payload",
    "build_debug_payload",
    "build_repair_payload",
    "capability_status",
    "create_server",
    "main",
]
