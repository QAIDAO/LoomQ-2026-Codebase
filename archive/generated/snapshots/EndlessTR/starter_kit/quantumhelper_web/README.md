# QuantumHelper Web

QuantumHelper Web 是 LoomQ 提交包中的零基础用户入口。当前首页采用 Agent First 单页工作台，
连接同一份 `starter_kit/adapter.py`，让用户通过自然语言生成、解释和修复量子线路，确定性选择
后端，并在电路包含测量时于同一页面运行线路、查看真实测量分布。旧 Bell、OpenQASM 导入和教学页面仍作为兼容入口保留。

网页已放在正式提交根目录 `starter_kit/` 内，不维护另一份 adapter，也不会把 API Key 写入前端。

## 当前能力

### LoomQ Agent

主入口：<http://127.0.0.1:8000/>

兼容入口：<http://127.0.0.1:8000/agent.html>（会引导回主工作台）

网页直接调用：

```text
index.html → POST /api/chat → 网页展示适配层 → adapter.agent_chat(prompt)
```

覆盖赛题 L2 的三类任务：

- 自然语言生成：根据用户意图生成 OpenQASM 2.0。
- 纠错与修复：在保持用户声明目标的前提下修复错误线路。
- 智能选后端：根据比特数、排队、费用等约束返回官方规范后端 ID。

Agent 返回的 QASM 不会直接执行。服务会再次调用 `adapter.parse_qasm()`，并对 SpinQ、OriginQ、
Braket 三个 L1 目标执行 `adapter.transpile()` 校验。工作台随后基于真实 operation 序列动态绘制
线路与逐门解释；不再根据 Bell 或固定比特数套用线路模板。支持全测量和指定量子比特的部分测量，
未知但可解析的门仍会正常绘制，并使用保守解释。没有测量的电路同样可以通过校验、查看线路与目标代码；
但它不会产生经典 counts，页面会禁用本地结果预览并解释“电路不一定要测量，只有测量后才能看到可视化结果”。

Repair 结果先进入“修复建议”，不会静默覆盖当前线路。用户点击“应用修复”后，网页会调用
`/api/check` 再次校验，成功才原子提交新 revision。后端规范 ID 最终由 adapter 内部能力表和
确定性 matcher 决定，网页只展示约束、匹配理由、未满足条件和本地可运行性。

当前会话使用单一、带版本的 `sessionStorage` 状态。请求通过 request ID、task ID、revision 和
AbortController 防止迟到响应覆盖新线路。支持 `GHZ 3 → 改成 5 比特 → 为什么需要 H` 的多轮流程；
解释轮次只读当前线路，不改变 revision。

后端信息明确分为三层：`recommendedBackend` 是系统建议的运行环境，`executionBackend` 是网页本次
实际调用的本地目标，`resultSource` 是当前图表的数据来源。若推荐真机无法由本地 adapter 直接提交，
页面只提供保守的继续操作指南，不显示“运行真机”按钮；本地结果会明确标注为模拟预览。

### OpenQASM 导入与运行

用户可以粘贴或上传 OpenQASM 2.0。网页会展示量子比特数、操作数、测量情况和双比特门数量，
同时展示标准 OpenQASM 2.0 与当前执行目标对应的 adapter 代码。电路包含测量时，网页可调用
`adapter.run()` 在选定的本地目标上执行，并使用 adapter 返回的实际 `counts` 绘制结果；没有测量时只做检查、转译与阅读，不伪造空分布。

当前可选执行目标：

- SpinQ 本地目标：`spinq`
- OriginQ 本地目标：`originq`
- Braket 本地目标：`braket`

网页不会使用或提交真机凭证，三个选项均为本地执行路径。

### 教学演示

首页提供两比特关联示例，以及查找、优化、测量、关联四类场景说明。场景线路是经过 adapter
校验的教学模板，用于解释流程，不代表已经实现通用 Grover 搜索、完整 QAOA 或用户业务求解。

## 页面流程

### 1. Agent 工作台

```text
自然语言输入 → Conversation + Workspace
              ├→ 任务理解 → 动态线路 → 逐门解释 → 真实校验 → 标准代码 + 目标 adapter 代码
              ├→ Repair 建议 → 用户应用 → 再校验 → 原子提交
              ├→ 确定性后端推荐 → 运行设置
              └→ /api/check → [含测量] /api/run → 真实 counts 图表
```

适合现场评测的三个任务：

1. `生成一个 3 比特 GHZ 态并进行全测量`
2. `我想制备一个贝尔态，但这段代码报错了，请修复：H q[0]; CX q[0] q[1]`
3. `我需要运行一个 15 比特电路，要求零排队并且免费，请选择后端`

