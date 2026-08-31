# Task 15B — L2 客观 20 分：黑盒 Agent 稳定性 + 120 秒总预算审计

## 背景

L1 15A 已进入 Docker / clean SDK 验证阶段。接下来优先保护 L2 客观 20 分。

当前 production L2 已经具备：

- `adapter.agent_chat(prompt: str) -> str` 真实模型调用；
- generate / repair / backend 三类任务；
- QASM Parser 校验；
- 独立 target judge；
- statevector Fidelity 语义校验；
- 候选失败后最多一次 bounded repair；
- pure-state downgrade guard；
- backend 只由 LLM 提取约束，本地 capability table 确定性筛选。

当前主要风险不在“缺功能”，而在正式黑盒评分形态：

1. 12 个私有 prompt 会做同义改写，不应依赖固定措辞；
2. 当前 transport timeout 是“单次调用 timeout”，而 QASM 路径可能有 2～3 次模型调用，不能保证整个 case 在 120 秒内结束；
3. DeepSeek/OpenAI-compatible 返回有时会出现 JSON fence / 前后少量包装文本，需要有限且无歧义的表示层容错；
4. backend 的否定表达、no-match 和约束组合容易被模型误提取；
5. 不应为了理论鲁棒性增加第 4 次模型调用、放宽 schema、重写已稳定的 verifier。

本 Task 目标是：

> 先建立 scoring-like 黑盒审计，再只针对真实失败做最小修复。

---

# A. 建立 12-case hidden-like 黑盒集

新增一个稳定、可版本化的本地 case set，例如：

```text
starter_kit/scripts/audit_l2_objective.py
```

或等价结构。

建议 case-set version：

```text
l2-hidden-like-2026-08-20-v1
```

总数固定 12 个，覆盖三类任务，但不要声称这些就是官方私有题。

## A1. Generate × 4

至少覆盖：

1. Bell / EPR 同义改写 + 明确测量；
2. 带负相对相位的 Bell- / relative phase，明确“不要求测量”；
3. 3-qubit GHZ + 全测量的自然语言改写；
4. 一个明确 ket / pure-state preparation，用非 Bell/GHZ 表述，防止 named-state 特判。

要求：

- prompt 使用不同于现有 stable prompt 的同义改写；
- expected 不使用模型自己输出；
- QASM 必须 Parser 通过；
- 明确纯态目标必须做独立 statevector 语义验证；
- 明确要求测量的 case 必须保留 measurement；
- 明确不要求测量的 case 不应被错误强制加测量作为“修复条件”。

## A2. Repair × 4

构造真实坏 QASM，并在 prompt 中同时提供“原本应该实现什么”。至少攻击：

1. 语法错误但目标明确；
2. 语法合法、语义错误（例如 CX 方向 / 缺关键门）；
3. relative phase 符号错误；
4. 测量语义错误：原需求要求测量但输入缺失，或原需求明确不要测量。

要求：

- 最终结果必须保持用户声明目标；
- 不能只验证“QASM 能 parse”；
- 有唯一纯态目标时，最终 statevector fidelity 必须达标；
- 最多允许 production 现有的一次 bounded repair；
- 不增加新的 retry loop。

## A3. Backend × 4

只测试官方现有 `BackendConstraints` 能表达的字段，不擅自新增 schema。

至少覆盖：

1. “不用真机 / 免费 / 不要账号 / 不排队”等否定式自然语言，验证不会误提取成 `require_qpu=true`；
2. “必须真机 + 免费或免费额度”组合；
3. 较高 qubit 数 + 不要账号 + 零排队，得到确定性窄匹配；
4. `require_qpu=true + require_no_queue=true` 的 no-match 组合。

注意：

- `require_qpu=false` 在当前 selector 中并不表示“必须模拟器”，不要把“无需真机”错误扩展成当前 schema 不支持的排除规则；
- 不测试“排除某个平台”等官方 schema 没有的能力；
- expected backend IDs 必须由测试侧直接基于官方 `backend_capabilities.json` / 明确约束计算，不让 LLM 决定正确答案；
- no-match 必须是合法结果，不能为了有推荐而擅自放宽约束。

---

# B. 120 秒必须成为整个 case 的硬预算

这是本 Task 的 P0。

当前 `LOOMQ_LLM_TIMEOUT_SECONDS` 是单次 transport timeout，不能等同于正式 per-case 120 秒。

实现总 deadline，要求：

```text
agent_chat() 整体 wall-clock < 120s
```

建议 production 内部保留安全余量：

```text
CASE_DEADLINE_SECONDS = 115
```

不要新增用户必须配置的新环境变量。

## B1. deadline 位置

在 `_run_agent()` 开始时记录：

```text
started = monotonic()
deadline = started + CASE_DEADLINE_SECONDS
```

每次模型调用前计算 remaining，并把本次 HTTP timeout 限制为：

```text
min(LOOMQ_LLM_TIMEOUT_SECONDS, remaining)
```

如果 remaining 已不足以安全发起下一次调用，立即安全失败，不再请求模型。

## B2. transport 修改

允许给 `llm_client.chat_completion()` 增加**内部 kw-only timeout override**，例如：

```python
chat_completion(messages, *, request_timeout_seconds=None, **extra)
```

但：

- 不改 `adapter.agent_chat(prompt: str) -> str` 官方签名；
- timeout override 只影响 `urlopen(..., timeout=...)`；
- 绝对不能把 timeout override 塞进 OpenAI API JSON payload；
- 最终 effective timeout 取配置 timeout 与 remaining 的较小值；
- 不增加网络调用次数。

