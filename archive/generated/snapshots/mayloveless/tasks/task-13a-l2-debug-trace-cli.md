# Task 13A：Quantum Debug Trace Engine + 极薄 CLI

## 背景与定位

L1 与 L2 客观评分链路已经稳定。接下来进入 L2 交互体验与新手引导。

目标用户不是“已经会量子计算、只想跨平台开发的量子开发者”，而是：

> **懂软件开发，但没有量子计算背景的 Web / AI / 应用开发者。让他们借用熟悉的 DevTools / Debugger 心智模型，第一次理解、生成、验证并运行一个量子程序。**

最终产品准备做成 Web Quantum DevTools。

这个产品有两层需要同时解释：

1. **Agent Trace**：LoomQ 是怎样理解请求、生成、校验、修复和选后端的；
2. **Circuit Trace**：量子电路每执行一个 gate，量子状态实际上发生了什么变化。

本任务不做正式 Web UI，而是先建立未来 Web 可以直接复用的统一 Trace Engine，并用一个**极薄 CLI**验证抽象成立。

不要为了拆任务而把 Trace Engine 与 CLI 再分开；但也不要把 CLI 做成正式产品。

---

## 目标

实现一套稳定、结构化、可序列化、无 UI 绑定的调试数据协议，覆盖两类 trace：

```text
用户自然语言
  ↓
┌──────────── Agent Trace ────────────┐
│ [LLM] Intent / Candidate            │
│ [LLM] Target Judge                  │
│ [LOCAL] Parser                      │
│ [LOCAL] Semantic Verify / Fidelity  │
│ [LLM] Repair（必要时）              │
│ [LOCAL] Backend Selection           │
└─────────────────────────────────────┘
  ↓
最终已验证 QASM
  ↓
┌──────────── Circuit Trace ──────────┐
│ Gate 1 → state before / after       │
│ Gate 2 → state before / after       │
│ ...                                 │
│ Measurement → classical readout说明 │
└─────────────────────────────────────┘
```

CLI 只需要证明这两类 trace 可以被逐步消费：

```text
[n / Enter] next
[c] continue
[q] quit
```

---

## 第一原则：生产 Agent 不复制、不改评分语义

严禁为了 CLI 或 Web 再实现一份 `agent_chat`。

应让当前生产 Agent 支持可选 observer / trace sink，例如：

```python
_run_agent(prompt: str, trace_sink=None) -> str
```

或等价设计。

要求：

- `agent_chat(prompt)` 仍走同一条生产路径，默认 `trace_sink=None`；
- Debug CLI 调同一条生产路径，只是打开 trace；
- 不能出现“正式评分走 A、CLI 走 B”；
- Agent Trace 不增加任何 LLM 调用；
- Agent Trace 不额外重复 Parser / semantic verifier；
- Trace 关闭时不得产生 stdout/stderr、额外网络请求或额外 SDK 工作；
- `starter_kit/adapter.py` 的官方 `agent_chat(prompt: str) -> str` 签名和返回格式保持不变。

**Circuit Trace 是调试体验专用能力，可以进行额外的本地模拟，但只能在显式 debug/trace 模式启用；正式 `agent_chat` 绝不能因此多跑模拟器。**

---

## 统一 TraceEvent 协议

新增轻量模块，例如：

```text
starter_kit/loomq/debug_trace.py
```

具体使用 dataclass / TypedDict 均可，不引入新依赖。

每个事件至少包含：

```text
seq        单次调试内递增序号
layer      agent | circuit
stage      稳定机器字段
executor   llm | local
status     running | ok | warning | error
summary    给开发者看的简短说明
data       结构化安全数据
```

不要把 CLI 排版字符串本身当成 Trace 协议。

未来 Web 必须可以直接消费这些事件，而不需要从终端文本重新解析。

---

# Part A：Agent Trace

## 建议阶段

QASM 正常路径至少：

```text
intent
qasm_candidate
target_spec
parser_validation
semantic_verification
agent_result
```

触发修复时追加：

```text
repair_started
repair_candidate
```

Backend 路径至少：

```text
intent
backend_constraints
backend_selected
agent_result
```

阶段命名可结合当前代码结构微调，但必须稳定、可测试。

## Agent Trace 可包含

- `task_type`；
- 候选 / 最终 QASM；
- 是否要求测量；
- local pure-state guard 是否命中；
- target verification mode；
- target qubit count；
- target amplitudes；
- Parser 成功状态；
- Fidelity 与阈值；
- 是否触发 repair；
- 清理后的 repair diagnostic；
- backend constraints；
- canonical backend IDs；
- LLM 调用序号（1 / 2 / 3）。

---

# Part B：Circuit Trace

这是本次相对原 Task 13A 新增的核心能力。

## 定位

