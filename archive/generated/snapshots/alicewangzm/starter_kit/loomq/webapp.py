#!/usr/bin/env python3
"""LoomQ web UI - the L2 zero-background-user entry point.

A tiny stdlib web server (no third-party deps) that wraps the L2 agent and the
L1 runtime so a non-expert can, in one page: describe what they want in plain
words, see the circuit the agent writes, RUN it on a local simulator, and see
the results visualized.

Run (with LOOMQ_LLM_* set, from the repo's .venv so the simulators are present):

    python starter_kit/loomq/webapp.py            # normal
    LOOMQ_DEV=1 python starter_kit/loomq/webapp.py  # dev: hot-reload on change

Then open http://localhost:8000

Endpoints:
    GET  /            -> the single-page UI (index.html beside this file)
    GET  /api/version -> {"v": <mtime>} for the dev auto-reload poller
    POST /api/chat    -> {"prompt": str}          -> {"reply": str, "qasm": str|null}
    POST /api/run     -> {"qasm": str, "shots"?}  -> {"counts": {...}, "backend": str}
"""

import glob
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent import _extract_qasm, agent_chat
from parser import parse_qasm
from runtime import run

_HERE = os.path.dirname(__file__)
_INDEX = os.path.join(_HERE, "index.html")
# originq's CPU simulator is little-endian and needs no bit-order handling, so it
# is a clean default for the "run it" button.
_DEFAULT_TARGET = "originq"
_DEV = bool(os.environ.get("LOOMQ_DEV"))

# Injected into the page in dev mode: polls /api/version and reloads on change.
_RELOAD_SNIPPET = """
<script>
(async () => { let last = null;
  for (;;) { try {
    const v = (await (await fetch('/api/version')).json()).v;
    if (last !== null && v !== last) location.reload(); last = v;
  } catch (e) {} await new Promise(r => setTimeout(r, 1000)); }
})();
</script>
"""


def _circuit(qasm):
    """Parse QASM into a simple {qubits, ops} shape for drawing a diagram."""
    if not qasm:
        return None
    try:
        ir = parse_qasm(qasm)
    except Exception:  # noqa: BLE001 - a diagram is best-effort, never fatal
        return None
    return {"qubits": sum(ir["qreg"].values()), "ops": ir["ops"]}


def _watched_files():
    return [_INDEX] + glob.glob(os.path.join(_HERE, "*.py"))


def _version():
    return max((os.path.getmtime(f) for f in _watched_files() if os.path.exists(f)), default=0)


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(_INDEX, "r", encoding="utf-8") as fh:
                html = fh.read()
            if _DEV:  # live-reload only in dev; the shipped page stays clean
                html = html.replace("</body>", _RELOAD_SNIPPET + "</body>")
            self._reply(200, html.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/version":
            self._reply(200, {"v": _version()})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return

        try:
            if self.path == "/api/chat":
                reply = agent_chat(str(payload.get("prompt", "")))
                qasm = _extract_qasm(reply)
                self._reply(200, {"reply": reply, "qasm": qasm, "circuit": _circuit(qasm)})
            elif self.path == "/api/run":
                result = run(
                    str(payload.get("qasm", "")),
                    _DEFAULT_TARGET,
                    int(payload.get("shots", 1024)),
                )
                self._reply(200, {"counts": result["counts"], "backend": result["backend"]})
            else:
                self._reply(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001 - surface a short message to the UI
            self._reply(500, {"error": str(exc).splitlines()[-1][:200]})

    def log_message(self, *args):  # keep the console quiet
        pass


def _serve():
    port = int(os.environ.get("PORT", "8000"))
    mode = "  [dev hot-reload]" if _DEV else ""
    print(f"LoomQ web UI running at http://localhost:{port}{mode}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def _supervise():
    """Dev supervisor: (re)spawn the server and restart it when a .py changes.

    The browser reloads itself via /api/version, so editing index.html or any
    Python module updates what you see without a manual restart.
    """
    py_snapshot = lambda: {f: os.path.getmtime(f) for f in glob.glob(os.path.join(_HERE, "*.py"))}
    print("[dev] hot-reload on - watching for changes (Ctrl+C to stop)")
    child_env = {**os.environ, "LOOMQ_CHILD": "1"}
    while True:
        snap = py_snapshot()
        child = subprocess.Popen([sys.executable, __file__], env=child_env)
        try:
            while child.poll() is None:
                time.sleep(0.8)
                if py_snapshot() != snap:
                    print("[dev] python change detected - restarting server")
                    break
        except KeyboardInterrupt:
            child.terminate()
            print("\nbye")
            return
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()


def main():
    # In dev, a supervisor process watches files and restarts the real server
    # (the child, marked by LOOMQ_CHILD). Normal runs just serve.
    if _DEV and not os.environ.get("LOOMQ_CHILD"):
        _supervise()
    else:
        _serve()


if __name__ == "__main__":
    main()
