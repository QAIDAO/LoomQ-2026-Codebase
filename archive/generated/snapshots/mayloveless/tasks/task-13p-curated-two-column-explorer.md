# Task 13P — Two-column curated Explorer

## 背景

Task 13O 已经把 Bell / Grover / Phase 三个正式实验从“逐 Gate 调试”提升为语义阶段 Story，但当前 Explorer 仍保留旧三栏结构：

- 左栏：逐 Gate step list
- 中栏：当前 Story 阶段、阶段导航、Gate disclosure、电路、QASM
- 右栏：Experiment Story、数值与概念 disclosure

这造成两套粒度同时争夺注意力：

- Story 是“语义阶段”粒度
- Circuit / QASM 是“Gate / 代码行”粒度

正式实验应明确分工，而不是强行一一对应。

---

## 核心目标

对 **有 Story 的正式实验（Bell / Grover / Phase）**，把 Explorer 改成稳定的两栏：

```text
┌──────────────────────┬────────────────────────────────┐
│ PROGRAM              │ STORY                          │
│                      │                                │
│ Circuit              │ 01 02 03 04                   │
│                      │                                │
│ OpenQASM             │ 当前阶段                       │
│                      │ 执行前 → 做了什么 → 执行后      │
│                      │ 为什么重要                     │
│                      │ 💡 当前概念                     │
│                      │ ← 上一阶段       下一阶段 →     │
└──────────────────────┴────────────────────────────────┘
```

一句话原则：

> 左边展示“程序怎么写”，右边解释“这段程序在做什么”。

**没有 Story 的自定义实验必须继续可用，不能因为正式实验重构而破坏现有通用 Explorer。**

---

# A. 有 Story 的正式实验

## 1. 删除左侧 CIRCUIT STEPS 栏

对 `experimentStory != null` 的结果：

- 不渲染旧 `sidebar / CIRCUIT STEPS`；
- 不显示逐 Gate step list；
- 不显示 verified summary 占据独立栏；
- 页面主工作区改为两栏。

验证状态可以变成 Program 区顶部一个很轻的：

> ✓ 已生成并通过 LoomQ 验证

不要再占第三栏。

---

## 2. 左栏 = Circuit + QASM

### Circuit

- 默认展开，不再放进 `查看完整逐 Gate 电路` disclosure；
- 继续使用真实 trace；
- 保留点击 Gate → `selectStep()` 能力；
- 但不要因为点击单个 Gate 把 Story 强制切成另一套逐 Gate阅读模式。

### QASM

- 正式实验中默认展开；
- 不再要求用户先点“查看完整 QASM”；
- 可以保留一个很轻的“收起代码”能力，但默认必须可见；
- 字体与行号提高可读性，不使用 9–10px 作为主阅读字号。

### Story 阶段与 Program 的对应关系

一个 Story 阶段可以对应多个 Gate / 多行 QASM。

因此：

- 切换 Story 阶段时，高亮这一阶段的 `gateIndices`；
- Circuit 中属于当前阶段的 Gate 应形成“阶段范围”高亮；
- QASM 中属于当前阶段的可执行行也形成“阶段范围”高亮；
- 当前代表 step 可以有更强的单点高亮，但不能让用户误以为“一个 Story 阶段 = 一条 Gate / 一行代码”。

如果某个 Story 阶段无法安全映射到全部 QASM 行：

- 至少高亮已知 `gateIndices`；
- 不要猜测、不伪造映射。

---

## 3. 右栏 = Story 的唯一导航与解释中心

删除中间旧 Story 区中的重复内容：

- 删除 `CURATED STORY · 阶段 xx` 的独立中栏块；
- 删除中栏的 `当前阶段要做什么`；
- 删除中栏的 `上一阶段 / 下一阶段`；
- 删除 `查看这一阶段对应的 Gate` disclosure。

这些信息只保留在右侧 `ExperimentStory`。

右栏顺序建议：

1. 实验名称 / 一句目标
2. Story 阶段导航
3. 当前阶段标题与一句目的
4. `执行前 → 做了什么 → 执行后`
5. `为什么重要`
6. `💡 当前概念`
7. `← 上一阶段 / 下一阶段 →`

不要在右栏底部再堆一整套重复的“发生了什么 / ProbabilityComparison / Current Gate”。

---

## 4. 概念解释进入 Story，而不是藏在技术细节

Task 13O 后，原 `ConceptCard` 在正式实验中被隐藏到数值 disclosure 里，这不符合“先看到变化，再知道它叫什么”。

正式实验每个 Story 阶段最多显示 **一个** 关键概念：

示例：

### Bell

- `叠加 Superposition`
- `纠缠 Entanglement`
- `测量 Measurement`

### Grover

- `叠加 Superposition`
- `相位翻转 Phase Flip`
- `干涉 Interference`
- `测量 Measurement`

### Phase

- `相对相位 Relative Phase`
- `干涉 Interference`（仅真实阶段需要时）

呈现方式：

```text
💡 当前概念
相位翻转 Phase Flip
振幅大小没有改变，但目标分支与其他分支的方向关系反了。
现在测量不一定看得出区别，后续干涉时才会显现。
```

