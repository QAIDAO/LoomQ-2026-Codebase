# Task 13R — Curated experiment completion and next-step guidance

## 背景

Task 13Q 已经把 Explorer 统一成同一套两栏心智：

- 左边 `Program`：Circuit + QASM
- 右边：
  - 有 Story 的 Bell / Grover / Phase → `Story`
  - 无 Story 的自定义实验 → `Explain`

现在正式实验已经是用户主动按阶段阅读，而不是自动逐 Gate 播放。

下一步补上一个很轻的**完成感 + 下一步引导**。不要做成闯关系统，也不要影响 Generic / 自定义实验。

---

## 目标

当用户读到 Bell / Grover / Phase 的最后一个 Story 阶段时：

- 不再只是看到 disabled 的“下一阶段”
- 显示一个明确按钮：

> **完成这个实验 ✓**

点击后，右侧 Story 区进入简短完成态：

```text
✓ 你已经完成 Bell 实验

你刚刚看到：
叠加 → 建立关联 → 测量

接下来：看看量子状态怎样真正参与一次搜索算法
[继续看 Grover 搜索 →]

[返回实验列表]
```

左侧 Program 保持可见，不需要整页跳到一个新的庆祝页面。

---

## 1. 只对 Curated Story 实验生效

完成按钮只存在于：

- `bell`
- `search`
- `phase`
- 且 `experimentStory != null`

Generic / 自定义实验：

- 不显示“完成实验”
- 不显示礼花
- 不显示下一实验推荐
- 继续保持 Task 13Q 的逐 Gate Explain 流程

Story 构建失败时也不要伪造完成态。

---

## 2. 最后一阶段的控制

在 Story 的非最后阶段：

```text
← 上一阶段        下一阶段 →
```

在 Story 的最后阶段：

```text
← 上一阶段        完成这个实验 ✓
```

点击“完成这个实验”后：

- 不触发任何 API / LLM / validation 请求
- 只改变本地 UI 状态
- 右侧从当前 Story 内容切换为完成态
- 左侧 Program 不变

如果用户从完成态返回上一个阶段，再走到最后阶段，允许再次点击完成；但不要自动触发礼花。

不需要把完成状态持久化为课程进度，也不做账号级成就系统。

---

## 3. 完成态内容

### Bell

标题：

> ✓ 你已经完成 Bell 实验

回顾：

> **叠加 → 建立关联 → 测量**

一句总结：

> 你看到两个量子位不再只能分别理解，而会形成一个需要整体描述的联合状态。

下一步推荐：

> **接下来看看：这种量子状态变化怎样真正参与一次算法。**

主 CTA：

> `继续看 Grover 搜索 →`

### Grover

标题：

> ✓ 你已经完成 Grover 搜索实验

回顾：

> **准备候选 → 翻转目标方向 → 干涉增强 → 测量**

一句总结：

> 你看到量子搜索不是逐项返回答案，而是先留下方向差异，再通过干涉把它变成测量优势。

下一步推荐：

> **刚才真正起作用的关键之一，是“相位”。接下来单独看看它。**

主 CTA：

> `继续看相位实验 →`

### Phase

标题：

> ✓ 你已经完成相位实验

回顾：

> **概率相同 → 改变方向关系 → 后续行为可能不同**

一句总结：

> 你看到“当前测量概率一样”并不等于“量子状态一样”，相对相位会影响之后的干涉。

下一步推荐：

> **三个正式实验已经看完，现在可以自己描述一个量子程序。**

主 CTA：

> `开始自由探索 →`

三个完成态都提供次级 CTA：

> `返回实验列表`

不要加入分数、徽章、等级、连续完成数或进度百分比。

---

## 4. 下一步导航

推荐顺序固定为：

```text
Bell → Grover → Phase → Free Explore
```

但这只是**推荐路径**，不是锁定路径。

用户仍然可以在 Experiments 页面自由打开任意实验。

### 继续下一个正式实验

点击 Bell → Grover 或 Grover → Phase 后：

- 直接进入目标实验的 Explorer ready 状态
- prompt 使用 `SCENARIOS` 中已经存在的 stable prompt
- **不要自动运行**
- 不复制 / 改写 stable prompt
- 旧实验的 `result / activeStep / activeStoryStage / completion state` 必须清空

