# Task 13G-2 — Global Navigation, Product Positioning, and Progressive UX

## 背景

Task 13G 已完成独立 Experiments 页面，但尚未最终验收。上游赛题现已明确：比赛为线上异步评测，不设置线下答辩、现场演示或口头解释；L2 完整分要求提供可由零基础用户直接操作的 Agent 入口。

因此，LoomQ 的页面本身必须能够独立解释产品定位、功能层级和下一步操作。

本任务在 13G 基础上收口全站信息架构与导航，不重做 Explorer 工作区，不实现 Repair / Backend 具体功能。

---

## 产品定位

LoomQ 面向：

> 有软件开发背景、但没有量子计算专业背景的开发者。

核心产品命题：

> 未来人人未必需要懂量子，但在今天，先让开发者能够借助 AI 跨过量子计算这道专业壁垒。

产品能力可概括为：

> 用自然语言生成、理解、验证和修复量子程序，并找到合适的运行平台。

注意：

- 不把 LoomQ 定位成“量子课程”；
- 不把 LoomQ 定位成专业 Quantum Debugger；
- 不把 LoomQ 定位成单纯 QASM Generator；
- AI 的价值是帮助开发者跨过专业知识壁垒，而不是要求用户先成为量子专家。

---

## 全站能力阶梯

全站固定形成以下 5 个层级：

```text
01 Learn
   基础：第一次认识量子程序

02 Experiments
   实验：看懂典型量子现象

03 Explorer
   创建：用 AI 生成并理解自己的量子程序

04 Repair · 进阶
   检查：检查和修复已有量子程序

05 Backend · 进阶
   运行：选择合适的量子运行平台
```

这 5 个入口应长期存在于站点全局导航中。

### 为什么 Repair / Backend 不能藏起来

它们是赛题 L2 明确要求的 Agent 能力，也是一个真实产品中熟练用户会直接使用的能力。

因此：

- 不要把 Repair / Backend 只放在某个页面底部；
- 不要要求用户先走完 Learn / Experiments 才能访问；
- 不要做成难发现的 Advanced Drawer；
- 可以通过 `04 / 05`、`进阶` 标签、较弱视觉色阶表达能力层级，但入口必须稳定可见。

“循序渐进”通过顺序、说明和视觉层级体现，而不是通过隐藏功能体现。

---

## 本任务范围

本任务完成：

1. 全局导航骨架；
2. Learn 首屏增加清晰产品定位；
3. Experiments 页面适配新全局导航；
4. Explorer 适配新全局导航；
5. Repair / Backend 先有清楚的导航入口与占位页，说明未来能力，但不实现真实功能；
6. 保持 13G 的 Bell / Grover / Phase 三个 Experiments 不变。

本任务不完成：

- Repair 真实输入 / 修复流程；
- Backend 真实约束提取 / 推荐流程；
- Explorer 信息层级重构；
- 实验完成态；
- Error Recovery 完整 UX；
- 真机运行入口；
- 新的 LLM 调用或后端 API。

---

## 全局导航

### 结构

在 Learn / Experiments / Explorer / Repair / Backend 页面保持统一导航。

建议显示：

```text
LoomQ

01 Learn
02 Experiments
03 Explorer
04 Repair   进阶
05 Backend  进阶
```

要求：

- 当前页面明确高亮；
- 数字编号是能力阶梯的一部分，不只是装饰；
- `进阶` 标签轻量，不要像警告或不可用状态；
- 中文主名优先，英文名可以弱化，不强制每项都显示；
- 导航不能占据过多纵向空间，不做大型侧栏；
- 桌面端可用顶部导航；移动端可折叠，但仍需容易访问；
- 不需要本任务引入 React Router，可以继续使用轻量 screen state；
- 不需要刷新后持久化当前页。

### 导航语义

不要写成：

- Learn / Playground / Debugger / Infra

优先保持用户能一眼理解的：

- Learn
- Experiments
- Explorer
- Repair
- Backend

每个页面内部再用中文副标题解释。

---

## Learn：同时承担 Landing + 新手入口

默认启动仍然进入 Learn。

但 Learn 第一屏不应立刻进入 qubit 教学，而要先回答：

> LoomQ 是什么？

### 首屏文案方向

主标题建议：

