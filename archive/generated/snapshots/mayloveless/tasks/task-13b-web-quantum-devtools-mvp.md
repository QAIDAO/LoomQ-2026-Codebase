# Task 13B：Web Quantum DevTools MVP

## 背景

Task 13A 已完成两层可复用 Trace：

- **Agent Trace**：模型生成、独立目标裁判、Parser、semantic verification、repair、backend selection；
- **Circuit Trace**：逐 gate 的 state before / after、概率、复振幅、measurement 与 warning。

CLI 已证明这套调试抽象成立，但 CLI 只是验证工具，不是最终体验。

现在开始做第一版 Web Quantum DevTools，让目标用户——**懂软件开发，但没有量子计算背景的 Web / AI / 应用开发者**——借用熟悉的 DevTools / Debugger 心智模型，看懂：

1. LoomQ 帮我生成了什么；
2. 电路每一步让量子状态发生了什么；
3. LoomQ 为什么认为结果正确。

本任务目标是先得到一版真实可操作的页面，供人工体验和后续 UX 迭代；不是比赛最终 polished 版本。

---

## UX 原则

### 1. Circuit Trace 是主角

默认体验顺序：

```text
我想做什么
→ LoomQ 生成了什么
→ 电路每一步发生什么
→ 为什么 LoomQ 认为它正确
→ 后续再考虑跑到哪里
```

不要让 `Intent / Target Judge / Fidelity / statevector` 等内部术语占据首页主视觉。

### 2. 像 DevTools，但不要像专业量子 IDE

视觉可以采用深色 IDE / DevTools 风格，但信息层级要面向量子新手：

- 首屏先看“当前步骤发生了什么”；
- 概率优先；
- complex amplitude 默认折叠；
- Agent Trace 默认压缩成“LoomQ 如何验证”；
- 不要求用户先理解量子术语才能操作。

### 3. 这一版是回放式 debugger

现有 Trace 是完整执行后得到事件，再由 UI 回放。

本任务保持这个模型：

```text
POST prompt
→ 后端完整执行 Agent + debug trace
→ 返回 reply + structured events
→ Web 前端逐步回放
```

不要为了“真的暂停模型执行”引入 SSE / WebSocket / streaming / 并发状态机。

---

# Part A：最小 Web 架构

仓库当前没有 Web 前端。本任务新增：

```text
starter_kit/web/
```

建议技术栈：

- Vite
- React
- TypeScript
- pnpm
- 原生 CSS / CSS Modules

不要为了第一版引入大型 UI 组件库、Tailwind、状态管理框架、图表框架或量子可视化库。

前端只负责展示和回放 Trace，不复制量子业务逻辑。

## Python debug API

新增一个极薄本地 API，例如：

```text
starter_kit/loomq/debug_web.py
```

优先使用 Python 标准库 HTTP server，避免为了 MVP 增加 Flask / FastAPI 依赖；如果现有仓库已经有等价轻量 HTTP 依赖可复用，也可以使用，但不要新增重框架。

至少提供：

```text
GET  /api/health
POST /api/debug
```

`POST /api/debug` 输入：

```json
{"prompt":"生成一个 Bell 态并测量"}
```

输出：

```json
{
  "reply": "...",
  "events": [TraceEvent...]
}
```

必须直接复用现有 `build_debug_trace(prompt)` / `TraceEvent.as_dict()` 或等价共享入口。

不要：

- 复制 `_run_agent()`；
- 复制 Circuit Trace；
- 自动读取 `.env.l2.local`；
- 把 API Key 返回给前端；
- 返回 Python traceback；
- 返回原始 LLM HTTP response。

开发环境继续由 shell 注入：

```bash
cd starter_kit
set -a
source .env.l2.local
set +a
python -m loomq.debug_web
```

Vite dev server 使用 proxy 将 `/api` 转发到本地 Python API，避免额外 CORS 复杂度。

本任务不要求把 Vite build 集成进正式 Docker；先保证本地开发体验成立。

---

# Part B：第一版页面结构

页面采用单页 DevTools 工作台。

## 1. 顶部：请求入口

包含：

- 产品名：`LoomQ Quantum DevTools`；
- 一句定位：例如“像调试普通代码一样，看懂量子程序每一步发生了什么”；
- 自然语言输入框；
- 主按钮：`开始调试`；
- 3 个示例快捷入口。

示例至少：

```text
生成一个 Bell 态并测量
生成一个 3 比特 GHZ 态并测量
生成一个带相对相位的 Bell- 态，不要求测量
```

用户点示例后只填入输入框或直接执行均可，选择实现更自然的一种。

加载时显示清晰中文状态：

```text
LoomQ 正在生成并验证量子程序…
```

不需要模拟实时阶段进度。

---

## 2. 主工作区：三栏

桌面宽度下建议：

```text
┌──────────────┬──────────────────────────┬──────────────────────┐
│ 调试步骤      │ QASM / 当前操作           │ 当前量子状态          │
│              │                          │                      │
│ Agent 概览    │ 当前 Gate                │ 发生了什么            │
│ Circuit Steps│ QASM Code                │ 概率分布              │
│              │                          │ 技术细节（折叠）       │
└──────────────┴──────────────────────────┴──────────────────────┘
```

