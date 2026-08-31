"""Run the organizer's public L2 check against a real local HTTP endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from starter_kit import evaluator


GHZ_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
measure q -> c;
"""


class Handler(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        type(self).calls += 1
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        content = json.dumps(
            {
                "task": "generate",
                "qasm": GHZ_QASM,
                "constraints": None,
                "explanation": "本地合同端点生成的 GHZ",
            },
            ensure_ascii=False,
        )
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = {name: os.environ.get(name) for name in (
        "LOOMQ_LLM_BASE_URL",
        "LOOMQ_LLM_API_KEY",
        "LOOMQ_LLM_MODEL",
        "LOOMQ_LLM_TIMEOUT_SECONDS",
    )}
    os.environ.update(
        {
            "LOOMQ_LLM_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "LOOMQ_LLM_API_KEY": "local-contract-key",
            "LOOMQ_LLM_MODEL": "fake-deepseek",
            "LOOMQ_LLM_TIMEOUT_SECONDS": "2",
        }
    )
    try:
        cases = evaluator.evaluate_l2()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    for case in cases:
        print(f"[{case['status']}] {case['case_id']}: {case['reason']}")
    print(f"model_calls={Handler.calls}")
    return 0 if cases and all(case["status"] == "PASS" for case in cases) and Handler.calls else 1


if __name__ == "__main__":
    raise SystemExit(main())