> 让开发者先跨过量子计算的专业壁垒

说明文案可围绕：

> 未来人人未必需要懂量子。
> 在今天，LoomQ 先帮助软件开发者借助 AI 生成、理解、验证和修复量子程序，并找到合适的运行平台。

可以再补一句非常短的产品说明：

> 不用先成为量子专家，也能完成自己的第一次量子实验。

要求：

- 首屏 5–10 秒内能看懂产品面向谁、解决什么问题；
- 不使用空泛的“AI 赋能”“降低门槛”等营销话术；
- 不上来解释 L1/L2、比赛评分或平台实现；
- 不把“人人”理解成完全没有编程背景的普通大众；
- 明确主要用户是软件开发者 / 有编程基础的人。

### 首屏 CTA

需要同时照顾新用户和熟练用户。

主 CTA：

> 30 秒看懂一个量子程序

它向下进入当前已经做好的三步 Learn 教学。

次级入口可以是：

> 直接选择实验 →

进入 Experiments。

不要让首屏直接同时摆 5 个大功能按钮，全局导航已经负责长期能力入口。

### 原三步 Learn 内容

13F 已验收方向保持不变：

- 量子电路三步框架；
- Prepare → H → Measurement；
- 中文优先；
- 在真实解释处补英文术语；
- `叠加（Superposition）` 保持“量子概念”强提示；
- 不恢复 glossary / popup。

只需要让 Landing 首屏与三步教学自然衔接，不重写整页。

---

## Experiments：保持产品教学，而不是评分目录

官方要求的是：

- 零基础用户可直接操作的 Agent 入口；
- evidence 中提供 3 个用户体验任务；
- L2 覆盖自然语言生成、纠错修复、智能选后端。

这些要求不意味着 Experiments 必须机械对应三个评分任务。

因此 13G 已确定的三个实验继续保留：

1. Bell 关联实验；
2. Grover 搜索实验；
3. 相位实验。

它们的职责是回答：

> 量子程序与普通程序相比，到底有哪些值得亲眼看到的不同？

不要为了评分把 Experiments 改成：

- Generate
- Repair
- Backend

最终 3 个 evidence 用户任务会另外覆盖官方三种 Agent 能力。

### Experiments 页面调整

- 接入统一全局导航；
- Hero 保持“选择一个量子实验”的教学定位；
- Bell / Grover / Phase 的 micro visualization 保留；
- Bell 仍然是推荐起点；
- 三张卡仍然是同等级实验；
- 保留自由探索入口；
- 不增加 GHZ 正式入口；
- 不自动运行实验；
- 不改三个稳定 prompt。

---

## Explorer：本轮只改导航，不做第二轮瘦身

Explorer 当前信息仍然较多，但这会单独作为后续任务处理。

本轮只做：

- 接入统一全局导航；
- 当前页高亮 `03 Explorer`；
- 移除当前顶部零散的 `Experiments · 选择实验` / `Learn · 基础概念` 按钮，避免与全局导航重复；
- 从 Experiments 带入稳定 prompt 的现有逻辑保持不变；
- 自由输入保持不变；
- 不改三栏 Workspace；
- 不改 autoplay；
- 不改 QASM disclosure；
- 不改 Teaching / Circuit Trace / state visualization。

Explorer 的信息层级、默认折叠、完成态之后单独优化。

---

## Repair 占位页

本任务只需要让导航能力真实可见，但不能伪装成功能已经完成。

页面可以非常简单：

标题：

> 检查和修复量子程序

说明：

> 已经有 OpenQASM？LoomQ 将帮助你检查语法和目标是否一致，在保持原始意图的前提下修复问题，并重新验证。

状态明确标识：

> 进阶能力 · 即将接入 Web

可以展示未来流程的静态 4 步：

```text
粘贴 QASM
→ 说明目标
→ AI 检查 / 修复
→ 本地验证
```

要求：

- 不提供假的输入框和假的“运行”按钮；
- 不伪造 repair 结果；
- 不触发 `/api/debug`；
- 不新增模型调用。

后续真实实现时再替换占位页。

---

## Backend 占位页

同样只展示未来能力与产品位置。

标题：

> 选择合适的运行平台

说明：

> 不需要先熟悉每家量子平台。告诉 LoomQ 你的 qubit、真机、排队和成本要求，它会提取约束并推荐合适后端。

