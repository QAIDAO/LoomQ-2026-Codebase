# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个平台填写一次。

### Origin Quantum Cloud

- 平台名称：Origin Quantum Cloud（后端：WK_C180）
- 平台 job ID：C631C56659A127243AFDB9D2B1086683
- 运行时间：2026-08-21T13:52:28.326096Z（UTC）
- shots：1000
- 实际执行的 QASM：[输入 QASM](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-input.qasm)
- 平台返回的原始结果：[raw result](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-raw-result.json)
- 任务页截图：[submitted.png](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-submitted.png)
- 实际提交的 OriginIR：[submitted.originir](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-submitted.originir)
- 提交记录：[submission.json](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-submission.json)
- metadata：[metadata.json](files/l1-real-hardware/originq/C631C56659A127243AFDB9D2B1086683-metadata.json)

### SpinQ Cloud

- 平台名称：SpinQ Cloud（后端：gemini_vp）
- 平台 job ID：G-260821-0005
- 运行时间：2026-08-21T14:46:21.039462Z（UTC）
- shots：1000
- 实际执行的 QASM：[submitted.qasm](files/l1-real-hardware/spinq/G-260821-0005-submitted.qasm)
- 平台返回的原始结果：[raw result](files/l1-real-hardware/spinq/G-260821-0005-raw-result.json)
- 原始输入 QASM：[input.qasm](files/l1-real-hardware/spinq/G-260821-0005-input.qasm)
- 解析后的结果：[parsed result](files/l1-real-hardware/spinq/G-260821-0005-parsed-result.json)
- metadata：[metadata.json](files/l1-real-hardware/spinq/G-260821-0005-metadata.json)

说明：SpinQ Cloud 的 QASM 提交接口不接受 `measure` 语句，因此 `submitted.qasm` 是实际发送给平台的无测量副本；`input.qasm` 保留原始完整测量语义，平台原始结果以概率数组返回。

## L2 交互体验

启动界面或 CLI 的命令：

### 构建镜像

先进入官方构建与评测根目录；如果当前环境已将 `starter_kit/` 提取为根目录，则无需重复执行 `cd`。后续命令均以 `starter_kit/` 为当前目录：

```bash
cd starter_kit
docker build -t loomq-final .
```

### 运行环境变量

以下三个变量必须在运行环境中设置，也可使用 Docker 的 `--env-file` 提供：

- `LOOMQ_LLM_BASE_URL`
- `LOOMQ_LLM_API_KEY`
- `LOOMQ_LLM_MODEL`

可选设置 `LOOMQ_LLM_TIMEOUT_SECONDS=120`。SpinQ 真机体验所需的 `SPINQ_USERNAME` 和 `SPINQ_KEY_PATH` 不影响基础 Web 启动，配置方法见下方可选命令。

### 启动 Web

```bash
docker run --rm -p 8000:8765 \
  -e LOOMQ_LLM_BASE_URL \
  -e LOOMQ_LLM_API_KEY \
  -e LOOMQ_LLM_MODEL \
  -e LOOMQ_LLM_TIMEOUT_SECONDS=120 \
  loomq-final \
  python -m loomq.debug_web --host 0.0.0.0 --port 8765 --serve-web
```

如需在 Web 中体验 SpinQ 真机，先将宿主机环境变量 `SPINQ_KEY_PATH` 设置为关联私钥的绝对路径，再运行：

```bash
docker run --rm -p 8000:8765 \
  -e LOOMQ_LLM_BASE_URL \
  -e LOOMQ_LLM_API_KEY \
  -e LOOMQ_LLM_MODEL \
  -e LOOMQ_LLM_TIMEOUT_SECONDS=120 \
  -e SPINQ_USERNAME \
  -e SPINQ_KEY_PATH=/run/secrets/spinq-private-key \
  -v "$SPINQ_KEY_PATH:/run/secrets/spinq-private-key:ro" \
  loomq-final \
  python -m loomq.debug_web --host 0.0.0.0 --port 8765 --serve-web
```

