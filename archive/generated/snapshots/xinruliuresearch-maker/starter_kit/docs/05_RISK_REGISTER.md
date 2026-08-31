# 05 · 风险登记册

严重度：Critical 会阻止有效提交或造成诚信/泄密问题；High 可能损失主要评分；Medium 影响工程、Bonus 或稳定性。测试缓解不等于官方验收。

| ID | 严重度 | 当前事实 | 影响 | 缓解/下一验收 | 状态 |
|---|---|---|---|---|---|
| R-01 | Critical | 标准 clone 已迁移并全量复测，`main` 已 commit/push 且远端页面已核验；官方预检已在一个已 push 的干净 HEAD 上完整通过 | 没有 Final Submission Issue 与 accepted 回执时仍不是有效赛事提交 | HEAD 变化后重跑预检，创建 Issue 并核对自动回执 | Git 发布与一次预检完成；Issue 外部阻塞 |
| R-02 | High | 完整基线 SHA 已由标准 clone 验证 | 快照身份歧义已消除 | 迁移前后审查 upstream 与合同差异 | 已关闭基线身份风险 |
| R-03 | High | L1 公开 6/6、100×3 随机 round-trip、门与 schema 单测通过 | 隐藏电路仍可能暴露边界 | 保持结构化 parser、三 IR 独立回读与随机/变形回归 | 本地缓解；隐藏风险保留 |
| R-04 | High | 公开电路只有 Bell/GHZ-3；隐藏可能含 GHZ-5/QFT/Grover/随机 | 样例特化会失效 | 12 门、参数、多寄存器、测量变形、100 seeds × 3；不按字符串/hash分支 | 已工程缓解 |
| R-05 | High | 官方会解析目标 IR；公开 evaluator 不覆盖全部 target 文法 | `run` 可过但 `transpile` 正式失败 | 三目标独立子集 parser 和 round-trip 测试 | 本地缓解 |
| R-06 | High | 位序、测量映射、shots 守恒易漂移 | Fidelity/schema 失败 | global mapping、little-endian、非对称测量与 counts admission 测试 | 本地缓解 |
| R-07 | High | 参考态矢覆盖 12 门但仍是本队 oracle | 参数门数值错误可能进入隐藏 case | 单门矩阵、复合/随机差分、固定 seed 与目标回读 | 本地缓解；独立官方隐藏未验证 |
| R-08 | High | L2 公开 1/1，真实本地 HTTP stub 与失败路径通过；正式 DeepSeek 未运行 | 正式响应差异、延迟或私有准确率未知 | 维持有界 JSON/一至两次请求/L1 admission；在注入环境复测 | 外部验证待完成 |
| R-09 | High | L3 公开 1/1，500×8 随机穷举差分通过 | 隐藏文法仍可能覆盖未想到边界 | parser/解释器/compiler 三方对照、label/寄存器压力回归 | 本地缓解；隐藏风险保留 |
| R-10 | High | 无 SpinQ/OriginQ 账号、额度、凭证、真实 job 或结果 | 无 L1 真机申报资格 | 账号持有人按 runbook 执行 `--record` 并保存完整证据 | 外部阻塞 |
| R-11 | Critical | Hardware 23/23 为 dry-run/证据安全测试，没有伪造 job | 误标或 secret 泄露会使证据无效 | simulator/QPU 强标识、record 前置检查、secret redaction、原子五件套、人工复核 | 控制已实现；真机路径未实测 |
| R-12 | High | SCI-Pegasus 根无权威 LICENSE | 复制代码/素材会有许可和披露风险 | 仅思想参考，clean-room Python 重写；无 TS/CSS/SVG/品牌资产复制 | 持续控制 |
| R-13 | Critical | `.codex_reference/` 被 `.gitignore` 排除、不在依赖图，且标准 clone 的 `git ls-files` 审计确认未跟踪 | 未来误添加仍会造成许可、隐私或归档风险 | 保持 ignore 与提交前 tracked-file 审计 | 当前发布已关闭；持续控制 |
| R-14 | High | Windows Python 3.10.11 已验证 119/119；Linux/Docker 未验证 | 官方容器环境可能暴露平台差异 | 核心只用标准库；在 Python 3.10 Linux/Docker 冷构建 | 部分缓解 |
| R-15 | Medium | Dockerfile 已写，但当前主机没有 Docker 可执行文件 | 工程复现声明不完整 | 有 Docker 的 runner 执行 `build --no-cache` 和默认 CMD，记录版本/digest | 开放 |
| R-16 | High | L2/L3 已在 submission 配置中启用；本地 gates 通过，L2 正式端点仍外部依赖 | 正式环境兼容失败 | 配置明确 `network.required_for_l2`；提交前合同审计和模型注入复测 | 受控，正式验证待完成 |
| R-17 | High | 公开 evaluator 不是正式评分器 | 误报隐藏通过或满分 | README、状态和报告统一标注 public self-check only | 持续控制 |
| R-18 | Medium | UI/Bonus 已完成且不反向依赖 adapter | 扩张可能造成回归或归档膨胀 | 全量 119/119、UI 9/9、Bonus 17/17；最终 archive scan | 本地缓解 |
| R-19 | Critical | 截止按 Issue `created_at`；fork 已 push 且预检曾完整通过，但 Issue 尚未创建 | 代码已发布但赛事提交仍可能无效 | 对最终 HEAD 重跑预检并创建 Issue，实时核对 `submission:accepted`、SHA-256 与 Artifact ID | 外部截止风险 |
| R-20 | Medium | 标准 clone 已有完整基线，但开发期间上游可能更新 | 合同或提交步骤漂移 | 提交前 fetch/review upstream 权威文件，不盲目合并破坏接口 | 开放 |
| R-21 | Critical | QASM/prompt/HTTP/UI/hardware 都接收不可信输入 | 执行、泄密、DoS、XSS、路径穿越 | 类型/长度/白名单、无 eval/exec、CSP/HTML 安全、path allowlist、secret tests | 本地缓解；持续控制 |
| R-22 | High | Evidence 已勾 L2 交互、工程、RISC-V、新手视觉；真机未勾 | 过度申报会损害可信度 | 每项给代码/命令/路径/限制；明确 stub、Docker 与真机边界 | 已对齐当前事实 |
| R-23 | Medium | 标准 clone 已完成统一 119/119 与公开/随机验证 | 迁移遗漏风险已由 clone 内复测覆盖 | 后续代码变化继续全量回归 | 已关闭当前迁移风险 |
| R-24 | Medium | 本地复测产生的 `__pycache__`/`.pyc` 均为 ignored，`git ls-files` 未跟踪缓存 | 错误强制添加仍可能污染归档 | 保持 ignore，并在后续提交前复查 tracked files | 当前发布已缓解 |
| R-25 | Medium | 工程与人工分细分口径可能有歧义 | 错误预期或过度宣称 | 完整交付可复现材料，但不自行计算得分 | 持续控制 |

## 停止规则

遇到以下情况必须失败关闭，不能“尽力返回”：

- 不支持的 target、门、寄存器、语法或超限输入；
- 目标 IR 无法独立回读；
- counts/shots/bit-order/schema 不一致或出现 mock 标志；
- LLM 配置缺失、超时、响应越界或最终候选未通过确定性准入；
- Hybrid 临时寄存器耗尽、label 无法解析或可能无界；
- hardware 响应不是明确 QPU、缺 job/time/raw counts，或任何 secret 可能落盘；
- Evidence 状态与实际文件、命令或结果不一致。

## 最终复审重点

Final Submission Issue 创建前必须复审 R-01、R-10、R-11、R-14、R-15、R-16、R-19、R-22：最终 HEAD 预检状态、Docker 真实性、Evidence 真机空缺、正式模型边界、远端记录与 Issue 回执。
