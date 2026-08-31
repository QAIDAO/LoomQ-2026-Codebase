# LoomQ 量子接入平权计划 · LoomQ-Agent

> LoomQ 2026 黑客松参赛作品 —— 把统一格式的量子电路翻译成三家量子云平台的方言（量旋 SpinQ / AWS Braket / 本源 OriginQ），并用自然语言 AI 助手让**零量子背景的人第一次跑通量子电路**。
>
> Team ID：`LinXuan2576` ｜ 提交内容：`starter_kit/`

---

## 这个工具让谁第一次用上了量子计算？

**答：完全不懂量子计算的普通开发者。**

使用方式：打开终端，说一句人话——"生成一个贝尔态电路并运行"。剩下的全部由工具完成：

```
你：生成一个2比特贝尔态电路
Agent：自动写出 OpenQASM → 模拟器自验（Fidelity ≥ 0.97）→ 自动选后端 → 运行
输出：  "00" ████████████████████  49.8%
        "11" ████████████████████  50.2%
```

不需要懂门电路、不需要懂量子云 SDK、不需要注册任何云平台账号。
新手教程见 [`docs/FIRST_RUN.md`](starter_kit/docs/FIRST_RUN.md) 与 [`starter_kit/QUANTUM_101.md`](starter_kit/QUANTUM_101.md)。

## 快速开始（一键 setup + run）

```bash
# 1. 安装依赖（Python 3.10）
cd starter_kit
pip install -r requirements.txt

# 2. 启动交互助手（自然语言量子电路编程）
python cli.py

# 3. 或者离线直接跑本地电路文件
python cli.py --run circuits/bell.qasm braket 8192
```

启动后输入自然语言即可对话，输入 `/help` 查看全部命令，`/exit` 退出。

## 功能全景

| 模块 | 文件 | 说明 | 状态 |
|---|---|---|---|
| L1 统一转译 + 执行 | `adapter.py` | OpenQASM 2.0 → 三平台方言 + 统一结果 Schema，12 门白名单 | ✅ |
| 量旋后端 | `adapter.py`（spinq） | spinqit 真路径 + 无依赖模拟器双模自动降级 | ✅ |
| Braket 后端 | `adapter.py`（braket） | QASM2→QASM3 改写 + LocalSimulator | ✅ |
| 本源后端 | `originq_backend.py` | QASM → OriginIR + pyqpanda CPUQVM | ✅ |
| L2 自然语言 Agent | `l2_agent.py` | LLM 生成 + 模拟器自验闭环 + 规则选后端 | ✅ |
| L3 混合编译器 | `hybrid_compiler.py` | Hybrid-QASM 三段式编译（词法/语法/代码生成）→ RISC-V | ✅ |
| **L2 交互入口** | **`cli.py`** | 自然语言对话 / 粘贴 QASM / 离线命令，ASCII 可视化 | ✅ 本作品新增 |
| **RISC-V 量子扩展** | `riscv_emulator_qext.py` | Q-Ext 指令集：H/X/CNOT/RZ/测量，6 项端到端测试 | ✅ 本作品新增 |

## 架构

```
┌────────────── 统一输入：OpenQASM 2.0 / Hybrid-QASM / 自然语言 ──────────────┐
│                                                                             │
│   cli.py（交互入口）                                                         │
│   ├── 自然语言 → l2_agent.py（LLM 生成 → 模拟器自验 → 纠错重试闭环）           │
│   └── QASM/文件  →  adapter.py（统一转译 + 执行，统一结果 Schema）             │
│                      ├── spinq   后端（spinqit / 内置模拟器）                 │
│                      ├── braket  后端（QASM3 + LocalSimulator）               │
│                      └── originq 后端（OriginIR + pyqpanda）                 │
│   hybrid_compiler.py（L3：词法 → 语法 → RISC-V 代码生成）                     │
│   riscv_emulator_qext.py（Q-Ext 量子扩展指令模拟器，Bonus）                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**统一结果 Schema**（三个后端输出完全一致）：`{backend, job_id, shots, counts(小端序), bit_order, timestamp, meta}`。

**关键设计**：
- 位序统一：三后端 counts 一律转成 little-endian（c[0] 最右），避免随机电路评测挂
- 依赖解耦：spinq 后端不依赖 antlr（与 braket 的 antlr 版本死锁问题绕开），缺失依赖时自动降级内置模拟器
- L2 自验闭环：模型生成 → 自家模拟器跑 8192 shots 验证期望态分布 → 不达标自动回喂修正

## 使用示例

```bash
# 交互对话（推荐体验）
python cli.py
LoomQ-Agent > 生成一个3比特GHZ纠缠态并运行

# 单轮演示（脚本/评分友好）
python cli.py --once "生成一个2比特贝尔态电路"

# 离线跑本地文件（不依赖网络/模型）
python cli.py --run circuits/bell.qasm spinq 8192
```

## 人工评分证据

按组委会模板逐项申报于 [`starter_kit/evidence/README.md`](starter_kit/evidence/README.md)：

- **L2 交互体验**：`cli.py` 入口 + 3 个用户任务
- **工程与产品化**：本 README + 架构说明 + 必答题
- **自定义量子 RISC-V Bonus**：规格 [`docs/riscv-quantum-ext.md`](starter_kit/docs/riscv-quantum-ext.md) + 实现 `riscv_emulator_qext.py` + 端到端测试
- **新手引导 Bonus**：`docs/FIRST_RUN.md`（首次运行）+ `QUANTUM_101.md`（概念）+ CLI 结果可视化

## 文档索引

| 文档 | 内容 |
|---|---|
| [`starter_kit/QUANTUM_101.md`](starter_kit/QUANTUM_101.md) | 量子概念零基础解释（门/叠加/纠缠/测量） |
| [`starter_kit/backend_capabilities.md`](starter_kit/backend_capabilities.md) | 三平台后端能力表 |
| [`starter_kit/gate_identities.md`](starter_kit/gate_identities.md) | 12 门白名单与平台门名映射 |
| [`starter_kit/target_ir_contract.md`](starter_kit/target_ir_contract.md) | 目标 IR 契约 |
| [`starter_kit/docs/FIRST_RUN.md`](starter_kit/docs/FIRST_RUN.md) | 零基础首次运行指南 |
| [`starter_kit/docs/riscv-quantum-ext.md`](starter_kit/docs/riscv-quantum-ext.md) | Q-Ext 量子扩展指令规格（Bonus） |
| [`starter_kit/CHANGELOG.md`](starter_kit/CHANGELOG.md) | 开发日志 |

> 说明：`starter_kit/README.md` 为组委会官方工具包说明，原样保留。
