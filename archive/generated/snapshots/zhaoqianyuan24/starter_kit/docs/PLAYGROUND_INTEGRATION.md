# LoomQ Playground 集成说明

## 集成定位

本分支以师姐仓库 `upstream/main` 的提交
`735faff12f9bfbc6376751be255dc15b66c6f4aa` 为底座，在不替换比赛核心代码的前提下，增加了 LoomQ Playground 产品层。

Playground 提供自然语言生成实验、量子问答、OpenQASM 与电路预览、量子门解释、后端推荐、按选中后端运行和测量结果可视化。比赛正式入口和公开接口保持不变。

## 代码边界

### 独立新增的产品层

- `starter_kit/frontend/`：原生 HTML、CSS 和 JavaScript 前端。
- `starter_kit/product_service.py`：静态页面与 Playground API 服务，负责会话配置、实验生成、运行调用和结果整理。
- `starter_kit/start_playground.bat`：Windows 启动与 Python 运行环境检查。
- `starter_kit/Dockerfile.playground`、`starter_kit/.dockerignore`：Playground 独立容器入口，不替换比赛 evaluator 的 Dockerfile。
- `starter_kit/docs/PLAYGROUND_QUICKSTART.md`：首次使用说明。

### 对比赛核心的必要兼容增量

仅在 `starter_kit/l2/client.py` 增加了 request-scoped LLM 配置入口：

- Playground 可以按浏览器会话使用用户自己的 OpenAI-compatible API。
- 配置通过 `ContextVar` 隔离，请求结束后恢复，不修改全局 `os.environ`。
- CLI 和 evaluator 仍继续读取正式的 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL`。
- `adapter.agent_chat(prompt)` 等比赛公开函数签名没有改变。

没有创建第二套 L1/L2/L3，也没有用旧版 `starter_kit/` 覆盖师姐代码。

## 保持不变的正式文件与接口

- `starter_kit/adapter.py` 的公开接口。
- `starter_kit/submission.yaml` 的提交契约。
- `starter_kit/Dockerfile` 的 evaluator 环境。
- L1、L2、L3 的既有业务路径与后端路由。
- SpinQ、OriginQ、Braket 的统一运行结果结构。

Playground 只通过现有 `adapter.agent_chat()` 和 `adapter.run()` 接入比赛能力。

## 主要数据流

```text
浏览器 Prompt
  -> Product Service /api/generate
  -> adapter.agent_chat(prompt)
  -> L2 生成 QASM 或后端推荐
  -> 现有 parser/IR 校验
  -> Circuit/QASM/解释展示

用户选择 backend 与 shots
  -> Product Service /api/run
  -> adapter.run(qasm, backend_id, shots)
  -> canonical backend ID 路由
  -> 本地 L1 backend 或已配置的远程 provider
  -> counts 与测量结果展示

用户提出概念或实验问题
  -> 前端统一输入的意图分流
  -> Product Service /api/ask（解释、概念、代码、测量问题）
  -> request-scoped LLM 配置 + 量子导师提示词
  -> 当前 QASM、步骤和 counts 上下文
  -> 中文解释返回到问答记录

用户提出生成、创建、构建或演示请求
  -> 前端统一输入的意图分流
  -> Product Service /api/generate
  -> adapter.agent_chat(prompt)
  -> L2 生成 QASM 或后端推荐
```

## 三个平台真机接入边界

赛事要求的是“同一套中间层统一适配多平台”，因此真机接入不新增第二个提交器，也不让 L2 直接调用某一家 SDK。当前实现的边界是：

```text
L2 backend recommendation
  -> canonical backend_id
  -> Product Service /api/run
  -> adapter.run(qasm, backend_id, shots)
       |-- spinq_cloud_qpu -> hardware/api.py -> hardware/spinq.py
       |-- originq_wukong  -> hardware/api.py -> hardware/originq.py
       `-- braket_cloud    -> hardware/api.py -> hardware/braket.py
```

