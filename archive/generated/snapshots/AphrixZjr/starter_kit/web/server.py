#!/usr/bin/env python3
"""Zero-dependency HTTP server for the LoomQ guided experiment."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from web.app import ConflictError, ExperimentStore, archived_hardware_evidence
else:
    from .app import ConflictError, ExperimentStore, archived_hardware_evidence


STATIC = Path(__file__).with_name("static")


class LoomQHandler(BaseHTTPRequestHandler):
    store = ExperimentStore()
    server_version = "LoomQGuide/1.0"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("[loomq-web] " + format % args + "\n")

    def _json(self, status: int, value: object) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise ValueError("request body too large")
        if not length:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _static(self, path: str) -> None:
        relative = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        target = (STATIC / relative).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            self._json(404, {"error": "not found"})
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(target.name)[0] or "application/octet-stream") + ("; charset=utf-8" if target.suffix in (".html", ".css", ".js", ".svg") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        # Circuit positions and data-bar widths are deterministic style attributes;
        # scripts, connections and all other resources remain same-origin only.
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            configured = all(os.environ.get(name) for name in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL"))
            backends = {
                backend_id: {
                    "connected": bool(value.get("available")),
                    "reason": value.get("reason", ""),
                }
                for backend_id, value in self.store.backend_availability.items()
            }
            self._json(200, {
                "status": "ok",
                "network_required": False,
                "agent_configured": configured,
                "l1_backends": backends,
            })
            return
        if path == "/api/hardware-evidence":
            self._json(200, archived_hardware_evidence())
            return
        match = re.fullmatch(r"/api/runs/([\w-]+)", path)
        if match:
            result = self.store.runs.get(match.group(1))
            self._json(200 if result else 404, result or {"error": "run not found"})
            return
        match = re.fullmatch(r"/api/experiments/([\w-]+)", path)
        if match:
            try:
                self._json(200, self.store.public(match.group(1)))
            except KeyError as exc:
                self._json(404, {"error": str(exc)})
            return
        self._static(path)

    def _dispatch(self, method: str) -> object:
        path, body = urlparse(self.path).path, self._body()
        if method == "POST" and path == "/api/experiments":
            return self.store.create(body.get("mode", "bell"), body.get("qasm"), body.get("goal"))
        match = re.fullmatch(r"/api/experiments/([\w-]+)(?:/(\w[\w-]*))?", path)
        if not match:
            raise KeyError("route not found")
        session_id, action = match.groups()
        if method == "PATCH" and action == "goal":
            return self.store.update_goal(session_id, body.get("goal", ""))
        if method == "PATCH" and action == "circuit":
            return self.store.update_qasm(session_id, body.get("qasm", ""), body.get("circuit_revision"))
        if method == "POST" and action == "advance":
            return self.store.advance(session_id, body.get("prediction"), body.get("circuit_revision"))
        if method == "POST" and action == "validate":
            return self.store.validate(session_id)
        if method == "POST" and action == "repairs":
            return self.store.repair(session_id, bool(body.get("apply")))
        if method == "POST" and action == "backend-recommendations":
            return self.store.recommendations(session_id)
        if method == "PATCH" and action == "backend":
            return self.store.select_backend(session_id, body.get("backend_id", ""))
        if method == "POST" and action == "agent":
            return self.store.agent_turn(session_id, body.get("prompt", ""))
        if method == "POST" and action == "apply-agent-proposal":
            return self.store.apply_agent_proposal(session_id, body.get("proposal_id", ""))
        if method == "POST" and action == "runs":
            return self.store.run(session_id, body.get("shots", 1024))
        if method == "POST" and action == "undo":
            return self.store.undo(session_id)
        if method == "POST" and action == "redo":
            return self.store.redo(session_id)
        raise KeyError("route not found")

    def _write_dispatch(self, method: str) -> None:
        try:
            self._json(200, self._dispatch(method))
        except ConflictError as exc:
            self._json(409, {"error": str(exc), "recovery": "刷新当前实验状态后重试"})
        except KeyError as exc:
            self._json(404, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": type(exc).__name__, "recovery": "实验已保留；可撤销、编辑 QASM 或继续本地路径"})

    def do_POST(self) -> None:
        self._write_dispatch("POST")

    def do_PATCH(self) -> None:
        self._write_dispatch("PATCH")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LoomQ guided experiment web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), LoomQHandler)
    print("LoomQ guided experiment: http://%s:%d" % (args.host, server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
