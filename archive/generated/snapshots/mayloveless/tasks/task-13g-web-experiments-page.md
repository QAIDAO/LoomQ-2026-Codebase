# Task 13G — Web Experiments Selection Page

## 目标

在已经完成的 Learn 与现有 Quantum Explorer 之间增加一个 **独立的 Experiments 页面**。

页面面向有编程基础、但没有量子计算背景的开发者。用户不需要先理解量子算法，而是从一个容易理解的现象 / 计算问题开始，选择实验后进入 Explorer，逐步观察量子程序如何改变状态。

本任务只完成：

- 独立 Experiments screen；
- 三个正式实验入口；
- Learn → Experiments → Explorer 的导航；
- Experiments 的视觉设计。

不要实现实验完成态、Error Recovery、真机入口或新的后端能力。

---

## 页面关系

本轮将 Web 的 screen 明确为：

```text
Learn
  ↓
Experiments
  ↓
Explorer
```

要求：

- Learn 的主 CTA 不再直接进入 Explorer，而是进入 Experiments；
- Experiments 与 Learn、Explorer 都是完整独立 screen；
- 从 Experiments 选择某个实验后进入 Explorer，并带入对应的稳定 prompt；
- Explorer 顶部增加一个轻量入口，可以回到 Experiments；
- Explorer 仍保留回 Learn 的入口；
- 不要求本任务引入 React Router，可以继续使用当前轻量 screen state；
- 不做浏览器刷新后的路由持久化。

### 本轮不要自动运行实验

用户在 Experiments 选择实验后：

1. 进入 Explorer；
2. 对应实验 prompt 已经选中 / 填好；
3. 用户仍然显式点击“运行量子程序”。

不要因为进入 Explorer 就自动触发 `/api/debug`，避免一次页面选择直接产生 LLM 请求。

---

## 三个正式实验

Experiments 页面只展示以下 3 个正式实验。

**不要要求它们与 `QUANTUM_101.md` 的测试电路清单一一对应。** 这里是产品教学路径，不是比赛测试电路目录。

现有 `SCENARIOS` 中的稳定 prompt 应尽量复用，不要为了卡片文案重新改写 prompt，尤其不要削弱当前 Grover prompt 的约束。

### 01 · 关联 / Bell

中文主名：

> Bell 关联实验

英文可以弱化补充：

> Bell State

主标题：

> 两个结果为什么总是同步？

场景说明：

> 让两个量子比特分别测量，却只看到 `00` 或 `11`。看看这种关联是怎样一步步建立起来的。

用户会看到：

- 叠加；
- 纠缠；
- 测量。

这是推荐第一个体验的实验，可以增加一个轻量的：

> 推荐从这里开始

不要在 Experiments 卡片里提前长篇解释“纠缠”，解释留到 Explorer 的 Bell 实验现场。

使用当前 Bell 的稳定 prompt：

```text
生成一个 Bell 态并测量
```

### 02 · 计算 / Grover

中文主名：

> Grover 搜索实验

英文弱化补充：

> Grover Search

主标题：

> 怎样让目标答案更容易被找到？

场景说明：

> 在 4 个候选结果中，把目标 `|11>` 被测到的概率逐步放大。

用户会看到：

- 均匀叠加；
- 标记目标；
- 干涉 / 概率放大；
- 测量。

这是三个实验里最像“计算任务”的一个。不要因为电路更复杂而弱化它，它对软件开发者理解“量子计算怎么拿来算东西”很重要。

必须继续使用当前已稳定的 Grover prompt，不要简化：

```text
设计一个 2 比特 Grover 搜索电路，搜索目标为 |11>。先创建均匀叠加，再实现标记 |11> 的 Oracle 和扩散算子，最后测量；请使用 OpenQASM 2.0 基础门展开，不定义自定义 gate。
```

### 03 · 状态 / Phase

中文主名：

> 相位实验

英文弱化补充：

> Phase

主标题：

> 概率没变，量子状态真的没变吗？

