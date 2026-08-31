# ADR-001：L2 引导式实验 Web 技术方案

- 状态：已采用
- 日期：2026-08-04
- 范围：`starter_kit/web/`

## 决策

首版采用 Python 3.10 标准库 `ThreadingHTTPServer`、原生 HTML/CSS/JavaScript、内存 `ExperimentStore` 和同源 JSON API。图形电路使用语义 HTML/CSS 渲染，结果柱状图同时提供等价数据表。数学表达使用 Unicode/文本，不增加外部字体或脚本。

领域边界保持不变：`loomq_l1.parse_qasm` 是语法和 IR 事实源，`l1_reference.distribution` 是断网本地模拟事实源，`backend_capabilities.json` 是后端事实源；`agent_chat()` 不承载 UI 会话状态。

## 理由与后果

- 干净 Python 环境一条命令启动，无包管理器、CDN、账号或网络依赖。
- 同源窄 API 可固定 session/revision、错误恢复和不可变运行快照。
- 原生控件、语义区域、可见焦点、live region、文本电路和数据表降低无障碍实现风险。
- 内存会话仅适合比赛演示与单机体验；进程重启后不持久化。首版明确不建设账户、数据库、多项目或云任务控制台。

## 安全与失败边界

服务默认只监听 `127.0.0.1`；限制 JSON 与 QASM 大小；静态路径经 resolve 校验；设置 CSP 和 `nosniff`。模型或真实后端不可用时，手动编辑、验证、修复和本地运行仍可用。
