# QuantumHelper 工程与产品化说明

## 1. 产品定位

QuantumHelper 是一套面向量子计算初学者、跨学科使用者和量子软件开发者的本地 Web Agent。它把“用自然语言描述目标”连接到“可检查、可转译、可运行的量子线路”，同时保留开发者需要的标准 OpenQASM 2.0、目标后端代码、校验状态和运行来源。

产品遵循一条清晰边界：模型负责理解意图、生成候选内容和组织解释；`starter_kit/adapter.py` 负责解析、转译和执行等确定性工作。模型返回的线路不会直接执行，浏览器保存的“已检查”状态也不会被服务端直接信任。

### 目标用户

| 用户 | 核心需求 | QuantumHelper 提供的价值 |
|---|---|---|
| 量子计算初学者 | 不会 QASM，也不知道从哪个算法开始 | 自然语言入口、任务摘要、线路图、逐门解释和友好错误恢复 |
| 跨学科研究者与教学演示者 | 快速验证一个小型量子线路思路 | 从问题描述到本地模拟结果的一页式闭环，并明确能力边界 |
| 量子软件开发者 | 核对统一源码与不同后端语法 | 同时展示标准 OpenQASM 2.0 和 SpinQ、OriginQ、Braket adapter 产物 |
| 评审与工程维护者 | 可复现、可审查、可回归 | 明确模块边界、命令化测试、Docker 构建和安全配置说明 |
| 混合量子程序开发者 | 验证经典控制与量子指令扩展 | L3 编译路径、custom-0 量子 RISC-V 编码和轻量模拟器 |

## 2. 已实现的产品能力

- 自然语言生成、修改、解释和修复量子线路。
- 导入并检查 OpenQASM 2.0。
- 基于真实 operation 数据绘制线路，不依赖固定 Bell/GHZ 图片模板。
- 同时展示标准 OpenQASM 2.0 和当前所选后端的 adapter 代码：SpinQ 为 OpenQASM 2.0、OriginQ 为 OriginIR、Braket 为 OpenQASM 3.0。
- 根据 `starter_kit/backend_capabilities.json` 做确定性后端匹配，区分“推荐运行环境”“本地执行目标”和“结果来源”。
- 通过 `adapter.run()` 在 `spinq`、`originq`、`braket` 三个本地目标执行并显示真实 counts。
- 支持无测量线路：线路仍可检查和阅读；只有包含测量时才启用结果预览和 counts 可视化，系统不会伪造结果。
- Repair 先展示建议，用户确认后再通过 `/api/check` 校验并提交新 revision。
- 用 request ID、task ID、QASM version、revision 和 AbortController 阻止迟到响应覆盖当前任务。

当前网页是本地演示和比赛评测产品，不是多租户 SaaS，也不直接提交真实量子云任务。

## 3. 构建与启动

### 3.1 环境要求

- 推荐 Python 3.10；当前代码兼容项目测试所覆盖的 Python 3.x 环境。
- 基础网页、QASM 检查和内置本地模拟回退只依赖 Python 标准库。
- Node.js 仅用于前端 reducer/语法测试，不是启动网页的必需条件。
- 完整第三方量子 SDK 环境由 `starter_kit/requirements.txt` 定义，所有依赖均精确锁定。

以下命令中的“仓库根目录”指包含 `starter_kit/` 的目录，不依赖压缩包或本机文件夹名称。

### 3.2 无模型的确定性启动

在仓库根目录运行：

```powershell
python starter_kit\quantumhelper_web\server.py
```

如果当前目录已经是评测归档中的 `starter_kit/`：

```powershell
python quantumhelper_web\server.py
```

终端会输出类似：

```text
QuantumHelper running at http://127.0.0.1:8000
```

浏览器入口：

- 主工作台：<http://127.0.0.1:8000/>
- 健康检查：<http://127.0.0.1:8000/api/health>
- 本机模型配置页：<http://127.0.0.1:8000/config.html>

不要直接双击 `static/index.html`；页面依赖同源 API 和服务端 adapter。

### 3.3 启用自然语言 Agent

比赛和部署环境应在同一个 PowerShell 窗口安全注入配置：

```powershell
$env:QUANTUMHELPER_ENABLE_LLM = "1"
$env:LOOMQ_LLM_BASE_URL = "https://组委会提供的兼容接口"
$env:LOOMQ_LLM_API_KEY = "由组委会安全注入"
$env:LOOMQ_LLM_MODEL = "组委会指定模型"
$env:LOOMQ_LLM_TIMEOUT_SECONDS = "120"
python starter_kit\quantumhelper_web\server.py
```