不用精准复刻 Chrome DevTools，但要有明显的“调试器”心智模型。

### 左栏：调试步骤

分两块：

#### Agent 概览

默认只展示紧凑状态，不把原始 JSON 铺开：

```text
✓ 理解需求
✓ 生成电路
✓ 本地校验
✓ 语义验证
```

如果发生 repair，要明显展示：

```text
! 第一次结果未通过
✓ LoomQ 自动修复后通过
```

Agent 流程不是主导航，不要求用户逐个点击 Agent event。

#### Circuit Steps

从 `layer=circuit` 的事件生成主导航：

```text
1  H q[0]
2  CX q[0], q[1]
3  Measure
```

当前步骤突出显示。

`statevector_skipped`、`trace_stopped_after_measurement` 等 warning 要显示为警告项，而不是伪装成普通 gate。

---

### 中栏：当前操作 + QASM

顶部突出当前操作，例如：

```text
第 2 / 3 步
CX q[0], q[1]
```

下面展示完整 QASM，使用 monospace。

尽量在 UI 层根据 `operation_index` 高亮对应 executable statement；如果可靠映射会显著增加复杂度，可以第一版只显示“当前 Gate”卡片 + 完整 QASM，不要为了高亮修改 Trace 协议或 Parser。

不引入 Monaco Editor。

QASM 是只读展示，不做在线编辑器。

---

### 右栏：当前量子状态

这是第一版 UX 的重点。

#### 当前发生了什么

优先展示一段短中文解释：

- 使用现有 `gate_description`；
- 可以结合 `summary`；
- 不新增 LLM 调用；
- 不在前端硬编码 Bell/GHZ 的固定答案。

例如：

```text
H 门把原本集中的振幅重新分配，使量子位进入叠加。
```

#### 概率分布

默认只展示 state/probability，不展示复数振幅。

视觉使用简单水平概率条：

```text
|00>  ██████████  50%
|11>  ██████████  50%
```

使用 CSS 实现，不引入 chart library。

对于 gate step：

- 默认展示 `state_after`；
- 可以用很轻的“执行前 / 执行后”切换或小对比；
- 如果这个切换会拖慢实现，第一版优先展示“执行后”，并在下方用简短文字注明变化前后的主要差异。

对于 measurement：展示 `probabilities_before` 与 quantum → classical mapping。

#### 技术细节

默认折叠：

```text
展开技术细节
```

展开后才展示：

- complex amplitude；
- raw gate parameters；
- operation index。

不要让 `+0.707107+0.000000i` 成为新手首屏信息。

---

## 3. 底部调试控制

至少：

```text
[← 上一步]   第 2 / 3 步   [下一步 →]
```

可以增加 `重新播放 / 回到第一步`。

本任务不要求自动播放；如果实现只需几行状态逻辑可以加，否则不做。

不要做真正 breakpoint 配置、任意跳转断点、线程控制。

用户点击左栏某个 Circuit Step 可以直接跳到该步骤。

---

## 4. “LoomQ 如何验证”折叠区

Agent Trace 的技术价值不能丢，但不要占主界面。

在主工作区下方或侧栏提供折叠面板：

```text
LoomQ 如何验证这段程序？
```

展开后，将 Agent events 整理成人话步骤，例如：

```text
模型生成候选 QASM
↓
独立目标裁判提取目标态
↓
本地 Parser 通过
↓
本地 statevector 模拟
↓
Fidelity 1.000 ≥ 0.970，验证通过
```

明显区分：

- `模型`；
- `本地`。

如果发生 repair，展示第一次失败的 Fidelity / diagnostic（已清理）和一次修复结果。

不要直接 dump `event.data` JSON 给普通用户。

---

# Part C：特殊结果处理

## Backend selection

如果请求返回的是 backend selection，没有 Circuit Trace：

- 页面不要报错；
- 左栏展示 Agent / backend flow；
- 主区域展示满足约束的 canonical backend IDs 与理由；
- 不出现空的量子状态面板。

这是基本兼容，不需要为 backend 做完整产品设计。

## Warning

`statevector_skipped`：

```text
电路规模较大，当前教学调试器不展开 statevector；Agent 结果仍然有效。
```

`trace_stopped_after_measurement`：直接展示现有中文 warning。

## Error

API 失败时只展示中文安全信息，例如：

```text
这次调试没有完成，请检查模型配置后重试。
```

不要把 traceback、绝对路径、API key、Authorization、原始模型错误显示到浏览器。

---

# Part D：视觉要求

第一版就要有基本完成度，但不要过度 polish。

方向：

- 深色背景；
- IDE / DevTools 气质；
- monospace 用于代码 / basis state；
- Agent、Circuit、模型、本地用有限的视觉区分；
- 当前步骤突出；
- 概率条清楚；
- 中文正文易读，不要所有文字都 monospace；
- 桌面优先，建议主要适配 >= 1100px。

