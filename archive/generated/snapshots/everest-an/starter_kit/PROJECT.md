# LoomQ 项目说明（选手版）

> 队伍：everest-an · SheNicest 2026 LoomQ 量子接入平权计划

## 一分钟看懂我们做了什么

**问题**：量子云平台各说各话——量旋讲 OriginIR、本源讲 QPanda、AWS 讲 OpenQASM 3。
一个不懂"黑话"的人，连第一步都迈不出去。

**答案**：我们做了一个**零第三方依赖**的量子通用中间层（LoomQ Transpiler）
加上一个**会说人话的智能体**（LoomQ Agent）：

```
你的自然语言 ──► Agent（LLM）──► OpenQASM 2.0 ──► 统一中间层 ──► spinq / originq / braket
                                                        │
                                                        └──► 本地模拟验证 → 分布可视化 → 结果解读
```

## 为什么零依赖是设计核心

正式评测在固定 Linux 容器内构建，默认禁止网络，第三方依赖必须精确锁定版本。
因此整个 L1 执行栈（解析、模拟、转译）全部用 Python 标准库自研：

| 模块 | 职责 |
|---|---|
| `circuit_ir.py` | 统一电路 IR（GateOp + Circuit），后端无关 |
| `qasm_parser.py` | OpenQASM 2.0 → IR；AST 白名单安全求值（不用 `eval`） |
| `simulator.py` | 状态向量模拟器；概率聚合 + 二分采样，8192 shots 秒级 |
| `codegen.py` | IR → 三后端原生代码（QASM 2.0 / QASM 3 / OriginIR） |
| `adapter.py` | 评测契约入口（transpile / run / agent_chat / compile_hybrid） |
| `agent.py` | L2 智能体：生成 → L1 自验 → 重试闭环，三类任务 |
| `hybrid_parser.py` + `riscv_codegen.py` | L3：Hybrid-QASM 经典块 → RISC-V 汇编 |
| `cli.py` | L2 交互入口：对话 → 验证 → ASCII 分布可视化 |
| `fhb_ref.py` | Fuxi Hypercube 闭式参考（自测与 Agent 自验共用） |

三段式架构（parser → IR → codegen）意味着接入新平台 = 新增一个 codegen 函数，
而不是三套硬编码分支——这正是"通用"二字的兑现方式。

## 验证体系（测试的是用户路径，不只是代码路径）

| 自测 | 验证什么 | 命令 |
|---|---|---|
| 官方 evaluator | 评测契约 L1/L2/L3 | `python3 starter_kit/evaluator.py --level declared --target spinq,originq,braket` |
| `selftest_fhb.py` | FHB 闭式解：转译器语义保持（t=π/4 均匀、t=π 回返） | `python3 starter_kit/selftest_fhb.py` |
| `selftest_l3.py` | 混合编译：穷举测量注入 vs 参考解释器 | `python3 starter_kit/selftest_l3.py` |
| `selftest_l3_fuzz.py` | L3 模糊测试：150 组随机 Hybrid-QASM（嵌套/负数/多测量位/表达式链）穷举验证 | `python3 starter_kit/selftest_l3_fuzz.py` |
| `selftest_roundtrip.py` | 隐藏电路风格（QFT-4/Grover-3/随机 5-12 比特）转译位级一致 | `python3 starter_kit/selftest_roundtrip.py` |
| `selftest_l2_variants.py` | L2 变体鲁棒性：10 组改写措辞的分类路由 + 端到端（需 LLM 环境变量） | `python3 starter_kit/selftest_l2_variants.py` |
| `selftest_quantum_isa.py` | 量子 RISC-V 扩展端到端 | `python3 starter_kit/selftest_quantum_isa.py` |
| `examples/verify_originir.py` | **本源官方 SDK 交叉验证**：pyqpanda 解析并运行我们的 OriginIR | 在 python:3.10 + pyqpanda 容器中运行 |
| `examples/verify_spinq_sim.py` | **量旋官方 SDK 交叉验证**：spinqit 编译运行我们的 spinq QASM 2.0（fidelity 1.000） | 在 python:3.10 + spinqit 容器中运行 |
| `examples/verify_braket.py` | **AWS 官方 SDK 交叉验证**：Braket LocalSimulator 解析运行我们的 braket QASM 3（fidelity 0.996/0.999） | 在 python:3.10 + amazon-braket-sdk 容器中运行（依赖同目录 vendored `stdgates.inc`，Apache-2.0，vendored 自 OpenQASM 项目 commit 4ca1d793） |

