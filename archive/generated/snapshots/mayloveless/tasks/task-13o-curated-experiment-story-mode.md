# Task 13O — Curated experiment story mode

## 背景

Task 13N 已经为 Grover 增加了基于真实 trace 的四阶段语义视图，技术方向是正确的：不伪造状态、不依赖固定 Gate index，并且能识别 uniform / oracle / diffusion / measurement。

但当前体验仍然有几个明显问题：

1. `只给目标 |11⟩ 做相位标记` 对零量子背景用户仍然太抽象；
2. 新面板主要展示“当前状态”，缺少清楚的 **做了什么 → 执行前 → 执行后**；
3. 可视化仍然偏数据图表，不像用户期待的“干涉过程可视化”；
4. Explorer 默认按低层 Gate 自动播放，约 1.8 秒就切一次，Grover 展开 Gate 多时页面不断变化，用户不知道该看哪里；
5. 关键文字大量使用 8–12px 和 faint / muted 色，整体偏小、偏暗、阅读费力；
6. 只有 Grover 有专用体验，默认推荐的 Bell 反而看不到这一层增强。

本 Task 不继续给 13N 打补丁，而是把 13N 的真实 trace 能力和原 Explorer 的“发生了什么 / 前后变化”融合成一套 **Curated Experiment Story Mode**，覆盖三个正式实验：Bell、Grover、Phase。

自由探索 / 自定义 prompt 不要求进入 Story Mode，继续使用通用 Explorer 即可。

---

## 核心目标

正式实验打开并运行后，用户首先看到的不是连续变化的 Gate 和数字，而是一帧一帧可以读完的“故事”：

```text
这一阶段要做什么
↓
执行前是什么样
↓
当前操作改变了什么
↓
执行后变成什么样
↓
为什么这件事重要
```

原则：

> **先看懂变化，再补量子术语；语义阶段是主角，低层 Gate 是证据。**

---

# 1. 播放逻辑：默认停住，不再自动扫 Gate

## 必须修改

请求完成后：

- 不要 `setAutoPlaying(true)`；
- 默认停在第一个可解释状态；
- 用户自己点击下一步 / 阶段后再变化。

当前“运行完自动以 1.8 秒逐 Gate 播放”的行为必须停止。

## Curated experiment

Bell / Grover / Phase 的主导航优先按 **语义阶段** 前进，而不是按每个展开后的基础 Gate 前进。

低层 Gate 仍然保留，可在 secondary detail 中查看。

如果保留“自动演示”按钮：

- Curated Story Mode 只自动切换语义阶段；
- 每阶段至少给足阅读时间（建议 4s 左右）；
- 不要再逐 Gate 快速扫过。

也可以本 Task 先只保留手动阶段切换，不强求自动演示。

---

# 2. Story Frame：融合“以前”和“现在”

不要把 GroverMechanism 作为一个新卡片继续堆在现有 state panel 上。

正式实验识别成功时，右侧主区域改成一个统一 Story Frame：

```text
[阶段名 / 一句话目的]

执行前                  当前操作                 执行后
[可视化]        →        [做了什么]       →       [可视化]

[一句：为什么这一步重要]

[查看对应 Gate / 数值 / QASM]
```

必须明确出现：

- **执行前**
- **做了什么**
- **执行后**

用户不应该需要自己对比上一帧和下一帧来猜变化。

原来的：

- `发生了什么？`
- `ProbabilityComparison`
- phase-only 提示
- TechnicalDetails

可以复用数据与逻辑，但要重新组织层级，不要重复展示两套相同信息。

---

# 3. 可视化语言：Interference-style schematic

用户期待的不是普通 bar chart，而更接近“光子干涉实验”那种：**能看见路径 / 波 / 相位方向如何变化，并最终产生干涉结果**。

注意：

> 这只是帮助理解振幅与干涉的教学示意，不要声称 Grover 电路里真的有光子沿这些路径运动。

