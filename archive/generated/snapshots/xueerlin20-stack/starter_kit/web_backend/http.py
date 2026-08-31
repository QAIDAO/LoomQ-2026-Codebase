"""HTTP transport and static asset delivery for the local LoomQ UI."""

from __future__ import annotations

import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from .application import WebApplication


WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
MAX_REQUEST_BYTES = 64 * 1024
STATIC_ASSETS = frozenset(
    {
        "index.html",
        "workspace.html",
        "styles.css",
        "js/api.js",
        "js/chat.js",
        "js/circuit-runner.js",
        "js/circuit-visualizer.js",
        "js/concept-basics.js",
        "js/conversation-session.js",
        "js/journey.js",
        "js/main.js",
        "js/markdown.js",
        "js/onboarding.js",
        "js/preferences.js",
        "js/quantum-lab.js",
        "js/results.js",
        "js/workspace.js",
    }
)


class LoomQRequestHandler(BaseHTTPRequestHandler):
    """Small transport adapter; business decisions live in WebApplication."""

    app = WebApplication()

    def log_message(self, format_string, *args):
        sys.stderr.write("[LoomQ Web] %s\n" % (format_string % args))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json_response(HTTPStatus.OK, self.app.configuration_status())
            return
        self._serve_static(path)

    def do_POST(self):
        routes = {
            "/api/chat": self.app.handle_chat,
            "/api/circuit/run": self.app.run_current_circuit,
            "/api/config": self.app.save_configuration,
            "/api/conversation/reset": self.app.reset_conversation,
        }
        handler = routes.get(urlparse(self.path).path)
        if handler is None:
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            response = handler(self._read_json_payload())
        except RequestSizeError as exc:
            self._json_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, str(exc))
            return
        except (json.JSONDecodeError, ValueError) as exc:
            self._json_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except RuntimeError as exc:
            # Upstream model/provider failures are actionable service errors, not
            # Python crashes. Keep implementation details out of the browser UI.
            self._json_error(HTTPStatus.BAD_GATEWAY, str(exc))
            return
        except Exception as exc:
            self._json_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "%s: %s" % (type(exc).__name__, exc),
            )
            return
        self._json_response(HTTPStatus.OK, response)

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path == "/" else path.lstrip("/")
        if relative not in STATIC_ASSETS:
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        file_path = WEB_ROOT / relative
        try:
            body = file_path.read_bytes()
        except OSError:
            self._json_error(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_payload(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise RequestSizeError("invalid request size")
        return json.loads(self.rfile.read(length))

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._json_response(status, {"ok": False, "error": message})

    def _json_response(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )


class RequestSizeError(ValueError):
    """Distinguish unsupported request body sizes from malformed JSON."""