配置来源优先级是：网页运行时配置 → `LOOMQ_LLM_*` 环境变量 → 未配置。可选的 `starter_kit/quantumhelper_web/.env` 只补充进程中尚未存在的允许字段，因此真实系统环境变量不会被 `.env` 覆盖。`.env` 和 API Key 都不得进入 Git、镜像、截图或聊天记录。

### 3.4 Docker 构建与启动

Web 镜像使用 `starter_kit/` 作为构建上下文。在仓库根目录执行：

```powershell
docker build -f starter_kit\quantumhelper_web\Dockerfile -t quantumhelper-web starter_kit
docker run --rm -p 8000:8000 quantumhelper-web
```

启用 Agent 时通过环境变量或部署平台 Secret 注入，不把凭证写入 Dockerfile：

```powershell
docker run --rm -p 8000:8000 `
  -e QUANTUMHELPER_ENABLE_LLM=1 `
  -e LOOMQ_LLM_BASE_URL `
  -e LOOMQ_LLM_API_KEY `
  -e LOOMQ_LLM_MODEL `
  quantumhelper-web
```

`starter_kit/Dockerfile` 是完整评测依赖镜像，默认入口为 evaluator；`starter_kit/quantumhelper_web/Dockerfile` 是轻量 Web 启动镜像。两者用途不同。

## 4. 主要模块

| 模块 | 实际路径 | 职责 |
|---|---|---|
| 统一 adapter | `starter_kit/adapter.py` | OpenQASM 解析、三目标转译、本地运行、L2 客观入口、L3 编译和 Bonus 编码 |
| Web 服务 | `starter_kit/quantumhelper_web/server.py` | 静态页面、同源 API、输入限制、QASM 再校验、运行编排和安全响应头 |
| Agent 路由 | `starter_kit/quantumhelper_web/web_agent.py` | 意图识别、量子问答、当前线路上下文和安全降级 |
| 后端选择 | `starter_kit/quantumhelper_web/backend_selector.py` | 根据能力表匹配硬约束与偏好，不让模型自由编造后端 ID |
| 模型配置 | `starter_kit/quantumhelper_web/runtime_config.py` | 运行时/环境变量配置解析、密钥最小暴露和请求上下文隔离 |
| 模型传输 | `starter_kit/llm_client.py` | OpenAI-compatible 请求；不判断量子线路正确性 |
| 单页工作台 | `starter_kit/quantumhelper_web/static/index.html`、`starter_kit/quantumhelper_web/static/app.js` | 对话、线路、双代码视图、后端、运行和结果呈现 |
| 前端状态 | `starter_kit/quantumhelper_web/static/workspace-state.js` | session schema、revision gate、转译产物版本绑定和错误恢复 |
| 后端事实 | `starter_kit/backend_capabilities.json`、`starter_kit/backend_capabilities.md` | 可审查的后端能力数据与说明 |
| IR 合同 | `starter_kit/target_ir_contract.md` | SpinQ、OriginQ、Braket 目标输出规范 |
| RISC-V 扩展 | `starter_kit/riscv_emulator.py`、`starter_kit/quantum_riscv_extension.md` | 经典子集执行、自定义量子指令解码与编码规范 |
| 评测与测试 | `starter_kit/evaluator.py`、`starter_kit/test_*.py` | L1/L2/L3 公开评测与工程回归 |

### 请求链路

```text
浏览器 index.html / app.js
  → POST /api/chat
  → server.py + web_agent.py 理解任务
  → adapter.agent_chat() 生成候选内容
  → adapter.parse_qasm() + adapter.transpile() 确定性校验
  → 标准 OpenQASM 2.0 + 三目标 adapter 产物 + operation 数据
  → workspace-state.js 按 QASM version 原子保存
  → 用户选择本地目标
  → POST /api/check → POST /api/run
  → adapter.run() → counts → 来源标识与柱状图