场景说明：

> 两个状态看起来都有相同的测量概率，但内部的相位信息已经不同。

用户会看到：

- 概率；
- 相位；
- 为什么“概率没变”不等于“什么都没发生”。

这里不要在卡片里展开复振幅或数学推导。

继续使用当前稳定的 Phase prompt：

```text
生成一个带相对相位的 Bell- 态，不要求测量
```

---

## GHZ 的处理

当前 `SCENARIOS` 里还有 GHZ。

本任务中：

- GHZ **不作为 Experiments 页的三个正式入口之一**；
- 不需要为了本任务删除 GHZ 的已有数据或执行支持；
- 不要因为它不展示就改动后端或正确性路径。

重点是把正式教学路径收敛成：Bell / Grover / Phase。

---

## Experiments 页面结构

建议从上到下：

### 1. 顶部导航

沿用 LoomQ 深色开发工具视觉语言。

展示：

- LoomQ / Experiments；
- 返回 Learn 的轻量入口；
- 不需要复杂全站导航。

### 2. 页面 Hero

建议标题：

> 选择一个量子实验

建议说明：

> 不用先理解算法。从一个现象开始，在 Explorer 里一步步看量子程序怎样改变状态。

不要写成课程目录，也不要强调“难度等级”。

### 3. 三个大实验入口

桌面端三个实验应形成一组清楚的大型内容块，而不是普通后台系统里的小卡片网格。

每个实验块至少包含：

- 编号 `01 / 02 / 03`；
- 中文实验名 + 弱化英文名；
- 一个具体问题式标题；
- 一句场景解释；
- 一个专属的小型可视化；
- “你会看到”的 2–4 个概念词；
- 清楚的进入 Explorer CTA。

CTA 文案建议使用：

> 在 Explorer 中打开 →

因为本任务不会自动运行实验，不要让按钮文案暗示点击后已经完成执行。

### 4. 自由探索入口

三张实验之后可以放一个视觉更弱的横向入口：

> 已经有自己的问题？直接描述你想探索的量子程序 →

点击进入 Explorer，但不选择正式实验，prompt 可以为空。

它不是第四张实验卡，不要和三个正式实验等权。

---

## 视觉方向

这是本任务的重要部分。

### 总体原则

Experiments 页仍然属于 LoomQ，同 Learn / Explorer 保持统一的：

- 深色背景；
- 开发工具 / IDE 气质；
- 清楚的 mono 辅助信息；
- 克制的边框和状态强调。

但不要把它做成另一个 DevTools 三栏页面。它应该更像一个“实验台入口 / playground catalog”。

避免：

- 通用 SaaS 功能卡片；
- emoji 大图标；
- stock illustration；
- 三张只有标题和按钮、彼此没有视觉差异的矩形卡；
- 大面积炫彩渐变；
- 为了好看加入与教学无关的动画。

### 三个实验必须有不同的“视觉现象”

不要只靠不同 icon 区分。

#### Bell 的视觉

用非常小的静态图形表达“两个结果保持关联”。

可以表现成：

```text
00   █████  50%
11   █████  50%
01           0%
10           0%
```

或者两个成对连接的结果节点。

视觉重点：

> 只留下 `00 / 11`。

不要要求用户先看懂 CNOT 电路符号。

#### Grover 的视觉

用 `2 × 2` 候选格最直观：

```text
00   01
10  [11]
```

从“候选机会接近”到“目标 `11` 更突出”，表达概率放大。

视觉重点：

> 目标答案从候选中被放大。

这张卡应该明显具有“计算 / 搜索问题”的感觉，而不是另一个纠缠演示。

#### Phase 的视觉

用“概率相同、内部信息不同”的对照表达：

```text
状态 A      状态 B
0  50%      0  50%
1  50%      1  50%

phase +     phase −
```

可以用 `+ / −`、相位标记或非常克制的波形 / 方向提示表达差异。

视觉重点：

> 两边概率一样，但状态并不一样。

