#!/usr/bin/env python3
import json
import os
import sys
 
from spinqit import get_compiler, get_spinq_cloud, SpinQCloudConfig, Circuit, H, CX
 
# 构建 Bell 态电路
circ = Circuit()
q = circ.allocateQubits(2)
circ << (H, q[0])
circ << (CX, (q[0], q[1]))
 
# 编译
compiler = get_compiler("native")
ir = compiler.compile(circ, 0)
 
# 连接 SpinQ Cloud
engine = get_spinq_cloud(
    username=os.environ["SPINQCLOUDUSERNAME"],
    keyfile=os.environ["PRIVATEKEYPATH"],
    host=os.environ.get("SPINQCLOUDHOST", "http://cloud.spinq.cn:6060"),
)
 
# 配置：指定真机平台 + shots
config = SpinQCloudConfig()
config.configure_platform("gemini_vp")
config.configure_shots(1024)
 
# 提交并等待结果
result = engine.execute(ir, config)
 
# 输出统一格式
unified = {
    "backend": "spinq_cloud_qpu",
    "job_id": result.task_code,
    "shots": 1024,
    "counts": {str(k): v for k, v in result.counts.items()},
    "probabilities": {str(k): v for k, v in result.probabilities.items()},
    "bit_order": "little",
}
print(json.dumps(unified, indent=2))
