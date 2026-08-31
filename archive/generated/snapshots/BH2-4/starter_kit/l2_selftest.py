#!/usr/bin/env python3
"""L2 变体自测器：--mock（本地 mock LLM，秒级回归）/ --live（真模型）。

判定独立于生成逻辑：期望分布全部手写解析解，从回复中用评测器同款正则
提取 QASM 后本地模拟对拍；选后端按能力表独立推导期望答案集。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

from loomq import parse_qasm, probabilities, simulate  # noqa: E402
import adapter  # noqa: E402

QASM_RE = re.compile(r"OPENQASM\s+2\.0;.*?(?=^\s*```|\Z)", re.DOTALL | re.MULTILINE)

# ---------------- 变体电池（期望分布手写，独立于模板库） ----------------

GEN_CASES = [
    ("gen-bell-1", "帮我生成一个贝尔态电路，要能测量", 2, {"00": 0.5, "11": 0.5}),
    ("gen-bell-2", "来个最大纠缠对，两比特就行", 2, {"00": 0.5, "11": 0.5}),
    ("gen-ghz-3", "生成一个 3 比特 GHZ 态并进行全测量", 3,
     {"000": 0.5, "111": 0.5}),
    ("gen-ghz-4", "我要 4 个比特的最大纠缠态，所有人都是同一种状态", 4,
     {"0000": 0.5, "1111": 0.5}),
    ("gen-ghz-5", "制备五比特 GHZ 并测量", 5, {"00000": 0.5, "11111": 0.5}),
    ("gen-ghz-6", "make a 6-qubit GHZ state with measurement", 6,
     {"000000": 0.5, "111111": 0.5}),
    ("gen-uni-3", "生成 3 比特的均匀叠加态", 3,
     {format(i, "03b"): 1 / 8 for i in range(8)}),
    ("gen-uni-4", "我要四比特完全均匀的测量结果", 4,
     {format(i, "04b"): 1 / 16 for i in range(16)}),
    ("gen-basis-1", "帮我制备 |01⟩ 这个态（两比特，右边是第 0 位）", 2, {"01": 1.0}),
    ("gen-basis-2", "生成确定态：q0=1，q1=0，q2=1 的三比特电路", 3, {"101": 1.0}),
    ("gen-w-3", "生成一个 3 比特 W 态", 3,
     {"001": 1 / 3, "010": 1 / 3, "100": 1 / 3}),
    ("gen-w-4", "来个四比特 W 态并测量", 4,
     {format(1 << i, "04b"): 0.25 for i in range(4)}),
]

FIX_CASES = [
    ("fix-bell-1",
     "我想制备一个贝尔态，但这段代码报错了，帮我修好：`H q[0]; CX q[0] q[1]`"
     "（未定义寄存器且门名大小写错误）",
     2, {"00": 0.5, "11": 0.5}),
    ("fix-bell-2",
     "这个贝尔态电路运行不了，修复它：\n```\nH q[0]\ncx q[0], q[1]\n```\n"
     "目标是 Bell 态", 2, {"00": 0.5, "11": 0.5}),
    ("fix-ghz-3",
     "帮我看下哪里错了，我要 3 比特 GHZ：h q[0]; cx q[0], q[1]; ccx q[0], q[1], q[2];",
     3, {"000": 0.5, "111": 0.5}),
    ("fix-uni-2", "我要两比特均匀叠加，但这代码只纠缠了：h q[0]; cx q[0], q[1]; 帮修",
     2, {"00": 0.25, "01": 0.25, "10": 0.25, "11": 0.25}),
    ("fix-wrong-param",
     "目标态是贝尔态，我的代码是 ry(1) q[0]; cx q[0], q[1]; 哪里不对？修一下",
     2, {"00": 0.5, "11": 0.5}),
    ("fix-ghz-4",
     "四比特 GHZ 代码报错：H q[0]; cx q[0],q[1]; cx q[1],q[2]; cx q[2],q[3]，"
     "缺了声明，修好它", 4, {"0000": 0.5, "1111": 0.5}),
]

# (case_id, prompt, 期望 id 集合)
SELECT_CASES = [
    ("sel-1", "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？",
     {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
    ("sel-2", "20 个比特的电路，不花钱，不想排队，跑哪里？",
     {"originq_local_simulator", "braket_local_simulator"}),
    ("sel-3", "我只有 2 比特的小电路，想上真机体验，选什么？",
     {"spinq_cloud_qpu", "originq_wukong"}),
    ("sel-4", "30 比特电路选哪个本地模拟器？",
     {"originq_local_simulator"}),
    ("sel-5", "有没有零排队、免费、24 比特以内的模拟器？",
     {"spinq_taurus_simulator", "originq_local_simulator", "braket_local_simulator"}),
    ("sel-6", "72 比特的真机有哪些可以选？",
     {"originq_wukong"}),
]

CHAT_CASE = ("chat-1", "你好，量子计算是什么呀？")


# ---------------- mock LLM 服务器 ----------------

class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 静音
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        user_text = "".join(
            m.get("content", "") for m in payload.get("messages", [])
            if m.get("role") == "user")
        content = json.dumps(_mock_intent(user_text), ensure_ascii=False)
        body = json.dumps({"choices": [{"message": {"role": "assistant",
                                                    "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _mock_intent(user_text: str) -> dict:
    """模拟一个完美的意图抽取器：按测试 case 特征返回正确 JSON。"""
    if "量子计算是什么" in user_text:
        return {"task": "chat"}
    if any(k in user_text for k in ("修", "报错", "错", "不对", "运行不了", "坏了")):
        intent = {"task": "fix", "broken_qasm": _mock_extract_code(user_text)}
        intent.update(_mock_target(user_text))
        return intent
    if any(k in user_text for k in ("选", "平台", "哪里", "模拟器", "排队", "真机")) and \
            "生成" not in user_text and "制备" not in user_text:
        constraints = {"max_qubits": None, "queue_none": False,
                       "cost_free": False, "kind": "any"}
        for n in (15, 20, 2, 30, 24, 72):
            if str(n) in user_text:
                constraints["max_qubits"] = n
        if "零排队" in user_text or "不想排队" in user_text or "无排队" in user_text:
            constraints["queue_none"] = True
        if "免费" in user_text or "不花钱" in user_text:
            constraints["cost_free"] = True
        if "真机" in user_text:
            constraints["kind"] = "qpu"
        if "模拟器" in user_text:
            constraints["kind"] = "simulator"
        return {"task": "select", "constraints": constraints}
    if "修" in user_text or "报错" in user_text or "错误" in user_text or "哪里不对" in user_text:
        intent = {"task": "fix", "broken_qasm": _mock_extract_code(user_text)}
        intent.update(_mock_target(user_text))
        return intent
    intent = {"task": "generate"}
    intent.update(_mock_target(user_text))
    return intent


def _mock_target(user_text: str) -> dict:
    if "W 态" in user_text:
        n = _mock_n(user_text, 3)
        return {"template": "w", "n_qubits": n, "ones": None}
    if "贝尔" in user_text or "Bell" in user_text or "纠缠对" in user_text:
        return {"template": "bell", "n_qubits": 2, "ones": None}
    if "均匀" in user_text:
        n = _mock_n(user_text, 3)
        return {"template": "uniform", "n_qubits": n, "ones": None}
    if "GHZ" in user_text or "最大纠缠" in user_text or "GHZ" in user_text.upper():
        n = _mock_n(user_text, 3)
        return {"template": "ghz", "n_qubits": n, "ones": None}
    if "|01" in user_text or "确定态" in user_text or "q0=1" in user_text:
        if "q0=1" in user_text:
            return {"template": "basis", "n_qubits": 3, "ones": [0, 2]}
        return {"template": "basis", "n_qubits": 2, "ones": [0]}  # |01⟩ 右位是 q0=1
    return {"template": "ghz", "n_qubits": 3, "ones": None}


def _mock_n(user_text: str, default: int) -> int:
    for word in ("两", "二", "三", "四", "五", "六", "七"):
        if word + "比特" in user_text:
            return {"两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}[word]
    match = re.search(r"(\d+)\s*个?比特", user_text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)-qubit", user_text)
    return int(match.group(1)) if match else default


def _mock_extract_code(user_text: str):
    fenced = re.findall(r"```[a-zA-Z]*\n(.*?)```", user_text, re.DOTALL)
    if fenced:
        return fenced[0]
    backtick = re.findall(r"`([^`]+)`", user_text)
    if backtick:
        return backtick[0]
    return user_text


def start_mock_server() -> tuple:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]


# ---------------- 判定 ----------------

def fidelity(observed: dict, expected: dict) -> float:
    states = set(observed) | set(expected)
    distance = math.sqrt(
        sum((math.sqrt(observed.get(s, 0.0)) - math.sqrt(expected.get(s, 0.0))) ** 2
            for s in states)) / math.sqrt(2.0)
    return max(0.0, min(1.0, 1.0 - distance))


def check_circuit_case(reply: str, expect: dict) -> tuple:
    match = QASM_RE.search(reply)
    if not match:
        return False, "回复中未找到 QASM"
    try:
        circuit = parse_qasm(match.group(0).strip())
        probs = probabilities(simulate(circuit))
        got = {format(i, "0%db" % circuit.n_qubits): p
               for i, p in enumerate(probs) if p > 1e-12}
    except Exception as exc:
        return False, "解析/模拟失败: %s" % exc
    fid = fidelity(got, expect)
    return (fid >= 0.97), "fidelity=%.4f" % fid


def run_battery(mode: str, only: str = None) -> int:
    cases = []
    for case_id, prompt, n, expect in GEN_CASES:
        cases.append((case_id, prompt, expect, "circuit"))
    for case_id, prompt, n, expect in FIX_CASES:
        cases.append((case_id, prompt, expect, "circuit"))
    for case_id, prompt, expected_ids in SELECT_CASES:
        cases.append((case_id, prompt, expected_ids, "select"))
    cases.append((CHAT_CASE[0], CHAT_CASE[1], None, "chat"))
    if only:
        cases = [c for c in cases if only in c[0]]

    results = []
    for case_id, prompt, expect, kind in cases:
        start = time.monotonic()
        try:
            reply = adapter.agent_chat(prompt)
        except Exception as exc:
            results.append((case_id, False, "%.0fs 异常 %s: %s"
                            % (time.monotonic() - start, type(exc).__name__, exc)))
            continue
        elapsed = time.monotonic() - start
        if kind == "circuit":
            ok, detail = check_circuit_case(reply, expect)
        elif kind == "select":
            ok = any(eid in reply for eid in expect)
            detail = "ids_ok=%s" % ok
        else:
            ok = isinstance(reply, str) and len(reply) > 10 and "OPENQASM" not in reply
            detail = "chat_reply"
        results.append((case_id, ok, "%.1fs %s" % (elapsed, detail)))
    passed = sum(1 for _, ok, _ in results if ok)
    for case_id, ok, detail in results:
        print("[%s] %-16s %s" % ("PASS" if ok else "FAIL", case_id, detail))
    print("---")
    print("%s 模式：%d/%d 通过" % (mode, passed, len(results)))
    return 0 if passed == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="本地 mock LLM 回归")
    parser.add_argument("--live", action="store_true", help="真实模型（需环境变量）")
    parser.add_argument("--only", default=None, help="按 case id 子串过滤")
    args = parser.parse_args()
    if not args.mock and not args.live:
        parser.error("选择 --mock 或 --live")
    if args.mock:
        server, url = start_mock_server()
        os.environ["LOOMQ_LLM_BASE_URL"] = url
        os.environ["LOOMQ_LLM_API_KEY"] = "mock-key"
        os.environ["LOOMQ_LLM_MODEL"] = "mock-model"
        os.environ["LOOMQ_LLM_TIMEOUT_SECONDS"] = "30"
        try:
            return run_battery("mock", args.only)
        finally:
            server.shutdown()
    return run_battery("live", args.only)


if __name__ == "__main__":
    sys.exit(main())