移动端本任务只要求不完全崩坏，不需要做好完整 responsive UX。

不要：

- 霓虹赛博朋克堆叠；
- 大量渐变；
- 复杂动画；
- 3D Bloch sphere；
- canvas 粒子效果；
- 为“量子感”牺牲可读性。

---

# Part E：实现边界

本任务允许：

- 新增 Web 前端；
- 新增 debug HTTP API；
- UI 层做 Trace → ViewModel 整理；
- 为 API 增加纯序列化 helper；
- 非侵入式测试 helper。

本任务不要修改：

- L2 system prompt / target judge prompt；
- pure-state guard；
- Fidelity 阈值；
- backend capability table / selection 规则；
- Parser / IR 语义；
- Circuit Trace 数值算法；
- `adapter.agent_chat()` 契约；
- `submission.yaml`。

正式评分路径仍必须保持：

- backend 1 次模型调用；
- QASM 正常 2 次；
- repair 最多 3 次；
- 正式 `agent_chat()` 不执行 Web Circuit Trace。

---

# Part F：开发命令

目标是给出简单清楚的本地运行方式。

建议：

终端 1：

```bash
cd starter_kit
set -a
source .env.l2.local
set +a
python -m loomq.debug_web
```

终端 2：

```bash
cd starter_kit/web
pnpm install
pnpm dev
```

Vite dev proxy 指向 Python debug API。

第一版允许两个进程启动；不要为了“一条命令”提前建设复杂进程管理。

---

# Part G：测试与验证

至少验证：

1. `POST /api/debug` 直接复用现有 Trace，不复制 Agent；
2. API 返回 JSON-serializable events；
3. API 错误不会泄露 traceback / API Key / absolute path；
4. Bell 请求能完整渲染 Circuit Steps；
5. previous / next / click step 能切换当前 gate；
6. 概率条按 `probability` 正确展示；
7. complex amplitude 默认隐藏，展开后可见；
8. measurement 能展示映射与测量前概率；
9. repair case 能在“LoomQ 如何验证”中看出失败 → 修复 → 通过；
10. backend selection 没有 circuit events 时页面仍能正常展示结果；
11. warning 不导致页面崩溃；
12. `pnpm build` 通过；
13. 原 Python 全量测试通过；
14. `python evaluator.py --level l2` 继续 PASS。

前端 MVP 不要求为了覆盖率引入完整测试框架。如果纯函数 ViewModel 很适合测试，可以加少量测试；不要为了测试体系拖慢页面实现。

---

# 手工体验用例

至少真实体验：

### A. Bell

```text
生成一个 Bell 态并测量
```

重点人工看：

- 第一次接触量子的人能否知道当前在哪一步；
- H 后能否直观看到概率从确定状态变为两个可能状态；
- CX 后能否看见 00 / 11 的结果结构；
- 默认页面是否没有被 complex amplitude 淹没。

### B. Bell-

```text
生成一个带相对相位的 Bell- 态，不要求测量
```

重点看：

- 概率相同的情况下，技术细节中仍能看到相位差；
- UI 不把“概率一样”错误解释为“状态一样”。

### C. Backend

```text
需要至少 15 比特、零排队的后端
```

重点看：

- 没有 Circuit Trace 也能正常给结果；
- 能看出“模型提取约束，本地决定 canonical ID”。

---

# 本任务明确不做

不要做：

- 真机提交按钮；
- 账号 / 登录；
- 历史会话；
- 多轮聊天；
- SSE / WebSocket；
- 实时模型 token streaming；
- 在线 QASM 编辑器；
- Monaco；
- Bloch sphere；
- 图形化线路编辑器；
- 完整量子课程；
- L3；
- 最终 evidence 文案；
- 比赛最终视频。

这些等第一版页面实际体验后再决定。

---

# 完成标准

Task 13B 完成时：

- 浏览器可输入 Prompt 调用真实 LoomQ debug API；
- Bell 可以从 H → CX → measurement 逐步回放；
- 当前 state 用中文 + 概率条展示；
- complex amplitude 默认隐藏；
- QASM 与当前 gate 同屏；
- Agent verification 可展开查看，并明确模型 / 本地边界；
- repair / backend / warning 基本可用；
- 页面已经有可评价的 DevTools 视觉雏形；
- 没有修改 L2 objective 规则；
- 全量回归和 public L2 evaluator 通过。

---

# 完成后汇报

只汇报：

1. Web 技术结构和新增目录；
2. debug API 入口与启动命令；
3. Bell 页面实际交互流程；
4. 三栏布局最终实现；
5. probability / amplitude / measurement 如何展示；
6. “LoomQ 如何验证”如何展示 Agent Trace；
7. repair / backend / warning 的处理；
8. `pnpm build`、Python tests、public L2 evaluator 结果；
9. 你认为第一版最明显的 3 个 UX 问题，先不要自行继续大改。

本任务结束时不要 commit、不要 push，等待人工体验和复核。
