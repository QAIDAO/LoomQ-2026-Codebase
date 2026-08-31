# L2 Real-Model Validation (DeepSeek V4 Flash)

> **重要声明**：这是参赛者在本地，用**真实 DeepSeek V4 Flash endpoint** 对 LoomQ L2 链路做的一次 robustness 压力测试。它**不能替代**组织方的 hidden / private L2 评测，也**不代表**官方 L2 已被证明满分。它只说明：在本地真实模型调用下，LoomQ 的 L2 生成 / 修复 / 后端推荐链路在给定测试集上的表现。

## 1. 测试对象

- 模型：`deepseek-v4-flash`
- 端点：真实公网 OpenAI 兼容 `chat/completions`（`LOOMQ_LLM_*` 配置）
- 链路（与官方一致）：natural language → DeepSeek V4 Flash → 严格 JSON plan → `parse_agent_plan` → QASM 提取 → LoomQ parser → validator → 独立参考模拟器语义验证 → 必要时 retry → 最终判定

## 2. 结果汇总

| Round | 说明 | 通过 | 失败 |
|---|---|---|---|
| 1 | 36 例（生成 12 / 修复 12 / 后端 12），自然措辞 | 36 | 0 |
| 2 | 36 例，**全部措辞改写**（验证泛化） | 36 | 0 |
| 3 | 18 例 adversarial（错配混杂、错别字、口语、多余上下文、语序变化） | 17 | 1 |
| 4 | 12 例 **私有 prompt 变体** smoke（GHZ 4 / 修复 4 / 后端 4，语义级判定） | 12 | 0 |
| **合计** | **102** | **101** | **1** |

- 平均延迟 ≈ 7.9 s / 次，p50 ≈ 7.7 s，p95 ≈ 9.0 s（非流式单次调用）。
- 重试率：1/90 ≈ 1.1%（分母为第 1–3 轮启用重试追踪的 90 次调用；第 4 轮 smoke 未计入重试统计）。

## 2.1 记录粒度（如实披露）

- 每轮通过情况以**聚合**形式记录在 `l2-deepseek-v4-flash-stress-summary.json`（total/passed/failed + 按 generate/repair/backend 的 breakdown + 轮次说明）。
- **失败用例保留逐例记录**（第 3 轮唯一失败含 case_id、prompt、失败类别、latency、retry_observed、复跑结论）。
- 通过用例**未逐例保存** prompt 与延迟明细；第 4 轮 12 例仅有聚合计数与变体说明（4 GHZ 措辞变体 / 4 损坏 Bell 修复变体 / 4 后端约束变体）。
- 所有文档中的 102/101/1 数字均由该 JSON 程序化重算支持（`scripts/validate_l2_stress.py`），不存在无记录的口头计数。

## 3. 失败分析（唯一 1 例）

- `adv_be_typo1`："我要30个比特的，排队时间要为零"（30 qubits + zero_queue）。
- 类别：**transient model output** —— 模型偶发返回不合规 JSON，内部 retry 一次后仍无法通过严格 `parse_agent_plan` 校验，抛出 `RuntimeError`。
- 判定：**非系统性缺陷**。单独重跑同一 prompt 即成功（`task=recommend, constraints=BackendConstraints(qubits=30, zero_queue=True)`，`select_backends` 返回 `['originq_local_simulator']`，与程序化期望一致）。
- 依据任务规则 L，provider 偶发 transient 失败**不修改产品逻辑去掩盖**，如实记录。

## 4. 语义验证（比官方更严格）

- 生成 / 修复：不仅要求 `parse_agent_plan` 接受 + verifier 能解析模拟，还**额外**用独立参考模拟器计算目标态分布，要求：
  - Bell → `P(00)≈P(11)≈0.5`
  - GHZ-n → `P(0^n)≈P(1^n)≈0.5`
- 后端推荐：用**程序化** `select_backends(官方 backend_capabilities.json)` 计算正确候选集合，要求模型推荐的后端 ID 集合与程序化结果**完全一致**（非字符串匹配）。

## 4. 结论

在真实 DeepSeek V4 Flash 下，LoomQ L2 的生成 / 修复 / 后端推荐在 102 例（含 adversarial 与私有 prompt 变体）中 **101 例通过**，唯一失败为 provider 偶发 transient，非系统性缺陷。当前实现**无需修改**。

## 5. 安全

- 本文件与配套 JSON **不含任何 API Key / Token / Authorization / Cookie / secret**。
- 未写入、未提交任何密钥；调用发生在本地，凭据仅通过环境变量注入。

## 6. 边界

- 这是本地 robustness evidence，**不替代**组织者 hidden/private L2 评测。
- 不声称"官方 L2 满分"；最终得分由组织者决定。