可以使用 SVG / CSS 做抽象的 wave / path / amplitude visualization。

视觉语言建议统一为：

- 每个候选 / 分支 = 一条清晰路径；
- 波形 / 箭头方向 = 相对相位方向；
- 振幅大小 = 波形高度 / 线条幅度；
- 干涉后增强 = 路径更强、更突出；
- 干涉后抵消 = 路径明显减弱；
- measurement 才转换成 probability 结果。

不要做：

- 粒子特效；
- 循环动画；
- 装饰性科技光效；
- 看起来像真实物理装置、但实际并不对应 trace 的假模拟。

轻量 transition 只用于帮助用户观察 before → after。

---

# 4. Grover Story

复用 Task 13N 已有的真实 trace 识别，不推翻正确性逻辑。

## Stage A — 准备候选

目的：

> 先让 4 个候选拥有同样的机会。

可视化：4 条等强路径 / 波。

文案尽量不用“均匀叠加”作为第一句话；术语可以放第二层：

> 四个候选现在一样强，这种状态叫均匀叠加。

## Stage B — Oracle

不要把主文案写成：

> 只给目标 `|11⟩` 做相位标记。

改成更直观的过程：

> Oracle 对候选执行同一个“是不是目标”的判断。对于符合条件的 `|11⟩`，它把振幅的方向翻过来。

然后补术语：

> 这个“方向翻转”就是相位翻转 / 相位标记。

开发者入口：

> `Oracle ≈ isTarget(x)`，但它不会直接返回答案。

必须视觉上明确：

```text
执行前：4 条波方向一致
        ↓ Oracle
执行后：|11⟩ 的波方向反过来
```

并明确：

> **此时 |11⟩ 的测量概率还没有变大。**

## Stage C — Diffusion / 干涉

重点不是再说“围绕平均振幅反射”就结束。

先用可见结果解释：

> 接下来让四个振幅重新相互作用。目标分支得到增强，其他分支被削弱。

视觉上做成：

```text
Oracle 后的波 / 路径
        ↓ Diffusion / 干涉
目标 |11⟩：建设性增强
其他候选：部分抵消
```

然后 technical copy 再补：

> 数学上可以理解为围绕平均振幅做反射。

## Stage D — Measurement

把最终振幅优势转换成 probability。

不伪造单次随机测量结果。

---

# 5. Bell Story

Bell 是默认推荐实验，也必须得到同等级的 Story Mode。

目标：让用户理解的不是“两个值碰巧一样”，而是关联如何建立。

建议语义阶段：

```text
01 起点
02 分出两个可能分支
03 建立关联
04 测量
```

## 起点

`|00⟩`，两个 qubit 都确定。

## H：分出两个分支

用路径分叉表示：

```text
|00⟩
  ├── 一个分支
  └── 另一个分支
```

用真实 trace 的 basis / amplitude 命名实际分支，不写死端序。

先说：

> 第一个量子位不再只有一个确定状态，程序保留了两个分支。

再补：叠加。

## CX：建立关联

必须做 before → operation → after：

> CX 根据第一个量子位的分支条件改变第二个量子位，最终只留下成对关联的两个分支。

最终视觉应突出 Bell 的两个相关结果分支（例如真实 trace 中对应的 `00 / 11`）。

不要类比成复制 bit / 共享变量。

## Measurement

展示：

> 单次测量只得到一组经典结果；重复运行后，关联模式出现在统计结果中。

如果当前 Web trace 没有真实 shots 数据，不要假装已经采样出具体次数。

---

# 6. Phase Story

Phase 是最适合使用“干涉式视觉语言”的实验之一。

目标：让用户直接看懂：

> **概率没变，不等于状态没变。**

建议阶段：

```text
01 两个分支
02 改变其中一个分支的方向
03 概率仍一样
```

使用现有 `isPhaseOnlyChange` / 真实 amplitude 数据。

核心视觉：

