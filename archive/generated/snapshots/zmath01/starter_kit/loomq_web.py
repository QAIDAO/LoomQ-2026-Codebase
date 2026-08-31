#!/usr/bin/env python3
"""LoomQ Web UI server (L2 interactive experience + beginner onboarding).

Zero-install: pure Python standard library. Serves the single-file frontend
``webui/index.html`` and a small JSON API that drives the same adapter used by
the contest evaluator:

    GET  /                  -> webui/index.html (the whole app, no CDN)
    GET  /api/health        -> {llm_configured, targets, backends}
    GET  /api/backends      -> backend capability table
    POST /api/run           -> {qasm, target, shots} -> unified result + IRs
    POST /api/chat          -> {prompt} -> agent reply (+ extracted QASM)

Security notes:
- Binds to 127.0.0.1 only. Intended for local and judge-laptop use.
- The API key lives only in LOOMQ_LLM_* environment variables; the server
  never echoes it, logs it, or sends it back to the browser.
- Request bodies are size-limited; no file reads beyond the webui directory.

Usage:
    python3 loomq_web.py [--port 8000]
    # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter  # noqa: E402

WEBUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webui")
INDEX_PATH = os.path.join(WEBUI_DIR, "index.html")
MAX_BODY = 1 << 20  # 1 MiB
MAX_SHOTS = 100_000

# Preset table (kept in sync with the Web UI). Used to inline QASM in
# /?run=<preset> requests so screenshots and headless tests never race the
# client-side fetch.
_PRESETS = {
    "bell":     {"file": "bell.qasm"},
    "ghz3":    {"file": "ghz3.qasm"},
    "qft4":    {"file": "qft4.qasm"},
    "grover3":  {"file": "grover3.qasm"},
}


def _read_circuit_file(name: str) -> str | None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits", name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()

_LLM_ENV = ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")


def llm_configured() -> bool:
    return all(os.environ.get(name) for name in _LLM_ENV)


def load_index() -> bytes:
    with open(INDEX_PATH, "rb") as handle:
        return handle.read()


_INDEX_CACHE: bytes | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "LoomQ/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ utils
    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            raise ValueError("request body too large or empty")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _error(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status)

    # ------------------------------------------------------------------ routes
    def _serve_index(self) -> None:
        """Serve index.html. When ?run=<preset> is present, inline the preset
        QASM into the HTML so the client doesn't have to fetch /circuits/
        asynchronously (avoids race in headless screenshots)."""
        global _INDEX_CACHE
        if _INDEX_CACHE is None:
            _INDEX_CACHE = load_index()
        body = _INDEX_CACHE.decode("utf-8")
        qs = urlparse(self.path).query
        if qs:
            from urllib.parse import parse_qs

            params = parse_qs(qs)
            run_preset = (params.get("run") or [None])[0]
            if run_preset and run_preset in _PRESETS:
                qasm_text = _read_circuit_file(_PRESETS[run_preset]["file"])
                if qasm_text is not None:
                    diag = "diag" in params
                    inject = (
                        '<script>window.__LOOMQ_PRESET=%s;'
                        'window.__LOOMQ_DIAG=%s;</script>'
                    ) % (
                        json.dumps({"key": run_preset, "qasm": qasm_text}),
                        "true" if diag else "false",
                    )
                    body = body.replace("</head>", inject + "</head>", 1)
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        global _INDEX_CACHE
        path = urlparse(self.path).path
        if path.startswith("/circuits/"):
            self._serve_circuit(path)
            return
        if path in ("/", "/index.html"):
            self._serve_index()
            return
            return
        if path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "llm_configured": llm_configured(),
                    "targets": list(adapter.SUPPORTED_TARGETS),
                    "backend_names": {
                        "spinq": "量旋 SpinQ (Taurus 模拟器/真机)",
                        "originq": "本源量子 (本地模拟器/悟空真机)",
                        "braket": "AWS Braket (LocalSimulator/云端)",
                    },
                }
            )
            return
        if path == "/api/backends":
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "backend_capabilities.json")
            with open(path, encoding="utf-8") as handle:
                self._send_json({"ok": True, "backends": json.load(handle)})
            return
        self._error("not found", 404)

    def _serve_circuit(self, path: str) -> None:
        """Serve a .qasm file from the circuits/ directory (no traversal)."""
        name = path[len("/circuits/"):]
        if "/" in name or ".." in name or not name.endswith(".qasm"):
            self._error("forbidden", 403)
            return
        circuits_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits")
        file_path = os.path.join(circuits_dir, name)
        if not os.path.isfile(file_path):
            self._error("circuit not found", 404)
            return
        with open(file_path, "rb") as handle:
            body = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        try:
            body = self._read_body()
        except Exception as exc:  # noqa: BLE001
            self._error("无法解析请求体：%s" % exc)
            return

        path = urlparse(self.path).path
        if path == "/api/run":
            self._api_run(body)
            return
        if path == "/api/chat":
            self._api_chat(body)
            return
        if path == "/api/circuit":
            self._api_circuit(body)
            return
        if path == "/api/agent-key":
            self._api_agent_key(body)
            return
        self._error("not found", 404)

    def _api_agent_key(self, body: Dict[str, Any]) -> None:
        # Set the LLM env vars at runtime so the agent picks up the new key
        # on the very next call (llm_client reads env on each invocation).
        # Keys are never echoed back; only the configured status is returned.
        base_url = (body.get("base_url") or "").strip()
        api_key = (body.get("api_key") or "").strip()
        model = (body.get("model") or "").strip()
        if base_url:
            os.environ["LOOMQ_LLM_BASE_URL"] = base_url
        if api_key:
            os.environ["LOOMQ_LLM_API_KEY"] = api_key
        if model:
            os.environ["LOOMQ_LLM_MODEL"] = model
        self._send_json({"ok": True, "configured": _llm_configured()})

    def _api_circuit(self, body: Dict[str, Any]) -> None:
        """Render the circuit with the de-facto standard open-source tool:
        Qiskit's QuantumCircuit.from_qasm_str + the canonical text drawer.
        No hand-rolled diagram is ever produced."""
        qasm = body.get("qasm")
        if not isinstance(qasm, str) or not qasm.strip():
            self._error("缺少 QASM 电路代码")
            return
        try:
            from loomq_core.qasm import parse_qasm2

            circuit = parse_qasm2(qasm)
            payload: Dict[str, Any] = {
                "ok": True,
                "num_qubits": circuit.num_qubits,
                "num_clbits": circuit.num_clbits,
                "standard_text": None,
                "qiskit": False,
            }
            try:
                import warnings

                import qiskit
                from qiskit import QuantumCircuit

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    qc = QuantumCircuit.from_qasm_str(qasm)
                    drawn = qc.draw(output="text")
                    text = drawn if isinstance(drawn, str) else drawn.__str__()
                payload["standard_text"] = text
                payload["qiskit"] = True
            except Exception:  # noqa: BLE001 - qiskit absent or unsupported QASM
                payload["standard_text"] = None
                payload["qiskit"] = False
            self._send_json(payload)
        except Exception as exc:  # noqa: BLE001 - user-facing parse errors
            self._error("电路无法解析：%s" % exc, 422)

    def _api_run(self, body: Dict[str, Any]) -> None:
        qasm = body.get("qasm")
        target = body.get("target", "spinq")
        shots = body.get("shots", 4096)
        if not isinstance(qasm, str) or not qasm.strip():
            self._error("缺少 QASM 电路代码")
            return
        if target not in adapter.SUPPORTED_TARGETS:
            self._error("未知目标后端：%r" % target)
            return
        try:
            shots = int(shots)
            if not 1 <= shots <= MAX_SHOTS:
                raise ValueError
        except (TypeError, ValueError):
            self._error("采样次数需为 1..%d 的整数" % MAX_SHOTS)
            return
        try:
            result = adapter.run(qasm, target, shots)
            transpilations = {
                t: adapter.transpile(qasm, t) for t in adapter.SUPPORTED_TARGETS
            }
            explanation = _explain_counts(result["counts"])
            self._send_json(
                {
                    "ok": True,
                    "result": result,
                    "transpilations": transpilations,
                    "explanation": explanation,
                }
            )
        except Exception as exc:  # noqa: BLE001 - user-facing parse/run errors
            self._error("电路无法运行：%s" % exc, 422)

    def _api_chat(self, body: Dict[str, Any]) -> None:
        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self._error("缺少问题内容")
            return
        if not llm_configured():
            self._error(
                "智能体尚未配置模型服务。请在启动服务器的终端里设置 "
                "LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL "
                "三个环境变量后重启。正式评测时组委会会自动注入。",
                503,
            )
            return
        try:
            reply = adapter.agent_chat(prompt)
        except Exception as exc:  # noqa: BLE001
            self._error("智能体调用失败：%s" % exc, 502)
            return
        qasm = None
        try:
            from loomq_core.agent import _extract_qasm

            qasm = _extract_qasm(reply)
        except Exception:  # noqa: BLE001
            pass
        self._send_json({"ok": True, "reply": reply, "qasm": qasm})

    # ------------------------------------------------------------- misc
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # Keep access logs minimal and never log request bodies or headers
        # (the Authorization header must not reach the console).
        if "/api/" in fmt % args:
            return
        super().log_message(fmt, *args)


def _explain_counts(counts: Dict[str, int]) -> str:
    from loomq_cli import explain_counts

    total = sum(counts.values())
    if total == 0:
        return "(没有测量结果)"
    return explain_counts(counts)


def main() -> int:
    parser = argparse.ArgumentParser(description="LoomQ Web UI server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not os.path.exists(INDEX_PATH):
        print("缺少 %s，无法启动 Web UI" % INDEX_PATH)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("LoomQ Web UI: http://%s:%d  (按 Ctrl+C 退出)" % (args.host, args.port))
    if llm_configured():
        print("智能体：已配置 LOOMQ_LLM_*，自然语言对话可用。")
    else:
        print("智能体：未配置 LOOMQ_LLM_*。电路运行仍可用；对话功能需配置后重启。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
