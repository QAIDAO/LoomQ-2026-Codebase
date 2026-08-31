"""LoomQ 真机证据采集：GHZ-3 → 本源量子云 PQPUMESH8（3 比特光量子真机）。

用法（先设置 API Key）：
  PowerShell: $env:QPANDA_QCLOUD_API_KEY="..." 然后 python 运行本文件
  Bash:       export QPANDA_QCLOUD_API_KEY="..." 然后 python 运行本文件

产出：打印 job ID / 状态 / counts / probs，并把服务端原始响应保存到
      pqpumesh8-ghz3-result.json（证据链原始材料）。
"""
import os
import time
from pathlib import Path

from pyqpanda3.core import CNOT, H, QProg, measure
from pyqpanda3.qcloud import DataBase, JobStatus, QCloudOptions, QCloudService

API_KEY = os.environ.get("QPANDA_QCLOUD_API_KEY")
BACKEND = os.environ.get("QPANDA_QCLOUD_BACKEND", "PQPUMESH8")  # 3 比特光量子真机
SHOTS = 8192

if not API_KEY:
    raise SystemExit(
        "未找到 QPANDA_QCLOUD_API_KEY 环境变量。\n"
        "PowerShell: $env:QPANDA_QCLOUD_API_KEY=\"你的key\"\n"
        "Bash: export QPANDA_QCLOUD_API_KEY=\"你的key\""
    )

service = QCloudService(API_KEY)
print("== 可用后端 ==")
for name, available in service.backends().items():
    print("  ", name, "available" if available else "unavailable")

backend = service.backend(BACKEND)

# GHZ-3 纠缠态（与 evidence/files/ghz3-qcloud.qasm 逻辑一致）：
# H(0) → 叠加；CNOT(0,1) 与 CNOT(0,2) → 三比特纠缠。理想结果 000/111 各 50%。
prog = QProg()
prog << H(0)
prog << CNOT(0, 1)
prog << CNOT(0, 2)
prog << measure([0, 1, 2], [0, 1, 2])

print(f"\n== 提交 {BACKEND}，shots={SHOTS} ==")
# 注意：默认 is_prob_counts=True 时 get_counts() 返回空 {}；
# 显式请求原始计数，证据中 000/111 出现次数更直观。
options = QCloudOptions()
options.set_is_prob_counts(False)
job = backend.run(prog, shots=SHOTS, options=options)
print("job id:", job.job_id())

while True:
    status = job.status()
    print("status:", status)
    if status == JobStatus.FINISHED:
        result = job.result()
        break
    if status == JobStatus.FAILED:
        result = job.query()
        print("error:", result.error_message())
        raise SystemExit(1)
    time.sleep(10)

print("\nfinal status:", result.job_status())
print("timing:", result.timing_info())

counts = result.get_counts(base=DataBase.Binary)
probs = result.get_probs(base=DataBase.Binary)
print("counts:", counts)
print("probs:", probs)

# 保存服务端原始响应（证据链原始材料，按后端命名）
out = Path(__file__).resolve().parent / f"{BACKEND.lower()}-ghz3-result.json"
out.write_text(result.origin_data(), encoding="utf-8")
print("\n原始响应已保存:", out)
