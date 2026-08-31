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

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

### 平台 1：量旋 SpinQ Cloud · triangulum_vp（3 比特核磁真机）

```text
平台名称：SpinQ Cloud（量旋量子云）
平台 job ID：S-260824-0002（Bell 电路）、S-260824-0003（GHZ-3 电路）
运行时间：2026-08-24T03:43:00Z / 2026-08-24T03:45:54Z
shots：8192
实际执行的 QASM：starter_kit/circuits/bell.qasm、starter_kit/circuits/ghz3.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-triangulum_vp-S-260824-0002.json、starter_kit/evidence/files/spinq-triangulum_vp-S-260824-0003.json
任务页截图：无（可登录 SpinQ Cloud 控制台按 job_id 溯源）
```

说明：SpinQ Cloud 自动测量，显式 measure 已由 `real_backends.py` 剥离；job_id 可在
SpinQ Cloud 任务列表溯源。Bell 主峰为 `00`/`11`，GHZ-3 主峰为 `000`/`111`，与理想
分布一致（真机带噪声）。另存有从结果 JSON `circuit_qasm` 字段逐字提取的副本
（evidence/files/spinq-triangulum_vp-S-260824-0002.qasm / -0003.qasm），供字节级比对。

### 平台 2：本源悟空真机（origin_72）

```text
平台名称：本源量子云（悟空超导真机）
平台 job ID：（本次提交未采集到真机证据——采集时段本源全部真机处于维护中）
运行时间：（未采集）
shots：8192（配置值）
实际执行的 QASM：starter_kit/circuits/bell.qasm
平台返回的原始结果：（未采集，见下方说明）
任务页截图：无
```

说明：本次提交未申报本源真机证据。采集时段本源悟空真机（origin_72）及五元
3/4/5 全部返回"Quantum computer under maintenance"，属平台侧维护（赛题声明
排队/维护等外部因素不挡评奖）。`real_backends.py` 的 OriginQ 集成已就绪并验证
可连通云端（能拿到"维护中"响应而非认证错误），且已支持通过 `--chip` 参数或
`LOOMQ_ORIGINQ_CHIP` 环境变量选用其他在线物理后端（如悟空 180 WK_C180_2）。
真机恢复后一条命令即可补齐证据：`python3 real_backends.py --backend originq --mode real_chip`。

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
启动界面或 CLI 的命令：python3 starter_kit/cli_agent.py --interactive
测试入口或页面地址：starter_kit/cli_agent.py（CLI 交互入口）
用于交互体验评测的 3 个用户任务：
1. 任务 1（意图生成）：输入"生成 3 比特 GHZ 态并测量"，观察自动生成 QASM、自验并运行，最终返回"00/11 各占一半 = 纠缠态"的可读解释。
2. 任务 2（代码纠错）：输入"我想制备贝尔态，但这段代码报错了：H q[0]; CX q[0] q[1]（未定义寄存器且门名大小写错误）"，观察 Agent 修复为合法电路并验证实现贝尔态。
3. 任务 3（智能选后端）：输入"我需要运行一个 15 比特电路，且零排队等待，选哪个平台？"，观察回复包含规范后端标识（如 braket_local_simulator）。
截图或演示视频：无
```

CLI 全程中文交互；电路信息、统一结果 Schema、counts 的"人话"翻译均自动呈现。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
  # 自动化自测（零依赖，一条命令）
  python3 starter_kit/evaluator.py --json-out report.json
  # 交互入口
  python3 starter_kit/cli_agent.py --interactive
架构说明：starter_kit/ARCHITECTURE.md（单一门模型 + 单一模拟器 + 三渲染器；L2 自验闭环；L3 编译器）
目标用户和使用场景：零物理背景的跨界创作者 / 产品 / 研究员 / 初学者 —— 用自然语言指挥真实量子计算机
完整使用流程：见 ARCHITECTURE.md「六、目标用户与使用流程」与 cli_agent.py 的 --interactive 模式
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/quantum_riscv/QUANTUM_RISCV_SPEC.md
模拟器扩展实现：starter_kit/quantum_riscv/quantum_riscv_emulator.py
端到端测试命令：
  python3 starter_kit/quantum_riscv/test_quantum_riscv.py
  python3 starter_kit/quantum_riscv/test_instruction_chain.py
```

采用**指令字驱动**的执行链路（主办方 Bonus 方向 1）：在 CUSTOM-0 编码空间
（opcode 0x0B）定义量子指令（无参数门 `qh/qx/qs/qsdg/qt/qtdg/qcx/qswap/qccx`、
参数门 `qry/qrz/qcu1`（1/16 π 定标立即数）、`qmeas`、`qinit`），模拟器通过
`assemble()` 把文本汇编为 32 位指令字，`execute()` 逐字 `decode_word()`（解析
opcode/funct3/funct7 字段）后分派执行，opcode 真正参与运行，而非仅存于文档。

模拟器为官方 `riscv_emulator.py` 的向后兼容 fork：200 组随机标准指令程序与官方
结果完全一致；量子门分布与 L1 无噪声模拟器逐一交叉验证；Bell/GHZ 频率统计、量子
测量驱动经典控制流的混合程序、机器码直接加载（`load_machine_code`）均通过端到端
测试。

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/BEGINNER_GUIDE.md（4 步：概念→一条命令→中文指挥→三个实验）
量子概念解释：starter_kit/QUANTUM_101.md（30 分钟入门）+ BEGINNER_GUIDE.md 第 1 节（3 句话版）
结果可视化：cli_agent.py 的 ASCII 条形图（|000> ███ 50.1%）+ 人话翻译（纠缠态/均匀叠加/主峰判定）
错误恢复或无障碍引导：BEGINNER_GUIDE.md 第 5 节（听不懂/非电路返回/真机失败的处理）+ cli_agent 自验重试与中文容错提示
```

以上四项各 1 分。CLI 全程中文、零 QASM 背景即可完成"自然语言 → 电路 → 运行 → 可视化理解"；
智能体对生成/修复/选型三类任务都有容错与自验（生成 QASM → L1 模拟器自验 → 不对重试）。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
