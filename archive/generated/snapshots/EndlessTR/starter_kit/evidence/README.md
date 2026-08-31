# LoomQ 人工评分证据

这份文件是最终提交的人工评分证据索引。自动评分直接运行 `starter_kit/` 中的程序；人工评分与 Bonus 按本文件给出的命令、路径和复现步骤核验。原始结果及附加材料统一保存在 `starter_kit/evidence/files/`，已有项目文档直接引用，不为评分重复复制。

## 申报状态

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## 要求对照与核实结果

| 评分项 | 截图所列必需说明 | 当前提交中的可核验证据 | 状态 |
|---|---|---|---|
| L1 真机 | 平台、job ID、运行时间、shots、实际 QASM、原始结果路径 | 下方两组完整记录，以及 `files/spinq/`、`files/originq/` 中的 QASM、JSON 和任务页截图 | 齐全 |
| L2 交互体验 | 启动方法、3 个用户体验任务 | 下方启动命令和三项输入；详细步骤见 `files/l2-interaction/l2-interaction.md` | 齐全 |
| 工程与产品化 | 构建和启动、主要模块、目标用户、完整流程 | 下方 Docker 命令；完整说明见 `files/engineering-productization/engineering-productization.md` | 齐全 |
| 自定义量子 RISC-V | 编码规格、模拟器实现位置、端到端测试命令 | `starter_kit/quantum_riscv_extension.md`、`starter_kit/adapter.py`、`starter_kit/riscv_emulator.py`、`starter_kit/test_l3_bonus.py` | 齐全 |
| 新手引导与视觉叙事 | 首次运行、概念解释、结果可视化、错误恢复或无障碍引导的位置 | 下方四项精确路径；人工复现见 `files/beginner-visual-guide/QuantumHelper_新手引导与视觉体验设计说明.md` | 齐全 |

截图、架构图和演示视频属于可附材料，不替代可运行代码或可追溯原始结果。当前 L1 已附任务页截图；其余项目以最终代码、精确路径和可重复执行步骤为主要证据，不把页面源码表述为截图。

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：量旋云
平台 job ID：G-260818-0010
运行时间：2026-08-18 20:04:16 ~ 2026-08-18 20:05:53 (UTC+8)
shots：1024
实际执行的 QASM：starter_kit/evidence/files/spinq/spinq-circuit.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq/spinq-result.json
任务页截图：starter_kit/evidence/files/spinq/spinq-result-photo.png
```

```text
平台名称：本源量子云
平台 job ID：6E22646EDE4F187EE8B6158EC2AB3115
运行时间：2026-08-19 18:10:56.940 ~ 2026-08-19 18:10:58.985 (UTC+8)
shots：1024
实际执行的 QASM：starter_kit/evidence/files/originq/originq-circuit.qasm
平台返回的原始结果：starter_kit/evidence/files/originq/originq-result.json
任务页截图：starter_kit/evidence/files/originq/originq-result-photo.png
```

本项目的真机证据按平台归档，路径模式如下：

```text
starter_kit/evidence/files/<platform>/<platform>-circuit.qasm
starter_kit/evidence/files/<platform>/<platform>-result.json
starter_kit/evidence/files/<platform>/<platform>-result-photo.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

### 启动方法与入口

```text
启动界面或 CLI 的命令：在仓库根目录运行 `python starter_kit/quantumhelper_web/server.py`；评测归档内运行 `python quantumhelper_web/server.py`。运行前由组委会注入 `LOOMQ_LLM_*`，并设置 `QUANTUMHELPER_ENABLE_LLM=1`。
测试入口或页面地址：`http://127.0.0.1:8000/`（`agent.html` 仅为兼容旧链接的薄入口）
```

### 三个用户体验任务

1. `生成一个 3 比特 GHZ 态并进行全测量`：Agent 生成 OpenQASM 2.0，经 L1 校验后进入运行流程。
2. `我想制备一个贝尔态，但这段代码报错了，请修复：H q[0]; CX q[0] q[1]`：Agent 保持 Bell 意图并补全、修复线路。
3. `我需要运行一个 15 比特电路，要求零排队并且免费，请选择后端`：Agent 返回官方能力表中的规范后端 ID，并明确未满足的约束。

关键流程的逐步复现、预期现象、错误恢复和自动化核验命令见 `starter_kit/evidence/files/l2-interaction/l2-interaction.md`。本项未以静态截图代替评测，工作人员可在统一模型环境中直接运行最终页面。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

### 干净环境构建与启动

在仓库根目录运行：

```powershell
docker build -f starter_kit/quantumhelper_web/Dockerfile -t loomq-submission starter_kit
docker run --rm -p 8000:8000 loomq-submission
```

启动后访问 `http://127.0.0.1:8000/`。无模型凭证时可独立核验确定性能力：

```powershell
docker run --rm loomq-submission python starter_kit/evaluator.py --level l1 --target spinq,originq,braket --shots 8192
docker run --rm loomq-submission python starter_kit/evaluator.py --level l3
```