Agent Trace 回答：

> LoomQ 为什么认为这段代码正确？

Circuit Trace 回答：

> 这段量子代码每执行一步，状态到底变成了什么？

面向的是不会量子计算、但理解 debugger 的开发人员。

## 输入

Circuit Trace 只消费**最终已经通过现有 Parser / semantic verification 的 QASM / Circuit**。

不要让 Circuit Trace 自己重新生成或修复 QASM。

## 执行方式

优先复用现有：

- Parser / Circuit IR；
- Braket serializer；
- `LocalSimulator("braket_sv")`；
- Task 12B/12C 已验证的 statevector bit-order 约定。

可以新增例如：

```text
starter_kit/loomq/circuit_trace.py
```

对最终 Circuit 的量子门按顺序构造 prefix circuit，在本地模拟每个关键步骤的 statevector。

不要自己重写一套量子模拟器。

## Circuit Trace 事件

每个 `GateOperation` 至少产生一个事件，例如：

```text
layer: circuit
stage: gate_step
executor: local
```

`data` 至少包含：

```text
operation_index
gate
qubits
parameters
state_before
state_after
probabilities_after
gate_description
```

其中 state 建议用可序列化形式：

```json
[
  {"basis":"00","real":0.70710678,"imag":0.0,"probability":0.5},
  {"basis":"11","real":0.70710678,"imag":0.0,"probability":0.5}
]
```

可以省略绝对值极小的 amplitude，但阈值必须固定且有测试；不要因为 UI 需要随意改数值语义。

bit string 顺序必须与当前 semantic verifier 已验证的约定一致：按 `q[0] ... q[n-1]` 展示，避免 Web 阶段重新踩 bit-order 坑。

## Measurement

`MeasureOperation` 可以产生独立事件，例如：

```text
stage: measurement
```

说明：

- 哪些 qubit 映射到哪些 classical bit；
- 测量前概率分布；
- “实际运行时会从该分布得到经典结果”。

**本任务不要伪造一次随机测量结果，也不要为了教学展示假装发生了真实波函数坍缩。**

## 人话解释

本任务只做**确定性的短 gate description**，不要再调用 LLM。

例如：

```text
H：重新分配这个量子位的振幅，使不同计算基状态可以形成叠加与干涉。
CX：当控制位为 1 时翻转目标位，因此会改变两个量子位之间的关联。
Measure：把量子状态按当前概率分布读成经典 0/1 结果。
```

不要在 13A 里建设完整量子教程，也不要为了 Bell 示例硬编码“这一步一定产生纠缠”。

“这一步为什么是纠缠 / 干涉 / 相位”的新手解释与视觉叙事，留到 Web DevTools 任务结合真实 UI 做。

## 状态规模保护

Circuit Trace 是教学 / debug 能力，不需要对很大的 statevector 强行展开。

设置一个明确的小规模上限（建议 8 qubits，或根据现有实现选择同量级合理值）：

- 小于等于上限：生成完整 Circuit Trace；
- 超过上限：产生一个 `warning` 事件说明 statevector 可视化被跳过；
- 不能因此让 Agent 主任务失败；
- 该限制只属于 debug trace，不影响 L1/L2 正式能力。

---

# CLI：只做 Trace Engine 的薄消费者

新增最小入口，例如：

```text
starter_kit/loomq/debug_cli.py
```

启动：

```bash
cd starter_kit
python -m loomq.debug_cli "生成一个 Bell 态并测量"
```

环境变量继续由 shell 注入，不读取 `.env`，不增加 `python-dotenv`。

## CLI 输出目标

先能看到 Agent Trace：

```text
[1] AGENT · LLM · Intent
    task: generate_qasm

[2] AGENT · LLM · Target
    |00> +0.707107
    |11> +0.707107

[3] AGENT · LOCAL · Semantic Verify
    fidelity: 1.000000
    ✓ passed
```

然后看到 Circuit Trace：

```text
[7] CIRCUIT · Gate 1 · h q[0]
    before: |00> 100%
    after : |00> 50% · |10> 50%
    H changes the amplitudes and creates a superposition.
```

```text
[8] CIRCUIT · Gate 2 · cx q[0], q[1]
    before: |00> 50% · |10> 50%
    after : |00> 50% · |11> 50%
    CX flips the target when the control is 1.
```

CLI 不要求漂亮，不增加颜色库、TUI 框架或设计系统。

## 操作语义

- `Enter` / `n`：到下一个 TraceEvent；
- `c`：后续不暂停，但继续打印；
- `q`：只退出本次 debug session；
- 不要求任意 breakpoint、回退、线程调度或 Python 行级 debugger。

这里的 step 是 **Agent stage / quantum gate 级 step**。

---

# 安全边界

