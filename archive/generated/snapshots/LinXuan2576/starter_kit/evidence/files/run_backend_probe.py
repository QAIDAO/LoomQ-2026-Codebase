"""LoomQ 后端探测：列出全部后端，并对每个可用真机后端跑 Bell 电路验证门执行。

背景：PQPUMESH8（3 比特光量子）在 2026-08-24 探测时所有量子门不执行
（X(0) 实测仍 |0> 99.9%），本次复查各后端是否恢复。

用法（API Key 不要贴聊天，用环境变量）：
  Bash:       export QPANDA_QCLOUD_API_KEY="..." && python run_backend_probe.py
  PowerShell: $env:QPANDA_QCLOUD_API_KEY="..."; python run_backend_probe.py
"""
import os
import time

from pyqpanda3.core import CNOT, H, QProg, measure
from pyqpanda3.qcloud import DataBase, JobStatus, QCloudOptions, QCloudService

API_KEY = os.environ.get("QPANDA_QCLOUD_API_KEY")
if not API_KEY:
    raise SystemExit("未找到 QPANDA_QCLOUD_API_KEY 环境变量")

SHOTS = 8192
options = QCloudOptions()
options.set_is_prob_counts(False)

# 云模拟器后端不参与真机探测（不计真机分）
SIMULATORS = {
    "full_amplitude", "amplitude_density_matrix", "single_amplitude",
    "partial_amplitude", "qgate", "qasm_simulator", "stabilizer",
}

service = QCloudService(API_KEY)
backends = service.backends()
print("== 全部后端 ==")
for name, available in backends.items():
    print("  ", name, "available" if available else "unavailable")

for name, available in backends.items():
    if not available:
        continue
    if name.lower() in SIMULATORS or "sim" in name.lower():
        print(f"  (跳过云模拟器: {name})")
        continue

    print(f"\n== 探测 {name}：Bell 2 比特，shots={SHOTS} ==")
    try:
        backend = service.backend(name)
        prog = QProg()
        prog << H(0) << CNOT(0, 1) << measure([0, 1], [0, 1])
        job = backend.run(prog, shots=SHOTS, options=options)
        print("job id:", job.job_id())
        while True:
            status = job.status()
            print("status:", status)
            if status in (JobStatus.FINISHED, JobStatus.FAILED):
                break
            time.sleep(10)
        result = job.result()
        if result.job_status() == JobStatus.FAILED:
            print("FAILED:", result.error_message())
            continue
        counts = result.get_counts(base=DataBase.Binary)
        print("counts:", counts)
        bell = counts.get("00", 0) + counts.get("11", 0)
        if bell > 0.9 * SHOTS:
            print(f"→ 纠缠正常（00+11 = {bell/SHOTS:.1%}）")
        else:
            print(f"→ 结果异常（00+11 = {bell/SHOTS:.1%}，门可能没执行）")
    except Exception as e:
        print("ERROR:", type(e).__name__, e)
