# Task 12A：L2 真实 API 打通与三类冒烟测试

## 目标

用真实 OpenAI-compatible 模型服务验证当前 L2 Agent 的完整调用链，确认以下三类请求都能至少成功跑通一例：

1. 自然语言生成 OpenQASM 2.0；
2. 修复有问题的 OpenQASM 2.0；
3. 根据自然语言约束选择规范后端 ID。

本任务只做真实 API 打通和冒烟验证，不做大规模 Prompt 调优，不开启最终 L2 提交开关。

## 前置条件

Task 11A / 11B / 11C 已完成并提交。

用户会在本机通过环境变量提供真实模型配置：

```bash
export LOOMQ_LLM_BASE_URL=<openai-compatible-base-url>
export LOOMQ_LLM_API_KEY=<your-api-key>
export LOOMQ_LLM_MODEL=<model-name>
export LOOMQ_LLM_TIMEOUT_SECONDS=120
```

要求：

- 不把真实 API Key 写入仓库、测试、日志快照或任务文档；
- 不新增 `.env`、配置文件或硬编码凭证；
- 不打印 Authorization Header；
- 不修改 `submission.yaml` 的 L2 开关。

## 实现与验证范围

### 1. 先做最小连接验证

优先直接使用现有 `llm_client.py` 和 `adapter.agent_chat()`，不要先改代码。

确认真实请求能够到达模型服务，并返回一个可被当前代码读取的 `choices[0].message.content`。

若失败，先区分：

- API 地址/模型名/凭证配置问题；
- OpenAI-compatible 协议差异；
- 当前响应解析或 Prompt 问题。

只修复真正阻断真实调用的最小兼容性问题。

### 2. 三类真实冒烟请求

至少真实执行以下三类请求各 1 次。

#### A. QASM 生成

使用与公开示例不同但同类的自然语言，例如：

```text
生成一个 2 比特 Bell 态，不要求测量。
```

检查：

- 至少发生一次真实模型调用；
- 最终返回完整 OpenQASM 2.0；
- 通过现有 Parser；
- 用户未要求测量时，不强制添加 creg / measure；
- 不出现第二份冲突 QASM。

#### B. QASM 修复

提供一段有明显问题的程序，并明确目标，例如：

```text
我想制备 Bell 态并测量，请修复下面的代码：
H q[0];
CX q[0] q[1]
```

检查：

- 最终 QASM 通过 Parser；
- 保持 Bell 态目标；
- 因为用户明确要求测量，最终包含经典寄存器和测量；
- 模型调用次数不超过当前设计上限 2 次。

#### C. 后端选择

使用自然语言约束，例如：

```text
我需要至少 15 比特、零排队，优先本地可运行的后端。
```

检查：

- 模型只负责提取约束；
- 最终 backend ID 来自 `backend_capabilities.json`；
- 输出规范 ID；
- 不采用模型自行编造的后端名；
- 只发生 1 次模型调用。

### 3. 记录真实失败案例

如果某一类真实请求失败，不要立刻大改 Prompt。

请先记录最小事实：

- 用户输入；
- 模型返回的结构形态（去除任何敏感信息）；
- 失败发生在：传输 / JSON 结构 / task_type / QASM 提取 / Parser / 后端约束解析 / 其他；
- 是否发生了第二次修复调用；
- 当前代码是否能通过很小的兼容调整解决。

不要把完整真实响应长期保存进仓库，除非已经确认不包含敏感数据且后续测试确实需要。

### 4. 最小兼容性修复原则

本任务允许修改：

- `starter_kit/llm_client.py` 的最小 OpenAI-compatible 兼容问题；
- `starter_kit/loomq/l2_agent.py` 中真实模型响应解析的明显健壮性问题；
- 对应测试。

不要在本任务中：

- 重写 Task 11 架构；
- 增加第三次及以上模型调用；
- 为单个真实返回硬编码特殊答案；
- 扩展 backend 能力表；
- 修改 L1；
- 做 UI / CLI；
- 开始 L3；
- 修改 `submission.yaml`。

### 5. 回归测试

任何代码修改后至少执行：

```bash
cd starter_kit
python -m unittest discover -s tests -v
```

如果只是环境配置成功且无需改代码，也要确认现有全量测试仍通过。

## 验收标准

- 真实 OpenAI-compatible API 已成功打通；
- 三类 L2 请求至少各成功跑通一例，或明确列出单一可复现阻断原因；
- QASM 生成/修复结果继续经过现有 Parser；
- 后端结果继续由本地能力表确定；
- 模型调用次数仍符合现有策略：QASM 最多 2 次，后端选择 1 次；
- API Key 未进入 Git 历史、测试或日志；
- 全量单元测试通过；
- `submission.yaml` 仍保持 L2 为 `false`。

## 完成后汇报

只需汇报：

1. 使用的 API Base URL 和模型名（不要汇报 Key）；
2. 三类真实冒烟测试结果；
3. 每类实际模型调用次数；
4. 是否遇到真实响应格式兼容问题；
5. 是否修改代码；
6. 全量测试结果；
7. 进入 Task 12B 前最需要处理的失败模式。