所有 trace 严禁包含：

- API Key；
- Authorization / Bearer Header；
- 完整环境变量；
- `.env.l2.local`；
- HTTP request headers；
- 原始 SDK traceback；
- 本机绝对路径；
- 未清理模型异常；
- 完整 OpenAI-compatible response dump。

复用已有错误清理边界。

---

# L2 客观部分保护

L2 objective 已冻结。本任务是 additive debug / UX 能力。

必须保持：

- Backend 正式路径仍 1 次模型调用；
- QASM 正常正式路径仍 2 次；
- repair 最多 3 次；
- Fidelity 阈值不变；
- pure-state guard 不变；
- backend filtering 不变；
- `submission.yaml` 保持 L2 开启；
- `adapter.agent_chat()` 返回格式不变；
- 正式路径不执行逐 gate Circuit Trace。

---

# 本任务明确不做

不要做：

- Web / React / Next.js；
- SSE / WebSocket；
- 图形化线路编辑器；
- Bloch sphere；
- polished 概率图表；
- 任意 breakpoint 配置；
- trace 历史保存；
- 多会话 / 用户系统；
- 完整新手教程；
- 真机提交交互；
- L3。

这里的“不做 L3”只表示**本 Task 不碰 L3**，不代表后续路线永久放弃；完成核心交互体验后再根据时间重新评估。

---

# 测试

至少覆盖：

## Agent Trace

1. Trace 关闭时 `agent_chat()` 与当前行为一致；
2. Trace 关闭时无 debug stdout/stderr；
3. QASM 正常路径事件顺序稳定；
4. repair 路径包含 repair event，调用仍最多 3 次；
5. Backend 路径包含 constraints / selected，仍恰好 1 次；
6. candidate / target / Fidelity 等数据进入正确事件；
7. Trace 不泄露假 API Key、Bearer、环境变量或绝对路径。

## Circuit Trace

8. Bell circuit 的 H step 状态变化正确；
9. Bell circuit 的 CX step 最终得到 `00/11` 各 0.5；
10. Bell- / 相位相关电路的 complex amplitude 不被只用 probability 替代；
11. bit-order 与现有 semantic verifier 一致；
12. global phase 不导致概率显示异常；
13. measurement event 正确描述 quantum → classical mapping；
14. statevector 超过 debug 上限时 warning + graceful skip，不影响最终 Agent 结果；
15. Circuit Trace 仅 debug 模式运行，普通 `agent_chat` 不增加 prefix simulation。

## CLI / Regression

16. `next` 逐事件推进；
17. `continue` 后不暂停但继续打印；
18. `quit` 仅终止 debug CLI；
19. 原有 L2 专项测试全部通过；
20. 全量测试通过；
21. `python evaluator.py --level l2` 继续 PASS。

---

# 真实 API 冒烟

只做轻量真实 DeepSeek 验证，不重跑 12C 矩阵。

## A. Bell

```text
生成一个 Bell 态并测量
```

确认：

- Agent Trace 正常；
- Circuit Trace 至少看到 H → CX → measurement；
- H 后状态与 CX 后状态符合预期；
- 最终 QASM 正常；
- 模型调用次数未因 debug 增加。

## B. Backend

```text
需要至少 15 比特、零排队的后端
```

确认：

- LLM 提取约束；
- LOCAL 能力表筛选；
- canonical IDs；
- 恰好 1 次模型调用；
- backend task 不生成 Circuit Trace。

---

# 完成标准

Task 13A 完成时：

- 存在统一、结构化、无 UI 绑定的 TraceEvent；
- `layer=agent|circuit` 可以清楚区分两类调试信息；
- Agent Trace 与生产 `agent_chat` 共用同一执行路径；
- Circuit Trace 消费最终已验证 Circuit，不复制 Agent 逻辑；
- Bell 示例可逐 gate 看到真实 statevector / probability 变化；
- CLI 可 `next / continue / quit`，但保持极薄；
- 正式 L2 路径零额外模型调用、零逐 gate 模拟；
- L2 objective / public evaluator 无回归；
- 真实 DeepSeek Bell + Backend 冒烟通过。

---

# 完成后汇报

只汇报：

1. TraceEvent 最终 schema；
2. Agent Trace 与生产路径如何共享；
3. Circuit Trace 如何生成每个 gate 的状态；
4. Bell 示例实际逐步 trace；
5. bit-order 与 complex amplitude 如何保证；
6. debug statevector 上限；
7. CLI `next / continue / quit` 行为；
8. 真实 DeepSeek Bell / backend 冒烟和调用次数；
9. 专项 / 全量 / public evaluator；
10. Web Quantum DevTools 可以直接复用哪些字段、还缺哪些。

本任务结束时不要 commit，不要 push，等待人工复核。
