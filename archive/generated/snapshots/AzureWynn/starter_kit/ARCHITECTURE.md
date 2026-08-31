# LoomQ 架构文档

> 用中文说出你想算什么，LoomQ 把它跑成量子程序。
> 本文档说明：为谁做、怎么拼、如何跑、怎么验。

## 1. 为谁做（必答题）

**你的工具让哪一类原本进不来的人，第一次能用上量子计算？**

量子计算的门槛，主要不在物理，而在"黑话"：QASM、OriginIR、三套互不相通的 SDK。
被挡在外面最典型的，是**有明确问题、却不用术语思考的人**——产品、设计、内容、
非科班工程师、学生、做科普的人。他们不缺想法，缺的是三样东西：

1. 看不懂 QASM / OriginIR 这类指令格式；
2. 面对量旋、本源、AWS 三套 SDK 不知从哪入手；
3. 即使写出电路，也说不准自己"做对没有"。

LoomQ 把这三点一次补齐：

- **自然语言入口**（L2 智能体 + CLI）：说需求，得到能跑的量子程序，并在本地模拟器
  上直接跑一遍给你看——新手看到"000 / 111 各 50%"，就懂了什么是纠缠。
- **一套中间层通三家**（L1）：程序在量旋、本源、AWS 间任意切换，位序、门集、SDK
  差异在中间层内统一消化。
- **生成即验证**（自验闭环）：错的电路在生成阶段就被拦下并自动重试，用户拿到的
  一定是能跑、且通过正确性校验的程序。

一句话：**让只说得出一句"帮我做个纠缠态"的人，几分钟内跑出第一个量子程序并看懂结果。**

## 2. 系统架构

```text
┌────────────────────────── 用户 ──────────────────────────┐
│  natural language / OpenQASM 2.0 / Hybrid-QASM             │
└──────────────┬───────────────────────────┬────────────────┘
               │                           │
        adapter.py（赛题契约薄层）          │
               │                           │
   ┌───────────┴───────────┐      ┌────────┴────────┐
   │  agent.py  L2 管道     │      │  hybrid.py L3   │
   │  分类→生成/纠错→自验     │      │  迷你文法解析→    │
   │  →重试→选型（装饰器）    │      │  RISC-V 生成     │
   └───────────┬───────────┘      └────────┬────────┘
               │                           │
   ┌───────────┴───────────────────────────┴────────┐
   │  backends.py  L1 策略 + 工厂                      │
   │  SpinQBackend / OriginQBackend / BraketBackend  │
   │  统一 transpile(pc)->IR   run_raw(pc,shots)      │
   └───────────┬───────────────────────────┬────────┘
               │                           │
   ┌───────────┴────────┐        ┌─────────┴─────────┐
   │ qasm_parser.py      │        │ normalize.py      │
   │ 12 门白名单解析      │        │ 位序归一化(little) │
   │ 安全参数求值         │        │ 统一结果 Schema    │
   └────────────────────┘        └───────────────────┘
```

### 设计模式

| 层 | 模式 | 说明 |
|---|---|---|
| L1 | 策略 + 工厂 | 每个后端一个 `BackendStrategy`（`transpile` + `run_raw`），`get_backend(target)` 工厂统一分派；新增平台只加一个类，不改调用方 |
| L2 | 管道 + 装饰器 | `agent_chat` 按"分类 → 生成/纠错 → 自验闭环 → 选型"管道推进；`@_retry` 装饰器对瞬时失败自动重试 |
| L3 | 递归下降解析 + 代码生成 | Hybrid-QASM 迷你文法 → AST → RISC-V 汇编；附参考解释器 `interpret_classical` 供穷举自验 |
| 全局 | 适配器 | `adapter.py` 作为赛题契约薄层，只做转发，业务都在策略/管道层 |

### 模块清单

