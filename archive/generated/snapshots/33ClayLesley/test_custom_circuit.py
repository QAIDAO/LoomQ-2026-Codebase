# test_custom_circuits.py
# 隐藏电路跑通测试 (swap/ccs/cu1)
from starter_kit.adapter import run

files = ["swap.qasm", "ccx.qasm", "cu1.qasm"]
for f in files:
    with open(f"starter_kit/circuits/{f}", "r") as file:
        qasm = file.read()
    try:
        result = run(qasm, target="spinq", shots=1024)
        print(f"{f}: ✅ PASS - counts: {result['counts']}")
    except Exception as e:
        print(f"{f}: ❌ FAIL - {e}")