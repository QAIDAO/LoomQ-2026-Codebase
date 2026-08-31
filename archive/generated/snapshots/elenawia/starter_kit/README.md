# LoomQ Starter Kit v1.1.0 · LoomQ 提交说明

本 `starter_kit/` 是本队最终评测目录。它保留 Starter Kit 的提交协议结构，并在其中补充本队已经完成的 L1 / L2 / L3 / Bonus 实现、运行命令、交互入口和人工评分证据。

一句话介绍：**LoomQ 把普通人的一句好奇或一段出错的量子步骤，变成可运行、可检查、可解释、可跨平台展示的量子实验。**

## 提交结构

```text
starter_kit/
├── submission.yaml             # 申报 L1/L2/L3
├── adapter.py                  # L1/L2/L3 核心接口实现
├── llm_client.py               # L2 OpenAI-compatible 模型调用传输层
├── l2_policy.json              # L2 运行时协议
├── evaluator.py                # 公开自测器
├── prepare_submission.py       # 最终提交预检
├── riscv_emulator.py           # L3 Tiny RISC-V + Bonus 量子扩展模拟器
├── backend_capabilities.json   # L2 后端选择能力表
├── QUANTUM_101.md              # 量子概念新手说明
├── gate_identities.md
├── target_ir_contract.md
├── requirements.txt
├── Dockerfile
├── circuits/
│   ├── bell.qasm
│   └── ghz3.qasm
├── loomq/
│   ├── agent/                  # L2 Agent 逻辑
│   └── web/                    # “量子第一步 · LoomQ”网页入口
└── evidence/
    ├── README.md               # 人工评分证据说明
    ├── bonus_quantum_riscv.md  # Bonus 指令编码规格文档
    └── files/                  # 真机结果、截图、QASM 等附件
```

在正式 fork 中，本 `starter_kit/` 目录就是构建与评测根目录。核心接口均在 `adapter.py` 中实现，人工评分证据统一放在 `evidence/`。

## 环境

当前实现以 Python 标准库为主，无额外第三方运行依赖。推荐环境：

```text
Python 3.10+
```

公开 evaluator 可直接运行：

```bash
python evaluator.py --json-out report.json
```

如果使用 Docker，可在 `starter_kit/` 内运行：

```bash
docker build -t loomq-submission .
docker run --rm loomq-submission
```

容器默认执行：

```bash
python evaluator.py --json-out /tmp/loomq-public-report.json
```

## Adapter 契约

L1 已实现：

```python
def transpile(qasm_str: str, target: str) -> str: ...
def run(qasm_str: str, target: str, shots: int) -> dict: ...
```

L2 已实现：

```python
def agent_chat(prompt: str) -> str: ...
```

L3 已实现：

```python
def compile_hybrid(hybrid_qasm_str: str) -> tuple[list, str]: ...
```

`submission.yaml` 当前申报：

```yaml
levels:
  l1: true
  l2: true
  l3: true
```

## 评委最快路径

从仓库根目录进入提交目录：

```bash
cd starter_kit
```

运行公开自测：

```bash
python evaluator.py --json-out report.json
```

打开 L2 新手网页：

```bash
python -m loomq.web.server --port 8765
```

然后访问：

```text
http://127.0.0.1:8765
```

页面名称是 **量子第一步 · LoomQ**。它不是代码编辑器式页面，而是面向零量子背景用户的引导式实验入口：先选择“从一个问题开始”或“我已经有一个实验任务”，再看到实验问题、运行结果、人话解释、跨平台展示和 LoomQ 实际做了什么。

## 公开自测

从 `starter_kit/` 内运行：

```bash
python evaluator.py --json-out report.json
python evaluator.py --level l1 --target spinq,originq,braket
python evaluator.py --level l3
```

从仓库根目录运行本队补充测试：

```bash
python -m unittest tests.test_adapter_qasm tests.test_l2_agent tests.test_loomq_lab tests.test_l3_hybrid tests.test_bonus_quantum_riscv
```

这些测试覆盖：QASM 解析、12 门白名单、多后端转译、本地模拟、L2 Agent 三类任务、网页服务、L3 混合编译和 Bonus 量子 RISC-V 扩展指令。

## 完成情况总览