测试入口：[http://localhost:8000](http://localhost:8000)

### 用户任务

1. 在 Learn 页面按步骤阅读 Bell 电路说明、查看状态变化与 QASM，再进入可选的真实量子设备体验入口。
2. 在 Explorer 输入“创建一个 Bell 态量子电路并测量”，查看自然语言生成的 OpenQASM、电路过程与语义验证结果。
3. 在“程序修复”页粘贴包含错误的 OpenQASM，并说明目标；查看 parser/语义验证诊断与可确认的修复提案。

- [首页入口](files/l2-agent/home.png)
- [Learn 教学、QASM 与状态变化](files/l2-agent/learn.gif)
- [自然语言生成、QASM 与电路过程](files/l2-agent/explorer-generation.gif)
- [验证或修复结果](files/l2-agent/repair-verification.gif)
- [执行平台选择](files/l2-agent/choose-backend.gif)

## 工程与产品化

干净环境中的构建和启动命令：

### 构建镜像

先进入官方构建与评测根目录；如果当前环境已将 `starter_kit/` 提取为根目录，则无需重复执行 `cd`。后续命令均以 `starter_kit/` 为当前目录：

```bash
cd starter_kit
docker build -t loomq-final .
```

### 运行环境变量

以下三个变量必须在运行环境中设置，也可使用 Docker 的 `--env-file` 提供：

- `LOOMQ_LLM_BASE_URL`
- `LOOMQ_LLM_API_KEY`
- `LOOMQ_LLM_MODEL`

可选设置 `LOOMQ_LLM_TIMEOUT_SECONDS=120`。SpinQ 真机体验所需的 `SPINQ_USERNAME` 和 `SPINQ_KEY_PATH` 不影响基础 Web 启动。

### 启动 Web

```bash
docker run --rm -p 8000:8765 \
  -e LOOMQ_LLM_BASE_URL \
  -e LOOMQ_LLM_API_KEY \
  -e LOOMQ_LLM_MODEL \
  -e LOOMQ_LLM_TIMEOUT_SECONDS=120 \
  loomq-final \
  python -m loomq.debug_web --host 0.0.0.0 --port 8765 --serve-web
```

需要体验 SpinQ 真机时，使用上方“L2 交互体验”中的可选真机启动命令。

### 自动化自检

```bash
mkdir -p runtime/reports

docker run --rm \
  -e LOOMQ_LLM_BASE_URL \
  -e LOOMQ_LLM_API_KEY \
  -e LOOMQ_LLM_MODEL \
  -e LOOMQ_LLM_TIMEOUT_SECONDS=120 \
  -v "$PWD/runtime/reports:/reports" \
  loomq-final \
  python evaluator.py --level all --target spinq,originq,braket --json-out /reports/all.json
```

架构说明：[architecture.md](files/docs/architecture.md)

### 目标用户和使用场景

面向具备编程基础、希望快速了解和体验量子计算的开发者。
用户无需从底层量子编程语法开始学习，通过自然语言交互、可视化代码解释、程序验证与真实量子设备体验，完成从量子程序理解、生成到执行的完整流程。

### 完整使用流程

1. 在 Learn 页面阅读量子电路、QASM 与状态变化说明。[Learn 页](files/l2-agent/learn.gif)
2. 在 Explorer 使用自然语言生成量子程序，并查看生成与验证过程。[Explorer 页](files/l2-agent/explorer-generation.gif)
3. 在程序修复页诊断并修复已有 OpenQASM。[验证或修复结果页](files/l2-agent/repair-verification.gif)
4. 根据条件查看后端推荐与约束匹配结果。[执行平台选择页](files/l2-agent/choose-backend.gif)

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

- 指令编码规格：[quantum-riscv.md](files/docs/quantum-riscv.md)
- 模拟器扩展实现：[bonus/quantum_riscv/emulator.py](../bonus/quantum_riscv/emulator.py)
- 端到端测试命令：

  ```bash
  docker run --rm loomq-final \
    python -m unittest tests.test_quantum_riscv_bonus -v
  ```

- 测试入口：[tests/test_quantum_riscv_bonus.py](../tests/test_quantum_riscv_bonus.py)

## 新手引导与视觉叙事 Bonus

- 零基础首次运行指南：[Learn 三步导览](files/l2-agent/learn.gif)；对应实现：[web/src/Learn.tsx](../web/src/Learn.tsx)
- 量子概念解释：[Learn 教学](files/l2-agent/learn.gif)；实验阶段中的叠加、纠缠、测量、相位与干涉解释见：[web/src/ExperimentStory.tsx](../web/src/ExperimentStory.tsx)
- 结果可视化：[Explorer 生成与电路过程](files/l2-agent/explorer-generation.gif)；实验状态、概率与相对相位可视化见：[web/src/ExperimentStory.tsx](../web/src/ExperimentStory.tsx)
- 错误恢复或无障碍引导：[真实量子设备不可用时的重试与模拟实验引导](files/l2-agent/real-hardware-not-configured.png)；对应 Learn 弹窗实现：[web/src/Learn.tsx](../web/src/Learn.tsx)

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
