#!/usr/bin/env python3
"""提交 Bell 态到本源真机"""
import pyqpanda as pq
import json
import os
 
api_key = os.environ.get("ORIGINQ_API_KEY", "")
print(f"[1] API Key: {api_key[:8]}...", flush=True)
 
qvm = pq.QCloud()
qvm.init_qvm(user_token=api_key)
print("[2] 初始化成功", flush=True)
 
# 构建 Bell 态
qubits = qvm.qAlloc_many(2)
cbits = qvm.cAlloc_many(2)
prog = pq.QProg()
prog << pq.H(qubits[0]) << pq.CNOT(qubits[0], qubits[1])
prog << pq.Measure(qubits[0], cbits[0]) << pq.Measure(qubits[1], cbits[1])
print("[3] 电路构建完成", flush=True)
 
# 逐个尝试芯片
chips = [
    ("origin_wuyuan_d5", pq.real_chip_type.origin_wuyuan_d5),
    ("origin_wuyuan_d4", pq.real_chip_type.origin_wuyuan_d4),
    ("origin_wuyuan_d3", pq.real_chip_type.origin_wuyuan_d3),
    ("origin_72", pq.real_chip_type.origin_72),
]
 
for chip_name, chip_type in chips:
    print(f"[4] 尝试 {chip_name} ...", flush=True)
    try:
        result = qvm.real_chip_measure(prog, 1024, chip_type)
        print(f"[4] {chip_name} 成功!", flush=True)
        unified = {
            "backend": "originq_wukong",
            "chip": chip_name,
            "shots": 1024,
            "counts": result,
            "bit_order": "little"
        }
        print(json.dumps(unified, indent=2))
        break
    except Exception as e:
        print(f"[4] {chip_name} 失败: {e}", flush=True)
 
qvm.finalize()
