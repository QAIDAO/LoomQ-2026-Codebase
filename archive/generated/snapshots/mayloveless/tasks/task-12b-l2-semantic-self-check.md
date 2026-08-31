# Task 12B：L2 独立语义裁判与本地模拟自验

## 背景

Task 12A 已完成真实 DeepSeek / OpenAI-compatible 调用冒烟。

当前 QASM 路径主要依赖：

```text
模型生成 / 修复
→ Parser 校验
→ 必要时再修一次
```

Parser 只能发现语法、结构和部分 L2 契约问题，无法发现“QASM 完全合法，但量子语义错误”。例如用户要求 Bell 态，模型却生成四态均匀叠加，Parser 仍会通过。

官方 L2 文档推荐的工程闭环本身就是：

```text
生成 QASM
→ 用自己的 L1 跑一遍自验
→ 不对就重试
```

本任务增加独立语义自验，不把“候选电路自己声明的目标”当作裁判依据。

---

## 目标

对 `generate_qasm` / `repair_qasm` 建立：

```text
原始用户 prompt
├─ 模型调用 A：生成候选 QASM
└─ 模型调用 B：独立提取目标态验证规格（不能看到候选 QASM）

候选 QASM
→ 现有 Parser / L2 结构校验
→ 去除测量，取得测量前量子态
→ 本地无噪声模拟
→ 与独立目标规格计算 Fidelity

通过 → 返回
失败 → 最多再调用模型一次修复 → 再验证 → 返回 / 失败
```

后端选择 `select_backend` 不进入量子语义模拟，保持 Task 11C 的确定性能力表筛选。

---

## 核心原则

### 1. 生成器不能给自己当裁判

独立目标判定调用只接收：

```text
原始用户 prompt
```

不得接收：

- 候选 QASM；
- 候选 explanation；
- 候选模型声明的 expected state / expected distribution；
- 本地模拟结果。

因此即使候选模型同时“电路写错 + 自己声称错误目标是正确的”，也不能让语义自验自动通过。

模型仍可使用同一个 `LOOMQ_LLM_*` 服务，但目标判定必须是独立调用、独立 system prompt、独立结构化响应。

### 2. 本地裁判必须是确定性的

模型只负责把原始自然语言转成目标态规格；最终是否通过由本地模拟结果和确定性 Fidelity 计算决定。

不要再让 LLM 阅读模拟结果后自行说“通过 / 不通过”。

### 3. 不修改 L1 Parser

继续复用现有：

- `parse_qasm()`；
- IR；
- Braket serializer / LocalSimulator 能力。

语义验证属于 L2 层，不把目标态逻辑塞进 L1 Parser。

---

## 目标态结构化协议

新增独立 target-judge Prompt，建议返回类似：

```json
{
  "verification_mode": "statevector",
  "qubit_count": 3,
  "amplitudes": [
    {"basis": "000", "real": 0.7071067811865476, "imag": 0.0},
    {"basis": "111", "real": 0.7071067811865476, "imag": 0.0}
  ],
  "explanation": "3-qubit GHZ+ target"
}
```

要求：

- 目标来自原始用户意图；
- 未列出的 basis amplitude 视为 0；
- basis 长度必须等于 `qubit_count`；
- amplitude 必须是有限数值；
- 本地检查归一化；
- 不允许 target-judge 输出或修改候选 QASM；
- 不接受候选生成器返回的 target 字段作为裁判依据。

如当前官方客观 QASM 任务可以明确表示为 pure state，优先使用 statevector 模式。

对于无法可靠转换为 pure-state 目标的非评分型自由请求，可明确返回不支持的验证模式并降级为现有 Parser 校验，不要伪造目标态。

---

## 本地状态模拟

新增轻量模块，例如：

```text
starter_kit/loomq/semantic_verifier.py
```

职责：

1. 接收 Parser 已得到的 `Circuit`；
2. 复制一份仅用于验证的电路，移除 `MeasureOperation`，比较测量前状态；
3. 复用现有 Braket OpenQASM 3 serializer / `LocalSimulator("braket_sv")`；
4. 使用 simulator state-vector result，`shots=0`；
5. 得到候选 statevector；
6. 与 target-judge 给出的期望 statevector 计算 pure-state fidelity：

```text
F = |<target | actual>|^2
```

7. Fidelity 阈值默认按正式评分目标采用 `>= 0.97`；
8. 比较必须天然忽略 global phase，但能发现相对相位错误；
9. 不依赖公网、不调用真机。

当前 `requirements.txt` 已固定 `amazon-braket-sdk`，不要再增加第二套量子 SDK，也不要重新实现完整量子模拟器。

如 Braket pinned version 的 statevector API 与上述接口有细节差异，先用最小实验确认实际 API，再实现；不要猜字段。