```

## 5. 完整使用流程

### 5.1 自然语言工作台

1. 按第 3 节启动服务并打开主工作台。
2. 输入目标，例如 `生成一个 3 比特 GHZ 态并进行全测量`。
3. 先核对“当前任务”，确认目标、量子比特数和测量范围符合意图。
4. 查看线路图和逐门解释；点击或聚焦门可联动相关步骤。
5. 查看“线路检查”。模型候选必须通过 adapter 解析和三目标转译才会显示为有效。
6. 展开“电路代码”，左侧核对标准 OpenQASM 2.0，右侧核对当前执行目标的 adapter 代码。
7. 查看推荐运行环境及理由；推荐真机与网页实际可运行的本地模拟器严格分开。
8. 若线路包含测量，选择 SpinQ、OriginQ 或 Braket、设置 shots，并进行本地预览。
9. 核对 bitstring、count、百分比、shots 和结果来源。页面明确标记本地模拟结果不是真机实验。
10. 若线路没有测量，线路仍是合法工作成果；页面说明只有加入测量后才会产生 counts 和可视化。
11. 在左侧继续要求修改或提问。修改会生成新 revision，解释类问题不会改写线路。

### 5.2 修复流程

1. 粘贴错误线路或用自然语言说明问题。
2. 系统展示诊断和 Repair 建议，不直接覆盖现有线路。
3. 用户选择“应用修复”后，服务重新调用 `/api/check`。
4. 只有通过检查的修复才提交为新 revision；失败时保留原线路和用户输入。

### 5.3 OpenQASM 导入流程

```text
首页 → 导入 OpenQASM → /api/check → 查看线路摘要
     → 选择本地目标 → /api/run → 测量分布
```

无测量的导入线路可以通过检查，但不会进入结果可视化；这是“没有经典读出”，不是语法错误。

### 5.4 无模型降级流程

没有 LLM 配置时，自然语言 Agent 会明确提示配置缺失；OpenQASM 导入、线路检查、三目标转译、本地模拟和确定性教学示例仍可使用。

## 6. 可靠性与安全边界

- 请求体最大 128 KiB；Web 最多处理 12 个量子比特、2000 个操作、10000 shots。
- 单进程按 IP 每分钟最多 60 个 API 请求，本地运行最多 4 个并发槽。
- 服务端重新解析 `context.current_qasm`，不信任浏览器的校验结论或展示代码。
- adapter 展示产物同时绑定 QASM 文本和版本，迟到的转译结果不能覆盖新线路。
- 运行始终以标准源码和所选目标重新校验、转译；前端展示的后端代码不是可信执行输入。
- API Key 只存在于服务端环境或进程内存；配置状态只返回 `api_key_present`。
- 模型配置管理接口同时限制回环客户端与本机 Host，降低远程访问和 DNS rebinding 风险。
- 静态路径被限制在 `starter_kit/quantumhelper_web/static/`，响应设置 CSP、DENY frame、nosniff、同源资源策略和权限策略。
- 多实例生产部署仍需补充身份认证、TLS 终止、共享限流/会话、集中 Secret 管理和可观测性。

## 7. 测试、验收与复现

在仓库根目录运行：

```powershell
python -m pytest -q
node starter_kit\quantumhelper_web\static\workspace-state.test.js
node --check starter_kit\quantumhelper_web\static\workspace-state.js
node --check starter_kit\quantumhelper_web\static\app.js
python starter_kit\test_l2_readiness.py
python -m unittest starter_kit.test_l3_bonus -v
python starter_kit\evaluator.py --level l1 --target spinq,originq,braket --shots 8192
python starter_kit\evaluator.py --level l3
```

人工闭环至少检查：

1. 生成全测量 GHZ，确认任务、图示、标准代码和三目标转译一致。
2. 切换 SpinQ、OriginQ、Braket，确认 adapter 代码语法与目标对应。
3. 运行带测量线路，确认 counts、shots、目标名称和来源一致。
4. 生成无测量线路，确认检查通过、预览禁用，并显示“只有测量才有可视化”的说明。
5. 应用一次 Repair，确认应用前不覆盖、应用后重新校验。
6. 测试无模型、错误模型配置和正常配置，确认确定性功能不受影响且错误不泄露密钥。
7. 刷新、返回首页、继续任务和新建任务，确认有效状态恢复且旧错误/旧结果不污染当前任务。

## 8. 文档与证据索引

- 项目与评测入口：`starter_kit/README.md`
- Web 技术说明：`starter_kit/quantumhelper_web/README.md`
- Web 新手操作：`starter_kit/quantumhelper_web/操作指南.md`
- L2 交互复现：`starter_kit/evidence/files/l2-interaction/l2-interaction.md`
- 新手与视觉叙事：`starter_kit/evidence/files/beginner-visual-guide/QuantumHelper_新手引导与视觉体验设计说明.md`
- 量子 RISC-V Bonus：`starter_kit/evidence/files/quantum-riscv-bonus.md`
- 人工评分总索引：`starter_kit/evidence/README.md`

## 结语

QuantumHelper 的产品化重点不是增加更多按钮，而是建立一条用户能理解、开发者能核对、评审能复现的可信路径：自然语言降低第一次尝试的门槛，确定性 adapter 守住正确性，版本化状态守住一致性，清晰的结果来源和安全边界守住用户预期。