| 比赛要求 | 本项目对应实现 | 如何核对 |
|---|---|---|
| L1 语义等价 | `adapter.py` 实现 `transpile()` 和 `run()`，支持 SpinQ / OriginQ / Braket 三种目标格式 | `python evaluator.py --level l1 --target spinq,originq,braket` |
| L1 真机证据 | 本源量子云和量旋云各保存 Bell / GHZ3 运行证据 | `evidence/README.md` 与 `evidence/files/` |
| L2 客观接口 | `adapter.py` 实现 `agent_chat(prompt)`，覆盖意图生成、代码纠错、智能选后端 | `python -m unittest tests.test_l2_agent` |
| L2 交互体验 | `loomq.web.server` 提供“量子第一步 · LoomQ”网页入口 | `python -m loomq.web.server --port 8765` |
| L3 混合编译 | `adapter.py` 实现 `compile_hybrid()`，把 Hybrid-QASM 经典块编译为 Tiny RISC-V | `python evaluator.py --level l3` |
| Bonus 自定义量子 RISC-V | `riscv_emulator.py` 增加 `qinit/qh/qx/qcx/qmeasure`，并提供 custom-0 32-bit 编码/解码，可端到端运行 Bell 态 | `python -m unittest tests.test_bonus_quantum_riscv` |
| 工程可复现 | 标准库实现为主，提供公开评测、自测、网页入口和证据目录 | 本 README 与 `evidence/README.md` |

## L1：多平台转译与本地运行

核心能力：

- `transpile(qasm_str, target)`：把 OpenQASM 2.0 转成目标平台格式。
- `run(qasm_str, target, shots)`：用统一模拟器运行并返回 counts。

支持目标：

| Target | 输出格式 |
|---|---|
| `spinq` | OpenQASM 2.0 |
| `originq` | OriginIR |
| `braket` | OpenQASM 3.0 |

支持赛题白名单门：

```text
h, x, s, sdg, t, tdg, rz, ry, cx, cu1, swap, ccx
```

L1 真机材料统一放在：

```text
evidence/README.md
evidence/files/
```

当前保存的证据包括：

- 本源量子云：Bell 与 GHZ3 的原始 `result.json`、任务截图、概率截图、线路截图。
- 量旋云：Bell 与 GHZ3 的平台导出 `result.msgpack`、源 QASM、线路图、任务详情截图、概率截图。

说明：本源量子云可以直接导出 JSON；量旋云当前保留平台可导出的 MessagePack 结果文件、任务编号、截图和源 QASM 作为可追溯材料。具体 job ID、时间戳、shots 和主峰命中说明见 `evidence/README.md`。

## L2：统一模型与智能体接口

核心接口：

```python
agent_chat(prompt: str) -> str
```

L2 模型服务读取环境变量：

| 环境变量 | 含义 |
|---|---|
| `LOOMQ_LLM_BASE_URL` | OpenAI-compatible API 根地址 |
| `LOOMQ_LLM_API_KEY` | 当前运行凭证 |
| `LOOMQ_LLM_MODEL` | 当前模型；正式评测为 `deepseek-v4-flash` |
| `LOOMQ_LLM_TIMEOUT_SECONDS` | 单次请求超时 |

正式评测时由组委会注入模型服务；本地没有 Key 时，网页体验和本地兜底逻辑仍可用于演示常见任务。

`agent_chat()` 对应 L2 三类客观评测任务：

- 意图生成：根据自然语言生成 GHZ / Bell 等可运行实验。
- 代码纠错：修复缺寄存器、门名大小写、测量缺失等问题，并保留目标态语义。
- 智能选后端：读取后端能力表，按比特数、排队、费用等条件筛选平台。

## L2 页面体验

启动命令：

```bash
python -m loomq.web.server --port 8765
```

页面地址：

```text
http://127.0.0.1:8765
```

页面设计目标：**让从没写过 QASM 的人，也能第一次看见一个量子实验如何被提出、运行、解释和跨平台翻译。**

页面结构：

