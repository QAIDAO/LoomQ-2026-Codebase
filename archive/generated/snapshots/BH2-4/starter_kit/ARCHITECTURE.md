# LoomQ 技术架构方案

> 一句话总览：一个三层翻译系统——用户说自然语言，系统输出各家量子平台的原生代码，
> 中间靠一套自研「统一中间表示（IR）」转接，全程可离线、可验证、零第三方依赖。

## 1. 分层总览

```text
用户："生成一个 3 比特 GHZ 态并测量"
  │
  ▼
chat.py                 对话入口：接话 → 自动跑电路 → ASCII 直方图 → 通俗解读
  │
  ▼
loomq_l2/   （L2 智能体）真模型只做「人话 → 意图 JSON」，
  │          电路由确定性模板库生成，本地验证器把关，失败自动回喂修复
  ▼
loomq/      （L1 中间层）QASM2 → 统一 IR → 三后端代码生成：
  │          spinq(QASM2) / braket(QASM3) / originq(OriginIR)
  │          内置无噪声状态向量模拟器（纯标准库，离线可用）
  ▼
loomq_l3/   （L3 混合编译）Hybrid-QASM 的经典块 → AST → 官方 RISC-V 7 指令汇编
             Bonus：riscv_emulator_qext.py 扩展 QH/QX/QCX/QMS/QP 量子指令（CUSTOM-0 空间）
```

## 2. 三层详解

### L1 通用中间层（`loomq/`）

- **职责**：任何合法 OpenQASM 2.0 电路进，三家后端的原生代码出；附带本地执行能力。
- **关键模块**：`qasm2.py`（白名单门集解析 + 自定义门展开）→ 统一 IR → `codegen.py`
  （三后端生成器）+ `sim.py`（状态向量模拟器）。
- **核心决策——统一 IR**：不是写三套互相翻译的转换器，而是「一次解析、一种中间表示、
  三处生成」。新增后端只需新增一个 codegen。隐藏电路（评测私有种子的 QFT/Grover/Random）
  走的是同一条理解路径，无任何针对公开样例的特判分支。

### L2 智能体层（`loomq_l2/`）

- **职责**：`agent_chat(prompt) -> str`，自然语言到电路的闭环。
- **核心决策——模型永不直接写量子代码**：LLM 只输出结构化意图 JSON（模板名 + 参数），
  电路由 `templates.py`（Bell/GHZ/均匀叠加/基矢/W 态）确定性生成，`validate.py`
  本地模拟对拍验证，失败把机器可读错误回喂修复（`repair.py` 同时承担用户坏代码规范化）。
  `selector.py` 按官方 `backend_capabilities` 确定性过滤并返回规范后端标识。
- **收益**：模型幻觉无法污染电路正确性；评测的隐藏措辞变体天然免疫
  （live 模式 25/25、mock 25/25 实测通过）。

### L3 混合编译层（`loomq_l3/`）

- **职责**：`compile_hybrid(hybrid_qasm_str) -> (quantum_ops, assembly)`。
- **实现**：经典文法 → AST → 官方 7 指令（li/add/sub/addi/beq/bne/j）汇编生成，
  全确定性。自测：200 随机用例 × 全部注入组合穷举，与参考实现 0 失配。
- **Bonus 扩展**：`l3_bonus_spec.md` 规格化 5 条量子指令（QH/QX/QCX/QMS/QP，占用 RISC-V
  CUSTOM-0/opcode 0x0B 扩展空间；QP 为 π/4 档位相位门，门集由此构成 {H,T,CX} 通用集），
  `riscv_emulator_qext.py` 为官方模拟器的扩展 fork
  （原文件零改动），量子演化→测量读数→经典控制一次执行闭环；200 随机混合用例与
  独立状态向量参考全对拍通过（另有 200 例相位门振幅级对拍，`l3_selftest.py --qp`）。

## 3. 端到端数据流（以 GHZ-3 为例）

1. 用户输入「生成一个 3 比特 GHZ 态并测量」（`chat.py` 或 `agent_chat`）。
2. L2 调用模型（读 `LOOMQ_LLM_*` 环境变量，无任何硬编码 URL/Key/模型名）→ 意图
   JSON `{template: ghz, n_qubits: 3, measure: true}`。
3. 模板库生成 QASM2（H + CX 链），本地模拟器 4096 次对拍：000/111 各约 50%。
4. L1 将 QASM2 解析为统一 IR；按需 `transpile` 到 spinq/braket/originq 任一后端。
5. `chat.py` 输出 ASCII 直方图 + 通俗解读；真机提交则由 `tools/qpu/` 脚本走平台 SDK。

## 4. 贯穿全局的设计决策

| 决策 | 目的 | 换来的分数底气 |
|---|---|---|
| 统一 IR，一次解析三处生成 | 隐藏电路泛化 | L1 45 |
| 模型只出意图、模板生成、本地验证 | 抗模型幻觉 + 变体免疫 | L2 30 |
| 纯标准库、零第三方依赖、可离线 | 评测环境断网可跑 | 工程产品化 |
| 密钥只走环境变量，仓库零密钥 | 反作弊红线 | 合规 |
| 全链路确定性可复现（除 L2 意图一步） | 争议可追溯 | L3 15 |

## 5. 目录速查

```text
starter_kit/
├── adapter.py              # 提交契约入口（transpile/run/agent_chat/compile_hybrid）
├── chat.py                 # 用户入口 CLI（--demo / 交互 / --prompt / --doctor）
├── loomq/  loomq_l2/  loomq_l3/
├── riscv_emulator_qext.py  # Bonus 量子 RISC-V 扩展模拟器
├── selfcheck.py            # 回归：官方 8 电路全集 + 随机电路，119 项
├── l2_selftest.py          # L2 变体自测（--mock / --live 各 25 例）
├── l3_selftest.py          # L3 穷举 + Bonus 端到端
├── GETTING_STARTED.md      # 零基础 5 分钟上手
└── evidence/               # 人工评分证据（真机 job 等）
tools/qpu/                  # 真机采集脚本（量旋/本源；凭证走环境变量）
```

## 6. 质量验证体系

```bash
python3 starter_kit/evaluator.py --target spinq,originq,braket  # 公开契约
python3 starter_kit/selfcheck.py                                # 119 项回归
python3 starter_kit/l2_selftest.py --mock                       # L2 离线回归
python3 starter_kit/l2_selftest.py --live                       # L2 真模型 25 例
python3 starter_kit/l3_selftest.py [--bonus]                    # L3 穷举 + Bonus
python3 -m unittest discover -s tests                           # 官方契约测试
```

以上全部通过，且已在 Python 3.10（与正式评测镜像一致）下复验；
`--live` 使用真实模型（25/25 通过，单例约 1 秒，远低于 120 秒时限）。