### 2. 已有线路流程

```text
首页 → 导入 OpenQASM → adapter 检查 → 标准/目标代码 → 选择本地目标 → [含测量] 运行与测量分布
```

### 3. 新手示例流程

```text
首页 → 理解两比特关联任务 → 查看 H/CX/测量 → 本地运行 → 读取 00/11 分布
```

## 零基础操作指南

### 创建并理解一条线路

1. 打开首页，在大输入框用日常语言描述目标。普通 Enter 换行，`Ctrl+Enter` 或 `Cmd+Enter` 提交。
2. 可以先试：`生成一个 4 比特 GHZ 态，只测量前两个量子比特`。
3. 提交后左侧保留对话，右侧依次显示任务、线路、步骤解释、校验、电路代码、运行环境和结果。
4. 线路符号中，`q` 表示量子比特，`●` 是受控门的控制端，`⊕` 是目标端；竖线表示二者属于同一个
   双比特操作。`M→c0` 表示把该量子比特的测量值写入经典位 `c0`。只有出现 `M` 的线路会被读取。
5. 鼠标悬停、点击门，或用键盘聚焦门，可以联动高亮对应解释。较长线路在卡片内部横向滚动，
   不会把整页撑宽或裁掉后半段。
6. 展开“查看标准代码与后端代码”可复制标准 OpenQASM 2.0 和当前执行目标对应的 adapter 代码；切换执行目标时后端代码同步更新。标准代码、图示和解释都来自同一份解析后的 operation 数据。
7. 没有 `M`/`measure` 的电路仍可检查和转译，但不会产生经典统计结果；结果区会给出说明，不把“没有结果”显示成运行故障。

### 多轮修改

在当前任务下方继续输入即可，例如先生成 Bell 态，再输入 `只测量第一个量子比特`。系统会保留原门
序列，只修改测量、重新校验，并生成新的 revision。解释类问题（例如 `为什么需要 H`）只回答当前
线路，不会改写线路。

### 读懂推荐、执行和结果

- “推荐运行环境”回答的是：如果要正式执行，系统建议去哪里。
- “本地结果预览”回答的是：QuantumHelper 当前实际能直接调用哪个本地模拟器。
- “结果来源”回答的是：柱状图具体来自哪个执行目标。

若推荐项是真机但显示“当前不能直接提交”，请展开“如何在真机上继续”。按照平台当前的任务提交
流程使用工作台中的 QASM；网页不会编造平台按钮或代替用户提交真机凭证。本地预览按钮只运行项目
已有的 `spinq`、`originq` 或 `braket` 本地目标。结果区会明确写明模拟器名称、shots，以及“不是
真机实验结果”。

### 返回首页与新建任务

- 点击左上 Logo 或“← 返回首页”：回到 landing page，但当前会话保留；点击“继续当前任务”可恢复。
- 浏览器 Back/Forward：使用 SPA history 切换首页与工作台，不依赖刷新。
- 点击“＋ 新建任务”：先中止未完成请求，再清空对话、线路、后端和结果，shots 恢复为 1024。

### 错误与恢复

页面会先显示面向新手的影响说明，并保留原输入和上一次有效线路。需要排错时展开“技术详情”查看
真实错误码。部分测量范围必须明确，例如“前两个”“q0 和 q2”或“全部”；无法可靠理解时系统会
要求改写，不会猜测，也不会返回服务器 500。

## CASE 1–5 现场验收步骤

1. 输入 `生成一个 4 比特 GHZ 态，只测量前两个量子比特`：应显示 4 条 wire、1 个 H、3 个 CX，
   且只有 q0/q1 有测量。
2. 输入 `生成一个 6 比特 GHZ 态并全部测量`：应动态显示 6 条 wire 和 6 个测量，不依赖 3 比特模板。
3. 先输入 `生成一个 Bell 态`，再输入 `只测量第一个量子比特`：QASM、图示、解释、校验应一起更新。
4. 请求一个本地不可直跑的真机：推荐卡应提示不能直接提交；下方只提供本地模拟预览，结果明确标为
   模拟来源，并提供保守的真机继续指南。
5. 进入任意任务后分别尝试 Logo、返回首页、浏览器 Back/Forward、继续当前任务和新建任务；新建后
   不应残留旧结果，shots 应为 1024。

## 快速启动

要求：Python 3.10 或兼容版本。基础页面、线路检查和本地运行使用 Python 标准库即可。

在仓库根目录运行：

```powershell
python starter_kit\quantumhelper_web\server.py
```

如果当前目录就是正式评测解压后的 `starter_kit/`：

