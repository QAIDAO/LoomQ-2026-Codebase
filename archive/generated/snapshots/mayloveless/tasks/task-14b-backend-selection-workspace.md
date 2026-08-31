# Task 14B — Backend：真实的约束提取与本地后端推荐工作区

## 背景

`04 Repair · 进阶` 已接入真实 production L2 路径。下一步实现 `05 Backend · 进阶`。

底层现有能力已经完整：

- LLM 只负责把自然语言提取成标准约束：`BackendConstraints`
- LLM **不能输出 / 推荐 backend ID**
- `select_backends()` 基于 `starter_kit/backend_capabilities.json` 做确定性筛选
- Trace 已有：`intent` → `backend_constraints` → `backend_selected` → `agent_result`

本 Task 不修改选择语义，只把这条真实能力接到 Web，并让用户看懂“为什么匹配 / 为什么被排除”。

---

## 产品定位

Backend 页面回答：

> **“我不知道该用哪一个量子后端。告诉 LoomQ 我的程序和使用限制，它帮我把要求翻译成约束，再从官方能力表里筛出真正满足条件的候选。”**

核心流程：

```text
自然语言要求
→ AI 提取约束
→ 本地能力表筛选
→ 符合条件的后端
→ 为什么匹配 / 为什么其他后端被排除
```

注意：

- 这里是“选择 / 推荐运行平台”，**不是实际提交量子任务**；
- 不增加“运行”按钮；
- 不展示实时队列、实时价格或实时可用性；
- `backend_capabilities.json` 是当前唯一事实来源。

---

## 1. 页面从占位变成真实工作区

`05 Backend · 进阶` 不再显示“即将接入 Web”。

建议结构：

```text
05 Backend · 进阶
选择合适的运行平台

┌──────────────────────┬──────────────────────────────┐
│ REQUIREMENTS         │ RECOMMENDATION               │
│                      │                              │
│ 描述你的运行要求      │ LoomQ 理解到的约束           │
│ [textarea]           │ [约束 chips / rows]          │
│                      │                              │
│ [分析并推荐]          │ 满足条件的后端               │
│                      │ [backend cards]              │
│ 示例要求              │                              │
│ ...                  │ 其他后端为什么没选            │
│                      │ [excluded rows]              │
└──────────────────────┴──────────────────────────────┘
```

窄屏纵向堆叠。

视觉继续沿用 Repair / Explorer 当前语言，不重新设计主题。

---

## 2. 输入

字段：

> **描述你的运行要求**

placeholder 示例：

> 例如：至少 20 个 qubit，不想排队，也不想注册账号。

允许提供 2–3 个轻量示例按钮，只负责填充 textarea，不自动请求。例如：

1. `至少 20 个 qubit，不想排队，也不想注册账号。`
2. `我想用真实量子硬件，8 个 qubit 就够，可以排队，也可以使用免费额度并注册账号。`
3. `只想本地免费运行，不需要真实量子硬件。`

不要使用现有约束模型无法表达的条件作为示例（例如指定拓扑、地区、特定厂商、精确价格）。

按钮：

> **分析并推荐**

请求中显示普通 loading，不伪装流式 agent 过程。

---

## 3. Web API

建议增加专用：

```text
POST /api/backend
{
  "prompt": "..."
}
```

返回结构化 payload，至少包含：

```json
{
  "constraints": { ... },
  "matches": [ ... ],
  "excluded": [ ... ],
  "capability_version": "2026-07",
  "events": [ ... ]
}
```

具体字段可根据现有类型调整，但必须满足下述事实约束。

### 关键实现原则

复用 production 路径：

```text
build_debug_trace(prompt)
→ _run_agent()
→ backend_constraints trace
→ backend_selected trace
```

不要直接在 Web 重新调用 LLM。

**本 Task 不允许新增额外 LLM call。**

Backend detail / exclusion reason 必须来自本地 `backend_capabilities.json` + 已提取的 `BackendConstraints`，不能让模型生成平台事实。

可以在 Web payload 层增加纯本地 helper 来解释筛选结果；不要改变 `select_backends()` 的筛选语义。

---

## 4. 约束展示

把真实 `backend_constraints` trace 翻译成人能读懂的内容。

至少展示：

- 最少 qubits
- 是否必须真机 QPU
- 是否要求零排队
- 成本策略
- 是否允许需要账号的后端

注意 `null / false / unspecified` 的语义：

- `min_qubits: null` → `未指定`
- `require_qpu: null` → `未限制设备类型`
- `require_no_queue: false` → `未要求零排队`
- `cost_policy: unspecified` → `未限制成本策略`
- `allow_account_required: null` → `未限制账号要求`

**不能把“未限制”展示成用户明确接受 / 拒绝了某条件。**

在约束区域写一句：

> AI 只负责理解你的要求；具体后端由本地能力表确定。

---

## 5. 匹配后端

`matches` 必须严格等于 production `backend_selected.data.backend_ids` 对应的本地能力表条目。

每个候选后端显示：

- `name`
- 类型：simulator / qpu / cloud
- `max_qubits`
- queue 分类
- cost 分类
- 是否需要账号