---

## 调用次数策略

本任务允许调整此前 QASM 路径“最多 2 次”的内部策略。

### QASM 任务

正常成功：

```text
1. 候选生成 / 修复
2. 独立 target judge
```

共 2 次模型调用。

候选语法或语义失败：

```text
1. 候选生成 / 修复
2. 独立 target judge
3. 修复一次
```

最多 3 次模型调用。

第三次修复后必须再次走 Parser + 本地语义验证；仍失败则停止，不继续第四次。

### 后端选择

继续保持：

```text
1 次模型调用提取约束
→ 本地 backend_capabilities.json 确定性筛选
```

不要为了统一流程给 backend 任务增加 target-judge 调用。

---

## 修复 Prompt

第三次模型调用触发条件包括：

- Parser / L2 QASM 校验失败；
- qubit count 与目标不一致；
- 本地模拟失败；
- Fidelity < 0.97。

修复 Prompt 可包含：

- 原始用户请求；
- 候选 QASM；
- 独立 target spec；
- 清理后的失败原因；
- 若是语义失败，可包含 Fidelity 数值。

不要包含：

- API Key；
- traceback；
- 本机绝对路径；
- 大段 SDK 内部异常。

修复模型不得修改 target spec；target spec 仍以独立 judge 的第一次结果为准。

---

## 必须覆盖的测试

### 单元测试（mock 模型，允许真实本地模拟器或稳定的 verifier fixture）

至少覆盖：

1. 正确 Bell state：Parser + semantic verifier 均通过；
2. **语法合法但错误的 Bell**：例如每个 qubit 都做 H，Parser 通过但 Fidelity 明显失败；
3. 正确 3-qubit GHZ：通过；
4. 语法合法但错误 GHZ：被语义层拒绝；
5. 相对相位错误：statevector fidelity 能发现，而不是只比较 Z-basis probability；
6. global phase：不应错误判失败；
7. target judge 只收到原始 prompt，断言其消息中没有候选 QASM；
8. 候选 response 即使带伪造 target / expected distribution，也不能影响 verifier；
9. 一次正确 QASM 总模型调用为 2；
10. 一次语义失败后修复成功总模型调用为 3；
11. 修复后仍语义错误：停在 3 次，不进行第 4 次；
12. backend selection 仍只调用模型 1 次；
13. 用户要求测量 / 不要求测量的 Task 11B 行为不回归；
14. L1 全量测试无新增失败。

### 真实 DeepSeek 回归

使用本地 `.env.l2.local` 注入的真实配置，至少跑：

- 3 种 GHZ/Bell 自然语言改写；
- 2 个语法合法但目标态错误的修复请求；
- 1 个相位相关错误；
- 2 个后端选择组合约束。

只记录：

- 输入类别；
- 是否一次通过 / 是否触发修复；
- Fidelity；
- 模型调用次数；
- 最终是否通过。

不要记录 API Key、Authorization Header 或完整敏感响应。

---

## 实现边界

允许修改 / 新增：

- `starter_kit/loomq/l2_agent.py`
- `starter_kit/loomq/semantic_verifier.py`
- 必要的轻量 L2 helper
- L2 专项测试

必要时允许对现有 Braket serializer 的**调用方式**做适配，但不要修改 L1 对外行为。

不要：

- 修改 L1 Parser 语义；
- 引入第二套量子 SDK；
- 自己写一整套新量子模拟器；
- 修改 `backend_capabilities.json`；
- 开启 `submission.yaml` 的 L2 开关；
- 做 UI / CLI；
- 开始 L3；
- commit 或 push。

---

## 验收标准

- QASM Parser 合法但语义错误时能够被本地自验发现；
- 目标规格与候选生成逻辑解耦，候选无法定义自己的正确答案；
- 使用本地无噪声 statevector 验证，而非只比较测量字符串或让 LLM 自评；
- pure-state Fidelity 正确处理 global phase；
- QASM 正常路径 2 次模型调用，失败修复路径最多 3 次；
- backend selection 保持 1 次模型调用；
- 修复后仍失败则稳定停止；
- 真实 DeepSeek 回归证明该闭环实际工作；
- 全量测试通过；
- `submission.yaml` 仍保持 L2 关闭。

---

## 完成后汇报

只汇报：

1. target judge 的结构化协议；
2. 为什么它与候选生成器独立；
3. 本地 statevector 获取方式；
4. Fidelity 实现与阈值；
5. 一次通过 / 修复时的模型调用次数；
6. 至少一个“Parser 通过但 semantic verifier 拒绝”的测试案例；
7. 真实 DeepSeek 回归结果；
8. 全量测试结果；
9. 进入下一 Task 前仍存在的风险。
