# Task 13A Fix：CLI 中文可读性 + mid-circuit measurement 安全降级

## 背景

Task 13A 已完成：

- 统一 Agent Trace；
- Circuit Trace；
- 极薄 CLI；
- 正式 `agent_chat()` 不受调试能力影响。

人工试用后发现两个收尾问题：

1. CLI 的 summary / gate description / 操作提示大多是英文。对于中文母语、且没有量子背景的用户，阅读成本明显偏高；
2. 当前 Circuit Trace 对 mid-circuit measurement（测量后还有量子门）会继续沿用测量前 statevector 进行后续 prefix simulation，这会产生教学上错误的状态解释。

本任务只做 13A 收尾，不继续建设 CLI 产品。重点仍然是尽快进入 Web Quantum DevTools。

---

## 目标

完成三件事：

1. CLI 默认使用简洁中文解释；
2. mid-circuit measurement 不再产生错误的后续 statevector trace；
3. 概率展示做一个零依赖、很轻的 ASCII / Unicode 进度条增强；如果实现明显复杂，则保留百分比即可，不要引入 TUI / rich 等依赖。

---

# 1. CLI 默认中文化

## 原则

只改**用户可见文案**，不要改稳定的机器字段。

以下字段继续保持英文机器值：

```text
layer: agent | circuit
executor: llm | local
stage: intent | qasm_candidate | target_spec | ...
status: running | ok | warning | error
```

未来 Web 仍依赖这些稳定字段。

但 CLI 展示应映射为中文，例如：

```text
AGENT       → Agent
CIRCUIT     → 电路
LLM         → 模型
LOCAL       → 本地
intent      → 识别任务
qasm_candidate → 生成候选 QASM
target_spec → 提取目标态
parser_validation → 语法校验
semantic_verification → 语义验证
repair_started → 开始修复
repair_candidate → 修复结果
backend_constraints → 提取后端约束
backend_selected → 本地筛选后端
agent_result → 最终结果
gate_step → 量子门步骤
measurement → 测量
```

不要修改 TraceEvent 中的原始 `stage/executor/layer` 值，只在 `debug_cli.py` 渲染层做映射。

## summary / gate description

当前 Agent Trace summary 和 Circuit gate descriptions 有较多英文。

优先做法：

- 把 `l2_agent.py` / `circuit_trace.py` 中 debug-only summary / description 改成简洁中文；
- 不影响正式 `agent_chat()` 返回文本；
- 不增加任何 LLM 调用；
- 不建设 i18n 框架，本期默认中文即可。

量子术语可以保留必要英文缩写，但第一次出现尽量中文解释：

```text
H 门：把振幅重新分配到多个基态，使量子位进入叠加。
CX 门：当控制位为 1 时翻转目标位，因此会改变两个量子位之间的关联。
RZ 门：改变相对相位，通常不会立刻改变测量概率。
测量：按当前概率分布把量子信息读成经典 0/1；这里不会伪造一次随机结果。
```

不要写成长教程。

## CLI 操作提示

改成类似：

```text
[Enter/n] 下一步 · [c] 连续执行 · [q] 退出
```

错误信息也应给用户一个最小中文提示，例如：

```text
调试失败：RuntimeError
```

仍不要输出 traceback、路径或凭证。

---

# 2. 概率展示轻量优化

当前：

```text
|00> 50.00%
|11> 50.00%
```

允许在 CLI 渲染层增加固定宽度小进度条，例如：

```text
|00>  ██████████░░░░░░░░░░  50.0%
|11>  ██████████░░░░░░░░░░  50.0%
```

要求：

- 纯字符串实现；
- 不增加依赖；
- 固定宽度，例如 20 格左右；
- 概率仍显示数值；
- 0% / 100% / 小概率显示稳定；
- statevector 中 complex amplitude 仍可保留在需要的位置，不能因为做概率条就丢掉相位信息。

如果为适配终端宽度、Unicode 兼容等需要写大量逻辑，则**不要做复杂版本**；保持百分比即可。这里不是本任务重点。

建议 gate step 输出紧凑一些，例如：

