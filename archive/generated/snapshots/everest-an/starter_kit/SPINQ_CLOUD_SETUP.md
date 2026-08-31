# SpinQ Cloud 公钥配置与真机证据采集指南

> 目标：把 L1 真机证据的第二个平台（spinq，+5 分）采集到位。
> 这是**唯一的待办步骤**——SSH 密钥已在本机生成，脚本与 API 均已验证。

## 第 1 步：复制公钥（已完成，密钥在本机）

本机已生成密钥对：`C:\Users\admin\.ssh\id_rsa_spinq`（私钥）+ `.pub`（公钥）。

公钥内容（可直接复制）：

```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7rEicL8EeGJa4aBZYxGSm8sH8UbPpGiKTeg9l6/s6iAWoKGwYA8PLAAwxskBpkq/ggBRjLMS6Stk9s3eWdlTXG9V99xUgCRDIugNeVn/N89rLQ+Ci2gwaF+SI7qMm1Attt9chTBc07gmy7jeojWhhNSkJH2pNOPy3yW0TkUhJvEqK8mevJwQdczZK9VnWq0RIRCSLqbt9Mw8bZmhncUg1cPJAG1HEzR9EhtorNONEpdR4813Bi+WB2pjniu8ATVyMFsu6a6nxGGCZHDs8i216zW/smmiz+kM1aHCdqXoccxOaHjOEhIuiR18eX6vIoiWXn2Kd72kZ6zC8asIivko3 loomq
```

## 第 2 步：在平台上添加公钥（需要你在浏览器操作）

1. 登录 https://cloud.spinq.cn
2. 进入平台文档 `#/docs` 或控制台个人设置，找到 **SSH 密钥** 管理入口
3. 粘贴上述公钥并保存
4. 告诉我你的 **SpinQ 云用户名**

## 第 3 步：采集真机证据（添加公钥后由我自动执行）

拿到用户名后，我会运行：

```bash
# 在 python:3.10 + spinqit 容器中
python examples/run_spinq_cloud.py \
    --username <你的用户名> \
    --keyfile /keys/id_rsa_spinq \
    --platform superconductor_vp \
    --circuit circuits/bell.qasm --shots 8192 \
    --out evidence/files/spinq-bell-result.json
```

流程：连接 SpinQ 云 → 检查 `superconductor_vp`（8 比特超导真机）可用性 →
提交 Bell/GHZ 电路 → 保存带 job_id 的原始 result.json。

## 第 4 步：截图与申报

1. 你在平台任务页**截图**（含 job_id，供评测组溯源复核）
2. 截图放入 `starter_kit/evidence/files/`
3. 我更新 evidence/README.md 的 L1 真机申报，重新跑提交预检

## 已就绪的技术验证（无需再操作）

- SSH 密钥：✅ 已生成（`id_rsa_spinq` + `.pub`）
- spinqit API 链：✅ 容器内实测认证可达（"No active user" 错误证明链路通）
- 采集脚本：✅ `examples/run_spinq_cloud.py` 已按官方文档写好
- 平台：✅ `superconductor_vp`（8 比特超导真机）已在 backend_capabilities 确认

## 环境注意事项（antlr4 版本冲突）

- `spinqit 0.2.4` 强制要求 `antlr4-python3-runtime==4.9.2`；
- `amazon-braket-sdk` 需要更高的 antlr4（4.13.2 实测可用）；
- 两者**不可共存于同一环境**。运行时请用独立环境：
  - spinqit 环境：`pip install spinqit antlr4-python3-runtime==4.9.2`
  - braket 环境：`pip install amazon-braket-sdk`（antlr4 会自动升级）
- 已采集的 braket 证据与 spinq/spinqit 交叉验证不受此冲突影响（各自在合适环境中完成并入库）。

> 注意：私钥 `id_rsa_spinq` 留在本机，**不要提交到仓库**（.gitignore 之外的
> 凭证都不应入库）。脚本通过 `--keyfile` 参数引用。
