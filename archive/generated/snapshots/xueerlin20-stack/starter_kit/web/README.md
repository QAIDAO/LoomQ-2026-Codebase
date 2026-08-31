# LoomQ Web 模块说明

网页保持零构建依赖，使用浏览器原生 ES Modules。`index.html` 是主入口，
`workspace.html` 是独立工作台，`styles.css` 负责共享视觉系统：

| 模块 | 单一职责 |
|---|---|
| `main.js` | 主界面组合根，只连接配置与新手引导 |
| `workspace.js` | 工作台组合根，连接对话、会话和实验进度 |
| `api.js` | `/api/config` 与 `/api/chat` 的 HTTP 客户端 |
| `conversation-session.js` | 保存会话 ID 与当前电路版本指针 |
| `concept-basics.js` | 零基础量子比特、门与测量互动演示 |
| `preferences.js` | 浏览器本地学习偏好 |
| `onboarding.js` | 首次配置、背景选择和步骤切换 |
| `quantum-lab.js` | Bell 电路互动教程状态机 |
| `chat.js` | 输入、请求生命周期和对话区更新 |
| `results.js` | QASM、counts、后端和错误结果渲染 |
| `journey.js` | 工作台实验进度叙事 |

后端模块位于 `starter_kit/web_backend/`：

| 模块 | 单一职责 |
|---|---|
| `configuration.py` | 本机环境配置读取、校验和安全写入 |
| `chat.py` | 对话载荷校验、多轮编排、讲解偏好和 Agent 调用 |
| `conversations.py` | 有时效的会话、有限轮次窗口和当前电路状态 |
| `context_builder.py` | 新建/修改/解释/运行分类与受限上下文构建 |
| `backend_presentation.py` | 将后端能力表转换为本地化、易读的展示字段 |
| `application.py` | 面向 HTTP 与测试的稳定业务门面 |
| `http.py` | API 路由、静态资源和安全响应头 |

`starter_kit/web_app.py` 仅保留命令行参数、服务生命周期和兼容导出。

## 扩展约定

- 新增浏览器功能时创建独立模块，并在对应页面的组合根中装配。
- 新增静态模块后，将资源路径加入 `web_backend/http.py` 的白名单。
- 新增 API 时先实现业务服务，再在 `http.py` 注册薄路由。
- 服务通过构造函数注入，测试不需要启动真实 HTTP 服务。
- `adapter.agent_chat()` 保持单轮评测契约；网页多轮能力只在外层编排。
