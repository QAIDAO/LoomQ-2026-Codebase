"""Local web UI for LoomQ L2 interaction (stdlib only, no extra pip deps).

Serves the Deutsch walkthrough at starter_kit/web/ and the HTTP APIs that page
calls. Unused leftover acts (Bernstein-Vazirani, old lesson cards) are not
exposed here.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Sequence, Tuple
from urllib.parse import urlparse

from loomq_l2 import deutsch as deutsch_mod
from loomq_l2.turn import env_ready, run_free_question

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DEFAULT_PORT = 8877


def _load_local_env() -> None:
    """Read starter_kit/.env or repo-root .env into os.environ if a key is missing.

    Keys already set in the process (the official L2 contract) are left alone.
    The file is gitignored; this only exists so `python web_chat.py` works on a
    machine where the variables were written to .env instead of the shell.
    """
    here = Path(__file__).resolve()
    candidates = (
        here.parents[1] / ".env",  # starter_kit/.env
        here.parents[2] / ".env",  # repo root
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


class Handler(BaseHTTPRequestHandler):
    server_version = "LoomQWeb/1.0"

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            index = WEB_DIR / "index.html"
            if not index.is_file():
                self._send_json(500, {"error": "web/index.html missing"})
                return
            self._send(200, index.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            status = env_ready()
            self._send_json(200 if status["ok"] else 503, status)
            return
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            target = (WEB_DIR / rel).resolve()
            if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
                self._send_json(404, {"error": "not found"})
                return
            ctype = "application/octet-stream"
            if target.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            elif target.suffix == ".js":
                ctype = "application/javascript; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)
            return
        self._send_json(404, {"error": "not found"})

    def _read_json(self) -> Tuple[Optional[dict], Optional[str]]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8")), None
        except Exception:
            return None, "invalid JSON"

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        data, err = self._read_json()
        if err:
            self._send_json(400, {"error": err})
            return
        assert data is not None

        if path == "/api/ask":
            question = str(data.get("question") or "").strip()
            if not question:
                self._send_json(400, {"error": "question is required"})
                return
            self._send_json(
                200,
                run_free_question(
                    question,
                    str(data.get("context") or ""),
                    shots=int(data.get("shots") or 1024),
                ),
            )
            return

        if path == "/api/session/new":
            self._send_json(200, deutsch_mod.new_session())
            return

        if path in (
            "/api/session/classical",
            "/api/session/quantum",
            "/api/session/reveal",
        ):
            session_id = str(data.get("session_id") or "").strip()
            try:
                if path == "/api/session/classical":
                    payload = deutsch_mod.session_classical_query(
                        session_id, int(data.get("bit"))
                    )
                elif path == "/api/session/quantum":
                    payload = deutsch_mod.session_quantum_run(
                        session_id,
                        shots=int(data.get("shots") or 1024),
                        target=str(data.get("target") or "braket").strip() or "braket",
                    )
                else:
                    payload = deutsch_mod.session_reveal(session_id)
            except KeyError as exc:
                self._send_json(410, {"error": str(exc).strip("'"), "expired": True})
                return
            except (TypeError, ValueError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
                return
            payload["ok"] = True
            self._send_json(200, payload)
            return

        self._send_json(404, {"error": "not found"})


class ExclusiveHTTPServer(ThreadingHTTPServer):
    """Refuse to share a port with leftover copies of ourselves.

    Windows lets several processes bind the same (host, port) if SO_REUSEADDR
    is on, which is how we previously ended up with several copies all claiming
    the same port. Browsers then get ERR_EMPTY_RESPONSE. Exclusive bind makes
    the second copy fail loud instead of serving garbage.
    """

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self) -> None:
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(host: str, port: int, open_browser: bool) -> None:
    _load_local_env()
    if not (WEB_DIR / "index.html").is_file():
        raise FileNotFoundError("missing starter_kit/web/index.html")
    httpd = ExclusiveHTTPServer((host, port), Handler)
    url = f"http://127.0.0.1:{port}/" if host in ("0.0.0.0", "") else f"http://{host}:{port}/"
    print(f"LoomQ web UI: {url}")
    print("Stop with Ctrl+C")
    status = env_ready()
    print(status["message"])
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LoomQ L2 web interaction entry")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    serve(args.host, args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
