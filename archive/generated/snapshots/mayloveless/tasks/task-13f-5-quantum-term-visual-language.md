# Task 13F-5 — Quantum Term Visual Language

## 目标

继续收尾 Learn 页面，但撤回 Task 13F-4 的可点击 glossary 思路。

当前真正需要解决的问题不是“用户点开术语后如何解释”，而是：

> **用户不需要额外操作，就能在扫读页面时立刻知道：哪些是量子领域术语，哪些是这次真正需要记住的核心量子概念。**

目标用户仍然是：**中文母语、有编程基础、没有量子计算背景的开发者**。

本任务只调整 Learn 页的术语文案与视觉语言，不改三步教学结构，不改 Explorer。

---

## 1. 撤回 Task 13F-4 的 glossary 交互

删除 / 停用当前 Learn 页面上的可点击术语交互：

- 不要虚线下划线；
- 不要点击弹出解释卡片；
- 不要要求用户发现“这里可以点”；
- 不要重复展示正文中已经解释过的内容。

如果 `Glossary.tsx` 在本任务后不再被任何地方使用，应删除无用组件、context、popover 逻辑及对应样式 / 测试，避免留下死代码。

这次不保留“以后可能复用”的交互架构；后续 Bell / Grover / Phase 如需术语视觉，复用本任务的静态视觉规则即可。

---

## 2. 中文优先，英文只做准确性补充

页面面向中文用户，新概念第一次出现时优先使用中文名称。

推荐格式：

- `量子电路（quantum circuit）`
- `量子比特（qubit）`
- `量子状态（quantum state）`
- `量子门（quantum gate）`
- `测量（measurement）`
- `叠加（superposition）`
- `重复运行次数（shots）`

不要在主要教学句中直接用以下英文作为用户首先需要理解的名词：

- `quantum circuit`
- `qubit`
- `gate`
- `measurement`
- `superposition`

英文可以：

- 放在中文后的括号中；
- 出现在 QASM / technical 区；
- 出现在较弱的辅助视觉中。

这样中文用户先建立熟悉的语义，再把英文术语作为准确名称记住。

---

## 3. 两级视觉语言

不要把所有量子词都做成同等强度的高亮。

### Level A：量子领域基础术语

包括：

- 量子电路
- 量子比特
- 量子状态
- 量子门
- 测量
- shots / 重复运行次数

它们的作用是：

> 告诉用户“这是一个量子编程领域里的术语”。

视觉要求：

- 使用统一、轻量、静态的术语样式；
- 可以用略亮的 cyan / teal 文字、mono 英文、非常轻的背景或底部 marker；
- 不要像按钮；
- 不要有 hover / cursor pointer / 下划虚线；
- 不要显著打断正文阅读；
- 同一个术语后续重复出现时可以降低强调，不要求每次都突出。

目标是“能被扫到”，不是“需要被点击”。

### Level B：本次实验真正学到的核心量子概念

Learn 当前只有：

- `叠加（superposition）`

未来其他实验会有：

- Bell：`纠缠（entanglement）`
- Grover：`干涉（interference）`
- Phase：`相位（phase）`

这些概念第一次出现时，需要明显高于 Level A 的视觉层级。

推荐结构：

```text
QUANTUM CONCEPT / 量子概念

这就叫：叠加（superposition）
```

视觉要求：

- 有一个非常小的 `量子概念` / `QUANTUM CONCEPT` 标签；
- `叠加（superposition）` 使用轻量“荧光笔 / marker”效果；
- marker 可以是不规则但克制的底色，或偏手写高亮感觉；
- 不要做霓虹发光、大按钮、强动画；
- 下面继续使用现有的人话解释；
- 第一次揭示后，页面后续再次出现“叠加”时不再重复强 marker。

这里的体验应该像：

> 用户先看到状态发生了变化，然后 LoomQ 给这个现象贴上一个明确的“量子概念”名字。

---

## 4. Learn 页文案调整

保持当前三步结构，不重写主流程，但把关键名词改成中文优先。

例如当前类似：

> 一个 quantum circuit，三步看完

改为更适合中文用户的：

> 一个量子电路（quantum circuit），三步看完

当前类似：

> 下面用一个 qubit，真正按这个顺序运行一遍。

改为：

> 下面用一个量子比特（qubit），真正按这个顺序运行一遍。

当前流程框架类似：

> 准备状态 → gate 改变状态 → measurement 读取结果

改为：

> 准备量子状态 → 量子门改变状态 → 测量读取结果

可以在合适位置用较弱文字补英文：

> quantum state · quantum gate · measurement

但英文不能成为主要阅读路径。

---

## 5. Recap 也使用中文主名

当前 recap 不要再以：

```text
qubit
state
gate
circuit
measurement
```

作为最醒目的主标题。

改为中文主名：

```text
量子比特
量子状态
量子门
量子电路
测量
```

英文作为较弱副标题：

```text
qubit
quantum state
quantum gate
quantum circuit
measurement
```

继续保留开发者版的一句话解释。

---

## 6. 不要新增额外教学内容

本任务不需要再增加术语定义。

已有正文已经在三步过程中解释：

- 量子比特是什么；
- 状态是什么；
- H 如何改变状态；
- 什么是叠加；
- 测量和多次 shots 的区别。

本任务的目的只是**让这些已经存在的知识更容易被识别和记住**。

不要再增加新的 glossary / tooltip / side panel / glossary page。

---

## 7. 验收重点

人工体验优先：

1. 第一次扫页面时，不点任何东西，也能识别出“量子电路 / 量子比特 / 量子门 / 测量”属于量子编程术语；
2. 中文用户不用先理解 `circuit / qubit / gate` 英文才能继续阅读；
3. 英文名称仍然存在，方便准确记忆和以后查资料；
4. “叠加（superposition）”第一次出现明显比普通术语更重要；
5. 用户能直观看出：这是本次刚刚遇到的一个 **量子概念**；
6. 页面上没有需要发现的隐藏点击行为；
7. 删除 Task 13F-4 留下的无用 popover / glossary 交互代码；
8. 不改三步程序结构；
9. 不改 Explorer、Experiments、Teaching Explainer、L2 correctness 或后端；
10. `pnpm test` 与 `pnpm build` 通过。

完成后停下，等待人工体验，不继续实现 Task 13G。
