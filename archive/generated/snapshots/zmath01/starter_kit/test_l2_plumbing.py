#!/usr/bin/env python3
"""Local plumbing test for agent_chat against a stub OpenAI-compatible server.

Not part of the scored submission; validates that agent_chat performs a real
model call, extracts QASM, and self-checks it. Usage:

    python3 test_l2_plumbing.py
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GHZ_REPLY = (
    "好的，这是 3 比特 GHZ 态电路：\n\n"
    "```qasm\n"
    "OPENQASM 2.0;\n"
    'include "qelib1.inc";\n'
    "qreg q[3];\n"
    "creg c[3];\n"
    "h q[0];\n"
    "cx q[0], q[1];\n"
    "cx q[1], q[2];\n"
    "measure q -> c;\n"
    "```\n\n"
    "测量后只会出现 000 和 111。\n"
)

BACKEND_REPLY = "推荐后端：braket_local_simulator（25 比特上限、零排队、免费）。"


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        assert payload["model"] == "stub-model", payload["model"]
        assert payload["temperature"] == 0
        user_text = payload["messages"][-1]["content"]
        content = BACKEND_REPLY if "选" in user_text or "后端" in user_text else GHZ_REPLY
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": content}}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    os.environ["LOOMQ_LLM_BASE_URL"] = "http://127.0.0.1:%d" % server.server_port
    os.environ["LOOMQ_LLM_API_KEY"] = "stub"
    os.environ["LOOMQ_LLM_MODEL"] = "stub-model"
    os.environ["LOOMQ_LLM_TIMEOUT_SECONDS"] = "10"
    try:
        import adapter
        from loomq_core.agent import _extract_qasm, _self_check

        reply = adapter.agent_chat("生成一个 3 比特 GHZ 态并进行全测量")
        qasm = _extract_qasm(reply)
        assert qasm and _self_check(qasm) is None
        print("[PASS] generation task: real model call, QASM extracted and runs")

        reply2 = adapter.agent_chat("我需要一个 15 比特、零排队的后端，选哪个？")
        assert "braket_local_simulator" in reply2
        print("[PASS] backend task: canonical backend id present in reply")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    print("L2 plumbing OK")


if __name__ == "__main__":
    main()
