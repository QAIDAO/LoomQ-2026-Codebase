# Task 13C：Web Quantum Debugger 解释层 UX

## 背景

Task 13B 已完成第一版 Web Quantum DevTools MVP。当前页面已经具备：

- 自然语言 Prompt；
- Agent Trace；
- Circuit Trace；
- QASM 与当前 Gate 高亮；
- 逐步回放；
- 概率展示；
- 技术细节；
- 深色 DevTools / IDE 风格。

当前核心问题已经不再是“能不能看见量子状态变化”，而是：

> **一个懂软件开发、但没有量子背景的人，是否能理解为什么这段电路要这样写。**

现有页面主要回答：

> 这一步做了什么？

例如 H 后从 `|00>` 变为 `|00> / |10>` 各 50%。

但还缺两个关键问题：

> 为什么这里需要这一步？
>
> 我为了理解当前步骤，最低限度需要知道哪个量子概念？

本任务只补这层解释能力，不继续扩大 Web 功能范围。

---

## 产品定位

不要把产品叙事限定为“量子版 Chrome DevTools”。

更准确的定位是：

> **Quantum Debugger for Software Developers**
>
> 不懂量子，也可以像调试代码一样，一步一步看懂量子程序为什么这样写、每一步发生了什么，以及 LoomQ 为什么认为它是正确的。

DevTools / Debugger 是用户熟悉的交互心智模型；真正的产品价值是降低量子理解门槛。

本任务不要求统一改完所有 branding 文案，但新增 UX 与文案应遵守这个定位。

---

# 本任务只解决 3 个核心问题

## 1. 增加“初始化”步骤

当前 Circuit Steps 从第一个 Gate 开始，新手容易误以为 `|00> 100%` 是 H 门产生的结果，而不是电路的初始状态。

在 Circuit Trace UI 中增加一个只用于展示的初始化步骤：

```text
0  初始状态
   |00> 100%

   所有量子位从 |0> 开始。
   这是这段程序执行前的起点。
```

要求：

- 不修改真实 QASM；
- 不伪造一个 GateOperation；
- 可以由 Web 视图根据第一个 gate 的 `state_before` 派生；
- 或增加明确的 presentation model；
- 不要污染底层 Circuit Trace 的科学语义；
- 初始化步骤参与上一步 / 下一步 / 自动播放；
- QASM 此时不高亮任何真实 gate；
- 线路图可显示“尚未执行任何门”的状态。

---

## 2. 每一步回答“为什么这里需要它”

当前 gate description 是通用说明，例如：

```text
H 门：把振幅重新分配到多个基态，使量子位进入叠加。
```

这只能回答 Gate 的通用作用，不能回答当前电路里的设计意图。

例如 Bell 电路：

```text
H q[0]
为什么：先制造两条可能路径，为后面的 CX 建立纠缠做准备。
```

```text
CX q[0], q[1]
为什么：把第二个量子位与第一个量子位关联起来，使两条路径变成 00 和 11。
```

### 不要把“为什么”做成本地 Gate 模板

同一个 H 在不同电路中的目的不同，不能写成固定映射。

允许新增一个 **Web Debug 专用 Teaching Explainer 模型调用**。

推荐结构：

```text
原始用户目标
+
最终已验证 QASM
+
现有 Circuit Trace
        ↓
Teaching Explainer
        ↓
结构化教学解释
```

重要边界：

- Teaching Explainer 只解释，不参与 QASM 生成；
- 不参与 Parser / semantic verification；
- 不修改 target；
- 不修改 Fidelity；
- 不修改 backend selection；
- 不触发 repair；
- 即使解释失败，已验证 QASM 和原始 Debug 页面仍应可用；
- 该模型调用只存在 Web Debug 体验，不进入正式 `adapter.agent_chat()`；
- 不改变正式 L2 objective 的模型调用次数。

### Teaching Explainer 输入

只给它解释所需的最小安全数据，例如：

```text
original_prompt
final_validated_qasm
circuit steps:
- operation_index
- gate
- qubits
- parameters
- state_before
- state_after
```

不要传：

- API Key；
- headers；
- raw OpenAI response；
- 环境变量；
- traceback；
- 本地绝对路径。

### Teaching Explainer 输出协议

必须是结构化 JSON，不要让前端解析散文。

建议：