可以显示 backend ID，但退到次要技术信息。

### 不要伪造“最佳后端”

当前 `select_backends()` 返回的是：

> **所有满足条件的后端，按官方能力表顺序**

它没有 ranking / score。

因此 UI 使用：

> `找到 N 个满足全部条件的后端`

不要把第一个写成：

- 最佳选择
- Top 1
- 最推荐
- 最快
- 最便宜

除非未来真的增加确定性 ranking，本 Task 不做。

---

## 6. 为什么匹配

对每个 matched backend，用**确定性条件对照**生成简短理由，例如：

```text
✓ 30 qubits ≥ 需要的 20
✓ 无排队
✓ 免费
✓ 无需账号
```

只展示用户实际提出 / 模型实际提取到的约束。

如果某字段是“未限制”，不需要用它作为匹配理由。

这些理由必须由本地代码根据 `BackendConstraints + Backend` 计算，不调用 LLM。

---

## 7. 其他后端为什么没有入选

这是本页面的重要价值。

对不在 `matches` 中的本地后端，计算真实 exclusion reasons，例如：

```text
本源悟空
× 需要账号
× 当前能力表队列分类为 hours
```

或：

```text
SpinQ Taurus
× 只有 24 qubits，不满足至少 30 qubits
```

同一后端可以有多个排除原因。

仅依据当前 selector 已支持的约束计算：

- max_qubits
- kind / require_qpu
- queue / require_no_queue
- cost_policy
- requires_account / allow_account_required

不要自行增加 selector 不支持的判断。

如果后端只是因为没有额外限制而“也可以”，它就应该在 matches，而不是被 UI 自行排除。

---

## 8. No match 状态

如果 `backend_selected.data.no_match === true`：

明确显示：

> **当前能力表中没有同时满足全部条件的后端。**

随后展示：

- 已提取的约束
- 每个后端的真实排除原因
- 可以考虑放宽的约束类别

“可以考虑放宽”可以沿用 production `_format_backend_reply()` 的类别逻辑，但不要自动修改用户要求，也不要自动重新请求。

提供：

> **修改要求后重新分析**

即可。

---

## 9. 能力表快照说明

结果区需要一个清楚但不抢眼的说明：

> 能力数据来自 LoomQ 官方后端能力表快照（version: 2026-07）。队列、成本等为评测基准分类，不代表平台实时状态。

版本号必须读取 JSON，不要把 `2026-07` 只硬编码在 UI。

不要展示：

- “当前排队 12 分钟”
- “当前价格 ¥x”
- “现在可用”

除非数据源未来真的提供实时数据。

---

## 10. 事实来源与 schema

当前能力表条目包含比 `Backend` dataclass 更多字段（如 platform / notes）。

本 Task 主展示只依赖 production selector 已验证的字段即可：

- id
- name
- kind
- max_qubits
- queue
- cost
- requires_account

如要展示 `notes`，必须从原始 JSON 真实读取，不能自行补文案；不是必需项。

不要为了 UI 修改 production capability snapshot 内容。

---

## 11. 错误与安全

请求失败：

> 这次推荐没有完成，请检查模型配置后重试。

不要输出：

- traceback
- API key
- 原始 model response
- 本地文件绝对路径

如果 trace 缺失 `backend_constraints` 或 `backend_selected`，不要猜测结果；返回安全失败 / incomplete 状态。

---

## 12. 测试要求

至少覆盖：

1. `/api/backend` 缺 prompt → 400；
2. endpoint 复用 production trace builder，不额外调用模型；
3. constraints 来自真实 `backend_constraints` event；
4. matches 与 `backend_selected.backend_ids` 一致；
5. matched reason 只基于真实已提取约束；
6. excluded reasons 与 `select_backends()` 条件一致；
7. no-match 不伪造候选；
8. capability version 从 JSON 读取；
9. 页面不出现实时队列 / 实时价格暗示；
10. Backend 页面不提供“实际运行量子任务”按钮；
11. Repair、Explorer 不回归。

如果仓库没有 CI，不要声称 CI passed。

---

## 13. 不做

本 Task 不做：

- 实际提交到 SpinQ / OriginQ / Braket
- 实时查询平台状态
- 新的后端 ranking 算法
- 拓扑 / fidelity / shots / error rate 选择
- 修改 SYSTEM_PROMPT
- 修改 `select_backends()` 现有选择语义
- 修改 `backend_capabilities.json`
- 新增 LLM call
- 修改 formal evaluator / `agent_chat()` 签名
- 修改 Learn / Experiments / Explorer / Repair 主流程

---

## 验收

完成后，一个不了解各量子平台的开发者应该能完成：

```text
“至少 20 个 qubit，不想排队，也不想注册账号”
        ↓
LoomQ：我理解到 20+ qubits / 零排队 / 无账号
        ↓
本地能力表筛选
        ↓
看到所有真正满足条件的候选
        ↓
同时理解其他后端具体因为什么被排除
```

并且用户能清楚知道：

> **AI 在这里负责理解要求，不负责编造后端事实；最后的筛选结论来自本地、可复核的能力表。**
