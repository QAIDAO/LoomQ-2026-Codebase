# Task 13Q — Unify Generic Explorer into the two-column shell

## 背景

Task 13P 已把 Bell / Grover / Phase 的 curated Story 模式改成两栏：

- 左：Program（Circuit + QASM）
- 右：Story（语义阶段解释）

当前没有 Story 的自由探索 / 自定义实验仍回退到旧三栏 Generic Explorer。功能虽然完整，但从同一个 Explorer 里切换过去会明显像两个不同产品。

本 Task 不再维护“两套页面骨架”，而是让 **Curated 与 Generic 共用同一个两栏信息架构**；差异只发生在“导航粒度”和“右侧解释内容”。

---

## 目标

统一 Explorer 心智：

```text
左边 = 程序本身
右边 = 帮你理解当前内容
```

### 有 Story 的正式实验

保持 Task 13P：

```text
Program | Story
```

- 左边按 Story 阶段高亮一组 Gate / QASM 行
- 右边按语义阶段解释

### 没有 Story 的自由探索 / 自定义实验

也使用相同两栏：

```text
Program | 当前步骤解释
```

- 左边按单个 Gate / QASM 行导航
- 右边展示原 Generic Explorer 的当前步骤、状态变化、概念解释和技术细节

不要重新显示旧的第三栏。

---

## 1. Generic 左栏：Program

没有 Story 时，左栏沿用 curated Program 的视觉骨架：

```text
PROGRAM
已生成并通过 LoomQ 验证

步骤 / Gate 导航
Circuit
OpenQASM
```

### Step list 不再作为独立第三栏

把旧 `CIRCUIT STEPS` 的能力放回 Program 栏内部，但做成紧凑导航，而不是恢复 235px 独立 sidebar。

推荐：

- 放在 Circuit 上方；
- 使用横向可滚动 / 紧凑 step strip，或其他不会挤占一整栏的形式；
- 展示 step number + `stepTitle`；
- 当前 step 明显高亮；
- warning 可以靠近该导航显示，但不要恢复旧 sidebar。

### Circuit + QASM

- Circuit 默认可见；
- QASM 默认展开，与 curated 模式保持一致；
- 点击 step / Circuit Gate：
  - 更新当前 Gate；
  - 高亮对应 Circuit Gate；
  - 高亮并滚动到真实 QASM 行；
- 不存在 Story 时只高亮单个当前 Gate / QASM 行，不伪造语义范围。

可以复用 / 抽取 Task 13P 的 Program 组件，不要复制两套 Circuit / QASM DOM。

---

## 2. Generic 右栏：原来的“理解当前步骤”内容

没有 Story 时，右栏不显示 `STORY`、Story stage nav 或 curated coach marks。

右栏改为类似：

```text
EXPLAIN
当前步骤

H q[0]
为什么这里需要它？
...

发生了什么？
执行前 → 执行后

💡 当前概念
...

[技术细节]

← 上一步        下一步 →
```

复用现有 Generic Explorer 已有能力：

- `stepTitle(current)`
- current statement / current QASM line（如果重复可只保留轻量引用）
- `currentPurpose`
- `StateDetailContent`
  - before / after probability
  - phase-only 提示
  - measurement mapping
- `ConceptCard`
- teaching explainer 内容
- `TechnicalDetails` 保持折叠
- teaching disclaimer

### 概念解释不要藏太深

`ConceptCard` 在 Generic 右栏仍应作为正文内容显示，而不是被塞入 technical disclosure。

---

## 3. Generic 导航粒度

没有 Story 时仍然是 **逐 Gate / step 粒度**。

右栏底部保留：

- 上一步
- 下一步

Autoplay：

- 只允许 Generic 模式存在；
- 默认关闭；
- 如果保留按钮，作为次要操作，不要比“下一步”更显眼；
- Curated 模式继续完全不显示 autoplay。

---

## 4. 两种模式必须看起来是同一个 Explorer

尽量共享以下视觉：

- 两栏宽度 / gutter / panel 背景
- Program header
- verified status
- Circuit 样式
- QASM 样式
- 主体字号与对比度

区别只应是：

```text
Curated：右边按 Story stage
Generic：右边按 Gate step
```

不要让用户感觉进入自定义实验后“跳回旧版调试器”。

---

## 5. Fallback 约束

`experimentStory == null` 包括：

- 自由探索
- 自定义 prompt
- Story 构建失败的正式实验

这些情况必须进入新的 **Generic two-column**，而不是空白，也不是旧三栏。

Story 构建失败时：

- 不能伪造 Story；
- 仍然完整展示真实 Circuit / QASM / step state / teaching；
- correctness 结果不受影响。

---

## 6. 不做

- 不修改 `buildExperimentStory` 的语义识别规则
- 不修改 Bell / Grover / Phase Story 文案和可视化
- 不修改 stable prompts
- 不修改 Python correctness / validator / semantic verifier
- 不新增 LLM 调用
- 不修改 teaching explainer prompt
- 不修改 Repair / Backend
- 不恢复旧三栏 sidebar

---

## 7. 测试要求

至少覆盖：

1. Story 存在时仍渲染 `curated-two-column`
2. Story 不存在时渲染 `generic-two-column`
3. Generic 不包含独立 `CIRCUIT STEPS` sidebar / 三栏布局
4. Generic Program 包含：
   - step 导航
   - Circuit
   - 展开的 QASM
5. Generic 右栏包含：
   - current step / purpose
   - state change
   - ConceptCard（有 teaching concept 时）
   - technical details
   - 上一步 / 下一步
6. Generic step 切换能同步 Circuit 与 QASM 当前行
7. Generic 可以保留 autoplay，但默认关闭；Curated 不出现 autoplay
8. Story 构建失败安全进入 Generic two-column
9. stable prompts 保持原值

如果现有测试命令可运行可以执行；不要为本 Task 修改无关失败项。

---

## 完成标准

从 Bell / Grover / Phase 切到自由探索时，用户应感觉自己仍在同一个 Explorer：

```text
左侧一直是“程序”
右侧一直是“解释”
```

只是：

- 正式实验由 Story 帮用户按语义阶段理解；
- 自定义实验由 LoomQ 按真实 Gate 一步步解释。

完成后停止，等待 review。