```json
{
  "circuit_goal": "制备并测量 Bell 态",
  "steps": [
    {
      "operation_index": 0,
      "purpose": "先制造两条可能路径，为后面的纠缠做准备。",
      "concept": "叠加",
      "concept_explanation": "一个量子位在测量前可以由多个基态共同描述；这里可先把它理解成后续计算同时保留了两条可能路径。"
    },
    {
      "operation_index": 1,
      "purpose": "把第二个量子位和第一个量子位关联起来，使两条路径变成 00 与 11。",
      "concept": "纠缠",
      "concept_explanation": "两个量子位的状态开始作为整体关联，不能再只分别看每一个量子位。"
    }
  ]
}
```

可以允许：

```text
concept: null
concept_explanation: null
```

不是每一步都必须塞一个新概念。

### 校验与降级

至少验证：

- `steps` 是数组；
- `operation_index` 必须对应真实 Circuit Trace gate；
- 不允许解释器创造不存在的 gate；
- `purpose` 必须是短字符串；
- concept 可空；
- 多余 / 非法 step 应忽略或整体安全降级，不影响主页面；
- Teaching Explainer 调用异常时 UI 使用现有 gate description 继续工作。

不要因为 explainer 输出失败重新调用多次模型；本任务最多允许一次 explainer 调用。

---

## 3. Just-in-time 量子概念解释

本任务需要解释量子基础，但**不要做量子基础课程**。

原则是：

> 只有当前步骤确实用到某个概念时，才解释这个概念。

例如：

```text
H q[0]

为什么这里需要它？
为后面的纠缠准备两条可能路径。

发生了什么？
|00> 100%
↓
|00> 50%
|10> 50%

💡 叠加
一个量子位现在由多个基态共同描述。
[了解更多]
```

```text
CX q[0], q[1]

为什么这里需要它？
让第二个量子位跟随第一个量子位，把两条路径关联成 00 / 11。

💡 纠缠
两个量子位现在需要作为一个整体理解。
```

### 展示层级

每一步的主要信息顺序固定为：

```text
① 当前操作
② 为什么需要这一步
③ 状态发生了什么变化
④ 当前涉及的量子概念（如有）
⑤ 技术细节（折叠）
```

默认首屏不要出现长篇量子理论。

`concept_explanation` 控制在 1～3 句话。

不要主动解释：

- 希尔伯特空间；
- 完整线性代数；
- 狄拉克符号体系；
- 密度矩阵；
- 量子力学历史。

除非当前程序确实需要，否则不进入本任务。

---

# 相位变化：本任务只做最小增强

这是 P1，不要发展成新的大任务。

现有 RZ / S / Bell- 等案例可能出现：

```text
probability before == probability after
```

但 complex amplitude / phase 已变化。

当前页面不能只给用户“看起来什么也没变”。

增加一个轻量提示：

```text
概率没有变化，但相位发生了变化。
相位不会总是立刻体现在测量概率里，但会影响后续干涉。
```

技术细节里继续保留 complex amplitude。

不要求本任务做：

- Bloch sphere；
- 复平面动画；
- phase wheel；
- amplitude arrow；
- 干涉可视化动画。

只要用户能知道“概率没变 ≠ 状态没变”即可。

---

# Web 页面调整

不要推翻 13B UI。

在当前 Current Step / 右侧解释区域基础上调整信息层级。

每个步骤至少能清楚看到：

```text
Step 1 / 3 · H q[0]

为什么这里需要它？
为后面的纠缠准备两条可能路径。

发生了什么？
[现有 before → after 概率可视化]

💡 叠加
[短解释]

[展开技术细节]
```

### Circuit Goal

在执行结果出来后，页面显著但不抢占主区域的位置展示：

```text
目标：制备并测量 Bell 态
```

优先使用 Teaching Explainer 的 `circuit_goal`。

如果 explainer 不可用，可以退回用户原始 Prompt 的简短展示，不再额外调用模型。

---

# Agent Trace 的位置保持次要

不要因为增加 Teaching Explainer，把 Agent Trace 再提到主视觉。

产品主线仍然是：

```text
用户目标
→ Quantum Circuit
→ 单步理解
→ 状态变化
→ 为什么正确
```

“LoomQ 如何验证”继续作为可展开可信度区域。

Teaching Explainer 自己也不需要在 Agent Trace 主流程里伪装成 correctness step。

可以单独标注：

