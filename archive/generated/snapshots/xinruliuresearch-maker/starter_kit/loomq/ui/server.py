"""Dependency-free local HTTP server for the LoomQ Pegasus workbench.

Run from ``starter_kit`` with::

    python -m loomq.ui.server --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Mapping
from urllib.parse import parse_qs, urlsplit

from .service import WorkbenchService
from .workspace import WorkspaceError, WorkspaceSession


MAX_HTTP_BODY = 600_000
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/mark.svg": ("mark.svg", "image/svg+xml; charset=utf-8"),
}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self'; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class WorkbenchHTTPServer(ThreadingHTTPServer):
    """Threaded server carrying only immutable configuration and a service."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: WorkbenchService,
        static_dir: Path,
    ) -> None:
        self.service = service
        self.static_dir = static_dir.resolve()
        self.listen_host = server_address[0]
        super().__init__(server_address, WorkbenchRequestHandler)


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    """Small allowlisted HTTP surface; it never serves arbitrary paths."""

    protocol_version = "HTTP/1.1"
    server_version = "LoomQWorkbench/1"
    sys_version = ""

    @property
    def workbench_server(self) -> WorkbenchHTTPServer:
        return self.server  # type: ignore[return-value]

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlsplit(self.path)
        if parsed.path in STATIC_FILES:
            self._serve_static(parsed.path)
            return
        if parsed.path == "/guide/QUANTUM_101.md":
            self._serve_quantum_guide()
            return
        if parsed.path == "/api/health":
            body = self.workbench_server.service.health()
            body["binding"] = _binding_kind(self.workbench_server.listen_host)
            self._send_json(HTTPStatus.OK, body)
            return
        if parsed.path == "/api/examples":
            self._send_json(
                HTTPStatus.OK,
                {"ok": True, "examples": self.workbench_server.service.examples()},
            )
            return
        if parsed.path == "/api/history":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "runs": self.workbench_server.service.workspace.history(),
                },
            )
            return
        if parsed.path == "/api/artifact":
            self._serve_artifact(parse_qs(parsed.query, keep_blank_values=True))
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "NOT_FOUND", "route not found")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlsplit(self.path)
        if parsed.path != "/api/run":
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "NOT_FOUND", "route not found"
            )
            return
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            self._send_error_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "JSON_REQUIRED",
                "Content-Type must be application/json",
            )
            return
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self._send_error_json(
                HTTPStatus.LENGTH_REQUIRED,
                "CONTENT_LENGTH_REQUIRED",
                "Content-Length is required",
            )
            return
        try:
            length = int(length_header)
        except ValueError:
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "INVALID_CONTENT_LENGTH",
                "Content-Length must be an integer",
            )
            return
        if length < 0 or length > MAX_HTTP_BODY:
            self._send_error_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "BODY_TOO_LARGE",
                "request body exceeds the 600000-byte HTTP limit",
            )
            return
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "INVALID_JSON",
                "request body must be valid UTF-8 JSON",
            )
            return
        if not isinstance(value, Mapping):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "JSON_OBJECT_REQUIRED",
                "request JSON must be an object",
            )
            return
        if _exceeds_json_depth(value):
            self._send_error_json(
                HTTPStatus.BAD_REQUEST,
                "JSON_TOO_DEEP",
                "request JSON exceeds the 32-level nesting limit",
            )
            return
        result = self.workbench_server.service.execute(value)
        self._send_json(HTTPStatus.OK, result)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
        self._send_error_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "METHOD_NOT_ALLOWED",
            "cross-origin preflight is not enabled for this local server",
        )

    def _serve_static(self, route: str) -> None:
        filename, media_type = STATIC_FILES[route]
        target = (self.workbench_server.static_dir / filename).resolve()
        try:
            target.relative_to(self.workbench_server.static_dir)
        except ValueError:
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "NOT_FOUND", "static asset not found"
            )
            return
        if not target.is_file():
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "NOT_FOUND", "static asset not found"
            )
            return
        self._send_bytes(
            HTTPStatus.OK,
            target.read_bytes(),
            media_type,
            cache_control="no-cache",
        )

    def _serve_quantum_guide(self) -> None:
        """Serve one exact checked-in guide without exposing a file browser."""

        target = Path(__file__).resolve().parents[2] / "QUANTUM_101.md"
        if not target.is_file():
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "GUIDE_NOT_FOUND", "local quantum guide not found"
            )
            return
        self._send_bytes(
            HTTPStatus.OK,
            target.read_bytes(),
            "text/markdown; charset=utf-8",
            cache_control="no-cache",
            extra_headers={
                "Content-Disposition": 'inline; filename="QUANTUM_101.md"'
            },
        )

    def _serve_artifact(self, query: Dict[str, list[str]]) -> None:
        run_id = query.get("run_id", [""])[0]
        name = query.get("name", [""])[0]
        try:
            payload, media_type = self.workbench_server.service.workspace.artifact(
                run_id, name
            )
        except WorkspaceError as exc:
            self._send_error_json(
                HTTPStatus.NOT_FOUND, "ARTIFACT_NOT_FOUND", str(exc)
            )
            return
        filename = Path(name).name.replace('"', "") or "artifact.txt"
        self._send_bytes(
            HTTPStatus.OK,
            payload,
            media_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            extra_headers={
                "Content-Disposition": 'inline; filename="%s"' % filename
            },
        )

    def _send_error_json(
        self, status: HTTPStatus, code: str, message: str
    ) -> None:
        self._send_json(
            status,
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": status.value >= 500,
                },
            },
        )

    def _send_json(self, status: HTTPStatus, value: Mapping[str, Any]) -> None:
        payload = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        self._send_bytes(
            status,
            payload,
            "application/json; charset=utf-8",
            cache_control="no-store",
        )

    def _send_bytes(
        self,
        status: HTTPStatus,
        payload: bytes,
        media_type: str,
        *,
        cache_control: str = "no-store",
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        try:
            self.send_response(status.value)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", cache_control)
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            if extra_headers:
                for name, value in extra_headers.items():
                    self.send_header(name, value)
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # A client-side cancel intentionally closes the socket. The service
            # still completes its atomic evidence writes in the worker thread.
            return

    def log_message(self, format: str, *args: object) -> None:
        # Avoid putting prompts, artifact names, or query strings in terminal
        # history. CLI startup information is printed once by ``main``.
        return


def _binding_kind(host: str) -> str:
    if host.lower() == "localhost":
        return "loopback"
    try:
        return "loopback" if ipaddress.ip_address(host).is_loopback else "non_loopback"
    except ValueError:
        return "configured_hostname"


def _exceeds_json_depth(value: Any, maximum: int = 32) -> bool:
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > maximum:
            return True
        if isinstance(item, Mapping):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return False


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    workspace: os.PathLike[str] | str | None = None,
) -> WorkbenchHTTPServer:
    """Build, but do not start, a workbench server (also used by tests)."""

    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    session = WorkspaceSession(workspace)
    service = WorkbenchService(session)
    static_dir = Path(__file__).resolve().parent / "static"
    return WorkbenchHTTPServer((host, port), service, static_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local LoomQ Pegasus compiler workbench."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="listen host (default: 127.0.0.1; no authentication is provided)",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="listen port (default: 8765)"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="base directory for UUID request evidence (default: OS temp)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    server = create_server(args.host, args.port, args.workspace)
    bound_host, bound_port = server.server_address[:2]
    display_host = "127.0.0.1" if bound_host in {"0.0.0.0", "::"} else bound_host
    print("LoomQ Pegasus local workbench: http://%s:%s" % (display_host, bound_port))
    print("Session: %s" % server.service.workspace.session_id)
    if _binding_kind(args.host) != "loopback":
        print("Warning: non-loopback binding has no authentication; use only on a trusted network.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nWorkbench stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["WorkbenchHTTPServer", "create_server", "main"]