要求：

- 先使用 Story 已经展示出的变化，再给术语；
- 不要把完整量子理论重新塞进页面；
- 概念解释可以来自固定 curated copy；
- 不新增 LLM 调用；
- 不修改 teaching explainer prompt。

---

## 5. 正式实验移除自动播放

对于 `experimentStory != null`：

- 不显示自动播放按钮；
- 不使用 1.8s timer 推进 Story；
- 请求完成后停在第一个 Story 阶段；
- 只通过阶段 nav / 上一阶段 / 下一阶段推进。

原因：用户需要时间比较执行前后与阅读解释。

现有 generic Explorer 的 autoplay 可以保留，见 B 部分。

---

## 6. 正式实验新手引导

第一次进入有 Story 的结果时，提供一个**短、非阻塞**的新手引导。

只讲三件事：

1. `先看右边：一次只解释一个阶段`
2. `看懂后点“下一阶段”继续`
3. `想看程序实现时，左边 Circuit 与 QASM 会同步标出当前阶段`

要求：

- 最多 3 个提示；
- 不做 5–8 步 wizard；
- 不遮住整个页面；
- 有明确 `知道了`；
- 关闭后不要在同一次使用过程中反复弹出；
- 可以提供轻量 `如何阅读这个页面？` 入口重新打开。

如果使用 localStorage，只存一个纯 UI onboarding flag，不存实验数据或用户输入。

---

# B. 没有 Story 的自定义实验 / 其他通用结果

这是本 Task 的兼容性重点。

当 `experimentStory == null` 时：

- 保留现有 generic Explorer；
- 逐 Gate step list 必须继续存在；
- 当前 step / purpose / Circuit / QASM / state detail 必须继续工作；
- 现有 `selectStep()` 行为不得回归；
- generic autoplay 可以继续保留；
- teaching explainer 仍按现有方式显示；
- 不要求自定义实验具备 Story；
- 不尝试根据任意用户 prompt 伪造 Story。

也就是说：

```text
有 Story（Bell / Grover / Phase）
→ 两栏 Curated Explorer

没有 Story（自由探索 / 自定义实验 / 无法识别）
→ 现有 Generic Explorer fallback
```

如果 curated Story 构建失败，也必须安全 fallback 到 Generic Explorer。

---

# C. Loading 优化（两种模式共用）

当前 loading 仍然过于 DevTools 化、字体偏小，而且阶段动画容易让人误解为真实流式进度。

改成更清晰的中央等待状态：

```text
正在准备你的量子实验

LoomQ 正在把自然语言需求变成
一个经过验证、可以逐步解释的量子程序。

理解需求
生成并校验程序
准备可视化解释

请求完成后会一次性展示真实结果。
```

要求：

- 标题约 20px；
- 正文约 15–16px；
- 三个步骤至少 14px；
- 不使用 8–10px 作为主要 loading 信息；
- 可以保留轻微 loading 动画；
- 不要通过逐项“完成”动画暗示真实 streaming；
- 明确这是等待说明，真实结果完成后一次返回。

---

# D. 可读性

正式 Story 两栏中：

- 主体说明至少 14–16px；
- Story 当前阶段标题约 20–24px；
- 概念名约 16–18px；
- Circuit Gate 标签 / QASM 代码至少达到实际可读水平；
- 关键解释不要使用 `var(--faint)`；
- `faint` 只用于真正 secondary metadata；
- 不新增一套彩色主题，继续沿用 Neutral UI + Vivid Quantum Visualization。

---

# E. 不做

- 不修改 Bell / Grover / Phase stable prompts；
- 不修改 Python correctness / validator / semantic verifier；
- 不新增 LLM 调用；
- 不修改 teaching explainer prompt；
- 不给自由探索生成 Story；
- 不重做 Repair / Backend；
- 不做真实光学模拟；
- 不伪造 Gate → QASM 映射；
- 不把 Story 阶段强行压成逐 Gate 粒度。

---

# F. 测试要求

至少覆盖：

1. Bell / Grover / Phase 有 Story 时使用 curated two-column layout；
2. curated layout 不渲染旧 `CIRCUIT STEPS` sidebar；
3. curated layout 默认展示 Circuit 与 QASM；
4. Story 阶段切换会同步 Program 区的阶段范围高亮；
5. curated layout 不显示 autoplay；
6. curated layout 不显示 `查看这一阶段对应的 Gate`；
7. Story 中能看到当前阶段概念解释；
8. `experimentStory == null` 时仍渲染 Generic Explorer，step list / Circuit / QASM / state detail 可用；
9. Story 构建失败时安全 fallback generic，不出现空白结果页；
10. stable prompts 保持原值；
11. loading 主信息不再依赖 8–10px 文本。

---

# 完成标准

正式实验第一次打开后，用户应该很明确：

> **右边负责理解，左边负责看程序。**

用户不需要同时理解“逐 Gate step list”和“Story 阶段”两套导航。

同时，自定义实验仍然完整保留 Generic Explorer，不因为 curated 体验升级而失去逐 Gate 调试 / 阅读能力。

完成后停止，等待 review。