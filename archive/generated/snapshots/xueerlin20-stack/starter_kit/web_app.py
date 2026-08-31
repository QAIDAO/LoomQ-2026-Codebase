#!/usr/bin/env python3
"""One-command launcher and compatibility exports for the LoomQ web app."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

try:
    from .run_l2 import (
        DEFAULT_ENV_FILE,
        load_environment,
        reexec_with_bundled_venv_if_needed,
        validate_ready,
    )
    from .web_backend import LoomQRequestHandler, WEB_ROOT, WebApplication
except ImportError:
    from run_l2 import (  # type: ignore
        DEFAULT_ENV_FILE,
        load_environment,
        reexec_with_bundled_venv_if_needed,
        validate_ready,
    )
    from web_backend import LoomQRequestHandler, WEB_ROOT, WebApplication  # type: ignore


def create_server(host: str, port: int, env_file: Path) -> ThreadingHTTPServer:
    """Construct a configured server without starting its lifecycle."""
    LoomQRequestHandler.app = WebApplication(env_file)
    return ThreadingHTTPServer((host, port), LoomQRequestHandler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the LoomQ Agent web interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    try:
        configuration = load_environment(args.env_file)
        validate_ready(configuration)
    except RuntimeError:
        # The browser onboarding owns recovery from missing or invalid local config.
        pass
    server = create_server(args.host, args.port, args.env_file)
    url = "http://%s:%d" % (args.host, server.server_port)
    print("LoomQ Agent 网页已启动：%s" % url)
    print("按 Ctrl+C 停止。")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLoomQ Agent 网页已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    reexec_with_bundled_venv_if_needed()
    sys.exit(main())