```text
[8] 电路 · 本地 · 量子门步骤
    CX q[0], q[1]

    执行前
    |00>  ██████████░░░░░░░░░░  50.0%
    |10>  ██████████░░░░░░░░░░  50.0%

    执行后
    |00>  ██████████░░░░░░░░░░  50.0%
    |11>  ██████████░░░░░░░░░░  50.0%

    CX：当控制位为 1 时翻转目标位，因此改变两个量子位之间的关联。
```

无需颜色库。

---

# 3. mid-circuit measurement 正确性修复

## 当前问题

类似：

```qasm
h q[0];
measure q[0] -> c[0];
x q[0];
```

当前 trace 会：

```text
H 后得到叠加态
→ 记录 measurement
→ 继续把测量前 statevector 当作后续 X 的输入
```

这在教学上是错误的，因为真实测量会引入随机经典结果 / 分支。

## 本任务不要做

不要实现：

- 随机测量采样；
- 多分支 statevector tree；
- classical-condition simulator；
- 真正的 mid-circuit debugger。

这些都超出本任务范围。

## 最小正确处理

当 Circuit Trace 遇到 `MeasureOperation` 时：

- 正常输出该 measurement event；
- 检查其后是否还有 `GateOperation`；
- 如果后面还有量子门，则追加一个稳定 warning event，例如：

```text
layer: circuit
stage: trace_stopped_after_measurement
executor: local
status: warning
```

`data` 至少包含：

```text
measurement_operation_index
remaining_gate_count
reason: mid_circuit_measurement
```

然后停止后续逐 gate statevector trace。

CLI 中文提示例如：

```text
⚠ 检测到中途测量。
测量后的量子状态会按随机结果产生分支；当前调试器暂不模拟这些分支，因此停止后续状态追踪。
QASM 本身仍然有效，Agent 最终结果不受影响。
```

注意：

- final measurement（后面没有 GateOperation）仍按当前逻辑正常结束，不产生 warning；
- 该限制只影响 debug Circuit Trace；
- 不影响 Parser、L1 runner、L2 semantic verifier 和正式 `agent_chat()`。

---

# 不要扩大范围

本任务不要：

- 改 TraceEvent schema，除非 `trace_stopped_after_measurement` 作为新 stage；
- 做实时 streaming；
- 做真正 breakpoint；
- 做 Web UI；
- 做 i18n 系统 / 多语言切换；
- 加 rich / textual / curses / colorama；
- 改 L2 Prompt / pure-state guard / Fidelity / backend；
- 做 L3。

修完立刻进入 Web Quantum DevTools。

---

# 测试

至少覆盖：

1. CLI stage / executor / layer 展示为中文，但底层 TraceEvent 机器字段保持不变；
2. H / CX / RZ / measurement 等主要 gate description 是中文可读文案；
3. CLI 操作提示为中文；
4. 概率条若实现：0%、小概率、50%、100% 格数与数值合理；
5. 概率条不替代 complex amplitude 数据；
6. final measurement 后无 gate：不产生 `trace_stopped_after_measurement`；
7. mid-circuit measurement 后还有 gate：输出 measurement + warning，并停止后续 gate trace；
8. warning data 中包含 measurement index / remaining gate count / 固定 reason；
9. mid-circuit graceful stop 不影响最终 Agent reply；
10. 正式 `agent_chat()` 不运行 Circuit Trace；
11. 原 Task 13A 测试全部通过；
12. 全量测试通过；
13. `python evaluator.py --level l2` 继续 PASS。

---

# 人工冒烟

只需要本地真实 DeepSeek 做一个中文 CLI 冒烟：

```bash
python -m loomq.debug_cli "生成一个 Bell 态并测量"
```

人工确认：

- 不需要读英文长句也能理解主流程；
- 能看懂“模型 / 本地”的区别；
- H / CX 的前后概率变化直观；
- `next / continue / quit` 中文提示正常；
- 最终仍能看到正确 QASM。

mid-circuit measurement 用本地固定 QASM 单测即可，不需要额外消耗真实模型调用。

---

# 完成后汇报

只汇报：

1. CLI 哪些文案改成中文；
2. 概率条是否实现，实际效果示例；
3. mid-circuit measurement 的停止规则；
4. 一个 Bell CLI 的实际中文输出片段；
5. 专项 / 全量 / public evaluator 结果；
6. 是否还有会阻塞进入 Web DevTools 的问题。

完成后不要 commit、不要 push，等待人工复核。
