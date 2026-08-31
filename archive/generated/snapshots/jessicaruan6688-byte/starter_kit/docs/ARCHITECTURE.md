# LoomQ 中间层架构（本仓库实现）

面向评委与协作者：说明我们如何把「人话 / OpenQASM」接到多家后端，而不是再发明一套厂商 SDK。

## 一句话

用户只写（或让 Agent 生成）**OpenQASM 2.0**；中间层解析成统一电路 IR，再按目标后端发射原生方言并执行，结果统一成竞赛 schema（`counts` + `bit_order: little`）。

## 数据流

```text
自然语言 (L2)
    │ agent_chat → LLM → 抽 QASM → 本地校验/重试
    ▼
OpenQASM 2.0
    │ parse_qasm
    ▼
统一 IR (Circuit: gates / measure map)
    ├─ emit(spinq)    → OpenQASM 2 方言 → spinqit 本地/真机路径
    ├─ emit(originq)  → OriginIR       → pyqpanda 本地 / 悟空云
    └─ emit(braket)   → QASM3 合同/原生 → LocalSimulator
    ▼
统一 result.json schema
```

L3 另路：`Hybrid-QASM` → `compile_hybrid` → `(量子操作序列, RISC-V 汇编)`，由官方 `riscv_emulator.py` 验语义。

## 模块地图

| 路径 | 职责 |
|---|---|
| `adapter.py` | 竞赛契约入口：`transpile` / `run` / `agent_chat` / `compile_hybrid` |
| `loomq/parse_qasm.py` | OpenQASM 2.0 → IR |
| `loomq/circuit.py` | 后端无关 IR |
| `loomq/gates.py` | 白名单门分解 |
| `loomq/emit.py` | SpinQ / OriginIR / Braket 发射 |
| `loomq/backends.py` | 三后端执行与 counts 规范化 |
| `loomq/reference_sim.py` | 无厂商依赖的参考态矢量（自验） |
| `loomq/hybrid.py` | L3 Hybrid→RISC-V |
| `loomq/agent.py` | L2：LLM + 校验 + ≤3 次重试 |
| `llm_client.py` | 只读 `LOOMQ_LLM_*` 的传输层 |
| `tools/l2_chat_cli.py` | 零基础可点的本地 CLI 入口 |
| `tools/run_bell_evidence.py` | 真机 Bell 证据落盘助手 |
| `evidence/` | 人工评分材料 |

## 设计约束（得分相关）

1. **不硬编码**隐藏电路答案；L2 不靠关键词表蒙公开样例。  
2. **位序**：schema 要求经典小端；各 SDK 返回值在 `result.py` / `backends.py` 统一处理。  
3. **密钥**：只走环境变量 / `.env`（gitignore），永不进 git。  
4. **声明与实现一致**：`submission.yaml` 勾了的 Level 必须可跑；勾 L2 时必须 `network.required_for_l2: true`。

## 目标用户（工程叙事必答题）

**没有量子课背景、但会用命令行或聊天框的产品/开发者**：  
用自然语言或一份标准 QASM，不必先学三家 SDK 方言，就能在模拟器上验证电路，并在账号齐全时把同一电路交到真机。

证明路径：

- 自动：`adapter.run` / `evaluator.py`  
- 交互：`python tools/l2_chat_cli.py`（需 `LOOMQ_LLM_*`）  
- 真机：`tools/run_bell_evidence.py` + `evidence/README.md`
