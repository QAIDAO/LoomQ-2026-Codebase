# Task 12C Fix：Pure-state 降级防护

## 背景

Task 12C 已完成真实 DeepSeek hidden-like 回归、statevector 语义验证、Docker 与 public evaluator，并已开启 L2。

当前剩余一个明确漏洞：`pure_state_requested` 完全由 target judge 自报。

若原始用户明确要求 Bell / GHZ / 其他纯态制备，但 target judge 错误返回：

```json
{
  "verification_mode": "unsupported",
  "pure_state_requested": false
}
```

本地会接受该结果，并降级为 Parser-only，从而绕过 statevector semantic verification。

本任务只修复这一条降级路径，并补充最小 Prompt 防御与回归测试；不要扩大 L2 功能范围。

---

## 目标

建立三层防护：

```text
原始用户 Prompt
→ 本地确定性判断：是否必须做 statevector 验证
→ target judge 提取目标规格
→ 本地禁止关键 pure-state 请求降级 unsupported
→ statevector + Fidelity 最终裁决
```

Prompt 负责“尽量让模型做对”，本地规则负责“关键请求不能绕过验证”。

---

## 1. 本地 deterministic guard

新增一个轻量函数，例如：

```python
requires_statevector_verification(prompt: str) -> bool
```

它只判断“原始请求是否明确要求一个可唯一验证的纯态目标”，不生成目标振幅，不生成 QASM。

至少保守识别：

- Bell / EPR / GHZ 等明确命名的纯态；
- 明确 ket 表达，例如 `|00>`、`(|00>+|11>)/sqrt(2)`；
- 明确 basis amplitude / 振幅 / relative phase / 相对相位；
- 明确 `pure state` / `纯态` / `state preparation` / `制备某个量子态` 等纯态制备描述。

注意：

- 这是“是否必须验证”的 guard，不是目标解析器；
- 不要在这里硬编码 Bell/GHZ 的目标振幅或 QASM；
- 规则应保守，宁可只拦明确 pure-state 请求，不要把普通算法/实验设计都误判为 pure-state。

---

## 2. 禁止关键请求降级

在 target judge 结果解析后、semantic verifier 运行前加入本地约束：

```text
if requires_statevector_verification(original_prompt):
    verification_mode == unsupported
    → 直接拒绝
```

此时不信任 target judge 自报的 `pure_state_requested=false`。

`pure_state_requested` 可以继续保留作为协议诊断字段，但不得作为是否允许 `unsupported` 降级的唯一授权来源。

不增加额外模型调用。

---

## 3. Target judge Prompt hardening

在 `TARGET_JUDGE_SYSTEM_PROMPT` 中收紧 `unsupported` 的语义。

明确要求：

- Bell / EPR / GHZ 等明确命名纯态必须返回 `statevector`；
- 明确 ket / amplitude / relative phase 的目标必须返回 `statevector`；
- 明确 pure-state / state-preparation 请求必须返回 `statevector`；
- 不得因为目标复杂、包含相位、自己不确定如何构造电路而返回 `unsupported`。

`unsupported` 只允许用于确实无法唯一表示为纯态目标的情况，例如：

- 用户只要求“设计一个量子实验/算法”，没有唯一目标态；
- 目标本质是 mixed state；
- 只给测量统计目标，无法唯一确定纯态；
- 原始信息不足以确定唯一纯态。

不要把 Prompt 扩成很长的量子知识库，只做这部分边界约束。

---

## 4. unsupported_reason（轻量诊断字段）

建议给 `unsupported` 增加枚举型原因：

```json
{
  "verification_mode": "unsupported",
  "pure_state_requested": false,
  "unsupported_reason": "no_unique_target | mixed_state | distribution_only | insufficient_spec",
  "explanation": "..."
}
```

要求：

- `statevector` 模式不需要 `unsupported_reason`；
- `unsupported` 必须提供合法枚举值；
- 非法/缺失原因视为 target judge 协议错误；
- 该字段只是诊断与收敛 Prompt 的辅助，不替代本地 deterministic guard。

如果当前实现为了最小改动不适合加入该字段，可说明原因并保留现有协议；但本地 guard 必须实现。

---

## 5. 必须新增的测试

至少覆盖：

1. Bell Prompt + judge 返回 `unsupported,false` → 必须失败，不能 Parser-only；
2. GHZ Prompt + `unsupported,false` → 必须失败；
3. 明确 ket / amplitude pure-state Prompt + `unsupported,false` → 必须失败；
4. Bell/GHZ 正常 `statevector` → 不回归；
5. 非纯态自由电路请求 + `unsupported,false` → 仍允许 Parser-only；
6. 如果实现 `unsupported_reason`：
   - 合法枚举可接受；
   - 缺失/非法枚举拒绝；
7. backend selection 行为不变，仍 1 次模型调用；
8. QASM 正常路径 2 次、修复路径最多 3 次，不增加第 4 次；
9. 全量 L1/L2 单测无回归。

---

## 6. 真实 DeepSeek 最小回归

不需要重新跑完整 48 次矩阵。

只跑关键样本：

- Bell+；
- Bell−；
- GHZ3；
- 一个明确 ket / amplitude 请求；
- 一个真正应允许 `unsupported` 的自由电路请求；
- 一个 backend selection。

记录：

- target judge mode；
- 本地 `requires_statevector_verification` 判定；
- Fidelity（如适用）；
- 模型调用次数；
- wall-clock；
- 最终是否通过。

目标：确认 Prompt hardening 没有把正常 pure-state 请求推向 `unsupported`，同时自由请求仍可安全降级。

---

## 7. 范围约束

允许修改：

- `starter_kit/loomq/l2_agent.py`
- `starter_kit/loomq/semantic_verifier.py`
- 必要的轻量 L2 helper
- L2 测试

不要：

- 修改 L1 Parser / serializer 对外行为；
- 引入新模型调用；
- 引入新量子 SDK；
- 修改 backend capabilities；
- 做 UI / CLI；
- 开始 L3；
- 回退已经通过的 statevector/Fidelity 方案；
- 关闭已经满足门槛的 L2，除非修复后关键回归失败；
- commit 或 push。

---

## 验收标准

- 明确 pure-state 请求不能再通过 `unsupported,false` 绕过 semantic verification；
- 本地 guard 独立于 target judge 自报字段；
- target judge Prompt 对 `unsupported` 边界更明确；
- 正常 Bell/GHZ/相位请求仍走 statevector；
- 真正非唯一纯态请求仍可 Parser-only 降级；
- 不增加模型调用次数；
- 关键真实 DeepSeek 回归通过；
- public L2 evaluator 仍 PASS；
- 全量测试通过；
- API Key / `.env` / Authorization 不进入 git。

---

## 完成后汇报

只汇报：

1. 本地 `requires_statevector_verification` 的判断边界；
2. 如何阻断 `Bell/GHZ + unsupported,false`；
3. Prompt hardening 做了什么；
4. 是否增加 `unsupported_reason`，以及原因；
5. 新增的漏洞回归测试结果；
6. 真实 DeepSeek 最小回归结果；
7. public evaluator / 全量测试结果；
8. 是否还存在需要在进入交互体验前处理的 L2 客观风险。