当前 `ExplorerScreen` 的 `initialScenarioId` 只用于初始化 state。实现跨实验跳转时要确保新实验得到真正的新 Explorer state；可以通过 App 层更新 `selectedExperimentId` 并用稳定 `key` remount Explorer，或使用等价且清晰的 reset 方案。

不要只修改 prop 却让旧内部 state 留着。

### Phase → Free Explore

点击“开始自由探索”后：

- 进入 Generic Explorer idle 状态
- prompt 为空
- 不自动运行
- 不伪造 Story

### 返回实验列表

回到 `02 Experiments`。

---

## 5. 轻量礼花 / celebration

点击“完成这个实验”时，可以有一次很短的庆祝视觉：

- 约 `600–900ms`
- 一次性 burst
- 数量克制
- 不循环
- 不遮挡完成文案
- 不引入大型 confetti 依赖；优先 CSS / 小型本地 DOM 实现
- 不使用声音

视觉风格继续服从当前 Neutral UI，不要突然变成彩色游戏界面。

### 可访问性

必须支持：

```css
@media (prefers-reduced-motion: reduce)
```

用户偏好 reduced motion 时：

- 不播放粒子 / 位移动画
- 完成态直接出现

礼花属于装饰：

- `aria-hidden="true"`
- 不成为键盘焦点
- 不被屏幕阅读器读成内容

---

## 6. 完成态不是新页面

不要：

- 弹 modal 遮住整个 Explorer
- 跳到独立“恭喜”路由
- 隐藏左侧 Program
- 自动跳转到下一个实验
- 自动运行下一个实验

推荐结构：

```text
┌──────────────────────┬──────────────────────────────┐
│ PROGRAM              │ ✓ 实验完成                  │
│ Circuit              │                              │
│ QASM                 │ 你刚刚看到…                 │
│                      │                              │
│                      │ 接下来推荐…                  │
│                      │ [继续下一个实验 →]           │
│                      │ [返回实验列表]               │
└──────────────────────┴──────────────────────────────┘
```

完成态仍然属于右侧“理解”区域。

---

## 7. 与新手引导的关系

Task 13P 的“如何阅读这个页面？”引导保留。

不要在完成态再增加新的 coach marks。

第一次使用引导负责告诉用户“怎么看”；完成态负责告诉用户“我看完了，下一步去哪”。二者不要混在一起。

---

## 8. 不做

- 不改 Generic / 自定义实验的信息架构
- 不修改 Circuit / QASM 映射逻辑
- 不修改 Story 阶段识别
- 不改 Bell / Grover / Phase stable prompts
- 不新增 API
- 不新增 LLM 调用
- 不修改 Python correctness / validator / semantic verifier
- 不修改 teaching explainer prompt
- 不做持久化课程进度
- 不做成就系统
- 不改 Repair / Backend

---

## 9. 测试要求

至少覆盖：

1. Curated 非最后阶段仍显示“下一阶段”
2. Curated 最后阶段显示“完成这个实验”，不显示 enabled 的“下一阶段”
3. 点击完成后显示对应实验的完成总结
4. Bell 推荐 Grover
5. Grover 推荐 Phase
6. Phase 推荐 Free Explore
7. 继续下一个实验后：
   - 使用 `SCENARIOS` stable prompt
   - 处于 ready / 未运行状态
   - 不继承上一个实验 result
8. Phase → Free Explore 后 prompt 为空、无 Story、未运行
9. GenericWorkspace 不出现完成按钮 / completion UI / confetti
10. 礼花为装饰内容，并对 `prefers-reduced-motion` 安全降级
11. 不改 stable prompts

如果现有测试命令可运行，可以执行；不要为了本 Task 修改无关失败。

---

## 完成标准

正式实验从“最后一步停住”变成一个完整的小闭环：

```text
理解一个阶段
→ 主动进入下一阶段
→ 完成实验
→ 简短回顾
→ 明确推荐下一步
```

同时不把 LoomQ 变成游戏，也不影响自定义实验的通用 Explorer。完成后停止，等待 review。
