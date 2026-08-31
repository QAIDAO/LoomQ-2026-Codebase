# LoomQ 产品说明（冲刺第一名交付文档）

> 让不懂量子“黑话”的人，也能指挥量子算力。

## 一分钟启动

```bash
cd starter_kit
python evaluator.py --json-out report.json
```

L2 交互（需 DeepSeek / OpenAI-compatible）：

```bash
set LOOMQ_LLM_BASE_URL=https://api.deepseek.com
set LOOMQ_LLM_API_KEY=你的密钥
set LOOMQ_LLM_MODEL=deepseek-v4-flash
python loomq_cli.py --run "生成一个 3 比特 GHZ 态并进行全测量"
```

REPL：

```bash
python loomq_web.py
# 浏览器打开 http://127.0.0.1:8765
```

## 架构（统一中间层，不是三套硬编码）

```text
自然语言 / OpenQASM 2.0 / Hybrid-QASM
        │
        ▼
   loomq_core.Circuit  IR
        │
   ┌────┼──────────────┐
   ▼    ▼              ▼
 SpinQ OriginIR     Braket QASM3
   │    │              │
   └────┴── run() ─────┘
            │
     统一 JSON Schema（little-endian counts）
```

| 模块 | 文件 | 作用 |
|---|---|---|
| IR / 转译 / 模拟 / L3 | `loomq_core.py` | 解析 12 门白名单、三后端发射、态矢量采样、经典块→RISC-V |
| 契约入口 | `adapter.py` | `transpile` / `run` / `agent_chat` / `compile_hybrid` |
| L2 策略 | `loomq_agent.py` | 任务分类、能力表选型、QASM 抽取 |
| 交互入口 | `loomq_cli.py` / `loomq_web.py` | 零基础 CLI 与网页：对话 → 自检 → 执行 → 柱状图 |
| 量子 RISC-V | `riscv_emulator.py` + `QUANTUM_RISCV.md` | custom-0 编码 H/X/CNOT/测量 |

## 目标用户

跨界创作者、产品经理、设计师、学生——会说人话，不会写 OriginIR / SpinQit / Braket 方言。

## 完整使用流程

1. 用自然语言描述意图（“做个贝尔态并测量”）
2. Agent 生成 OpenQASM 2.0，并用本队 L1 引擎自检
3. 同一中间层转译到 spinq / originq / braket
4. 返回统一 `counts`；CLI 用白话解释主峰含义

## 现场体验三任务

1. “生成 2 比特贝尔态并测量”
2. “这段坏掉的贝尔态代码帮我修好：`H q[0]; CX q[0] q[1]`”
3. “15 比特电路、零排队，选哪个平台？”

## 冲第一还缺什么（执行清单）

| 优先级 | 项 | 分值 | 行动 |
|---|---|---:|---|
| P0 | L1 隐藏电路全过 | →35 | 已用统一 IR；补 GHZ-5/QFT/Grover 自测 |
| P0 | L2 三类任务稳定 | →20 | 能力表确定性选型 + 生成/纠错自检闭环 |
| P0 | L3 随机用例 | →15 | 嵌套 if、多 cbit、表达式赋值 |
| P1 | L2 CLI 体验 | +10 | `loomq_cli.py` + evidence 申报 |
| P1 | 工程叙事 | →10 | 本文档 + 一键命令 |
| P1 | 真机×2 | +10 | 注册量旋/本源，跑 Bell，归档 job_id |
| P2 | RISC-V 量子扩展 | +8 | 自定义 opcode + 扩展模拟器 + e2e |
| P2 | 新手视觉叙事 | +4 | 结果条形图、错误恢复文案 |
