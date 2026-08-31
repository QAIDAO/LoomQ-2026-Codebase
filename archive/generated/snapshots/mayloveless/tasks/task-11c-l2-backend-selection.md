# Task 11C：L2 确定性后端选择

## 前置条件

Task 11A、11B 已完成并通过：

- L2 调用骨架和结构化响应解析可用；
- QASM 生成、修复和最多一次重试可用；
- 全量测试无回归。

本任务只增加第三类 L2 客观任务：智能选择后端。

## 目标

实现：

```text
用户自然语言约束
→ LLM 提取结构化约束
→ 本地读取官方能力表
→ 确定性筛选
→ 返回规范后端 ID 和简短理由
```

模型不得凭记忆直接决定最终后端；最终答案必须来自：

```text
starter_kit/backend_capabilities.json
```

正式请求仍必须至少发生一次有效模型调用，不能用纯规则绕过模型。

## 实现范围

### 1. 扩展结构化协议

支持：

```json
{
  "task_type": "select_backend",
  "qasm": null,
  "backend_constraints": {
    "min_qubits": 15,
    "require_qpu": false,
    "require_no_queue": true,
    "cost_policy": "free_only | free_or_quota | paid_allowed | unspecified",
    "allow_account_required": true
  },
  "explanation": "简短说明"
}
```

约束字段含义：

- `min_qubits`：所需最小量子比特数，未声明为 `null`；
- `require_qpu`：明确要求真实硬件时为 `true`，明确接受模拟器时可为 `false`，未声明为 `null`；
- `require_no_queue`：明确要求零排队时为 `true`；
- `cost_policy`：
  - `free_only`：只允许完全免费；
  - `free_or_quota`：允许免费或免费额度；
  - `paid_allowed`：允许付费；
  - `unspecified`：未声明；
- `allow_account_required`：明确不能注册/登录时为 `false`，否则为 `true` 或 `null`。

模型只负责提取约束，不输出或决定最终 backend ID。

### 2. 新增后端选择模块

新增轻量模块，例如：

```text
starter_kit/loomq/backend_selector.py
```

职责：

- 使用相对于模块或 Starter Kit 的稳定路径加载 JSON；
- 不依赖当前工作目录；
- 校验顶层对象、`backends` 数组和必要字段；
- 不在源码中复制能力表数据；
- 返回满足条件的后端对象或规范 ID；
- 保持能力表原始顺序，确保结果稳定。

必要字段至少包括：

- `id`
- `kind`
- `max_qubits`
- `queue`
- `cost`
- `requires_account`
- `name`

字段缺失或类型错误时应明确报错，不静默猜测。

### 3. 确定性筛选规则

至少支持：

#### 量子比特

```text
backend.max_qubits >= min_qubits
```

#### 真实硬件

`require_qpu=true` 时，只接受 `kind == "qpu"`。

不要把 `cloud` 自动视为 QPU；以官方 JSON 的 `kind` 为准。

#### 零排队

`require_no_queue=true` 时，只接受：

```text
queue == "none"
```

#### 费用

- `free_only`：只接受 `cost == "free"`；
- `free_or_quota`：接受 `free` 和 `free_quota`；
- `paid_allowed` 或 `unspecified`：不因费用字段排除。

#### 账号

`allow_account_required=false` 时，只接受：

```text
requires_account == false
```

未声明的约束不得擅自收紧。

### 4. 最终回复

有匹配时返回：

- 一个或多个规范 backend ID；
- 简短说明它们满足哪些约束；
- 不输出模型臆测的实时排队时长或价格；
- 不把平台营销名称替代规范 ID。

示例格式：

```text
满足条件的后端：`backend_id_1`、`backend_id_2`。
理由：它们支持至少 N 比特，并且在官方能力表中标记为零排队/免费等。
```

无匹配时：

- 明确说明当前官方能力表中无解；
- 指出可以考虑放宽的约束类别，如比特数、真机、零排队或费用；
- 不推荐不满足条件的后端；
- 不编造 backend ID。

### 5. 与现有 L2 流程集成

- `task_type == select_backend` 时走本地选择器；
- 不进入 QASM 提取或修复流程；
- `generate_qasm`、`repair_qasm` 行为保持不变；
- 未知 task type 继续稳定失败；
- 模型调用仍为一次，后端选择不需要第二次模型调用。

## 自动化测试

至少覆盖：

1. **15 比特、零排队**：返回能力表中所有满足条件的规范 ID；
2. **真实硬件、5 比特、免费或免费额度**：只返回满足条件的 QPU；
3. **完全免费且无需账号**：正确排除免费额度和需账号后端；
4. **允许付费**：不会错误排除付费后端；
5. **超过最大比特数**：无匹配；
6. **真实硬件且零排队**：若无解则明确无解；
7. **稳定顺序**：结果顺序与能力表一致；
8. **路径稳定性**：从 Starter Kit 之外的工作目录调用仍能加载 JSON；
9. **Schema 异常**：临时能力表缺字段时明确失败；
10. **不信任模型 ID**：即使模型响应额外包含 backend ID，也不得直接采用；
11. **调用次数**：后端任务只调用一次模型；
12. **QASM 回归**：11A、11B 行为不变；
13. **全量回归**：L1 测试无新增失败。

测试期望可以明确列出当前官方契约 ID，或从能力表加载并按独立测试逻辑推导；不要复制生产筛选函数作为测试预期。

## 回归验证

至少执行：

```bash
cd starter_kit
python -m unittest tests.test_l2_agent -v
python -m unittest tests.test_backend_selector -v
python -m unittest discover -s tests -v
```

文件名可按实际实现调整。

本任务仍不要求真实 API，也不运行正式 L2 评测。

## 修改边界

允许修改或新增：

- Task 11A、11B 的 L2 核心模块；
- 新的 `backend_selector.py`；
- L2 专项测试；
- `adapter.py` 的最小委托调整。

不要修改：

- `backend_capabilities.json` 的内容；
- L1 生产逻辑和 evaluator；
- `submission.yaml`；
- Dockerfile 和依赖；
- 真机证据；
- L3 代码。

不要 commit 或 push。

## 验收标准

- 模型只提取约束；
- 最终 backend ID 完全由官方 JSON 确定；
- 比特数、QPU、排队、费用和账号约束均可筛选；
- 无匹配时不编造结果；
- 后端任务只调用一次模型；
- QASM 生成和修复无回归；
- L2 专项和全量测试通过；
- `submission.yaml` 的 L2 仍为 `false`。

## 完成后汇报

只需汇报：

1. 约束字段和默认语义；
2. 能力表加载与 Schema 校验；
3. 确定性筛选规则；
4. 典型匹配与无解测试；
5. L2 专项和全量测试结果；
6. 是否修改依赖、Docker 或官方数据；
7. 进入 Task 12 前仍缺少的事项。