```powershell
python quantumhelper_web\server.py
```

打开：

- 首页：<http://127.0.0.1:8000/>
- 兼容旧 Agent 链接：<http://127.0.0.1:8000/agent.html>（会回到主工作台）
- 健康检查：<http://127.0.0.1:8000/api/health>

不要直接双击 HTML 文件。页面依赖同源 API、服务端脚本注入和 adapter，必须通过服务访问。

可指定监听地址和端口：

```powershell
python starter_kit\quantumhelper_web\server.py --host 127.0.0.1 --port 8080
```

局域网访问时可以使用 `--host 0.0.0.0`，并仅开放确有需要的防火墙端口。

## 启用真实 Agent

Agent 默认关闭，避免无意消耗模型额度。PowerShell 配置示例：

```powershell
$env:QUANTUMHELPER_ENABLE_LLM="1"
$env:LOOMQ_LLM_BASE_URL="https://你的 OpenAI-compatible 接口"
$env:LOOMQ_LLM_API_KEY="你的密钥"
$env:LOOMQ_LLM_MODEL="模型名称"
$env:LOOMQ_LLM_TIMEOUT_SECONDS="120"
python starter_kit\quantumhelper_web\server.py
```

本机长期使用时，可将 `starter_kit/quantumhelper_web/.env.example` 复制为同目录下的 `.env` 并填写配置；
如果当前目录已经是解压后的 `starter_kit/`，对应路径为 `quantumhelper_web/.env.example`。
服务启动时会读取该文件，真实系统环境变量优先级更高。`.env` 已被 Git 忽略、位于静态文件目录之外，
不会通过网页提供；仍应将它视为敏感文件，不要上传、截图或分享。配置页面保存的密钥只对当前进程
有效，保存动作本身会显式启用本次运行的模型，并在保存后立即清空表单中的密钥。

远程模型地址必须使用 HTTPS；只有 `localhost`、`127.0.0.1` 和 `::1` 允许使用 HTTP。
模型配置的查看、修改、清除和连接测试接口同时要求回环客户端地址与本机 `Host`，以降低远程访问和 DNS 重绑定风险。容器或远程部署应通过
平台 Secret/环境变量注入，不应依赖配置页面。

正式 L2 评测由组委会注入 `LOOMQ_LLM_*` 配置。密钥只应存在于服务端环境变量中，不要写入
HTML、JavaScript、Git、截图或聊天记录。

未启用模型时，Agent 页面会给出明确提示；教学演示、QASM 导入、线路检查和本地运行仍可使用。

## API

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/health` | 服务状态、LLM 开关与运行限制 |
| `GET` | `/api/backends` | 网页允许使用的三个本地 adapter 目标 |
| `GET` | `/api/config/status` | 仅在服务器本机读取脱敏后的模型配置状态 |
| `POST` | `/api/config` | 仅在服务器本机保存本次进程的模型运行时配置 |
| `POST` | `/api/config/test` | 仅在服务器本机测试尚未保存的模型配置 |
| `DELETE` | `/api/config` | 仅在服务器本机清除本次进程的模型运行时配置 |
| `POST` | `/api/chat` | 调用 `adapter.agent_chat()` 并识别 QASM、后端 ID 或文本结果 |
| `POST` | `/api/check` | 解析线路并转译到三个 L1 目标，返回结构摘要 |
| `POST` | `/api/run` | 调用 `adapter.run(qasm, target, shots)` |
| `POST` | `/api/plan` | 生成经过 adapter 校验的离线教学模板 |

所有 POST 接口使用 `application/json`。新版 `/api/chat` 在保留旧 `{prompt}` 和旧响应字段的同时，
可接收 `schema_version/request_id/session_id/task_id/base_revision/context`，并返回结构化 task、circuit、
validation、explanation、repair 和 backend 展示数据。`context.current_qasm` 会在服务端重新解析和转译，
不会信任浏览器提交的校验结论。除基于当前真实线路的本地解释外，Agent 任务需要
`QUANTUMHELPER_ENABLE_LLM=1`。

## 目录结构

```text
starter_kit/
├── adapter.py                    # L1/L2/L3 正式评测入口
├── backend_capabilities.json     # Agent 后端选择的官方能力表
├── test_quantumhelper_web.py     # 网页与 Agent API 回归测试
└── quantumhelper_web/
    ├── server.py                 # 同源 HTTP/API 服务
    ├── README.md                 # 本文件
    ├── Dockerfile
    ├── .env.example
    └── static/
        ├── index.html            # 首页
        ├── agent.html            # 兼容入口薄壳
        ├── app.js                # API、工作台渲染与旧页面兼容流程
        ├── workspace-state.js    # 版本化 session/reducer/revision gate
        ├── workspace-state.test.js # Node 状态与并发回归
        ├── styles.css            # 全站样式
        ├── example-*.html        # 新手示例流程
        ├── circuit-*.html        # 导入线路流程
        ├── custom-*.html         # 教学模板流程
        ├── backend.html          # 本地执行目标选择
        ├── scenario.html         # 四类任务场景说明
        └── task-adjust.html      # 信息不足时的补充引导
