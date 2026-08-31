# 02 · SCI-Pegasus 复用矩阵

## 复用原则

SCI-Pegasus 是架构研究材料，不是 LoomQ 的运行依赖。当前参考包无权威 LICENSE，因此只抽取一般性的系统设计思想，再针对官方 Python 3.10 合同 clean-room 重写；不复制 TypeScript 源码、Prompt、页面组件或持久化实现。

参考包身份：

- 文件：用户提供的 `sci-pegasus-main(2).zip`（本地只读审计，不入库）
- 大小：1179936 字节
- 修改时间：2026-08-19T00:29:24+08:00
- SHA-256：7306ACF30D33BA1A393660AFA23D3CAA05BDE2C28041641AC3BCA8090FF02CEE
- 隔离参考目录：.codex_reference/sci-pegasus/
- 许可结论：根目录未发现可作为依据的 LICENSE；不得推断 MIT、Apache 或其他许可

## 吸收并重写的思想

| SCI-Pegasus 思想 | 参考观察点 | LoomQ clean-room 设计 | 正式路径边界 | 当前状态 |
|---|---|---|---|---|
| 有状态 Agent Loop | lib/agent/ 的主循环与工具回合 | 理解 → 计划 → 生成 → 验证 → 修复 → 输出的有限状态流 | 一次主要 LLM 调用；必要时最多一次修复；禁止无界循环 | 已独立重写并测试 |
| Provider 抽象 | lib/agent/provider.ts 与文献 provider registry | SpinQProvider、OriginQProvider、BraketProvider 共享接口 | Provider 只负责目标 IR、运行/模拟、结果读取、位序归一化、能力与错误 | 已独立重写并测试 |
| Tool Input Boundary | lib/agent/tool-input-boundary.ts 的不可信输入准入 | 对 prompt/QASM/target/shots/索引/长度/路径做显式校验 | adapter 保持薄；任何工具动作前先校验，拒绝 NaN、越界和非白名单 | 已独立重写并测试 |
| Tool Result Admission | lib/agent/tool-result-admission.ts | 对 IR、counts、bitstring、shots、mock、敏感字段和语义门槛统一准入 | 不合格结果不能进入下一阶段或 UI Evidence | 已独立重写并测试 |
| Failure Policy | lib/agent-runtime/failure-policy.ts 的分类与有界恢复 | 分类错误 → 确定性修复 → 可选一次模型修复 → 再验证 → 成功或清晰失败 | 不隐藏异常、不无限重试、不把模拟器说成真机 | 已独立重写并测试 |
| Workspace / Evidence | lib/workspace/ 的路径政策、CAS、审计与产物概念 | UI 运行可生成 request、intent、normalized QASM、target IR、result、verification、manifest | 官方 adapter 调用无状态；持久 Workspace 仅用于产品和证据 | 已独立重写并测试 |
| UI 工作台 | TaskWorkbench、WorkspacePanel、状态与产物卡片 | 左导航、中任务区、右侧工作流/IR/counts/证据；本地资源 | Python 本地 HTTP + HTML/CSS/JS/SVG；无 CDN | 已独立重写并浏览器验收 |
| Agent Team 可视化 | Root/成员/任务/状态面板 | Intent Analyst、Circuit Builder、Transpiler、Runtime、Verifier 五个“工作流阶段/验证角色” | 除非真实执行多个独立 Agent，否则不得称五个 LLM Agent | 仅实现诚实的工作流阶段视图 |
| 审计而非思维链 | 工具事件、结果、workspace provenance | 记录输入摘要、结构化意图、工具 I/O 摘要、验证、错误、修复和最终产物 | 不保存或展示模型私有推理过程 | 全阶段约束 |
| 来源绑定与能力表 | 文献工具按来源固定 provider | 后端 registry 与 backend_capabilities.json 作为唯一选型事实 | 模型不得自由编造后端能力 | 已独立重写并测试 |

## LoomQ 的结果准入清单

进入下一阶段前必须验证：

1. 值类型与非空性正确；
2. OpenQASM/目标 IR 能被对应 parser 重新解析；
3. target 属于 spinq、originq、braket；
4. shots 为受限正整数；
5. counts 总数严格等于 shots；
6. bitstring 长度与经典寄存器一致且仅含 0/1；
7. bit_order 为 little，最右字符映射 c[0]；
8. 不含 meta.is_mock=true；
9. 达到相应语义验证门槛；
10. 输出、异常和日志不含凭证或个人信息。

## Workspace 产物约定

产品界面的每次持久运行可形成：

| 产物 | 内容 | 敏感性约束 |
|---|---|---|
| request.json | 输入摘要与运行参数 | 不保存 Key 或完整隐私文本 |
| intent.json | 结构化任务、目标和约束 | 不含私有思维链 |
| normalized.qasm | 经 parser 验证的规范电路 | 保持真实输入语义 |
| target.ir | 实际发射的目标 IR | 标明 target |
| result.json | 规范化结果 | 明示 simulator/QPU |
| verification.json | schema、语义与保真度检查 | 记录失败也不篡改 |
| run_manifest.json | 时间、版本、文件 SHA-256、关系索引 | 不含凭证 |

这些产物是 UI/证据功能的目标设计，尚未宣告全部实现。正式 adapter 不能依赖它们存在，也不能依赖持久数据库。

## 明确不迁移

| 不迁移内容 | 原因 |
|---|---|
| Next.js API 与生产运行时 | 不符合 Python 3.10 轻量正式根，增加 Node 构建风险 |
| React 状态管理和现成组件源码 | 许可不明；UI 用本地 HTML/CSS/JS clean-room 实现 |
| MongoDB Repository、GridFS、数据库迁移 | 官方接口应无状态，容器与归档成本不合理 |
| NextAuth、登录注册、Cookie、用户系统 | 与评分无关并引入凭证/隐私/攻击面 |
| 支付、配额、计费 | 与赛事合同无关 |
| 持久后台 Runner、lease、多进程恢复 | 远超每 case 120 秒和无状态 evaluator 所需 |
| Workspace CAS 的原实现 | 只吸收“产物有 provenance”的思想，不迁移数据库代码 |
| Agent 长期记忆、Hippocampus、compaction | 易污染独立 case，违反隐藏评测隔离预期 |
| 32 身份、8 并发多 Agent | 成本与复杂度不提高客观正确率 |
| OSS 对象存储与媒体管线 | 需要外部服务，非正式评分所需 |
| 文献检索、arXiv、Sciverse、PDF 解析 | 与 LoomQ 合同和评分无关 |
| TypeScript Agent Loop 源码 | 许可不明且运行时不适配；只保留有限状态机思想 |
| 模型注册数据库 | 正式模型配置必须来自 LOOMQ_LLM_* |

## 复用验收

每个受到 SCI-Pegasus 启发的新模块都必须回答：

- 它是否直接提高评分正确率、可复现性、安全性或可信度？
- 是否可用 Python 3.10 标准库或已精确锁定依赖实现？
- 是否完全位于 starter_kit/ 且不读取 .codex_reference/？
- 是否有独立测试证明，而非仅在文档中出现？
- 是否能说明是“思想借鉴 + 新代码”，而不是不明许可源码的复制？

任何一项无法回答时，不进入正式评测路径。
