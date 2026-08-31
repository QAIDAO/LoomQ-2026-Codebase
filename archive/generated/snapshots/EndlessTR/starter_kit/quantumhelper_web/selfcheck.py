#!/usr/bin/env python3
r"""本地自检：验证 Web Agent 全链路，不接触、不打印你的 API Key。

用法（在 PowerShell 里，不要粘贴 key 到聊天）：

    $env:QUANTUMHELPER_ENABLE_LLM = "1"
    $env:LOOMQ_LLM_BASE_URL = "<你的服务地址>"
    $env:LOOMQ_LLM_API_KEY  = "<你的 key>"
    $env:LOOMQ_LLM_MODEL    = "deepseek-v4-flash"
    python starter_kit\quantumhelper_web\selfcheck.py

脚本从 os.environ 读取配置，输出只有 status / intent / 摘要，不含任何密钥。
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request

import server

HOST, PORT = "127.0.0.1", 8013


def _post(body: dict):
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/api/chat",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


#: (label, prompt, context, want_kind, want_intent, needs_llm)
CASES = (
    ("概念问答 H 门", "H 门到底干嘛的，别给我公式", None, "qa", "quantum_qa", False),
    ("概念问答 shots", "shots 是什么，说人话", None, "qa", "quantum_qa", False),
    ("新手生成（确定性）", "给我弄个新手能看懂的量子线路", None, "qasm", "generate_circuit", False),
    ("简单纠缠（需LLM）", "给我一个最简单的量子纠缠例子，不要太复杂", None, "qasm", "generate_circuit", True),
    ("标准 GHZ（需LLM）", "生成一个 4 比特 GHZ 态，只测量前两个量子比特", None, "qasm", "generate_circuit", True),
    ("Repair（需LLM）", "我想制备一个贝尔态，但这段代码报错了：H q[0]; CX q[0] q[1]", None, "qasm", "repair_circuit", True),
    ("场景·查找", "我有 8 个候选编号，其中只有一个满足条件，希望找到它。", None, "scenario", "scenario_help", False),
    ("场景·关联", "生成并运行一个 Bell 实验，看看两个量子比特怎样产生关联。", None, "qasm", "generate_circuit", False),
    ("未知·澄清", "今天天气怎么样", None, "clarify", "unknown", False),
    ("优化·澄清", "给我弄个量子优化线路", None, "clarify", "generate_circuit", False),
)

_BELL_QASM = (
    "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
    "h q[0];\ncx q[0],q[1];\nmeasure q -> c;"
)


def main() -> int:
    if os.getenv("QUANTUMHELPER_ENABLE_LLM") != "1":
        print("[提示] 请先设置 QUANTUMHELPER_ENABLE_LLM=1，否则生成/修复路径会走 LLM_DISABLED。")
    missing = [v for v in ("LOOMQ_LLM_BASE_URL", "LOOMQ_LLM_API_KEY", "LOOMQ_LLM_MODEL")
               if not os.environ.get(v)]
    if missing:
        print("[提示] 未检测到这些环境变量：" + ", ".join(missing))
        print("       没有它们，「需LLM」的用例只能验证到 LLM_NOT_CONFIGURED 这一层。\n")

    httpd = server.ThreadingHTTPServer((HOST, PORT), server.QuantumHelperHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)

    print(f"{'用例':<22}{'status':<7}{'kind':<9}{'intent':<22} 结果")
    print("-" * 78)
    passed = 0
    total = 0
    try:
        for label, prompt, ctx, want_kind, want_intent, needs_llm in CASES:
            total += 1
            body = {"prompt": prompt, "schema_version": "1.0"}
            if ctx:
                body["context"] = ctx
            status, payload = _post(body)
            kind = payload.get("kind")
            intent = payload.get("intent")
            code = payload.get("code")
            if kind == "error":
                intent = code or intent  # show LLM_NOT_CONFIGURED etc.
            ok = status == 200 and kind == want_kind and intent == want_intent
            # 需 LLM 的用例，若因缺 key 只走到 LLM_NOT_CONFIGURED / LLM_DISABLED，
            # 也记为「已走通路由」——说明路由与配置检测都正确，只差真 key。
            if not ok and needs_llm and code in ("LLM_NOT_CONFIGURED", "LLM_DISABLED"):
                ok = True
            passed += ok
            summary = (payload.get("answer") or payload.get("user_message")
                       or payload.get("error") or "").replace("\n", " ")[:44]
            mark = "OK " if ok else "FAIL"
            print(f"{label:<22}{status:<7}{str(kind):<9}{str(intent):<22} {mark} {summary}")
            if not ok and needs_llm is False:
                print(f"{'':<22}        期待 kind={want_kind} intent={want_intent}")
    finally:
        httpd.shutdown()

    print("-" * 78)
    print(f"通过 {passed}/{total}（需LLM的用例在未配置key时按「已走通路由」计）")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