完整 L2 由组委会通过 Secret 或环境变量注入 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL` 与 `QUANTUMHELPER_ENABLE_LLM=1`，不把凭证写入镜像或提交文件。

### 模块、用户与流程

- **主要模块：** `starter_kit/adapter.py` 负责 L1 多后端编译、L3 混合程序解析/代码生成及 Bonus 指令编码；`starter_kit/riscv_emulator.py` 负责经典 RISC-V 子集执行和自定义量子指令解码；`starter_kit/evaluator.py` 是统一评测入口；后端约束见 `starter_kit/backend_capabilities.md` 和 `starter_kit/target_ir_contract.md`。
- **目标用户：** 一类是需要把统一量子电路描述编译到 SpinQ、本源量子和 Amazon Braket 的开发者；另一类是没有量子物理或 QASM 背景、希望用自然语言首次生成、修复并运行量子线路的跨界用户。
- **完整流程：** 自然语言或 QASM 输入 → 任务理解 → 生成或修复候选线路 → adapter 确定性校验 → 线路图与解释 → 标准 OpenQASM 2.0 与所选目标 adapter 代码 → 后端匹配；线路包含测量时可本地执行并查看真实 counts，不含测量时仍可检查和阅读，但页面会明确说明没有可视化结果。
- **完整文档：** 项目入口见 `starter_kit/README.md`，Web 使用见 `starter_kit/quantumhelper_web/README.md`，量子基础见 `starter_kit/QUANTUM_101.md`，架构、产品、安全边界和验收见 `starter_kit/evidence/files/engineering-productization/engineering-productization.md`。

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

截图要求的三项均已落到最终提交：

```text
指令编码规格：`starter_kit/quantum_riscv_extension.md`
模拟器扩展实现：`starter_kit/riscv_emulator.py`（`qinst` 解码、合法性校验与量子操作记录）及 `starter_kit/adapter.py`（`QuantumInstructionEncoder` / `compile_hybrid_bonus`）
端到端测试：`starter_kit/test_l3_bonus.py`
完整实现链路、指令安全性质和测试覆盖说明：`starter_kit/evidence/files/quantum-riscv-bonus.md`
```

在仓库根目录运行：

```powershell
python -m unittest starter_kit.test_l3_bonus -v
python starter_kit/evaluator.py --level l3
```

### L3 与 Bonus 实现摘要

`compile_hybrid()` 使用通用编译流水线而非匹配公开样例：清理注释并分离量子语句和一个或多个 `classical { ... }` 块，经词法分析和递归下降解析得到赋值、表达式及嵌套 `if/else` AST，再把 `r1..r9` 映射为 `x1..x9`、测量位 `c[k]` 映射为 `x10+k`，最终生成官方模拟器支持的经典汇编。量子门和测量保持原始顺序。

`compile_hybrid_bonus()` 在同一解析结果上把量子操作编码为 custom-0（opcode `0x0B`）32 位指令，并以 `qinst 0xXXXXXXXX` 形式与经典汇编共同交给扩展模拟器。模拟器先完整解码和校验，只有合法指令才会原子地记录量子操作，不改变经典寄存器语义。

提交内测试覆盖 13 种门/测量编码往返、全部 8 种三测量位组合、50 组固定种子随机经典程序、非法与畸形指令的原子拒绝、最大量子位编号、状态重置和 1000 步边界；同时验证基础 `compile_hybrid()` 输出仍可由官方接口直接执行。

## 新手引导与视觉叙事 Bonus

| 检查项 | 最终代码中的位置 |
|---|---|
| 零基础首次运行 | `starter_kit/quantumhelper_web/README.md`、`starter_kit/quantumhelper_web/static/index.html`、`starter_kit/quantumhelper_web/static/example-task.html` |
| 量子概念解释 | `starter_kit/quantumhelper_web/static/example-task.html`、`starter_kit/quantumhelper_web/static/example-circuit.html`、`starter_kit/quantumhelper_web/static/scenario.html` |
| 结果可视化 | 主工作台 `starter_kit/quantumhelper_web/static/app.js` 的真实 counts 动态图表，以及 `starter_kit/quantumhelper_web/static/example-result.html`、`starter_kit/quantumhelper_web/static/circuit-result.html`、`starter_kit/quantumhelper_web/static/custom-result.html` |
| 错误恢复或无障碍引导 | `starter_kit/quantumhelper_web/static/task-adjust.html`、`starter_kit/quantumhelper_web/static/styles.css` 的键盘焦点与高对比度样式、`starter_kit/quantumhelper_web/static/workspace-state.js` 的 revision gate，以及 `starter_kit/quantumhelper_web/static/app.js` 的输入校验和错误提示 |

四项人工检查的体验目标、精确证据、复现步骤和自动化辅助验证见 `starter_kit/evidence/files/beginner-visual-guide/QuantumHelper_新手引导与视觉体验设计说明.md`。

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
