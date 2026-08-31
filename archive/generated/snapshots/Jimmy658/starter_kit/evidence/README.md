# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [ ] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：[填写]
平台 job ID：[填写]
运行时间：[填写，带时区]
shots：[填写]
实际执行的 QASM：[填写仓库内路径]
平台返回的原始结果：[填写仓库内路径]
任务页截图：[选填，填写仓库内路径]
```

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：
cd starter_kit
python beginner_cli.py

测试入口或页面地址：无，本项目提供命令行交互界面。

适合现场体验的 3 个用户任务：
1. Generate a five-qubit GHZ state and measure all qubits.
2. Paste malformed Bell-state OpenQASM and ask the agent to repair it.
3. I need at least 15 qubits, zero queue, and a free backend.

截图或演示视频：无额外附件；可直接运行 CLI 复现。
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
1. cd starter_kit
2. python evaluator.py --level l1 --target spinq,originq,braket
3. python examples/l1_local_checks.py
4. python examples/l2_local_checks.py
5. python examples/beginner_cli_checks.py
6. python evaluator.py --level l3
7. python examples/l3_local_checks.py

架构说明：
详见仓库根目录 README.md 与 ARCHITECTURE.md。

主要模块：
1. L1 adapter：解析 OpenQASM 2.0 子集，构建 GateOp / MeasureOp / CircuitIR，输出 spinq、originq、braket 目标格式，并提供本地状态向量模拟。
2. L2 agent：通过 adapter.agent_chat(prompt) 暴露自然语言入口；LLM 用于意图理解/生成/修复，显式 qubit 数、backend 约束、Bell/GHZ 语义检查由确定性代码完成。
3. L3 compiler：通过 adapter.compile_hybrid(hybrid_qasm_str) 暴露 Hybrid-QASM 编译入口；独立实现 classical block splitter、tokenizer、parser/AST 与 tiny RISC-V compiler。
4. Beginner CLI：starter_kit/beginner_cli.py 是新手交互包装层，只调用 adapter.agent_chat()，不重新实现 L2 私有逻辑。

目标用户和使用场景：
面向有编程或线性代数基础、但不熟悉 OpenQASM、量子 SDK 和 backend ID 的学习者。用户可以从自然语言任务开始，例如“五比特 GHZ 态”、修复 QASM、选择免费零排队后端，再由系统生成、验证并格式化结果。

完整使用流程：
1. L1：将 OpenQASM 2.0 电路传入 adapter.transpile(qasm, target) 或 adapter.run(qasm, target, shots)。
2. L2：运行 python beginner_cli.py，选择生成电路、修复 QASM、选择后端或 Quick Example。
3. L3：将包含一个 classical { ... } block 的 Hybrid-QASM 传入 adapter.compile_hybrid()，得到 quantum_ops 与 RISC-V assembly。
4. 使用上方本地命令复现公开 evaluator、mock L2、beginner CLI 和 L3 randomized differential checks。

当前已验证结果：
- L1 official evaluator：6 passed / 0 failed
- L1 local checks：PASS
- L2 local/mock checks：PASS
- Beginner CLI checks：19 PASS
- L3 public evaluator：1 passed / 0 failed
- L3 randomized differential：1206 programs / 30357 measurement combinations，PASS
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：[填写文档路径]
模拟器扩展实现：[填写代码路径]
端到端测试命令：[填写命令或文档路径]
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：[填写]
量子概念解释：[填写]
结果可视化：[填写]
错误恢复或无障碍引导：[填写]
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
