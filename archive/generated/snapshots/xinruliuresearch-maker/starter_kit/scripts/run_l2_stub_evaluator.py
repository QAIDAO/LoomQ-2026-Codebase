#!/usr/bin/env python3
"""Exercise the public L2 evaluator through a real local HTTP transport.

The server in this script stands in only for the organizer-provided language
model endpoint.  It never supplies quantum execution results: LoomQ still
parses and verifies the QASM locally before returning it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List


class _Handler(BaseHTTPRequestHandler):
    server_version = "LoomQL2Stub/1.0"

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400)
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
            self.send_error(400)
            return
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "intent": "generate_qasm",
                                "pattern": "ghz",
                                "qubits": 3,
                                "basis": "z",
                                "qasm": "",
                            },
                            separators=(",", ":"),
                        )
                    }
                }
            ]
        }
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
        with self.server.request_lock:  # type: ignore[attr-defined]
            self.server.requests.append(payload)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        default="evidence/files/l2-public-report.json",
        help="public evaluator report path, relative to starter_kit by default",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.json_out)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.requests: List[Dict[str, Any]] = []  # type: ignore[attr-defined]
    server.request_lock = threading.Lock()  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        environment = os.environ.copy()
        environment.update(
            {
                "LOOMQ_LLM_BASE_URL": "http://%s:%d/v1" % (host, port),
                "LOOMQ_LLM_API_KEY": "local-test-only",
                "LOOMQ_LLM_MODEL": "local-transport-stub",
                "LOOMQ_LLM_TIMEOUT_SECONDS": "10",
                "LOOMQ_LLM_MAX_OUTPUT_TOKENS": "1024",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        completed = subprocess.run(
            [
                sys.executable,
                "evaluator.py",
                "--level",
                "l2",
                "--json-out",
                str(output),
            ],
            cwd=root,
            env=environment,
            check=False,
        )
        request_count = len(server.requests)  # type: ignore[attr-defined]
        if completed.returncode != 0:
            return completed.returncode
        if request_count < 1:
            print("FAIL: evaluator passed without an HTTP model request", file=sys.stderr)
            return 1
        print("PASS: public L2 evaluator used %d real HTTP request(s)" % request_count)
        print("Report: %s" % output)
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
