# Task 13H — Visual Readability & Product Identity

## 目标

对现有 LoomQ Web 做一次**纯视觉语言调整**：提高可读性，并摆脱当前常见的“AI 生成暗色 DevTools”观感。

本任务不调整信息架构、不重做 Explorer、不新增功能。重点只解决两个问题：

1. 当前整体过暗，正文、次要文字和边界信息可读性不足；
2. 黑灰背景 + 青色高亮 + mono + 细边框的组合过于接近常见 AI DevTools 模板，缺少 LoomQ 自己的辨识度。

新的方向不是“普通白色 SaaS”，而是：

> **明亮实验室 / 工程笔记 + 深色技术工作台**

页面承担阅读和解释的区域更明亮；代码、量子状态、技术细节区域可以继续保留深色技术面板。让“读懂”优先于“氛围感”。

---

## 本任务范围

只调整现有 Web 的视觉 token / CSS / 样式层级，包括：

- 全局背景与面板层级；
- 主文字 / 次文字 / 辅助文字对比度；
- 导航样式；
- Learn / Experiments / Explorer / Repair / Backend 的现有视觉统一；
- 卡片、边框、按钮、标签、代码块的配色；
- hover / focus 等轻量交互视觉；
- 保持现有布局与结构不变。

不要顺手修改页面信息结构或业务逻辑。

---

## 视觉方向

### 1. 页面主背景：从“暗黑终端”改成“实验室 / 工程纸面”

不要继续让整个页面都处于接近黑色的背景。

建议：

- 主页面使用偏暖或中性的浅色背景，例如 off-white / warm gray / very light blue-gray；
- 不要使用纯白 + 蓝色按钮的通用 SaaS 风格；
- 可以保留极轻的网格、纸面、实验台感，但不要加入装饰性噪音；
- 页面应该更适合长时间阅读。

目标感觉：

> developer notebook / lab console / scientific workspace

而不是：

> hacker terminal / generic AI dashboard

### 2. 技术区域仍可深色

以下区域可以继续使用深色或高对比技术面板：

- QASM / code；
- Explorer 的状态 / execution technical panel；
- 必要的量子状态可视化背景；
- terminal-like 小块。

这样技术内容会自然形成视觉焦点，而不是整页所有区域都一样黑。

### 3. 文字必须明显变亮 / 变清楚

当前一些 secondary / muted 文案过暗。

要求：

- 正文必须在正常显示器上无需靠近屏幕即可阅读；
- 主标题、正文、说明文字形成明确的三级层级；
- secondary text 可以弱化，但不能靠“接近背景色”来弱化；
- placeholder / metadata / mono label 也不能低到难以辨认；
- 不允许出现“为了高级感把文字压成灰黑”的情况。

尽量满足 WCAG AA 的常规文本对比度目标；至少人工视觉上必须明显比当前版本更清楚。

### 4. Accent 不再依赖“暗底 + 青蓝霓虹”

当前 cyan / teal 可以保留一部分量子技术语义，但不要继续让它成为整个产品唯一视觉识别。

建议：

- 选择一个更克制的主强调色；
- cyan / teal 可以用于量子状态、运行状态或局部技术信息；
- Learn 的术语黄色强调语义继续保留，但适配新背景；
- 成功 / warning / current step 等状态要依靠文字、形状或边框共同表达，不只靠颜色。

不要大面积渐变，不要霓虹光晕。

### 5. Mono 字体只用于“技术语义”

不要让所有辅助信息都像 terminal。

Mono 继续用于：

- QASM / code；
- step number；
- technical label；
- state / basis / probability；
- 少量 eyebrow。

普通中文解释、教学文字、按钮主要使用正常 UI 字体。

---

## 各页面要求

### Global Navigation

保留 01 → 05 的渐进结构和当前高亮逻辑。

视觉上：

- 在浅色主背景上仍需有足够边界；
- 不要做成普通企业后台导航；
- 01–05 的“能力阶梯”仍然一眼可见；
- `Repair / Backend · 进阶` 不要因为颜色太淡而变成难以发现。

### Learn

- 首屏产品定位必须仍然是最清楚的阅读中心；
- 三步教学区域在浅背景下保持层级；
- 黄色强调仍可使用，但调整为适合浅背景的可读状态；
- QASM 示例可以成为深色技术块，与正文形成对比；
- 不修改 13F 已验收的教学内容和顺序。

### Experiments

- 三张实验卡不要变成普通白底 SaaS cards；
- 可以用实验台 / scientific card 的感觉；
- Bell / Grover / Phase 的 micro visualization 必须仍然是卡片中的主要差异；
- “自由探索”入口继续保持弱于三张正式实验，但必须清楚可见。

### Explorer

本任务**不要修改信息结构和 Result 三栏**。

只调整现有视觉：

- Idle、Loading、Result 三种状态都适配新主题；
- Idle 仍然不能出现 loading skeleton；
- Loading 的 skeleton 在浅色背景下仍明确表示“正在处理”，但不要过度闪烁；
- Result 中代码 / 状态区域允许保留深色技术面板；
- 正文解释文字优先提高可读性。

### Repair / Backend

当前仍是正式占位页。

- 保留“进阶能力 · 即将接入 Web”的真实状态；
- 不因为新主题做成营销落地页；
- 流程说明清楚即可。

---

## 不做

本任务禁止：

- 修改导航结构；
- 修改 Learn 教学内容；
- 修改 Experiments 的三个实验或 prompt；
- 修改 Explorer 信息层级；
- 修改 Explorer Result 三栏结构；
- 新增 Grover Oracle / Diffusion 教学；
- 新增量子适用场景内容；
- 实现 Repair；
- 实现 Backend；
- 修改 `/api/debug`；
- 修改 parser / verifier / repair / backend selector；
- 修改 Teaching Explainer / Circuit Trace；
- 新增 LLM 调用。

Grover 可视化、量子适用场景、Explorer 瘦身全部留给后续独立任务。

---

## 验收重点

完成后重点人工体验以下问题：

1. 普通亮度显示器下，是否所有正文和说明文字都能轻松阅读？
2. 第一眼是否仍然像常见的“黑底 AI DevTools 模板”？如果是，本任务不算完成。
3. 是否形成“浅色阅读区域 + 深色技术工作台”的明确层级？
4. Learn、Experiments、Explorer 是否仍然看起来属于同一个 LoomQ 产品？
5. QASM / state 等技术信息是否因为局部深色面板反而更突出？
6. 导航 01–05 是否仍然清楚且可发现？
7. 是否没有发生任何功能、页面结构、prompt 或 correctness 路径变更？

完成后停止，先让用户体验和 review 视觉，不要继续做 Explorer 瘦身、Grover 教学或内容新增。
