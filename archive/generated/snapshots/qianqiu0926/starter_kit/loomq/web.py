"""Zero-dependency local web application for first-time quantum users."""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .agent import chat
from .pipeline import verified_run


ASSETS = Path(__file__).with_name("web_assets")
MAX_REQUEST_BYTES = 1024 * 1024


def _run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    qasm = payload.get("qasm")
    target = str(payload.get("target") or "spinq").strip().lower()
    shots = payload.get("shots", 1024)
    if not isinstance(qasm, str) or not qasm.strip():
        raise ValueError("请先输入一段 OpenQASM 2.0 电路。")
    if isinstance(shots, bool):
        raise ValueError("shots 必须是正整数。")
    shots = int(shots)
    if not 1 <= shots <= 1_000_000:
        raise ValueError("shots 必须在 1 到 1,000,000 之间。")
    result, artifact = verified_run(qasm, target, shots)
    return {"result": result, "target_ir": artifact}


class LoomQHandler(BaseHTTPRequestHandler):
    server_version = "LoomQ/1.0"

    def log_message(self, format: str, *args: object) -> None:
        print("[LoomQ] " + format % args)

    def _send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("无效的请求长度。") from exc
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValueError("请求内容为空或过大。")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("请求必须是 JSON 对象。")
        return value

    def do_POST(self) -> None:
        try:
            payload = self._payload()
            if self.path == "/api/run":
                self._send_json(200, _run_payload(payload))
                return
            if self.path == "/api/agent":
                prompt = payload.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    raise ValueError("请先用自然语言描述你想做的实验。")
                reply = chat(prompt.strip())
                match = re.search(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", reply, re.DOTALL | re.MULTILINE)
                response: dict[str, Any] = {"reply": reply, "qasm": match.group(0).strip() if match else None}
                if response["qasm"]:
                    response.update(_run_payload({**payload, "qasm": response["qasm"]}))
                self._send_json(200, response)
                return
            self._send_json(404, {"error": "没有这个 API 入口。"})
        except Exception as exc:
            self._send_json(
                400,
                {
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "recovery": "检查输入后重试；若使用智能体，请确认 LOOMQ_LLM_* 环境变量已配置。",
                },
            )

    def do_GET(self) -> None:
        raw_path = unquote(urlparse(self.path).path)
        relative = "index.html" if raw_path == "/" else raw_path.lstrip("/")
        candidate = (ASSETS / relative).resolve()
        if ASSETS.resolve() not in candidate.parents or not candidate.is_file():
            self.send_error(404, "Not found")
            return
        body = candidate.read_bytes()
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), LoomQHandler)
    print(f"LoomQ 已启动：http://{host}:{server.server_port}")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLoomQ 已停止。")
    finally:
        server.server_close()
