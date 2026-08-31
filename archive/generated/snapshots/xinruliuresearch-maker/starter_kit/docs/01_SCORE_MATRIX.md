# 01 · 评分—实现—验证矩阵

状态词只表示本队工程状态，不表示官方得分。公开 evaluator、自建差分和人工证据准备均不能替代隐藏评测或组委会复核。

## 总表

| 模块 | 官方判定核心 | 实现落点 | 已有可复跑验证 | 当前结论 |
|---|---|---|---|---|
| L1 语义等价 | 三目标 IR、题面门集、结果 Fidelity/schema/位序 | `adapter.py`、`loomq/qasm/`、`loomq/targets/`、`loomq/runtime/` | 公开 6/6；100 seeds × 3 target round-trip；12 门与结果准入单测 | 本地 Gate A 完成；不推导隐藏分数 |
| L1 真机 | 可追溯真实 QPU job、赛程内时间、原始结果与实际 QASM | `loomq/hardware/`、`scripts/hardware/`、`docs/hardware/` | 23/23 dry-run/证据契约测试 | 未完成；无凭证、无 job、无真机文件，不申报 |
| L2 客观 | 生成、修复、推荐；每 case 有真实模型请求；120 秒约束 | `adapter.agent_chat`、`loomq/agent/`、`llm_client.py`、`backend_capabilities.json` | 公开 1/1；本地 OpenAI-compatible HTTP stub 确实收包；提示变体、超时、429、畸形响应测试 | 本地实现完成；正式 DeepSeek 未验证 |
| L2 交互体验 | 可运行入口、新手友好、错误恢复、可视化和一致性 | `loomq/ui/` | UI 9/9；Chrome 桌面/390px QA 无 console error；请求级证据 | 申报人工复核；正式 Agent 仍依赖注入模型服务 |
| L3 | Hybrid 随机程序、测量组合穷举、经典终态和量子序列一致 | `loomq/hybrid/` | 公开 1/1；500 programs × 8 measurement assignments | 本地 Gate C 完成；不推导隐藏分数 |
| 工程与产品化 | 可复现启动、架构清晰、目标用户与完整流程 | README、`scripts/run_all_checks.py`、`loomq/ui/`、Dockerfile、docs | Python 3.10.11；syntax 78/78；unittest 119/119；UI/browser QA | 标准 clone 已迁移复测并 push；Docker 未构建；Issue 回执待完成 |
| 量子 RISC-V Bonus | 编码规格、模拟器扩展、端到端测试三件套 | `loomq/bonus/`、`docs/bonus/` | 17/17；demo 退出码 0 | 本地实现与证据齐全，申报人工复核 |
| 新手与视觉叙事 Bonus | 首次运行、概念解释、结果可视化、恢复/无障碍 | README、`loomq/ui/static/`、UI evidence | UI 9/9；桌面/移动截图与 browser QA | 本地实现与证据齐全，申报人工复核 |

官方总分、人工项拆分和 Bonus 以题面及最终评委口径为准。本项目不根据本表自行计算或宣称得分。

## L1 实现与验收

L1 支持题面白名单 `h`、`x`、`s`、`sdg`、`t`、`tdg`、`rz`、`ry`、`cx`、`cu1`、`swap`、`ccx`。统一 AST 消费多寄存器、广播、表达式和测量映射，并生成：

- `spinq`：完整 OpenQASM 2.0；
- `originq`：规范 OriginIR；
- `braket`：完整 OpenQASM 3.0。

当前 `run()` 对三个 target 都使用本队标准库参考态矢引擎。`backend` 与 `meta.execution_engine` 明确写 `loomq_reference_statevector_*` / `loomq_reference_statevector`，`native_sdk_used=false`。这能验证逻辑、结果 schema 和位序，但不是厂商 SDK 集成或真机证据。

本地验收：