| 文件 | 职责 |
|---|---|
| `adapter.py` | 赛题四个接口的薄转发层（契约不变） |
| `backends.py` | 三后端策略 + 工厂；各自的 `transpile` IR 渲染与本地模拟器执行 |
| `qasm_parser.py` | OpenQASM 2.0 白名单解析（12 门 + `pi` 表达式安全求值） |
| `normalize.py` | counts 位序归一化为 little-endian；统一 result Schema（job_id/shots/bit_order/meta） |
| `agent.py` | L2 智能体管道 + 自验闭环 + 约束选型 + 无 Key 回退 |
| `hybrid.py` | L3 迷你文法解析器 + RISC-V 生成 + 参考解释器 |
| `cli.py` | 零基础交互入口（REPL / 单次模式） |
| `llm_client.py` | 官方无依赖 OpenAI 兼容传输（读取 `LOOMQ_LLM_*`） |

## 3. 一键搭建与运行

### 方式 A：Docker（任何机器，最省事）

```bash
docker build -t loomq-submission starter_kit
docker run --rm loomq-submission
# 或指定全目标：
docker run --rm loomq-submission python evaluator.py --target spinq,originq,braket
```

> 注意：spinqit / pyqpanda 只发布 x86_64 Linux wheel，Apple Silicon 构建需
> `docker build --platform linux/amd64`（官方评测即为 x86_64 Linux，不受影响）。

### 方式 B：本地 venv（macOS / Linux 开发）

```bash
bash setup_local.sh          # 安装 Python 3.10 + 锁定版本三 SDK + macOS 补丁
source .venv/bin/activate
python3 starter_kit/evaluator.py --level all --target spinq,originq,braket
```

### 方式 C：L2 交互入口

```bash
python3 starter_kit/cli.py              # 交互模式
python3 starter_kit/cli.py "生成一个 3 比特 GHZ 态并全测量"   # 单次模式
```

## 4. 目标用户与完整使用流程

| 用户 | 入口 | 流程 |
|---|---|---|
| 零基础用户 | CLI | 说需求 → Agent 生成/修复 QASM → 本地模拟器运行 → 直方图看懂结果 → 按需换后端 |
| 懂 QASM 的用户 | `adapter.transpile/run` | 输入 OpenQASM 2.0，选目标，拿统一 Schema 结果 |
| 开发者 | 代码 API | `transpile/run/agent_chat/compile_hybrid` 四个接口任意组合 |

完整流程示例（新手 5 分钟）：

```text
loomq> 生成一个 3 比特 GHZ 态并全测量
→ Agent 生成 OPENQASM 2.0 程序，本地模拟器自验 fidelity ≥ 0.97
→ 展示 QASM + 运行直方图：111 50.3% / 000 49.7%
loomq> 15 比特电路且零排队，选哪个后端？
→ 按官方 backend_capabilities.json 约束过滤，推荐 braket_local_simulator 等
```

## 5. 正确性如何保证

- **L1 自验**：`evaluator --level l1` 8 电路 × 3 目标（bell/ghz3/ghz5/qft4/grover3/random×3）两两交叉
  fidelity ≥ 0.97；相位敏感电路（t/sdg/tdg 干涉、cu1、ccx）验证分解正确性。
- **L2 自验闭环**：Agent 生成/修复的 QASM 必须先在本地模拟器通过 fidelity 自检，失败自动重试
  （`@_retry`），仍失败则回退确定性生成器兜底，保证永远返回可运行程序。
- **L3 穷举**：随机 Hybrid-QASM 用例 + 参考解释器对照，穷举注入所有测量组合逐一比对寄存器终态。
- **跨平台归一化**：spinq/braket 原生 big-endian、pyqpanda 原生 little-endian，统一在
  `normalize.to_clbit_counts` 单点归一。

## 6. 安全与合规

- 所有 Key/Token 只从 `LOOMQ_LLM_*` 环境变量读取，代码零硬编码；错误信息不回显 Key。
- 依赖全部 `==` 精确锁定（见 `requirements.txt` 的解析说明注释）。
- 评测进程只收当前输入，无任何打表/Mock 路径（`meta` 不含 `is_mock`）。
- 本地 macOS 需要给 spinqit 打 rpath 补丁（wheel 缺陷），Linux 容器无此问题（见 `setup_local.sh`）。