"""L2 variant-robustness test: reworded prompts must classify and solve correctly.

Simulates the organizer's "unpublished prompt variants" by rewording each
task class without the obvious trigger keywords. The classifier (LLM-based,
keyword fallback) must route every variant to the right solver, and the
solver must return a structurally valid answer.
"""

import json
import sys

sys.path.insert(0, "starter_kit")
from agent import _classify, _extract_qasm, _valid_backend_ids, _rule_filter_backends, _load_capabilities
from adapter import agent_chat

VARIANT_CASES = [
    # (expected_category, prompt)
    ("GENERATE", "制备一个 3 比特的 GHZ 态并全部测量"),
    ("GENERATE", "帮我写一个 2 比特的贝尔态电路"),
    ("GENERATE", "我想让两个量子比特纠缠起来，给我电路"),
    ("GENERATE", "构建一个 4 比特的量子傅里叶变换电路"),
    ("FIX", "这段电路有问题，帮我看看：H q[0]; CX q[0] q[1]（我想制备贝尔态）"),
    ("FIX", "这个代码跑不了，帮忙改正：H q[0]; CX q[0] q[1] 缺了寄存器声明"),
    ("FIX", "调试一下这个电路：H q[0]; CX q[0] q[1]，目标贝尔态"),
    ("SELECT", "运行一个 15 比特电路，要零排队等待，用哪个平台"),
    ("SELECT", "免费的模拟器有哪几个？我想跑 20 比特的电路"),
    ("SELECT", "20 比特的电路用 Braket 还是 SpinQ 更合适"),
]

# --- Deterministic rule filter tests (no LLM needed) -------------------------

RULE_CASES = [
    ("运行一个 15 比特电路，要零排队等待",
     {"braket_local_simulator", "originq_local_simulator", "spinq_taurus_simulator"}),
    ("免费的模拟器有哪几个？我想跑 20 比特",
     {"braket_local_simulator", "originq_local_simulator", "spinq_taurus_simulator"}),
    ("选个后端跑真机",
     {"braket_cloud", "originq_wukong", "spinq_cloud_qpu"}),
]

failures = 0

# 1. Rule filter unit tests
data = json.loads(_load_capabilities())
for prompt, expected_set in RULE_CASES:
    hits = _rule_filter_backends(prompt, data)
    ok = hits == expected_set
    if not ok:
        failures += 1
    print("[%s] rule: %s -> %s (expected %s)" % (
        "OK " if ok else "BAD", prompt, sorted(hits), sorted(expected_set)))

# 2. Classification variants
for expected, prompt in VARIANT_CASES:
    try:
        got = _classify(prompt)
        mark = "OK " if got == expected else "BAD"
        if got != expected:
            failures += 1
        print("[%s] classify: expected=%s got=%s | %s" % (mark, expected, got, prompt))
    except Exception as exc:
        failures += 1
        print("[ERR] classify failed for %r: %s: %s" % (prompt, type(exc).__name__, exc))

# End-to-end: solve a few full variants through agent_chat
E2E = [
    ("FIX", "这段电路有问题，帮我看看：H q[0]; CX q[0] q[1]（我想制备贝尔态）"),
    ("SELECT", "免费的模拟器有哪几个？我想跑 20 比特的电路"),
    ("GENERATE", "制备一个 3 比特的 GHZ 态并全部测量"),
]
print("\n=== end-to-end ===")
for expected, prompt in E2E:
    try:
        answer = agent_chat(prompt)
        if expected == "GENERATE" or expected == "FIX":
            qasm = _extract_qasm(answer)
            ok = qasm is not None
            print("[%s] e2e:%s qasm_extracted=%s | %s" % ("OK " if ok else "BAD", expected, ok, prompt))
            if not ok:
                failures += 1
        else:
            valid = any(bid in answer for bid in _valid_backend_ids())
            # rule-based guarantee: for constraint-carrying prompts, the
            # reply MUST lie inside the deterministic legal set
            rule_hits = _rule_filter_backends(prompt, json.loads(_load_capabilities()))
            in_legal_set = (not rule_hits) or any(bid in answer for bid in rule_hits)
            print("[%s] e2e:SELECT valid_backend_id=%s in_legal_set=%s | %s" % (
                "OK " if valid and in_legal_set else "BAD", valid, in_legal_set, prompt))
            if not (valid and in_legal_set):
                failures += 1
    except Exception as exc:
        failures += 1
        print("[ERR] e2e failed for %r: %s: %s" % (prompt, type(exc).__name__, exc))

print("\n%s: %d failure(s)" % ("L2 variant test FAILED" if failures else "L2 variant test PASSED", failures))
sys.exit(1 if failures else 0)