| 验收 | 结果 |
|---|---:|
| 公开 Bell/GHZ-3 × spinq/originq/braket | 6/6 |
| 随机结构化 QASM 的三目标 round-trip | 100 × 3 |
| counts 非空、二进制固定宽度、合计等于 shots | 通过单元/集成测试 |
| `bit_order=little`，最右字符为 `c[0]` | 通过单元/集成测试 |
| 真实硬件 | 未执行 |

## L2 实现与验收

| 客观任务 | 工程策略 | 本地证据与边界 |
|---|---|---|
| 自然语言生成 | 有界模型 JSON → 参数化 Bell/GHZ-n/均匀叠加/纠缠链/计算基态合成 → L1 准入 | 多种中英文措辞测试；本地真实 HTTP stub，不是正式 DeepSeek |
| QASM 修复 | 分离自然语言与代码；确定性修复；已知目标语义优先；最终仅一份 QASM | 错误候选、有效但语义错误候选、注入与 fenced code 测试 |
| 后端推荐 | 代码机械筛选 `backend_capabilities.json`；模型不创造 backend ID | 比特数、真机/模拟器、费用、队列和账号组合测试 |

模型调用仅从 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL` 和超时变量读取配置。正常只发一次请求；仅本地准入失败时允许第二次。正式评测模型、私有 12 case 与客观得分尚未由本队看到或验证。

## L3 实现与验收

| 能力 | 实现 | 已有验证 |
|---|---|---|
| 词法/解析 | 整数、`r1..r9`、`c[k]`、`+ - == !=`、赋值、`if/else`、顺序语句 | parser/错误边界单测 |
| 映射 | `r1..r9 → x1..x9`，`c[k] → x10+k`，临时寄存器避让 | 分配与耗尽测试 |
| 汇编 | 只生成 `li/add/sub/addi/beq/bne/j`，唯一 label | compiler/官方模拟器兼容测试 |
| 量子序列 | 保持源操作顺序，经典块不混入量子 list | 单元与差分测试 |
| 差分 | AST 解释器对编译结果，穷举测量赋值 | 500 × 8 全通过 |
| 公开 evaluator | 官方公开 branch case | 1/1 |

## 工程与人工证据

- Python 正式验证版本：3.10.11。
- 全部 `unittest`：119/119；Python 源语法检查：78/78。
- UI：9/9；真实 loopback HTTP；浏览器桌面 1440×900 与移动 390×844 QA，无 console error、无横向页面溢出。
- Bonus：17/17；ISA 规格、扩展模拟器、端到端 demo 均在仓库内。
- Hardware preparation：23/23，仅说明 dry-run、凭证保护与证据原子性，不能勾真机。
- Dockerfile 已提供，但当前主机没有 Docker，未执行 build/run。
- 标准 clone 已迁入开发差异并完整复测，`main` 已 commit/push 且远端页面已核验；官方预检已在一个已 push 的干净 HEAD 上完整通过。任何后续 commit 必须重跑预检；Final Submission Issue 与接收回执仍待完成。

## Gate 结论

| Gate | 当前结论 | 剩余条件 |
|---|---|---|
| A · L1 | 本地完成 | 隐藏评测和正式评分只能由组委会给出 |
| B · L2 | 实现、本地 stub 与公开 case 完成 | 正式 DeepSeek 注入环境与私有 case 未验证 |
| C · L3 | 本地完成 | 隐藏评测未验证 |
| D · 工程/UI | Python/UI、标准 clone 复测、fork 发布与一次官方预检完成 | 最终 HEAD 预检核对、Docker 冷构建和 Issue 回执 |
| E · Bonus | 本地完成，申报人工复核 | 由评委按最终 commit 复核 |
| F · 真机 | 未完成 | 账号、真实 QPU job、原始结果与赛程内时间戳 |

## 声明纪律

- 公开报告明确保留 `Public self-check only; this report is not an official score.`。
- 不从 emitter 输出推导厂商 SDK 或硬件执行。
- 不从 dry-run、runbook 或测试覆盖推导真实 job。
- 不从本地模型 stub 推导正式模型准确率。
- `evidence/README.md` 只勾有实际代码、命令和材料的人工项；L1 真机保持未勾选。
