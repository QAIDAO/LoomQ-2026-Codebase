# L2 客观评测契约矩阵

版本：2026-08-15。该矩阵只覆盖 `agent_chat(prompt: str) -> str` 的 20 分客观评测，不声明 L2 交互体验分。

| 项目 | 权威来源 | 已确认行为 | 本地实现 | 可硬拒绝 |
|---|---|---|---|---|
| 模型协议 | `l2_policy.json`、`llm_client.py` | OpenAI chat completions；正式模型 `deepseek-v4-flash`；thinking disabled；temperature 0；非流式；每 case 120 秒 | 环境变量读取，固定正式字段，整体 deadline 与返回预留 | 是 |
| 有效模型调用 | `problem_statement.md` L2 判定、旧 PDF 兼容边界 | 每个 case 至少一次有效模型调用 | 所有任务先调用模型；最多 3 次 transport attempt，其中至多一次瞬态重试和一次 QASM 定向修复 | 是 |
| 任务类型 | `problem_statement.md` L2 判定 | QASM 生成、QASM 纠错、后端选择 | 带标签 JSON 联合类型；原始 QASM 仅回退到 QASM 路径 | 是 |
| QASM 提取 | `evaluator.py::extract_qasm` | 从 `OPENQASM 2.0;` 提取到 fence 或文本结尾 | 去除包装，仅返回一个规范完整程序 | 是 |
| QASM 语法与门集 | `loomq_l1.py`、题面 12 门白名单 | OpenQASM 2.0、寄存器、索引、参数、测量及白名单门 | 复用 L1 parser/IR；不维护第二套语法 | 是 |
| QASM 目标语义 | 题面公开生成/纠错任务 | 仅明确有限目标可独立重建 | 用户原文可恢复 Bell/GHZ 时做有界状态向量验证；已知错误候选不进入 fallback，repair 失败时 canonical 电路仍须通过同一 oracle；其他目标保持 unknown | 仅可信有限目标 |
| Fidelity 定义 | `evaluator.py`、`l1_reference.py` | Hellinger 规则与无噪声参考语义 | 复用已回归的本地参考模拟路径 | 仅可信有限目标 |
| 后端事实 | `backend_capabilities.json` | 表中字段及规范 ID 是唯一判定快照 | 强类型、版本化、唯一 ID 校验后的不可变缓存 | 是 |
| 后端自然语言约束 | 题面与能力表 schema | 比特数、kind、queue、cost、账号、platform | 模型给出原文证据；本地以直接支配模式区分“except AWS / without using AWS”与“AWS without an account / no paid services”，并归一化 real/physical machine 为 QPU | 仅确认项 |
| 后端选择 | `backend_capabilities.json` | 满足全部硬约束的正确答案集 | 单次全表求值，硬约束/排除项筛选，软偏好与稳定 tie-break | 是 |
| 无解文本 | 未发布固定字符串 | 没有已确认的机器可读无解格式 | 不伪造后端 ID，显式抛出运行错误 | 否 |
| 资源上限 | `l2_policy.json`、正式 120 秒与旧 PDF 兼容边界 | 120 秒、最多 3 attempt、累计 8,000 输入/2,000 输出、单次输出 ≤1,000 | `loomq_l2.py` 负责逐 case 累计预算、将每次请求 cap 收缩到剩余输出额度，以及 retry/repair；`llm_client.py` 负责 transport、response bytes 和执行该次请求 cap；prompt/JSON/QASM/模拟规模另有本地边界 | 是 |

模型自报的目标、推荐 ID 或没有用户原文支持的约束不作为事实源。后端事实只来自能力表；未知 QASM 目标只做协议与静态验证，不以启发式语义拒绝。