不要在卡片里展示复杂振幅公式。

### 卡片层级

Bell 可以有轻量“推荐从这里开始”标记，但三张卡尺寸保持一致，不要把 Bell 做成占两列的大 Banner。

建议视觉节奏：

```text
编号 / 分类
实验中文名  English
问题式大标题
一句解释

[ 专属 micro visualization ]

你会看到：概念 · 概念 · 概念

在 Explorer 中打开 →
```

Hover 可以有非常轻的边框 / 位移反馈，但不需要复杂 3D 或动画。

移动端三张卡纵向排列，可正常滚动。

---

## Explorer 调整

Experiments 成为正式示例选择页后，Explorer 不应再承担“大型示例选择页”的职责。

本任务调整：

- 初始 Explorer 不再展示当前的大型 `ScenarioGrid`；
- 结果后的“切换示例”大型展开区也移除；
- Explorer 顶部提供轻量 `Experiments · 选择实验` 返回入口；
- 自由输入 prompt 继续保留；
- 从 Experiments 进入时，对应 scenario 的 prompt 与 selected state 正确带入；
- 如果用户自己修改 textarea，继续按现有逻辑取消 scenario selection；
- 不改 Explorer 三栏工作区本身。

现有 `ScenarioGrid` 如果不再有调用，可以删除死代码与对应 CSS；如果还有其他真实用途，可以保留，但不要为了清理而扩大改动。

---

## 状态与数据建议

可以让 App 保存一个轻量的 `selectedExperimentId` / `initialScenarioId`，用于从 Experiments 进入 Explorer。

不要为了本任务引入全局状态库。

Experiment 数据应尽量复用当前稳定的 scenario 数据，避免同一 prompt 在多个文件复制后发生漂移。

可以根据当前结构选择：

- 从 `SCENARIOS` 中筛选 Bell / Search / Phase；或
- 抽出共享的 scenario / experiment data 文件。

以最小改动、减少重复为优先。

---

## 文案规则

延续 Learn 已确定的阅读习惯：

- 面向中文用户，中文是主要阅读路径；
- `Bell State / Grover Search / Phase` 只作为弱化英文补充；
- 不要上来堆 `qubit / superposition / interference` 等英文；
- 卡片不是概念课，核心概念只列关键词，详细解释留在 Explorer 的真实步骤中。

---

## 数据 / 架构边界

禁止：

- 新增 LLM 调用；
- 修改 `/api/debug`；
- 修改 `adapter.agent_chat()`；
- 修改 Teaching Explainer schema / prompt；
- 修改 parser / verifier / repair；
- 修改 Circuit Trace；
- 修改 Grover / Bell / Phase 当前稳定 prompt；
- 自动运行实验；
- 实现实验完成总结；
- 实现 Error Recovery；
- 增加真机入口。

---

## 验收重点

至少确认：

1. 默认仍先进入 Learn；
2. Learn 主 CTA 进入独立 Experiments screen；
3. Experiments 只展示 Bell / Grover / Phase 三个正式实验；
4. 三张实验在视觉上能仅凭 micro visualization 看出方向不同；
5. Bell 明确是推荐起点，但不压制另外两张卡；
6. 点击某个实验后进入 Explorer，对应稳定 prompt 已填入，但 **不会自动调用后端**；
7. Explorer 不再重复展示大型 ScenarioGrid / “切换示例”区域；
8. Explorer 可以回到 Experiments，也可以回 Learn；
9. 自由探索入口能进入空白 / 未选择 scenario 的 Explorer；
10. 中文为主，英文只做准确补充；
11. GHZ 不出现在 Experiments 页，但已有执行支持不因本任务被破坏；
12. Bell / Grover / Phase prompt 不被改写；
13. 不产生额外后端 / LLM 请求；
14. `pnpm test` 通过；
15. `pnpm build` 通过。

完成后停下，等待人工体验和视觉 review；不要自行继续做实验完成态或 Error Recovery。
