"""LoomQ 对照实验：定位 PQPUMESH8 上 GHZ-3 结果异常（000=99.6% 无纠缠特征）。

对照 1：本地模拟 GHZ-3 —— 验证电路构造本身正确（应为 000/111 各约 50%）
对照 2：云端 Bell 2 比特 —— 验证 H+CNOT 在该真机上的纠缠效果
对照 3：云端 X(0) 翻转 —— 验证单比特门执行（|0> 应翻转为 |1>）
"""
import os
import time

from pyqpanda3.core import CNOT, CPUQVM, H, QProg, X, measure
from pyqpanda3.qcloud import DataBase, JobStatus, QCloudOptions, QCloudService

API_KEY = os.environ.get("QPANDA_QCLOUD_API_KEY")
BACKEND = "PQPUMESH8"
SHOTS = 8192
options = QCloudOptions()
options.set_is_prob_counts(False)


def submit(name, prog):
    print(f"\n== [云端 {BACKEND}] {name} ==")
    job = backend.run(prog, shots=SHOTS, options=options)
    print("job id:", job.job_id())
    while True:
        status = job.status()
        if status in (JobStatus.FINISHED, JobStatus.FAILED):
            break
        time.sleep(5)
    result = job.result()
    if result.job_status() == JobStatus.FAILED:
        print("FAILED:", result.error_message())
        return
    print("counts:", result.get_counts(base=DataBase.Binary))
    print("probs:", result.get_probs(base=DataBase.Binary))


# 对照 1：本地模拟 GHZ-3（不消耗云额度，验证电路本身）
print("== [本地模拟] GHZ-3 ==")
prog = QProg()
prog << H(0) << CNOT(0, 1) << CNOT(0, 2) << measure([0, 1, 2], [0, 1, 2])
qvm = CPUQVM()
qvm.run(prog, SHOTS)
print("counts:", qvm.result().get_counts())

service = QCloudService(API_KEY)
backend = service.backend(BACKEND)

# 对照 2：Bell 2 比特（量旋成功案例同电路）
p = QProg()
p << H(0) << CNOT(0, 1) << measure([0, 1], [0, 1])
submit("Bell 2比特", p)

# 对照 3：X(0) 单门翻转
p = QProg()
p << X(0) << measure([0], [0])
submit("X(0) 翻转", p)
