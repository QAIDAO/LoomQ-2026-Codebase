# 本源量子云真机接入笔记（API 表面验证记录）

> 状态：**探索级** —— 以下均为在 pyqpanda 3.8.5（python:3.10 容器）中
> 实测验证的 API 表面（方法名/字段名），**完整调用序列尚未经本源官方
> 文档确认，写正式脚本前必须先查证**（防幻觉原则）。

## 1. 云服务入口（pyqpanda.OriginService）

```
from pyqpanda.OriginService import QCloudMachine, QCloudService, QCloudTaskConfig
```

- `QCloudTaskConfig`（pyqpanda.pyQPanda 原生类）字段：
  `chip_id`, `cloud_token`, `open_amend`, `open_mapping`, `open_optimization`, `shots`
- `QCloudService` 关键方法（真机相关）：
  `build_real_chip_measure`, `build_real_chip_measure_batch`,
  `cyclic_query`, `get_status`, `set_qcloud_url`, `user_token`,
  `init`, `run_with_configuration`, `query_prob_dict_result`
- `real_chip_type` 枚举：`origin_72`（悟空 72 比特）、
  `origin_wuyuan_d3 / d4 / d5`（五原系列）
- `origin_72` / `origin_wuyuan_d*` 也是 `real_chip_type` 成员

## 2. 与评测契约的对应

- 本源云任务：`QCloudTaskConfig` 的 `chip_id` + `cloud_token` + `shots`
  （token 从本源量子云 qcloud.originqc.com.cn 申请，注意不要硬编码进仓库）
- 任务结果需要能溯源（评测组会复核 job/task ID），提交时保留任务回执

## 3. 待办清单（如需申请本源真机 +5 分）

1. [ ] 用户在本源量子云注册并申请 API Token（审核较慢，可提前申请）
2. [ ] 对照本源官方文档确认 QCloudService 调用序列
   （参考：https://qcloud.originqc.com.cn/zh · pyqpanda-toturial.readthedocs.io）
3. [ ] 写 `examples/run_originq_cloud.py`，token 从环境变量读取
4. [ ] 采集真机 result.json + 任务页截图，填 evidence

## 4. 优先级说明

SpinQ 云（`examples/run_spinq_cloud.py`）为第一真机平台，已万事俱备
（SSH 密钥 + API 链验证通过）；本源为可选的第二平台（+5 分）。
两个真机平台都有后，L1 真机分满分（+10）。