```

## Docker

Dockerfile 使用 `starter_kit/` 作为构建上下文。在仓库根目录运行：

```powershell
docker build -f starter_kit\quantumhelper_web\Dockerfile -t quantumhelper starter_kit
docker run --rm -p 8000:8000 quantumhelper
```

如果容器中需要启用 Agent，请通过安全的环境变量或部署平台 Secret 注入配置，不要把密钥写入镜像。

## 测试

网页与 Agent API：

```powershell
python -m unittest starter_kit.test_quantumhelper_web -v
node starter_kit\quantumhelper_web\static\workspace-state.test.js
node --check starter_kit\quantumhelper_web\static\workspace-state.js
node --check starter_kit\quantumhelper_web\static\app.js
```

相关回归：

```powershell
python starter_kit\test_l2_readiness.py
python -m unittest starter_kit.test_l3_bonus -v
python starter_kit\evaluator.py --level l1 --target spinq,originq,braket --shots 8192
```

网页测试当前覆盖：

- Agent First 首页与兼容入口只加载一份控制器；
- Agent QASM 重新经过 L1 校验并序列化为真实线路和解释；
- Repair proposal、应用前不覆盖和真实再校验；
- 后端规范 ID、完整/最接近/未验证匹配及 QPU 本地运行边界；
- `/api/check`、`/api/run`、shots 边界和真实 adapter counts；
- GHZ 3→5 多轮修改、H 门上下文解释和不可信 context 拒绝；
- reducer 的 stale response、Repair/Chat 交叉并发、Run/revision 和刷新恢复。
- 4/6 比特数据驱动 GHZ、部分/全/无测量、多轮测量修改、经典寄存器扩容与交错测量保护；
- 推荐/执行/结果来源边界，以及返回首页、新建任务、浏览器历史和运行被对话中止后的恢复。

测试数量以当前提交运行上述命令的输出为准，避免文档中的固定数字随回归用例增加而失效。自动测试之外，
正式演示前建议按上方 CASE 1–5 在目标浏览器人工走查一次，尤其检查长线路滚动、双比特门连接线和 360px 移动宽度。

## 安全与运行限制

- 请求体最大 128 KiB。
- 最多 12 个量子比特。
- 最多 2000 个线路操作。
- 每次最多 10000 shots。
- 每个 IP 每分钟最多 60 次 API 请求。
- 最多 4 个并发运行任务。
- 静态文件访问限制在 `static/` 目录内。
- 响应启用 CSP、`X-Frame-Options: DENY`、`nosniff`、同源 Referrer/Resource Policy，并禁用摄像头、麦克风和定位权限。
- 模型配置和真机凭证不会发送到浏览器。

这些限制适用于演示和现场评测入口，不等同于 adapter 或各量子平台的理论能力上限。

## 当前边界

- Agent 工作台当前会话保存在单一、带 schema version 的 `sessionStorage`；旧兼容页面仍使用各自的
  `localStorage` key。两者都不是多用户任务数据库。
- 限流状态保存在单个 Python 进程内，多实例部署需要外部共享限流服务。
- 网页只执行本地 adapter 目标，不提交真实量子云任务。
- `/api/plan` 是离线教学模板；真实自然语言能力只来自 `/api/chat` 和 `adapter.agent_chat()`。
- 正式 L2 得分仍取决于组委会模型环境和隐藏 Prompt，网页通过不能替代 `agent_chat()` 客观评测。
- 自动化 API、状态和语法测试均已覆盖；不同浏览器的 390/820/1440 像素级视觉效果仍建议在正式演示机
  上按实际字体与缩放设置人工走查一次。

## 赛题对应关系

- L1：导入 OpenQASM、三目标转译、统一运行结果和测量分布可视化。
- L2 客观接口：网页直接复用正式提交的 `adapter.agent_chat()`。
- L2 交互体验：为零量子背景用户提供生成、纠错、后端选择和错误恢复入口。
- 工程产品化：一条命令启动、同源无框架服务、Docker 构建和回归测试。
- 新手引导 Bonus：分步概念解释、线路可视化、实际 counts 图表和键盘焦点样式。