- 顶部引导：说明用户不需要先学公式，也不需要先写量子代码。
- 左侧入口：保留层级但不折叠，用户一眼能看到所有开始方式。
- 主工作区：点击不同入口后，当前问题、输入区和示例会完整切换。
- 结果区：用柱状图和文字解释展示实验 counts，不在未开始时制造大空白。
- 技术区：直接展示 LoomQ 实际做了什么，包括输入、生成步骤、检查结果和平台版本。
- 跨平台区：解释为什么有多个量子平台，并展示同一份实验如何被翻译到 SpinQ / OriginQ / AWS Braket。

页面包含四个入口：

1. 从一个问题开始 → 选择一个现成问题。
2. 我已经有一个实验任务 → 准备一份实验。
3. 我已经有一个实验任务 → 修复实验步骤。
4. 我已经有一个实验任务 → 选择运行环境。

评委可以快速体验四件事：

- 选择“电脑能不能像掷硬币一样随机给出 0 或 1”，查看本地模拟 counts 和解释。
- 选择“准备一份实验”，输入 GHZ / Bell 类自然语言目标，查看生成实验。
- 选择“修复实验步骤”，粘贴类似 `H q[0]; CX q[0] q[1]` 的错误步骤，查看修复和验证。
- 选择“选择运行环境”，输入“15 比特、零排队、不付费”等约束，查看推荐平台。

## L3：Hybrid-QASM 混合编译

核心接口：

```python
compile_hybrid(hybrid_qasm_str: str) -> tuple[list, str]
```

支持能力：

- 从 Hybrid-QASM 中分离量子操作和 `classical { ... }` 经典控制块。
- 支持整数常量、`r1..r9` 寄存器、`+`、`-`、`==`、`!=`。
- 支持顺序赋值、`if/else` 和嵌套分支。
- 将测量位 `c[k]` 映射到 Tiny RISC-V 输入寄存器 `x10+k`。
- 输出可被官方 `riscv_emulator.py` 执行的 Tiny RISC-V 汇编。

核对命令：

```bash
python evaluator.py --level l3
```

## Bonus：自定义量子 RISC-V 扩展指令

本项目实现了一组量子 RISC-V 扩展指令，包含 custom-0 32-bit 编码/解码、模拟器执行支持和 Bell 态端到端测试。

实现位置：

```text
riscv_emulator.py
evidence/bonus_quantum_riscv.md
```

同时提供 `encode_quantum_instruction()` / `decode_quantum_instruction()`，验证这些量子指令可映射到 RISC-V custom-0 32-bit 指令字段。

新增自定义量子指令：

| 指令 | 作用 |
|---|---|
| `qinit n` | 初始化 `n` 个量子位 |
| `qh q0` | 对量子位执行 H 门 |
| `qx q0` | 对量子位执行 X 门 |
| `qcx q0, q1` | 执行 CNOT |
| `qmeasure q0, x1` | 测量量子位并写入经典寄存器 |

端到端 Bell 示例：

```asm
qinit 2
qh q0
qcx q0, q1
qmeasure q0, x1
qmeasure q1, x2
```

核对命令：

```bash
python -m unittest tests.test_bonus_quantum_riscv
```

## 人工评分证据

人工评分材料统一放在：

```text
evidence/README.md
evidence/files/
```

当前申报：

- L1 真机证据
- L2 交互体验
- 工程与产品化叙事
- Bonus：自定义量子 RISC-V 扩展指令
- Bonus：新手引导与视觉叙事页面材料

说明：L3 混合编译属于自动评测项，已在 `submission.yaml` 中声明，并由 `adapter.compile_hybrid()` 与 `tests/test_l3_hybrid.py` 覆盖，不作为人工证据项单独勾选。

## 最终提交

截止时间为 **2026-08-25 12:00 UTC+8**。从 fork 根目录运行：

```bash
python starter_kit/prepare_submission.py --team-id elenawia
```

预检会确认工作区干净、HEAD 已推送、fork 所有者与 Team ID 匹配，并输出最终提交 Issue 需要填写的 fork 地址和 40 位 commit SHA。

如果只是本地保存，不想推送 GitHub，可以先执行：

```bash
git status
git add starter_kit/README.md
git commit -m "Update final starter kit README"
```

## 版本政策

合同版本为 `1.0`。本提交保留 Starter Kit v1.1.0 的接口契约，并在 `adapter.py` 中实现申报 Level 所需接口；公开 `evaluator.py` 只表示契约自测结果，不是正式分数。