```text
执行前：两个分支波形 / 方向
当前操作：改变相对相位
执行后：波的方向关系改变，但高度 / 概率相同
```

主文案：

> 两个分支的“大小”没有变，所以现在测量概率看起来一样；但其中一个分支的方向变了。

第二层再补：

> 这个方向关系就是相对相位，它会影响以后两个分支再次发生干涉时的结果。

如果展示“以后再次干涉”的示意，必须标成：

> **如果后续重新干涉**

不要伪装成当前 trace 已经执行的步骤。

---

# 7. 低层 Gate / QASM 降级

Story Mode 成功识别时：

主区域不要同时常驻：

- 大量 Gate 文本；
- probability before/after；
- amplitude 数值；
- technical details；
- 新 Story 图；

否则仍然信息过载。

建议：

- Story Frame = 主内容；
- `查看这一阶段对应的 Gate` = disclosure；
- `查看数值` = disclosure；
- 完整 QASM = 继续现有 disclosure。

左侧逐 Gate step list 可以保留，但视觉权重降低；Curated experiment 的语义阶段导航应更明显。

---

# 8. 字体与对比度：本 Task 一并修

当前 Explorer 中存在大量 8px / 9px / 10px / faint 关键文字，不适合作为比赛主要阅读界面。

本 Task 至少调整 Story Mode 和 Explorer 主要信息区：

- 主体说明：至少 14–16px；
- 关键阶段标题：至少 18px；
- 阶段导航：至少 13–14px；
- 重要 basis / 状态标签：至少 13px；
- 仅 metadata / 次要技术标识允许 11–12px；
- 不再用 8–10px 显示需要用户阅读理解的信息。

对比度：

- 关键解释使用 `var(--text)` 或明显可读的次级色；
- `var(--faint)` 只用于真正可忽略的 metadata；
- 不要把关键教学句放在 faint / 很暗的 muted 色里。

整体背景可以继续当前 Soft Dark，不需要再改主题颜色。

---

# 9. 数据与识别要求

所有 Story Mode 必须来自真实、已验证 trace。

- Grover：复用 Task 13N 识别逻辑；
- Bell：从真实 state_before / state_after / measurement events 识别分支与关联；
- Phase：从真实 phase-only change / amplitude 识别；
- 识别失败：回退通用 Explorer，不伪造 Story 数据。

不要依赖固定 operation index。

---

# 10. 不做

- 不改三个 stable prompts；
- 不新增 LLM 调用；
- 不改 Python correctness / semantic verification；
- 不改 teaching explainer prompt；
- 不做自由探索 Story Mode；
- 不做 GHZ Story Mode；
- 不做 Repair / Backend；
- 不重新设计 Learn / Experiments；
- 不做全站主题重构。

---

# 11. 测试要求

至少覆盖：

1. 请求完成后默认 **不自动播放**；
2. Grover Story 能展示 before → Oracle action → after，并避免把“相位标记”作为唯一解释；
3. Bell 正式实验可以进入 Story Mode；
4. Phase 正式实验可以进入 Story Mode；
5. Story 识别失败安全 fallback；
6. Story Mode 关键教学文案不依赖 8–10px 样式；
7. 三个 stable prompts 逐字不变；
8. 自由探索仍走通用 Explorer；
9. 不新增后端 / LLM 请求。

---

# 完成标准

一个第一次接触量子计算的软件开发者运行三个正式实验时：

- 页面默认停住，能先读完再操作；
- 一眼知道当前“做了什么”；
- 同一屏看到执行前和执行后的差别；
- Grover 能看懂“方向翻转 → 干涉增强”，而不仅是看到四根振幅柱；
- Bell 能看懂“分支 → 建立关联”；
- Phase 能看懂“概率不变，但分支方向关系改变”；
- 低层 Gate / QASM 仍然可查，但不抢主视觉；
- 主要文字不再因为过小、过暗而费力。

完成后停止，等待 review。