```text
教学解释：由模型根据已验证电路生成，不参与正确性判断。
```

必要时放在技术细节或帮助文案里，不要抢占主流程。

---

# 重点体验案例

本任务只需要重点把以下案例打磨清楚，不要追求覆盖所有量子算法。

## A. Bell

Prompt：

```text
生成一个 Bell 态并测量
```

必须能清楚看到：

```text
初始化
→ H：为什么要先叠加
→ CX：为什么形成关联
→ Measure：为什么最终要读成经典结果
```

这是本任务最重要的验收案例。

## B. GHZ

确认 3 qubit 时同样可以说明：

- 第一个 H 创建两条路径；
- 后续 CX 把更多 qubit 加入同一个关联状态；
- 不要求解释器写成长篇 GHZ 理论。

## C. Phase

使用现有一个相位案例，例如 Bell- / S / RZ。

确认页面能表达：

```text
概率可能保持不变
但状态的相位发生变化
相位会影响后续干涉
```

---

# 本任务明确不做

不要做：

- 全面重做 UI；
- 新设计系统；
- 真机执行入口；
- onboarding wizard；
- 量子基础课程页；
- 知识图谱；
- 聊天式追问教程；
- SSE / WebSocket；
- 实时 Agent streaming；
- Monaco；
- Bloch sphere；
- 复杂 statevector 筛选器；
- 自动回放速度控制；
- 大规模概率列表优化；
- 复杂多寄存器线路编辑器；
- Backend 页面重做；
- L3。

这些先不要顺手做。

---

# 正式 L2 路径保护

必须保持：

- `adapter.agent_chat()` 不变；
- 正式 Backend 路径仍 1 次模型调用；
- 正式 QASM 正常路径仍 2 次模型调用；
- repair 最多 3 次；
- Teaching Explainer 不进入正式路径；
- Fidelity / pure-state guard / backend filtering 不变；
- 不修改现有 target judge Prompt 以服务 UI；
- 不修改现有 QASM 生成 Prompt 以获得更好的教学解释；
- Web explainer 失败不能导致已验证 Agent 任务失败。

---

# 测试

至少覆盖：

1. 初始化 presentation step 存在且排在第一个真实 Gate 前；
2. 初始化步骤不对应虚假 QASM 行；
3. Teaching Explainer 只调用一次；
4. explainer 输入使用最终已验证 QASM，而不是未验证 candidate；
5. explainer 输出 operation_index 只能映射真实 Circuit Trace gate；
6. invalid / missing explainer response 会安全降级到现有 UI；
7. explainer 失败不改变最终 QASM / Agent reply；
8. `adapter.agent_chat()` 不触发 Teaching Explainer；
9. Bell 页面 H / CX 至少都出现 `purpose`；
10. concept 有值时展示 Just-in-time concept block；
11. concept 为空时不显示空卡片；
12. phase-only 变化时能显示“概率未变但相位变化”的提示；
13. 原有 Web / Trace / L2 专项测试继续通过；
14. 全量 Python 测试继续通过；
15. Web build 通过；
16. `python evaluator.py --level l2` 继续 PASS。

---

# 手工体验验收

完成后请实际运行 Web，并用 Bell 从初始化走到 Measure。

人工判断以下问题：

1. 不看 QASM，只看右侧解释，能不能理解每一步为什么存在？
2. 是否能意识到 `|00> 100%` 是初始状态，而不是 H 的输出？
3. 是否能用一句话理解“叠加”？
4. 是否能用一句话理解“纠缠”？
5. 是否明显区分：
   - Gate 做了什么；
   - 为什么这里用这个 Gate；
   - 状态具体发生了什么变化？
6. 技术细节是否仍然可查看，但默认不压过新手解释？

如果这些成立，本任务结束。

不要在本任务继续修其他已知 UX backlog。

---

# 完成后汇报

只汇报：

1. 初始化步骤如何实现；
2. Teaching Explainer 的输入 / 输出 schema；
3. 如何保证它不进入正式 L2 correctness path；
4. Bell 的 H / CX / Measure 实际解释结果；
5. GHZ 实际解释结果；
6. phase 案例如何提示“概率未变但相位变化”；
7. explainer 失败时的降级行为；
8. Web build / Python tests / L2 evaluator 结果；
9. 实际页面体验后仍然最明显的 3 个 UX 问题。

本任务结束时不要 commit，不要 push，等待人工复核。
