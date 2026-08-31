# Task 13L — Move Why Quantum Motivation to Experiments

## 目标

把当前放在 Learn 首屏中的“量子计算适合什么 / 为什么值得关心”内容移到 `02 Experiments` 页面，避免 Learn 首屏信息过载，并让“为什么值得看量子 → 选一个实验看看”形成自然衔接。

本任务只调整 Learn / Experiments 的内容归属和轻量布局，不修改实验 prompt、不重构 Explorer、不改后端逻辑。

---

## 产品逻辑

重新明确两个页面的职责：

### 01 Learn

只回答：

> **量子程序到底是怎么运行的？**

保留：

- LoomQ 产品定位；
- 面向有编程基础、但没有量子背景的开发者；
- “30 秒看懂一个量子程序”；
- Task 13J 已完成的 `Prepare → H → Measure` 三步体验；
- 源码按需查看；
- 状态变化可视化；
- recap / technical details。

Learn 首屏不要继续承担“量子计算适用场景”科普。

### 02 Experiments

先回答：

> **量子计算为什么值得继续探索？**

然后自然引导用户：

> **先从三个小实验，看看这种“不同”到底发生在哪里。**

这样页面逻辑变为：

```text
量子计算不是更快的普通电脑
↓
它只在少数特殊问题上可能很强
↓
密码学 · 搜索与组合 · 量子系统模拟
↓
那它到底“不同”在哪里？
↓
Bell / Grover / Phase
```

---

## Learn 修改

从 Learn 首屏移除当前这段内容：

> 量子计算并不适合大多数程序，但在少数特殊问题上可能非常强：
> 密码学 · 搜索与组合 · 量子系统模拟

要求：

- 不新增替代说明块；
- 不把这段搬到 Learn 右侧产品流程；
- 不再在 Learn 首屏解释密码学 / 搜索 / 模拟；
- 保持 Task 13J 三步教学不变；
- `30 秒看懂一个量子程序` 继续直达 `#learn-quickstart`。

Learn 首屏目标应重新变得干净：

```text
LoomQ 是什么
↓
不用成为量子专家也能开始
↓
30 秒看懂一个量子程序
```

---

## Experiments 修改

在现有 Experiments Hero / 三张实验卡之前，加入一个**非常轻量的动机说明**。

推荐文案：

### 标题

> **量子计算不是“更快的普通电脑”**

### 正文

> 它不适合大多数普通程序，却可能在少数特殊问题上提供完全不同的求解方式。

### 范围提示

> `密码学 · 搜索与组合 · 量子系统模拟`

### 过渡句

> **先从三个小实验，看看这种“不同”到底发生在哪里。**

然后紧接当前 Bell / Grover / Phase 三张实验卡。

---

## 视觉要求

这不是新增一个重型科普 section。

要求：

- 不做三张“应用场景卡”；
- 不为密码学 / 搜索 / 模拟分别增加图标或彩色 tag；
- 不增加新的大面积背景色；
- 不与三张实验卡争夺视觉焦点；
- 这段内容只承担“为什么选择一个实验看看”的过渡作用；
- `密码学 · 搜索与组合 · 量子系统模拟` 可以使用一行轻量文字 / mono，但不要做成按钮。

主视觉仍然应该是下面三张实验卡。

---

## 三张实验卡保持不变

不要修改：

### Bell

- 标题：`两个结果为什么总是同步？`
- description / concepts / micro visualization 保持现状；
- stable prompt 不变。

### Grover

- 标题：`怎样让目标答案更容易被找到？`
- description / concepts / micro visualization 保持现状；
- stable prompt 不变。

### Phase

- 标题：`概率没变，量子状态真的没变吗？`
- description / concepts / micro visualization 保持现状；
- stable prompt 不变。

本任务不要开始实现 Oracle / Diffusion 新可视化。

---

## 自由探索入口

保持 Task 13G-3 已确定的位置和文案逻辑：

- 自由探索入口仍然存在；
- 不因本次 Hero 调整重复自由探索 CTA；
- 不把“为什么值得关心”内容塞到自由探索块里。

---

## 不做

本任务禁止：

- 修改 Bell / Grover / Phase stable prompts；
- 修改实验点击后的 Explorer 行为；
- 新增 Grover Oracle / Diffusion 教学；
- 修改 Explorer Result；
- 修改 Learn 三步交互；
- 修改 Repair / Backend；
- 修改 parser / verifier / repair / backend selector；
- 修改 Teaching Explainer / Circuit Trace；
- 新增 LLM 调用；
- 把 Experiments 改成 Generate / Repair / Backend 功能目录。

---

## 验收重点

1. Learn 首屏是否重新变得更干净，不再承担量子应用领域科普？
2. Experiments 是否自然回答“为什么我要选一个实验看看”？
3. “量子计算不是更快的普通电脑”是否只是轻量动机，而不是抢占页面主角？
4. Bell / Grover / Phase 是否仍然是 Experiments 页面的核心视觉和交互对象？
5. stable prompts 是否完全未改？
6. 是否没有引入新的重型卡片、复杂颜色和无关功能？

完成后停止，让用户先 review Experiments 页面，再决定是否进入 Grover Oracle / Diffusion 可视化任务。
