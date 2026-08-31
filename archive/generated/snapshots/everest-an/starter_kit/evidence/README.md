# LoomQ 人工评分证据

## 队伍信息

- 团队名称：everest-an
- 提交账号（Team ID）：everest-an

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

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：spinq（量旋 SpinQ 云真机 gemini_vp，2 比特）
平台 job ID：
  evidence/files/spinq-bell-result.json  -> G-260807-0002
运行时间：2026-08-06T16:59:51Z（UTC，赛程窗口内）
shots：8192
实际执行的 QASM：starter_kit/circuits/bell.qasm（经中间层剥离显式测量后提交，云平台自动末尾测量）
平台返回的原始结果：evidence/files/spinq-bell-result.json（含 counts + probabilities）
任务页截图：待补（平台任务页含任务号 G-260807-0002，可溯源）
```

```text
平台名称：spinq（量旋 SpinQ 云真机 triangulum_vp，3 比特）
平台 job ID：
  evidence/files/spinq-ghz3-result.json  -> S-260807-0001
运行时间：2026-08-06T17:02:28Z（UTC，赛程窗口内）
shots：8192
实际执行的 QASM：starter_kit/circuits/ghz3.qasm（经中间层剥离显式测量后提交，云平台自动末尾测量）
平台返回的原始结果：evidence/files/spinq-ghz3-result.json（含 counts + probabilities）
任务页截图：待补（平台任务页含任务号 S-260807-0001，可溯源）
```

> spinq 平台两个任务的主峰均命中理想分布（Bell: 00/11 合计 86.4%；
> GHZ3: 000/111 为前两大态，真机噪声允许）。任务号 G-260807-0002 /
> S-260807-0001 可在量旋云控制台任务页溯源复核。

```text
平台名称：braket（AWS Braket LocalSimulator）
平台 job ID：
  evidence/files/braket-bell-result.json  -> b18ebd6d-cf17-4248-9d0d-ac860a909a5f
  evidence/files/braket-ghz3-result.json  -> ad4d12cc-880b-4e09-a8a8-f211baf31825
运行时间：2026-08-06T16:34:53Z（UTC，赛程窗口内）
shots：8192
实际执行的 QASM：starter_kit/circuits/bell.qasm / ghz3.qasm（经 adapter.transpile(..., "braket") 转译为 OpenQASM 3）
平台返回的原始结果：evidence/files/braket-bell-result.json、evidence/files/braket-ghz3-result.json
任务页截图：无（本地模拟器，无网页控制台；按赛题第七节允许以 LocalSimulator 替代付费云端真机申报）
```

> 申报依据：赛题第七节「AWS Braket：LocalSimulator 本地模拟器免费、无需 AWS 账号——
> 允许以本地模拟器替代付费云端真机」；backend_capabilities.json 亦注明
> 「允许以 LocalSimulator 替代，无需使用付费云端」。故 braket 平台以
> LocalSimulator 的 job_id 作为可溯源任务标识申报，不占用付费 AWS 账号。

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
启动界面或 CLI 的命令：[见下方「启动方法」]
测试入口或页面地址：[无，CLI 交互终端]
适合现场体验的 3 个用户任务：
1. [任务 A] 输入「生成一个 3 比特 GHZ 纠缠态」——观察 CLI 自动生电路、本地验证并画出 000/111 各约 50% 的分布图
2. [任务 B] 输入「我想制备贝尔态，但这段代码报错了帮我修好：H q[0]; CX q[0] q[1]」——观察纠错闭环返回可运行电路并显示贝尔态分布
3. [任务 C] 输入「我需要运行一个 15 比特电路，且零排队等待，选哪个平台？」——观察 Agent 依据后端能力表给出规范后端 id
截图或演示视频：[选填]
```

**启动方法**（在 fork 根目录，需配置 LOOMQ_LLM_* 环境变量）：

```bash
export LOOMQ_LLM_BASE_URL=<OpenAI-compatible 地址>
export LOOMQ_LLM_API_KEY=<你的 Key>
export LOOMQ_LLM_MODEL=<模型名>
python3 starter_kit/cli.py
# 可选：python3 starter_kit/cli.py --backend braket --shots 8192
# 单轮模式：python3 starter_kit/cli.py --prompt "生成一个 2 比特贝尔态"
```

CLI 内置新手引导（欢迎页 + help 命令）、电路可视化（ASCII 分布条）和
「生成 → 本地验证 → 重试」闭环；每轮回答都会在本地通过 L1 中间层实际
模拟验证并给出结果解读。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
  python3 starter_kit/evaluator.py --level declared --target spinq,originq,braket   # 契约自测（零第三方依赖）
  python3 starter_kit/selftest_fhb.py    # FHB 闭式解自测（易经卦象 ↔ 超立方体量子游走）
  python3 starter_kit/selftest_l3.py     # Hybrid-QASM 混合编译穷举自测
  python3 starter_kit/selftest_roundtrip.py  # 隐藏电路风格 round-trip 语义自洽
  python3 starter_kit/cli.py             # L2 交互入口
架构说明：见 starter_kit/PROJECT.md（parser → 统一 IR → 模拟器/三后端 codegen 三段式，零第三方依赖）
目标用户和使用场景：没有量子背景的跨界创作者/学生/产品经理——用自然语言驱动量子模拟器与云端真机
完整使用流程：见 starter_kit/PROJECT.md「快速上手」与 CLI 欢迎页
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/riscv_quantum_isa.md（opcode 0xF + qop 字段 + Q14 定点参数，含二进制编码示例）
模拟器扩展实现：starter_kit/riscv_emulator_quantum.py（fork 官方模拟器，新增 qinit/qh/qx/qrz/qry/qcx/qswap/qm 指令，测量写回 x10+k 并坍缩）
端到端测试命令：python3 starter_kit/selftest_quantum_isa.py（编码往返/贝尔态测量反馈/旋转精度/经典回归，5/5 通过）
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/cli.py 欢迎页 + help 命令（启动方法见本文档「L2 交互体验」）
量子概念解释：CLI 内置 tutorial 命令（量子计算 101：比特/叠加/纠缠/门/分布图解读，输入 tutorial 即可查看）
结果可视化：CLI 的 ASCII 概率分布条 + 结果解读（「几乎确定输出 X」/「纠缠叠加态特征」），见 verify_and_explain()
错误恢复或无障碍引导：模型调用失败时给出 LOOMQ_LLM_* 排查建议；电路解析失败时提示换种说法重试或让模型修复
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
