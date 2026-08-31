# LoomQ 提交架构说明

> 本文件说明本提交的系统设计、目标用户与可复现方式，供异步评审。

## 必答题：你的工具让谁第一次用上量子计算？

让**有真实问题意识、却没有量子物理或编程背景的跨界创造者**——产品经理、设计师、内容创作者、教师、学生，以及所有被传统量子技术「黑话高墙」挡在门外的人——第一次能够**只用一句中文自然语言**，生成、运行并「看见」一个真实的量子电路结果。

他们不需要知道什么是 OpenQASM、指令集、幺正矩阵或 Hellinger 保真度。就像写 Markdown 的人不需要会写渲染引擎：本提交把量子计算的门槛从「懂物理 + 懂 SDK」降到了「会说一句话」。

## 目标用户与使用场景

| 用户 | 场景 | 入口 |
|---|---|---|
| 零背景跨界创作者 | 用一句中文描述想要的量子态 | `chat_cli.py` |
| 会一点代码但不懂量子 | 修复一段报错的 QASM、选一个合适的后端 | `chat_cli.py` |
| 评测器 / 系统集成方 | 程序化调用转译与执行 | `adapter.py` 契约函数 |

## 架构总览

```
OpenQASM 2.0（唯一源语言）
        │
        ▼  parse_qasm2()
   ┌────────────┐
   │  Circuit IR │  统一的中间表示（寄存器 + 门序列）
   └─────┬──────┘
         ├───────────────► transpile() ──► spinq(QASM2) / braket(QASM3) / originq(OriginIR)
         │                                    （纯文本转译，零依赖）
         │
         └───────────────► simulate()  ──► counts ──► run() 统一 Schema
                              （自写无噪声状态向量模拟器）

自然语言 ──► agent_chat() ──► LLM ──► 生成/修复 QASM ──► 复用 parse_qasm2 自验 ──► 重试
                       └──► 选后端（能力表内嵌 system prompt）
```

核心设计原则：**一切以 OpenQASM 2.0 为源，先解析成统一 IR，再分两条路走**。转译与执行共享同一个 IR，因此二者语义必然一致——这就是「通用中间层」而非三套硬编码的关键。

## 模块说明（`adapter.py`）

| 模块 | 函数 | 职责 |
|---|---|---|
| 数据模型 | `Gate` / `Circuit` | 门（名、参数、qubit、cbit）与电路（比特数 + 门序列） |
| 解析器 | `parse_qasm2` / `_parse_param` | QASM 2.0 文本 → Circuit；`pi/2` 等参数安全求值（`ast`，不 `eval`） |
| 模拟器 | `simulate` / `_apply_gate` / `_measure_state` | 12 门白名单的无噪声状态向量采样，纯标准库实现 |
| 转译器 | `_to_qasm2` / `_to_qasm3` / `_to_originir` | IR → 三种后端原生文本；唯一「真转译」是 `cu1→cp`（QASM3 无 cu1，矩阵等价） |
| 执行 | `run` | 解析→模拟→统一 Schema（含 little 位序归一化） |
| L2 智能体 | `agent_chat` / `_chat_completion` / `_validate_qasm` | 读 `LOOMQ_LLM_*` 调 OpenAI-compatible 服务；「生成→自验→重试」闭环 |
| CLI | `chat_cli.py` | 零基础交互入口 + 结果直方图可视化 |

## 关键设计决策

1. **零第三方依赖**：L1 转译器与模拟器、L2 客户端全部用 Python 标准库实现，正式评测隔离容器无需安装任何依赖即可运行。
2. **门白名单全覆盖**：12 个门在模拟器里逐个用稀疏矩阵操作实现，隐藏电路（QFT/Grover 用到的 rz/ry/cu1/ccx/swap）均已用 pyqpanda 交叉验证分布一致。
3. **位序归一化**：统一采用大赛约定（counts key 最右字符为 `c[0]`），跨平台差异在中间层内消除。
4. **自验闭环**：L2 用 L1 的解析器当「质检员」，LLM 生成的 QASM 语法错误会被发现并回传修正，而非直接返回错误结果。

## 一键复现

```bash
# L1 自测（零依赖，任何干净环境一条命令跑通）
python3 starter_kit/evaluator.py --level l1 --target spinq,originq,braket --json-out report.json

# L2 智能体（需模型服务配置，正式评测由组委会注入；本地可自备 OpenAI-compatible 服务）
export LOOMQ_LLM_BASE_URL=...
export LOOMQ_LLM_API_KEY=...
export LOOMQ_LLM_MODEL=deepseek-v4-flash
python3 starter_kit/evaluator.py --level l2

# 零基础交互入口
python3 starter_kit/chat_cli.py "生成一个 3 比特纠缠态"
```

## 完整使用流程

1. 用户在 `chat_cli.py` 输入一句中文（如「让 3 个比特像串联灯泡一样同时亮灭」）。
2. `agent_chat` 调 LLM 生成/修复 OpenQASM 2.0，或从能力表选后端。
3. 生成的 QASM 经 `parse_qasm2` 自验，语法错误自动重试修正。
4. CLI 用 `run` 在无噪声模拟器跑 8192 次，以直方图展示测量结果。
5. 用户「看见」了量子态分布，全程无需接触 QASM 或任何 SDK。