三个 provider 适配器只做平台相关工作：加载官方 SDK、读取进程环境凭证、提交/轮询任务、提取 `job_id` 和 counts，并通过 `hardware/common.py` 归一化为比赛统一结果 Schema。公开的 `adapter.run(qasm, target, shots)` 仍兼容 `spinq`、`originq`、`braket` 三个 L1 平台 target；Playground 使用的六个规范后端 ID 只是附加路由，不改变正式 evaluator 合同。

| 规范 ID | 适配器 | 真机/云端配置 | 默认无真机时的行为 |
|---|---|---|---|
| `spinq_cloud_qpu` | `hardware/spinq.py` | `spinqit-mcp-tools`、`PRIVATEKEYPATH`、`SPINQCLOUDUSERNAME`、真实 `LOOMQ_SPINQ_PLATFORM`；官方提交器固定 1000 shots | 回退 `spinq_taurus_simulator` |
| `originq_wukong` | `hardware/originq.py` | `pyqpanda`、`LOOMQ_ORIGINQ_API_TOKEN`，可选芯片和轮询参数 | 回退 `originq_local_simulator` |
| `braket_cloud` | `hardware/braket.py` | `amazon-braket-sdk`、设备 ARN、S3 结果位置和 AWS 凭证 | 回退 `braket_local_simulator` |

回退是 Product Service 的运行时安全策略：`LOOMQ_REMOTE_FALLBACK` 默认为 `local`，远端依赖或凭证未就绪时不会向云端发起任务，而是查找已就绪的本地模拟器；成功响应会附带 `fallback: true`、`requested_backend_id` 和 `fallback_reason`。真机证据必须使用没有 `fallback` 的真实 provider 结果；需要严格模式时设置 `LOOMQ_REMOTE_FALLBACK=error`。

因此接入任一家真机的操作固定为：安装对应依赖 → 在同一 Product Service 进程配置凭证 → 重启服务 → 让 L2 推荐或手动选择规范 ID → 点击统一的 `Run Experiment` → 保存 provider 返回的 `job_id`、实际 QASM、shots 和原始 JSON。详细环境变量与证据命名见 [`HARDWARE_QUICKSTART.md`](HARDWARE_QUICKSTART.md) 和 [`../evidence/README.md`](../evidence/README.md)。

## LLM 配置优先级与安全边界

```text
当前浏览器会话配置
  > 服务端完整 LOOMQ_LLM_* 环境变量
  > 未配置
```

用户 API Key 仅保存在 Product Service 进程内存中的随机浏览器会话里，不写入源码、Git、日志或 `localStorage`，也不会由配置查询接口返回。服务重启后，会话 Key 自动失效。

问答上下文只包含当前页面公开展示的实验资料和对话历史，不包含 API Key；服务端会限制问题、历史和上下文长度，并拒绝把 `LOOMQ_TASK` / `LOOMQ_ACTION` 协议内容当作普通回答展示。

## 后续同步 upstream 的原则

1. 始终以新的 `upstream/main` 为底座构造集成版本。
2. 不整体替换 `starter_kit/`，只迁移 Playground 产品增量。
3. 若 upstream 已提供等价能力，优先适配正式接口。
4. 若 `starter_kit/l2/client.py` 同一区域发生变化，应人工审查 request-scoped 配置兼容性，不自动选择 ours/theirs。
5. 每次同步后重新验证 L1、L2、L3，以及 Generate、Circuit、Backend、Run、Measurement 完整链路。

## 启动与验证

首次试玩请参阅 [Playground 快速开始](PLAYGROUND_QUICKSTART.md)。Windows 环境可从仓库根目录运行：

```powershell
starter_kit\start_playground.bat
```

然后访问 `http://127.0.0.1:4173/`。不要直接通过 `file://` 打开 `starter_kit/frontend/index.html`。