## B3. 三条调用路径都测

用 deterministic fake transport / patched clock 做单测：

```text
backend: 1 call
generate/repair candidate success: 2 calls
candidate failure + bounded repair: 3 calls
```

断言：

- 永远不会出现第 4 次调用；
- 后续调用拿到的 timeout 会随剩余预算下降；
- 总预算耗尽时在下一次请求前停止；
- timeout / transport 失败不会把 API key、Authorization header、原始 response body 写进错误。

本 Task 不做完整“安全失败分类”，只保持当前不泄漏原则。

---

# C. 结构化输出只做有限、无歧义容错

当前严格 JSON 校验保留。

允许的表示层兼容：

1. 纯 JSON object；
2. 一个完整的 Markdown JSON fence；
3. 若真实 benchmark 暴露需要，可接受“整个响应中恰好存在一个完整顶层 JSON object”，但必须：
   - string-aware / brace-aware；
   - 只提取一个；
   - 出现两个候选对象时拒绝；
   - 提取后继续走现有严格字段校验。

禁止：

- 字段名模糊匹配；
- `min_qubits: "20"` 自动转数字；
- `yes/no` 自动转 bool；
- task_type 猜测；
- 从散文中猜 QASM / backend constraint；
- JSON 修复模型调用；
- 任何第 4 次 LLM call。

如果现有 benchmark 没有暴露 fence / wrapper 失败，只需补安全测试，不必继续放宽 parser。

---

# D. Pure-state / unsupported 边界回归

必须保留现有 guard：

以下明确 pure-state 请求不得被 target judge 降级为 unsupported：

```text
Bell / EPR / GHZ
明确 ket
明确 amplitudes
relative phase
pure-state
state-preparation
```

至少新增同义改写测试，确认中文 / 英文表达不会轻易漏掉。

另一方面，以下没有唯一纯态目标的请求可以保持 unsupported / Parser-only：

```text
仅要求一个测量分布但无唯一态
信息不足
非唯一目标
```

不得为了“全都语义验证”伪造 target state。

---

# E. Scoring-like benchmark 报告

新增可重复执行的 benchmark 入口。

建议：

```bash
cd starter_kit
python scripts/audit_l2_objective.py --json-out /tmp/l2-audit.json
```

如果真实 LLM 环境变量缺失：

- case-set / evaluator / unit tests 仍应可运行；
- real-model benchmark 明确报告 `SKIP / unavailable`；
- 不伪造 PASS。

如果真实 LLM 可用：

每个 case 记录：

```text
case_set_version
case_id
task_type
source_commit / dirty
model
status
llm_calls
elapsed_seconds
parser_valid
semantic_mode / fidelity（适用时）
backend_ids / no_match（backend 时）
repair_triggered（适用时）
error_category（仅安全、高层类别；不要原始 secret-bearing exception）
```

报告中禁止记录：

```text
LOOMQ_LLM_API_KEY
Authorization header
完整 base URL（如无必要）
原始 HTTP response body
```

如果 model 不是正式 `deepseek-v4-flash`，报告必须明确：

> local compatibility benchmark only; not final formal-model evidence

最终 evidence 要等 executable code freeze 后重新生成。

---

# F. “先测再修”规则

先新增 / 跑：

```text
local adversarial tests
deadline tests
现有 L2 tests
```

再决定是否改 `SYSTEM_PROMPT` / parser tolerance。

只有真实 failing case 才允许调整 production prompt。

如果需要改 prompt：

- 只补普适规则；
- 不写 12-case 关键词答案；
- 不硬编码 Bell/GHZ/Backend case；
- 不增加调用次数；
- backend 仍只让 LLM 提取约束；
- target judge 仍不能看 candidate QASM。

---

# G. 建议验证命令

至少执行：

```bash
cd starter_kit
python -m unittest tests.test_l2_agent -v
python -m unittest tests.test_l2_semantic_agent -v
python -m unittest tests.test_backend_selector -v
python -m unittest discover -s tests -v
```

新增的 deadline / adversarial test 单独运行。

若当前环境有真实模型配置，再运行 scoring-like benchmark；没有则明确 pending。

不要因为 L2 audit 等待 L1 Docker。

---

# H. Scope Freeze

本 Task 不做：

- L1 / L3 修改；
- Web / Explorer / Repair / Backend UI 修改；
- 第 4 次模型调用；
- RAG / Agent framework；
- 新 backend 字段；
- 多轮 chat session；
- 正式 submission evidence；
- 大规模 prompt 重构；
- 没有失败证据的宽松 normalize。

如果 audit 发现 production bug，只修最小正确层。

---

# 完成汇报

完成后只汇报：

1. 新增的 12-case hidden-like 分布与 case-set version；
2. deadline 如何保证 1/2/3-call 路径整体不越过 120 秒；
3. JSON 表示层是否发现真实兼容问题、做了什么有限修复；
4. backend 否定/no-match case 是否暴露约束提取问题；
5. pure-state downgrade guard 是否有新盲区；
6. real-model benchmark 是否实际运行，模型名、source SHA、pass/fail、总耗时；
7. 哪些项目因缺少真实模型环境 pending；
8. 是否修改 production prompt / code，以及修改依据。

完成后停止，让我 review；不要继续做 L3 或 submission。