## 快速上手

```bash
# 1. 契约自测（无需任何模型配置）
python3 starter_kit/evaluator.py --level declared --target spinq,originq,braket

# 2. 配置模型（OpenAI-compatible，正式评测由组委会注入）
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<your-key>
export LOOMQ_LLM_MODEL=deepseek-v4-flash

# 3. 用自然语言指挥量子计算机
python3 starter_kit/cli.py
```

## 平权叙事：为什么这件事值得做

> **你的工具，让哪一类原本进不来的人，第一次能够使用并受惠于量子计算？**

我们让**不懂量子黑话的人**第一次用上了量子计算——而且是带着文化亲近感进入的。

这个项目里藏着一个跨学科彩蛋：我们团队把易经六十四卦与 n 维超立方体图
的数学同构（[The Fuxi Hypercube Benchmark](https://github.com/AwareLiquid/The-Fuxi-Hypercube-Math)）
做成了转译器的验证基石。伏羲先天卦在单爻变化下恰好构成超立方体 Q₆，
其上的量子游走在 t=π/4 处**精确均匀混合**、在 t=π 处**精确回返**——
分布全部有闭式解，无需经典模拟即可验证转译器是否正确。

这意味着两件事：
1. **工程上**：我们获得了一个秒级、零依赖、闭式参考的转译正确性回归网；
2. **叙事上**：三千年前的东方符号系统与现代量子计算在数学上同构——
   "原来量子计算不是只有西装革履的实验室，它和我们的文化根系是相通的"。

（需要强调：我们不做任何"古人预见量子力学"的夸张声明——同构是形式数学事实，
FHB 论文对此有明确边界说明。）

## 技术亮点（评委走查时可以展开）

- **安全参数求值**：QASM 表达式用 AST 白名单求值器，仅允许常量、pi、四则运算，杜绝 `eval` 注入
- **概率聚合采样**：测量先按经典寄存器 key 聚合概率一次（O(2ⁿ)），再用二分采样，
  8192 shots 不随比特数线性恶化
- **LLM 输出结构化自验**：Agent 的每个回答都经过本地解析 + 模拟 + 语义评审三层检查，
  失败时把具体错误喂回模型重试（QAgent/QUASAR 论文验证过的闭环模式）
- **多任务路由（MTL 风格）**：LLM few-shot 三分类（GENERATE/FIX/SELECT）替代关键字匹配，
  对改写措辞的评测变体鲁棒（10/10 变体测试）；语义评审返回具体原因喂回重试
- **L3 负数支持**：parser 支持负数字面量（`r1 = -50`），随机模糊测试 150 组穷举全过
- **L3 穷举正确性**：经典块编译为 RISC-V 后用官方模拟器穷举注入所有测量组合，
  与 Python 参考解释器逐寄存器比对（固定 10 组 + 模糊 150 组全过）
- **round-trip 位级断言**：隐藏电路风格程序（含 12 比特大电路）经 transpile →
  重新解析 → 模拟，与原始分布逐位相同——转译器语义保持的最强断言

## 参赛 Level 声明

- **L1 通用中间层**：✅ 三后端全部打通（spinq/originq/braket），12 门白名单全覆盖；
  本源官方 SDK（pyqpanda 3.8.5）独立交叉验证通过（bell fidelity 0.996 / ghz3 0.993）
- **L2 智能体**：✅ agent_chat 三类任务 + 交互 CLI（客观分与交互分全申报）
- **L3 混合编译**：✅ Hybrid-QASM → RISC-V，穷举验证通过
- **L1 真机**：两个平台均已申报（+10）——
  - spinq：gemini_vp 真机（job G-260807-0002，Bell 主峰 00/11 合计 86.4%）+
    triangulum_vp 真机（job S-260807-0001，GHZ3 主峰 000/111），
    证据见 `evidence/files/spinq-*-result.json`；
  - braket：LocalSimulator 按赛题第七节替代条款（job b18ebd6d…/ad4d12cc…），
    证据见 `evidence/files/braket-*-result.json`。
