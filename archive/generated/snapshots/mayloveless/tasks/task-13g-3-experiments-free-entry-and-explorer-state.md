# Task 13G-3 — Experiments Free Entry + Explorer Idle / Loading State

## 背景

13G / 13G-2 已经完成：

- Learn → Experiments → Explorer 的主路径；
- 01 Learn / 02 Experiments / 03 Explorer / 04 Repair / 05 Backend 全局导航；
- Bell / Grover / Phase 三个正式实验；
- Repair / Backend 进阶能力占位。

本任务只做 13G 的最后一轮 UX 收口，解决两个当前明显问题：

1. Experiments 页支持自由输入 prompt，但入口放在页面底部，不容易被第一次访问的用户发现；
2. Explorer 在尚未运行时已经展示类似 loading 的骨架 / 占位结构，容易让用户误以为系统已经开始执行。

本任务完成后，13G 系列即可验收。Explorer Result 工作区的进一步信息瘦身另开任务处理。

---

## 目标一：Experiments 提前说明“可以自由输入”

Experiments 不只是三个预设实验目录。LoomQ 的核心能力之一是：用户可以直接用自然语言描述自己想探索的量子程序。

### 页面结构调整

将当前底部的自由探索入口移动到 Hero 之后、三张正式实验卡之前。

建议阅读顺序：

```text
选择一个量子实验
不知道从哪里开始？从下面三个实验开始。

已经有自己的想法？
直接描述你想探索的量子程序 →

Bell / Grover / Phase
```

要求：

- 自由探索入口在首屏 / 上半区容易被发现；
- 视觉权重低于 Hero 和三张正式实验，不做成第四张实验卡；
- 点击后继续进入 Explorer，`selectedExperimentId = null`，prompt 为空；
- 不自动运行，不触发 `/api/debug`；
- 删除页面底部原有重复的自由探索入口，避免同一功能出现两次；
- 文案应明确说明用户可以自己输入自然语言 prompt，而不是只能选择三个示例。

建议文案：

> 已经有自己的想法？直接描述你想探索的量子程序 →

可以在其附近增加一行弱化说明：

> 不限于下面三个示例，Explorer 支持直接输入自然语言实验需求。

不要使用“高级模式”“自定义模式”等会让普通用户误以为门槛更高的称呼。

---

## 目标二：Explorer 明确区分 Idle / Loading / Result

Explorer 必须让用户一眼知道系统目前处于什么状态。

### 状态定义

#### 1. Idle

条件：

- `loading === false`
- `result == null`

此时系统没有执行任何生成 / 验证任务。

**禁止出现：**

- loading skeleton；
- staged loading process；
- 闪烁或灰色步骤骨架；
- 看起来像“正在准备电路”的占位图；
- 任何暗示已经请求模型的状态。

Idle 应明确表达：

> 输入已经准备好，等待用户点击“运行量子程序”。

### 从正式实验进入时

例如从 Bell 进入：

- textarea 仍显示对应稳定 prompt；
- workspace 不显示伪步骤或骨架；
- 可以使用简洁静态 empty state 告诉用户下一步：

```text
Bell 实验已准备好

LoomQ 会先生成并验证量子程序，
再带你逐步查看状态变化。

点击上方“运行量子程序”开始。
```

文案不必逐字一致，但必须明确“尚未运行”。

### 自由探索进入时

prompt 为空。

Empty state 应强调：

```text
描述你想探索的量子程序

例如：让两个量子比特形成 Bell 态并测量

输入后点击“运行量子程序”。
```

不要在 workspace 内再复制一个真正的 textarea；输入仍使用页面现有 request textarea。

#### 2. Loading

条件：

- `loading === true`

只有此状态允许展示：

- `LoadingProcess`；
- staged process；
- skeleton；
- “正在生成并验证量子程序…”等状态。

现有加载阶段可以继续使用：

- 理解需求；
- 生成电路；
- 本地验证；
- 准备探索视图。

这些阶段仍然只是 presentation-only staged indicator，不得改造成虚假的实时 Agent Trace，也不得用 ✓ 声称尚未真实完成的步骤已经完成。

#### 3. Result

条件：

- `result != null`

继续使用当前真实 Explorer workspace。

**本任务不要修改 Result 工作区的信息架构。**

不要顺便修改：

- 左侧真实执行步骤；
- 中间 current operation；
- 右侧 state visualization；
- autoplay；
- QASM 展开；
- Teaching Explainer；
- concept card；
- phase presentation。

这些后续单独优化。

---

## 状态真值原则

UI 必须严格根据真实状态展示：

```text
Idle   = 还没有发请求
Loading = 请求正在处理中
Result  = 已拿到真实 response
```

禁止使用静态 skeleton 来装饰 Idle 页面。

特别注意：从 Experiments 点击实验只负责选择 / 预填 prompt，**不代表已经开始实验**。

---

## 不在本任务范围

不要修改：

- `/api/debug`；
- `adapter.agent_chat()`；
- L2 prompt / correctness；
- parser / verifier / repair；
- backend selector；
- Teaching Explainer；
- Circuit Trace；
- Bell / Grover / Phase 稳定 prompt；
- Repair / Backend 页面；
- Learn 页面；
- Explorer Result 工作区布局；
- 实验完成态；
- Error Recovery；
- 真机运行入口。

不要新增 LLM 调用。

---

## 测试 / 验收

至少补充或调整测试确认：

1. Experiments 自由探索入口出现在三张正式实验之前；
2. 页面中只保留一个自由探索入口；
3. 自由探索进入 Explorer 时 textarea 为空；
4. 从正式实验进入 Explorer 时稳定 prompt 正确预填；
5. `loading=false && result=null` 时不渲染 loading process / skeleton；
6. Idle 页面有明确“尚未运行 / 点击运行开始”的提示；
7. `loading=true` 时才渲染 LoadingProcess；
8. Result 模式保持现有真实 workspace；
9. 不自动调用 `/api/debug`；
10. Bell / Grover / Phase prompt 不变化。

完成后停止，不继续 Explorer Result 信息瘦身。
