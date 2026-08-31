# 07 · 来源、贡献与许可边界

本文记录来源与合规事实，不是许可证文本，也不对权利未明确的材料作再许可。

## 1. LoomQ 官方材料

| 项目 | 记录 |
|---|---|
| 上游 | `https://github.com/QAIDAO/LoomQ-2026` |
| 参赛 fork | `https://github.com/xinruliuresearch-maker/LoomQ-2026` |
| 正式评测根 | `starter_kit/` |
| 开发材料初始取得方式 | fork 的 GitHub codeload 归档 |
| 标准 clone | 已恢复在 `<standard-clone>/` |
| 已验证基线 HEAD | `1071f713e9026e8063b3ba7b6f09985c0ff99e02` |
| 当前提交状态 | 实现已迁入标准 clone 并完整复测，`main` 已 commit/push 且远端页面已核验；官方预检已在一个已 push 的干净 HEAD 上完整通过，Issue/accepted 回执尚无 |
| LICENSE 观察 | 仓库根未观察到可为全部内容授权的权威 LICENSE |

赛事 Starter Kit、题面和接口是参赛必需基础。没有 LICENSE 不等于可以自行选择许可证；对官方材料只做比赛所需修改，不作超范围再许可声明。

## 2. SCI-Pegasus 参考材料

| 项目 | 记录 |
|---|---|
| 本地文件 | 用户提供的附件 `sci-pegasus-main(2).zip`（绝对路径不进入仓库文档） |
| 大小 | 1,179,936 字节 |
| 修改时间 | `2026-08-19T00:29:24+08:00` |
| SHA-256 | `7306ACF30D33BA1A393660AFA23D3CAA05BDE2C28041641AC3BCA8090FF02CEE` |
| 只读参考副本 | `.codex_reference/sci-pegasus/`，不得进入正式依赖、迁移或提交 |
| LICENSE 状态 | 根目录未发现权威 LICENSE；参考包文档也提示许可表述曾冲突 |
| 可验证公共源 URL | 本次材料中未提供 |

因此不得将 SCI-Pegasus/Pegasus 宣称为 MIT、Apache、BSD、GPL 或其他具体许可，也不得把能读取本地附件解释为拥有公开再分发或再许可权。

## 3. 实际参考范围

只参考以下抽象设计思想：

- 有限 Agent 工作流与明确阶段；
- Provider/registry 分层；
- 不可信工具输入边界与 result admission；
- 错误分类、有界恢复和 secret redaction；
- 请求级 Workspace、原子 artifact 与 provenance；
- 工作台布局、进度和错误状态；
- 将多个职责表达为工作流阶段，而不是虚构多个独立 LLM Agent。

LoomQ 中的算法、数据模型、测试、文案、品牌和 UI 均围绕官方 Python 3.10 合同独立设计、独立命名和独立实现。

## 4. 明确未迁移

- SCI-Pegasus 的 TypeScript Agent loop、Next.js API、React 组件、CSS 或 SVG；
- MongoDB、GridFS、Repository、lease、恢复和长任务 Runner；
- NextAuth、用户/Cookie、支付、配额或模型数据库；
- 长期记忆、compaction、多身份/并发团队实现；
- OSS/媒体存储、文献检索、PDF/科研数据管线；
- Prompt、测试数据、图片、商标、品牌资产；
- `.env`、Key、Token、Cookie、数据库、日志或用户信息。

正式 UI 的 HTML/CSS/JavaScript/SVG 为本项目 clean-room 原创，不复制附件资产。

## 5. 本队已完成的独立贡献

以下已在标准 clone 实现、通过本地测试并推送到参赛 fork；最终是否计分仍取决于 Final Submission Issue、自动接收回执及评委验证：

- OpenQASM 2 子集 lexer、不可变 AST、parser、语义验证、规范化和序列化；
- SpinQ、OriginQ、Braket 三目标 emitter 与独立 round-trip parser；
- 标准库参考态矢、统一 counts schema 与 little-endian 归一化；
- 有界 OpenAI-compatible L2 工作流、确定性生成/修复/推荐与 L1 admission；
- Hybrid-QASM AST、参考解释器、寄存器分配和 Tiny RISC-V compiler；
- 隔离的 RISC-V `custom-0` 量子 ISA、扩展模拟器、demo 与差分测试；
- 标准库 loopback HTTP 工作台、本地静态 UI、请求级原子证据和浏览器 QA；
- SpinQ/OriginQ 安全 hardware runner、dry-run、runbook 和五件套证据契约。

当前统一验证为 Python 3.10.11、119/119 tests；L1 6/6、L2 stub 1/1、L3 1/1 均为公开/本地证据，不是隐藏或正式得分。hardware 23/23 仅为 dry-run/契约，不是 QPU。

## 6. Clean-room 规则

1. 先从官方 LoomQ 合同形成需求和测试；
2. 参考附件时只记录职责、边界与失败模式，不复制表达性源码或素材；
3. 用 Python 3.10 独立实现 LoomQ 特定接口；
4. 用官方公开 evaluator、自建独立回读/解释器与随机测试验证；
5. 文档明确区分官方文件、设计启发和本队新增代码；
6. 若未来迁移任何表达性材料，必须先取得书面许可，保留版权/许可证通知并单独审计。

## 7. 依赖与厂商边界

评分核心、UI、随机测试和 Bonus 使用 Python 3.10 标准库；`requirements.txt` 没有进入正式路径的第三方包。硬件 SDK 属于可选外部运行环境，不进入主 requirements 或离线 adapter import。

厂商名称仅用于描述比赛指定方言、能力表或可选 QPU 集成路径，不表示厂商背书。当前三个 `run()` target 都由 LoomQ reference statevector 执行；没有声称 SpinQ、OriginQ 或 AWS SDK 已在评分主链运行。

## 8. 发布与外部未决事项

- 对 Final Submission Issue 将引用的最终 HEAD 重跑官方 `prepare_submission.py` 并确认通过；
- 创建 Final Submission Issue 并等待 `submission:accepted`、归档 SHA-256 与 Artifact ID 回执；
- 在有 Docker 的 Linux/Python 3.10 环境冷构建；
- 获得 SCI-Pegasus/Pegasus 与官方仓库许可边界的书面确认（若需要超比赛用途发布）；
- 如要申报真机，取得账号并保存可追溯真实 QPU 证据；
- 在组委会正式 DeepSeek 环境复核 L2。

在依据充分前，不添加会错误覆盖官方 Starter Kit、参考材料或第三方内容的根 LICENSE。
