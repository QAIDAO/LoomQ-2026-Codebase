#!/usr/bin/env python3
"""LoomQ first-experiment demo: hardware replay + L2 agent_chat.

Not used by the official scorer. Hardware histograms are archived
SpinQ jobs (no cloud call). Agent chat still requires LOOMQ_LLM_*.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import time
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Deque
from urllib.parse import urlparse

WEB_ROOT = Path(__file__).resolve().parent
KIT_ROOT = WEB_ROOT.parent
EVIDENCE_FILES = KIT_ROOT / "evidence" / "files"
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from llm_client import REQUIRED_ENV, _load_dotenv  # noqa: E402
from loomq.agent import extract_backend_id, extract_qasm  # noqa: E402
from loomq.reference_sim import ideal_distribution  # noqa: E402

DEFAULT_PORT = 8765
# Demo-only chat throttle (protect LLM budget when judges click rapidly).
CHAT_RATE_LIMIT = max(1, int(os.environ.get("LOOMQ_WEB_CHAT_RATE_LIMIT", "20")))
CHAT_RATE_WINDOW_SEC = max(1.0, float(os.environ.get("LOOMQ_WEB_CHAT_RATE_WINDOW_SEC", "60")))
_CHAT_HITS: Deque[float] = deque()
_CHAT_LOCK = threading.Lock()
STATIC_SUFFIXES = {".html", ".css", ".js", ".png", ".svg", ".ico", ".json"}
EVIDENCE_ALLOWLIST = {
    "spinq-bell-hardware-result.png",
    "spinq-ghz3-hardware-result.png",
    "spinq-bell-sim-preview.png",
    "spinq-ghz3-sim-preview.png",
}

EXPERIMENT_FILES = {
    "bell": {
        "id": "bell",
        "title": "两枚永远同面的硬币",
        "plain": (
            "两枚硬币各自仍是随机的，但几乎从不一面一背。"
            "这就是纠缠：联合结果绑在一起，不是两枚普通硬币。"
        ),
        "noise": "真机有噪声，所以 01/10 不会是绝对的零；看主峰在 00 与 11。",
        "result_name": "spinq-bell-result.json",
        "qasm_name": "spinq-bell.qasm",
        "screenshot": "spinq-bell-hardware-result.png",
        "ideal_states": ("00", "11"),
    },
    "ghz3": {
        "id": "ghz3",
        "title": "三枚永远同一面的硬币",
        "plain": (
            "三枚硬币要么几乎全是正面，要么几乎全是反面。"
            "这是三比特 GHZ：比两枚硬币多一个人，关联仍然绑死。"
        ),
        "noise": "真机泄漏会出现在别的八个格子里；主峰仍应在 000 与 111。",
        "result_name": "spinq-ghz3-result.json",
        "qasm_name": "spinq-ghz3.qasm",
        "screenshot": "spinq-ghz3-hardware-result.png",
        "ideal_states": ("000", "111"),
    },
}


def l2_configured() -> bool:
    _load_dotenv()
    return all(os.environ.get(name) for name in REQUIRED_ENV)


def chat_rate_ok() -> bool:
    """Sliding-window limiter for /api/chat (thread-safe)."""
    now = time.time()
    with _CHAT_LOCK:
        while _CHAT_HITS and _CHAT_HITS[0] <= now - CHAT_RATE_WINDOW_SEC:
            _CHAT_HITS.popleft()
        if len(_CHAT_HITS) >= CHAT_RATE_LIMIT:
            return False
        _CHAT_HITS.append(now)
        return True


def run_chat(prompt: str) -> str:
    from adapter import agent_chat

    return agent_chat(prompt)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_experiment(exp_id: str) -> dict[str, Any]:
    spec = EXPERIMENT_FILES[exp_id]
    raw = _read_json(EVIDENCE_FILES / spec["result_name"])
    qasm_path = EVIDENCE_FILES / spec["qasm_name"]
    shot_name = spec["screenshot"]
    screenshot_on_disk = (EVIDENCE_FILES / shot_name).is_file()
    return {
        "id": spec["id"],
        "title": spec["title"],
        "plain": spec["plain"],
        "noise": spec["noise"],
        "ideal_states": list(spec["ideal_states"]),
        "job_id": raw.get("job_id"),
        "platform_name": raw.get("platform_name"),
        "task_url": raw.get("task_url"),
        "status": raw.get("status"),
        "created_at": raw.get("created_at"),
        "ended_at": raw.get("ended_at"),
        "backend": raw.get("backend"),
        "replay": True,
        "replay_note": "以下柱状图回放赛期内已归档的真机任务，评委演示不会再排队上云。",
        "experiment": raw.get("probabilities_experiment_approx_from_chart") or {},
        "simulation": raw.get("probabilities_simulation") or {},
        "qasm": _read_text(qasm_path) if qasm_path.is_file() else "",
        "screenshot": f"/evidence/{shot_name}" if screenshot_on_disk else None,
    }


def list_experiments() -> dict[str, Any]:
    return {
        "ok": True,
        "experiments": [build_experiment(exp_id) for exp_id in ("bell", "ghz3")],
    }


def load_backends() -> list[dict[str, Any]]:
    data = _read_json(KIT_ROOT / "backend_capabilities.json")
    backends = []
    for item in data.get("backends", []):
        row = dict(item)
        row["fits_15q_no_queue"] = (
            int(item.get("max_qubits") or 0) >= 15
            and item.get("queue") == "none"
            and item.get("kind") == "simulator"
        )
        backends.append(row)
    return backends


def local_ideal(qasm: str) -> dict[str, Any]:
    dist = ideal_distribution(qasm)
    peaks = sorted(dist.items(), key=lambda pair: pair[1], reverse=True)[:2]
    return {
        "probabilities": {key: float(value) for key, value in dist.items()},
        "peaks": [key for key, _value in peaks],
    }


def enrich_reply(prompt: str, response: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "response": response,
        "qasm": extract_qasm(response),
        "backend_id": extract_backend_id(response),
        "local_ideal": None,
        "backends": load_backends(),
    }
    if payload["qasm"]:
        try:
            payload["local_ideal"] = local_ideal(payload["qasm"])
        except Exception as exc:  # noqa: BLE001
            payload["local_error"] = f"本地验算没过：{type(exc).__name__}"
    if payload["backend_id"]:
        table = {item["id"]: item for item in payload["backends"]}
        payload["backend"] = table.get(payload["backend_id"])
    return payload


def friendly_chat_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if "api" in lowered and "key" in lowered:
        return "模型钥匙无效或没填好。请检查 .env 里的 LOOMQ_LLM_API_KEY，真机结果不受影响。"
    if "timeout" in lowered:
        return "模型这次超时了。真机回放仍可用；可再试一次 Agent。"
    if "connection" in lowered or "connect" in lowered:
        return "连不上模型服务。请确认 LOOMQ_LLM_BASE_URL。真机柱状图不需要网络模型。"
    return "Agent 这次没跑通。上面的真机结果是归档回放，不受这次失败影响。"


class L2WebHandler(BaseHTTPRequestHandler):
    server_version = "LoomQFirstExperiment/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _safe_web_file(self, url_path: str) -> Path | None:
        relative = url_path.lstrip("/")
        if not relative or relative == "index.html":
            relative = "index.html"
        candidate = (WEB_ROOT / relative).resolve()
        web_root = WEB_ROOT.resolve()
        if not str(candidate).startswith(str(web_root)):
            return None
        if candidate.suffix.lower() not in STATIC_SUFFIXES:
            return None
        if not candidate.is_file():
            return None
        return candidate

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "l2_configured": l2_configured(),
                    "hardware_ready": True,
                },
            )
            return

        if path == "/api/backends":
            self._send_json(HTTPStatus.OK, {"ok": True, "backends": load_backends()})
            return

        if path in ("/api/experiments", "/api/demo"):
            try:
                self._send_json(HTTPStatus.OK, list_experiments())
            except OSError as exc:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"无法读取真机归档：{exc}"},
                )
            return

        if path.startswith("/api/experiments/"):
            exp_id = path.rsplit("/", 1)[-1]
            if exp_id not in EXPERIMENT_FILES:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "没有这项真机实验"})
                return
            try:
                self._send_json(HTTPStatus.OK, build_experiment(exp_id))
            except OSError as exc:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"无法读取真机归档：{exc}"},
                )
            return

        if path.startswith("/evidence/"):
            name = Path(path).name
            if name not in EVIDENCE_ALLOWLIST:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            file_path = EVIDENCE_FILES / name
            if not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = file_path.read_bytes()
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            self._send_bytes(HTTPStatus.OK, data, mime)
            return

        if path in ("/", "/index.html") or path.startswith("/"):
            file_path = self._safe_web_file(path if path != "/" else "/index.html")
            if file_path is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            if file_path.suffix == ".js":
                mime = "application/javascript; charset=utf-8"
            elif file_path.suffix == ".css":
                mime = "text/css; charset=utf-8"
            elif file_path.suffix == ".html":
                mime = "text/html; charset=utf-8"
            self._send_bytes(HTTPStatus.OK, file_path.read_bytes(), mime)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/simulate":
            try:
                payload = self._read_json_body()
                qasm = str(payload.get("qasm", "")).strip()
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "请求格式不对"})
                return
            if not qasm:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "需要一段 OpenQASM"})
                return
            try:
                self._send_json(HTTPStatus.OK, local_ideal(qasm))
            except Exception as exc:  # noqa: BLE001
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"这段电路本地跑不通：{type(exc).__name__}"},
                )
            return

        if parsed.path != "/api/chat":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json_body()
            prompt = str(payload.get("prompt", "")).strip()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "请求格式不对，请用页面上的按钮再试一次。"},
            )
            return

        if not prompt:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "请先写一句话，或点上面的第一次实验。"},
            )
            return

        if not l2_configured():
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "error": (
                        "还没填模型配置。复制 .env.example 为 .env，"
                        "填写 LOOMQ_LLM_* 后再让 Agent 说话。"
                        "上面的真机柱状图不需要钥匙。"
                    ),
                    "missing": [
                        name for name in REQUIRED_ENV if not os.environ.get(name)
                    ],
                },
            )
            return

        if not chat_rate_ok():
            self._send_json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "error": (
                        f"请求太频繁：{CHAT_RATE_WINDOW_SEC:.0f} 秒内最多 "
                        f"{CHAT_RATE_LIMIT} 次 Agent 调用。稍后再试。"
                    )
                },
            )
            return

        try:
            response = run_chat(prompt)
        except Exception as exc:  # noqa: BLE001 — surface to browser
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": friendly_chat_error(exc)},
            )
            return

        self._send_json(HTTPStatus.OK, enrich_reply(prompt, response))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoomQ first-experiment web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the demo in a local browser after bind",
    )
    args = parser.parse_args(argv)

    class ReuseHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True

    server = ReuseHTTPServer((args.host, args.port), L2WebHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"LoomQ 第一次实验：{url}")
    print("真机 Bell / GHZ 为归档回放，无需 API Key。")
    if not l2_configured():
        print(
            "提示：LOOMQ_LLM_* 未配置时仍可看真机；Agent 三项任务需填写 .env。",
            file=sys.stderr,
        )
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