状态：

> 进阶能力 · 即将接入 Web

可展示未来流程：

```text
描述运行要求
→ AI 提取约束
→ 本地能力表筛选
→ 给出推荐与原因
```

要求：

- 不展示伪造的实时平台状态；
- 不展示伪造队列时间 / 价格；
- 不调用后端 selector；
- 不新增 API。

---

## 视觉方向

这是本任务的重要验收点。

### 总体

全站继续保持 LoomQ 已有：

- 深色背景；
- 开发者工具气质；
- mono 辅助信息；
- 克制边框和状态色；
- 中文作为主阅读路径。

但要避免“每个页面都是一套不同产品”。统一导航应成为视觉锚点。

### 能力阶梯感

可以通过以下方式表达：

- `01` 到 `05` 的序号；
- 当前页高亮；
- `04 / 05` 的轻量 `进阶` 标记；
- 页面副标题从“认识 / 实验 / 创建 / 检查 / 运行”逐步变专业。

不要使用：

- 锁图标；
- 灰掉无法点击；
- Game Level / RPG 等夸张升级视觉；
- 复杂进度条；
- 强制用户按顺序解锁。

这是“认知上的渐进”，不是权限上的渐进。

### Landing 首屏

首屏要更像产品入口而不是课程封面。

建议视觉上可以轻量表现一条从自然语言到量子程序再到运行平台的链路，例如：

```text
你的意图
   ↓ AI
Quantum Program
   ↓ verify / repair
Backend
```

但不要做复杂架构图，不要上来展示 SpinQ / OriginQ / Braket 三个平台 logo。

---

## 最终官方体验任务的关系

本任务不填写 evidence，但全站信息架构应为最终 3 个官方用户体验任务留出清晰入口：

1. 自然语言生成并理解一个量子程序 → Explorer；
2. 检查并修复已有量子程序 → Repair；
3. 根据要求选择运行后端 → Backend。

因此评委不需要作者解释，就能从导航看出 LoomQ 覆盖了 L2 的完整能力范围。

Experiments 是教学入口，不需要与这 3 个任务一一对应。

---

## 技术边界

禁止：

- 修改 `adapter.agent_chat()`；
- 修改 L2 system prompt；
- 修改 parser / semantic verifier / repair；
- 修改 backend selector；
- 修改 `/api/debug`；
- 修改 Teaching Explainer；
- 修改 Circuit Trace；
- 新增 LLM 调用；
- 新增真实 Repair / Backend API；
- 修改 Bell / Grover / Phase 稳定 prompt；
- 自动运行实验；
- 重构 Explorer Workspace。

允许：

- 新增统一 Navigation 组件；
- 扩展 App 的 screen state；
- 新增 Repair / Backend 静态占位 screen；
- 调整 Learn 首屏结构和文案；
- 调整 Experiments / Explorer 顶部导航；
- 增加对应前端测试和 CSS。

---

## 验收重点

至少确认：

1. 默认打开 Learn，首屏 5–10 秒能理解 LoomQ 的目标用户和产品价值；
2. 全站稳定显示 01 Learn / 02 Experiments / 03 Explorer / 04 Repair / 05 Backend；
3. 当前页面有明确 active state；
4. Repair / Backend 始终可见且可进入，但清楚标明尚未接入 Web，不伪造功能；
5. Learn 三步教学没有被破坏；
6. Experiments 仍然只有 Bell / Grover / Phase 三个正式实验；
7. Experiments 的三张 micro visualization 与稳定 prompt 不变；
8. Explorer 移除重复的 Learn / Experiments 顶部按钮，改用统一导航；
9. Explorer Workspace、Teaching、Trace、autoplay、QASM、state visualization 不变；
10. 没有新增 `/api/debug` 调用或任何 LLM 调用；
11. 没有修改 parser / verifier / repair / backend selector；
12. 移动端导航仍然可访问，不产生横向溢出；
13. 测试至少覆盖：默认 Learn、全局 5 项导航、页面切换、Experiments 3 个实验、Repair / Backend 无真实提交行为。

完成后先让我体验整体导航和 Learn / Experiments 的视觉，不要继续实现 Repair / Backend，也不要开始 Explorer 信息瘦身。
