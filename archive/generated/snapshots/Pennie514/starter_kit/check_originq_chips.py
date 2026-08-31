#!/usr/bin/env python3
"""本源量子云真机状态探测：找出当前可提交的芯片

用法：
    export ORIGINQ_API_TOKEN="你的 API Token"
    python3 starter_kit/check_originq_chips.py

对每个候选芯片（72=悟空，7/5/2=悟源系列）提交一个极小任务（100 shots 的
Bell 电路）探测：能拿到 task_id = 芯片可提交；报 maintenance = 维护中。
探测成功后，用返回的芯片号跑完整真机验证：
    python3 starter_kit/real_machine.py originq_wukong \
        --qasm starter_kit/circuits/bell.qasm --shots 8192 \
        --config starter_kit/evidence/config_originq_wukong.json \
        --chip-id <可用的芯片号> \
        --out starter_kit/evidence/files/originq_wukong_result.json

注意：探测会消耗少量免费机时（约 1-2 秒/芯片）；新用户约 60 秒额度足够。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

token = os.environ.get("ORIGINQ_API_TOKEN")
if not token:
    raise SystemExit("请先设置环境变量 ORIGINQ_API_TOKEN（qcloud.originqc.com.cn 个人中心→账号设置）")

import pyqpanda as pq  # noqa: E402

CHIPS = [
    (72, "悟空 72 比特超导真机"),
    (180, "本源 180 比特超导真机（本源180）"),
    (7, "悟源系列（chip 7）"),
    (5, "悟源系列（chip 5）"),
    (2, "悟源系列（chip 2）"),
]

PROBE_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

machine = pq.QCloud()
machine.init_qvm(user_token=token, enable_logging=False, log_to_console=False)
try:
    print("正在探测本源真机可用性（每个芯片提交 1 个小任务）……\n")
    for chip_id, name in CHIPS:
        try:
            prog, _q, _c = pq.convert_qasm_string_to_qprog(PROBE_QASM, machine)
            task_id = machine.async_real_chip_measure(
                prog, shot=100, chip_id=chip_id,
                is_amend=True, is_mapping=True, is_optimization=True,
                task_name="LoomQ-chip-probe",
            )
            print(f"  ✅ chip_id={chip_id}（{name}）可提交！task_id={task_id}")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "maintenance" in msg.lower():
                print(f"  🔴 chip_id={chip_id}（{name}）维护中")
            else:
                print(f"  ⚠️  chip_id={chip_id}（{name}）其他错误: {msg[:120]}")
        time.sleep(1)
finally:
    machine.finalize()

print("\n探测完成。把 ✅ 的 chip_id 填入 real_machine.py 的 --chip-id 参数重跑完整验证。")
print("若全部维护中：过 20-30 分钟重跑本脚本，直到出现 ✅。")
