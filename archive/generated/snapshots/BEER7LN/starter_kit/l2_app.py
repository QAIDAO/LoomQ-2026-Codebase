#!/usr/bin/env python3
"""Accessible local web entry for the LoomQ L2 agent."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

if __package__:
    from .adapter import agent_chat
    from . import learning
    from .loomq.qasm import MeasureOperation, parse_openqasm2
    from .loomq.simulator import run_local
    from .loomq.web_hardware import (
        JOBS,
        PROFILES,
        ProfileNotFoundError,
        ProfileReadOnlyError,
        configure_hardware,
    )
else:
    from adapter import agent_chat
    import learning
    from loomq.qasm import MeasureOperation, parse_openqasm2
    from loomq.simulator import run_local
    from loomq.web_hardware import (
        JOBS,
        PROFILES,
        ProfileNotFoundError,
        ProfileReadOnlyError,
        configure_hardware,
    )


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
EVIDENCE_ROOT = ROOT / "evidence" / "files"
QASM_PATTERN = re.compile(
    r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE
)
FENCED_QASM_PATTERN = re.compile(
    r"```(?:qasm|openqasm)?\s*\n?(OPENQASM\s+2\.0;.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


MODE_PREFIXES = {
    "generate": "Task mode: generate a complete measured OpenQASM 2.0 circuit.",
    "repair": "Task mode: repair the supplied circuit while preserving the user's intent.",
    "select": "Task mode: select a backend that satisfies every stated constraint.",
}

HARDWARE_ENVIRONMENTS = (
    {
        "id": "originq_wukong",
        "name": "本源悟空 180",
        "platform": "originq",
        "module": "pyqpanda3",
        "required": ("LOOMQ_ORIGINQ_API_TOKEN", "LOOMQ_ORIGINQ_BACKEND"),
        "max_qubits": 180,
        "queue": "以平台实时状态为准",
        "cost": "使用账户额度",
    },
    {
        "id": "spinq_cloud_qpu",
        "name": "SpinQ 云真机",
        "platform": "spinq",
        "module": "spinqit",
        "required": (
            "LOOMQ_SPINQ_USERNAME",
            "LOOMQ_SPINQ_KEYFILE",
            "LOOMQ_SPINQ_HOST",
            "LOOMQ_SPINQ_PLATFORM_CODE",
        ),
        "max_qubits": 8,
        "queue": "以平台实时状态为准",
        "cost": "使用账户额度",
    },
)


def available_environments(
    *, module_available: Callable[[str], bool] | None = None
) -> dict[str, Any]:
    """Report only environments this local service can genuinely offer.

    Credentials are reduced to booleans and are never returned to the browser.
    Cloud providers without a configured local execution path are intentionally
    absent instead of being presented as selectable demo devices.
    """

    can_import = module_available or (
        lambda module_name: importlib.util.find_spec(module_name) is not None
    )
    environments = [
        {
            "id": "local_reference",
            "name": "LoomQ 本地模拟器",
            "platform": "local",
            "kind": "simulator",
            "max_qubits": 20,
            "queue": "无需排队",
            "cost": "免费",
            "detail": "始终可用，不需要平台账号，也不会消耗真机额度。",
        }
    ]
    unavailable: list[dict[str, str]] = []
    for definition in HARDWARE_ENVIRONMENTS:
        configured = all(os.environ.get(name, "").strip() for name in definition["required"])
        sdk_ready = can_import(str(definition["module"]))
        if configured and sdk_ready:
            environments.append(
                {
                    key: value
                    for key, value in definition.items()
                    if key not in {"module", "required"}
                }
                | {
                    "kind": "qpu",
                    "detail": "本机凭据与 SDK 已就绪；提交前仍会再次确认。",
                }
            )
            continue
        reason = "尚未配置本机凭据" if not configured else "当前 Python 环境缺少供应商 SDK"
        unavailable.append(
            {
                "id": str(definition["id"]),
                "name": str(definition["name"]),
                "reason": reason,
            }
        )
    return {"environments": environments, "unavailable": unavailable}


def hardware_bell_evidence() -> dict[str, Any]:
    """Return a secret-free replay of the two archived Bell hardware runs."""

    runs: list[dict[str, Any]] = []
    for filename in ("originq-bell-result.json", "spinq-bell-result.json"):
        path = EVIDENCE_ROOT / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        counts = payload.get("counts")
        shots = payload.get("shots")
        if (
            not isinstance(counts, dict)
            or not isinstance(shots, int)
            or any(
                not isinstance(state, str)
                or set(state) - {"0", "1"}
                or not isinstance(count, int)
                or count < 0
                for state, count in counts.items()
            )
            or sum(counts.values()) != shots
        ):
            raise RuntimeError(f"invalid archived evidence: {filename}")
        runs.append(
            {
                "platform": payload["platform"],
                "backend": payload["backend"],
                "job_id": payload["job_id"],
                "timestamp": payload["timestamp"],
                "shots": shots,
                "counts": counts,
                "bit_order": payload["bit_order"],
                "top_k_match": bool(payload.get("top_k_match")),
                "source_file": f"evidence/files/{filename}",
            }
        )
    return {
        "kind": "archived_real_hardware_evidence",
        "creates_new_job": False,
        "runs": runs,
    }


def health_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "level": "l2",
        "service": "loomq-studio",
        "ui_revision": "remotion-hyperframes-1",
        "agent_revision": "validated-live-llm-2",
        "learning_engine": "loomq.l1.statevector",
        "curriculum_schema": learning.load_curriculum()["schema_version"],
    }


def build_chat_payload(
    prompt: str,
    *,
    mode: str | None = None,
    agent: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if mode is not None and mode not in MODE_PREFIXES:
        raise ValueError("mode must be generate, repair, or select")
    normalized_prompt = prompt.strip()
    if mode is not None:
        normalized_prompt = f"{MODE_PREFIXES[mode]}\nUser request: {normalized_prompt}"
    active_agent = agent or agent_chat
    answer = active_agent(normalized_prompt)
    fenced_match = FENCED_QASM_PATTERN.search(answer)
    match = fenced_match or QASM_PATTERN.search(answer)
    qasm = match.group(1).strip() if fenced_match else (
        match.group(0).strip() if match else None
    )
    display_answer = answer
    if fenced_match:
        display_answer = FENCED_QASM_PATTERN.sub("", answer).strip()
    elif match:
        display_answer = (answer[: match.start()] + answer[match.end() :]).strip()
    if qasm and not display_answer:
        display_answer = "量子电路已生成，并完成 1024 次本地模拟验证。"
    simulation = run_local(qasm, "originq", 1_024) if qasm else None
    return {
        "answer": display_answer,
        "qasm": qasm,
        "simulation": simulation,
        "engine": "loomq.l1.statevector" if simulation else None,
        "model": os.environ.get("LOOMQ_LLM_MODEL"),
    }


def run_environment_payload(
    environment_id: object,
    qasm: object,
    shots: object,
) -> dict[str, Any]:
    if environment_id != "local_reference":
        raise ValueError("selected environment does not support web execution")
    if not isinstance(qasm, str) or not qasm.strip():
        raise ValueError("qasm must be a non-empty OpenQASM 2.0 program")
    if not isinstance(shots, int) or isinstance(shots, bool) or not 1 <= shots <= 4096:
        raise ValueError("shots must be an integer between 1 and 4096")
    result = run_local(qasm.strip(), "originq", shots)
    return {
        "environment": {
            "id": "local_reference",
            "name": "LoomQ 本地模拟器",
            "kind": "simulator",
        },
        "engine": "loomq.l1.statevector",
        "result": result,
    }


def validate_qasm_payload(qasm: object) -> dict[str, Any]:
    if not isinstance(qasm, str) or not qasm.strip() or len(qasm) > 64_000:
        raise ValueError("qasm must be a non-empty OpenQASM program within 64000 characters")
    normalized = qasm.strip()
    program = parse_openqasm2(normalized)
    measurement_count = sum(
        isinstance(operation, MeasureOperation) for operation in program.operations
    )
    if measurement_count == 0:
        raise ValueError("OpenQASM program must include at least one measurement")
    return {
        "qasm": normalized,
        "validation": {
            "qubits": program.quantum_register.size,
            "classical_bits": program.classical_register.size,
            "operations": len(program.operations),
            "measurements": measurement_count,
        },
        "engine": "loomq.l1.qasm",
    }


class LoomQRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format_string: str, *args: object) -> None:
        print("LoomQ UI: " + (format_string % args))

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, health_payload())
            return
        if path == "/api/lessons":
            self._json(200, learning.lesson_catalog())
            return
        if path == "/api/environments":
            self._json(200, available_environments())
            return
        if path == "/api/evidence/hardware/bell":
            self._json(200, hardware_bell_evidence())
            return
        if path == "/api/hardware/profiles":
            try:
                self._json(200, PROFILES.list())
            except Exception:
                self._json(502, {"error": "backend request failed"})
            return
        if path == "/api/hardware/jobs":
            try:
                self._json(200, JOBS.list())
            except Exception:
                self._json(502, {"error": "backend request failed"})
            return
        if path.startswith("/api/hardware/jobs/"):
            task_id = unquote(path.removeprefix("/api/hardware/jobs/"))
            job = JOBS.get(task_id)
            if job is None or "/" in task_id:
                self._json(404, {"error": "hardware job not found"})
                return
            self._json(200, job)
            return
        if path.startswith("/api/lessons/"):
            lesson_id = unquote(path.removeprefix("/api/lessons/"))
            lesson = next(
                (
                    item
                    for item in learning.lesson_catalog()["lessons"]
                    if item["id"] == lesson_id
                ),
                None,
            )
            if lesson is None or "/" in lesson_id:
                self._json(404, {"error": "lesson not found"})
                return
            self._json(200, lesson)
            return
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/quantum-story.iife.js": (
                "quantum-story.iife.js",
                "text/javascript; charset=utf-8",
            ),
            "/motion/loomq-motion.css": (
                "motion/loomq-motion.css",
                "text/css; charset=utf-8",
            ),
            "/motion/loomq-motion.iife.js": (
                "motion/loomq-motion.iife.js",
                "text/javascript; charset=utf-8",
            ),
        }
        asset = assets.get(path)
        if asset is None:
            self._json(404, {"error": "not found"})
            return
        filename, content_type = asset
        body = (WEB_ROOT / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlsplit(self.path).path
        if path not in {
            "/api/chat",
            "/api/simulate",
            "/api/validate-qasm",
            "/api/run-environment",
            "/api/hardware/config",
            "/api/hardware/profiles",
            "/api/hardware/jobs",
        }:
            self._json(404, {"error": "not found"})
            return
        try:
            request = self._request_json(
                max_bytes=48_000
                if path in {"/api/hardware/config", "/api/hardware/profiles"}
                else 80_000
            )
            if path == "/api/chat":
                payload = build_chat_payload(
                    request.get("prompt"), mode=request.get("mode", "generate")
                )
            elif path == "/api/simulate":
                payload = learning.simulate_lesson_experiment(
                    request.get("lesson_id"),
                    request.get("experiment_id"),
                    request.get("shots"),
                    request.get("nonce", ""),
                )
            elif path == "/api/validate-qasm":
                payload = validate_qasm_payload(request.get("qasm"))
            elif path == "/api/run-environment":
                payload = run_environment_payload(
                    request.get("environment_id"),
                    request.get("qasm"),
                    request.get("shots"),
                )
            elif path == "/api/hardware/config":
                payload = configure_hardware(request)
            elif path == "/api/hardware/profiles":
                payload = PROFILES.create(request)
            else:
                payload = JOBS.submit(request)
        except json.JSONDecodeError:
            self._json(400, {"error": "request body must be valid JSON"})
            return
        except ProfileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
            return
        except (KeyError, ValueError) as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:  # SDK errors can contain credentials; never echo them.
            self._json(502, {"error": "backend request failed"})
            return
        status = 202 if path == "/api/hardware/jobs" else (
            201 if path == "/api/hardware/profiles" else 200
        )
        self._json(status, payload)

    def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
        self._json(404, {"error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
        self._delete_hardware_profile()

    def _delete_hardware_profile(self) -> None:
        path = urlsplit(self.path).path
        prefix = "/api/hardware/profiles/"
        if not path.startswith(prefix):
            self._json(404, {"error": "not found"})
            return
        profile_id = unquote(path.removeprefix(prefix))
        if not profile_id or "/" in profile_id:
            self._json(404, {"error": "hardware profile not found"})
            return
        try:
            payload = PROFILES.delete(profile_id)
        except ProfileReadOnlyError as exc:
            self._json(403, {"error": str(exc)})
            return
        except ProfileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
            return
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:
            self._json(502, {"error": "backend request failed"})
            return
        self._json(200, payload)

    def _request_json(self, *, max_bytes: int = 64_000) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid request size") from exc
        if length <= 0 or length > max_bytes:
            raise ValueError("invalid request size")
        request = json.loads(self.rfile.read(length))
        if not isinstance(request, dict):
            raise ValueError("request body must be an object")
        return request

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LoomQ L2 local experience")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("LoomQ web service may only bind to loopback")
    return ThreadingHTTPServer((host, port), LoomQRequestHandler)


def main() -> int:
    args = parse_args()
    server = create_server(args.host, args.port)
    print(f"LoomQ Studio: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
