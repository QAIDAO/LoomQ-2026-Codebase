import os
import sys

import pyqpanda as pq

originir = "QINIT 2\nCREG 2\nH q[0]\nCNOT q[0],q[1]\nMEASURE q[0], c[0]\nMEASURE q[1], c[1]"
token = os.environ.get("ORIGINQ_API_TOKEN", "FAKE")

cloud = pq.QCloud()
cloud.init_qvm(user_token=token)
cloud.set_qcloud_url("https://qcloud.originqc.com.cn")

# Hypothesis: prog must be bound to the SAME (cloud) machine, not a CPUQVM.
conv = getattr(pq, "convert_originir_str_to_qprog", None)
print("convert fn:", conv)
out = conv(originir, cloud)
prog = out[0]
print("prog type:", type(prog))

print("submitting async_real_chip_measure ...")
task_id = cloud.async_real_chip_measure(prog, 64, chip_id=2)
print("task_id:", task_id)
