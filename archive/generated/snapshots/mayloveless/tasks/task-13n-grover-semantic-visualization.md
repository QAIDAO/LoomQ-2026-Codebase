# Task 13N — Grover semantic visualization in Explorer

## 背景

Task 13M 已经把 Experiments 的三张卡改成“普通开发者的直觉问题”。卡片只负责让用户愿意点进去，不需要在卡片上把量子机制讲完。

下一步先把 **Grover** 做成一个真正能看懂的实验：不是继续加文字，而是把目前隐藏在低层 Gate / statevector 里的关键过程可视化。

本 Task 只处理 `search / Grover` 场景，不做 Explorer 全局重构。

---

## 目标

用户打开 Grover 实验并运行后，不需要理解全部 Gate，也能看懂这条主线：

1. **准备候选**：4 个候选先处于均匀叠加
2. **Oracle 标记**：目标 `|11>` 被相位标记，但此时测量概率还没有增加
3. **Diffusion 放大**：通过干涉 / 关于平均振幅的反射，让目标振幅变大
4. **测量**：现在 `|11>` 更容易被测到

核心教学句：

> Oracle 负责“标记谁是目标”，Diffusion 才负责把这个标记转化成更高的测量概率。

开发者类比可使用：

> `Oracle ≈ isTarget(x)`

但必须同时明确：

> Oracle 不直接返回答案，只给目标做相位标记。

---

## 交互与视觉

### 1. 只在 Grover 场景显示专用机制视图

当且仅当：

- 当前选中场景为 `search`
- 已经有真实、已验证的 circuit trace
- 能从 trace 中安全识别下面的关键状态

才显示 `GroverMechanism`（命名可调整）。

如果识别失败：

- **不要伪造演示数据**
- 不要根据固定 Gate 下标硬猜
- 直接回退到现有 Explorer 通用状态视图

### 2. 四个语义阶段

专用视图展示四个阶段：

```text
01 均匀叠加
02 Oracle 标记
03 Diffusion 放大
04 测量
```

阶段可以点击，并跳到对应的真实 trace step。

当前低层 Gate 所在的语义阶段需要高亮，但不要隐藏现有逐 Gate 导航能力。

### 3. 振幅而不是只有概率

Grover 的关键是：Oracle 后**概率没变，但相位变了**。

因此专用视图不要继续只画 probability bar。

建议用 4 个基态：

```text
|00>  |01>  |10>  |11>
```

以中心线表示 0：

- 振幅在中心线上方：正方向
- 振幅在中心线下方：相对相位翻转
- 高度表达振幅大小
- 测量阶段可以再转回 probability / measurement emphasis

Oracle 阶段应能一眼看到类似：

```text
00 ↑   01 ↑   10 ↑   11 ↓
```

并显示一句：

> `|11>` 已被标记，但测量概率仍与其他候选相同。

Diffusion 阶段应能看到目标振幅被放大，例如：

```text
00 ·   01 ·   10 ·   11 ↑↑↑
```

可轻量标注：

> Diffusion：围绕平均振幅做反射

注意：**不要把 Oracle 画成“镜子”**。如果使用“反射 / 镜像”视觉，它属于 Diffusion。

### 4. 动画

允许非常轻的状态切换动画：

- 振幅柱在语义阶段变化时做短 transition
- Oracle 时 `|11>` 从上方翻到下方
- Diffusion 时目标柱被放大

不要：

- 循环动画
- 游戏化粒子效果
- 与现有 1.8s 自动回放再叠一套独立计时器

动画只是现有真实 trace 状态变化的呈现。

---

## 从真实 trace 识别关键阶段

不要依赖固定 Gate index，因为 Grover prompt 要求基础门展开，LLM 可能生成等价但不同的 Gate 序列。

可在前端 / `viewModel` 增加纯函数，从真实 `StateEntry[]` 中识别候选快照。

### A. 均匀叠加 snapshot

寻找较早的 gate step：

- 有 `00 / 01 / 10 / 11` 四个基态
- 四个 probability 约为 `0.25`

允许小 tolerance。

### B. Oracle 标记 snapshot

在均匀叠加之后寻找：

- 四个 probability 仍约为 `0.25`
- `|11>` 与非目标基态出现相对相位翻转

相位判断必须考虑**全局相位不影响物理状态**，不能简单写死“`|11>` real < 0”。

建议以某个非零非目标振幅为 reference，比较相对相位；如果状态包含无法安全投影成该教学图的复杂相位，则放弃专用视图并 fallback。

### C. Diffusion / amplification snapshot

Oracle snapshot 之后寻找：

- `|11>` 的 probability 明显高于其他候选
- 且相对均匀态已经发生明显放大

不要写死必须 100%。真实 trace 是唯一数据源。

### D. Measurement

使用真实 measurement event 和 measurement 前的概率分布。

不要生成假的单次测量结果。

---

## Explorer 中的信息层级

本 Task 不重做 Explorer，但 Grover 场景可以先试验一条以后可复用的原则：

> **语义状态变化是主角，低层 Gate / 原始数值是技术细节。**

如果专用 Grover 视图成功识别：

- 它应成为右侧 state panel 的主要可视化
- 现有逐 Gate `ProbabilityComparison` / 复振幅明细仍可保留，但降为 secondary detail / disclosure
- 不要把新视图简单堆在现有所有信息上方，导致页面更拥挤

左侧 step list、CircuitDiagram、QASM disclosure 暂时都保留；本 Task 不做 Explorer 全局瘦身。

---

## 文案约束

必须准确表达：

- `Oracle ≈ isTarget(x)` 只是开发者理解入口
- Oracle 标记目标，而不是告诉用户答案
- 标记的核心是相位变化
- Oracle 后测量概率可以仍然不变
- Diffusion / 干涉把相位差转化成目标振幅 / 概率优势
- 测量发生在最后

不要写：

- “Oracle 找到了 |11>”
- “Oracle 放大了答案”
- “Oracle 是镜子”
- “量子计算同时把所有答案算出来然后挑正确的”

---

## 不做

- 不修改 `SCENARIOS.search.prompt`，stable prompt 必须逐字保持
- 不改 Bell / Phase / GHZ
- 不新增后端 API
- 不修改 Python correctness / validator / semantic verifier
- 不增加新的 LLM 调用
- 不修改 teaching explainer prompt
- 不改自动回放定时逻辑
- 不做 Explorer 全局 layout 重构
- 不做 Repair / Backend

---

## 测试要求

至少覆盖：

1. 用构造的 canonical 2-qubit Grover trace 可以识别：
   - uniform
   - oracle-marked
   - amplified
   - measurement
2. Oracle 识别不依赖固定 operation index
3. 全局相位翻转后仍能正确识别相对相位标记，或安全 fallback
4. 缺少关键 snapshot 时不渲染专用 Grover 机制，不伪造状态
5. `SCENARIOS.search.prompt` 保持原值
6. Bell / Phase 页面行为不受影响

如果仓库现有测试命令可运行，可以执行；不要为了本 Task 修改与之无关的失败项。

---

## 完成标准

运行 Grover 实验后，一个没有量子背景但懂软件开发的人，应该能只看右侧主视觉理解：

```text
4 个候选一样
→ Oracle 像 isTarget(x) 一样标记 |11>（相位翻转，概率还没变）
→ Diffusion 把这个标记变成振幅优势
→ 最后测量时 |11> 更容易出现
```

完成后停止，不继续改 Explorer 其他问题，等待 review。
