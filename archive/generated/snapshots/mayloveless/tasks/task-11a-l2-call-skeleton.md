# Task 11A：L2 模型调用骨架与单次 QASM 生成

## 目标

建立最小、可测试的 L2 调用链：

```text
用户 prompt
→ agent_chat
→ LLM 结构化响应
→ 提取 QASM
→ 现有 Parser 校验
→ 返回最终文本
```

本任务只支持“第一次模型响应已经给出合法 QASM”的成功路径，以及模型响应异常的失败路径。

暂不实现：

- QASM 二次修复；
- 后端选择；
- UI / CLI；
- `submission.yaml` 的 L2 开关。

## 官方接口

保持：

```python
def agent_chat(prompt: str) -> str:
    ...
```

调用仓库现有：

```python
llm_client.chat_completion(messages)
```

配置只能来自：

- `LOOMQ_LLM_BASE_URL`
- `LOOMQ_LLM_API_KEY`
- `LOOMQ_LLM_MODEL`
- `LOOMQ_LLM_TIMEOUT_SECONDS`

不得硬编码 URL、Key 或模型名。

## 实现范围

### 1. 建立轻量模块边界

新增一个轻量 L2 核心模块，例如：

```text
starter_kit/loomq/l2_agent.py
```

必要时再新增一个小型 QASM 工具模块，例如：

```text
starter_kit/loomq/qasm_tools.py
```

要求：

- `adapter.agent_chat()` 只负责委托；
- Prompt、模型响应解析和格式化不堆在 `adapter.py`；
- 不引入第三方 Agent 框架；
- 模块导入时不得发起网络请求。

### 2. 首次模型调用协议

第一次调用要求模型返回一个 JSON 对象：

```json
{
  "task_type": "generate_qasm",
  "qasm": "OPENQASM 2.0; ...",
  "explanation": "简短说明"
}
```

系统提示至少说明：

- 返回 JSON，不返回额外散文；
- 使用 OpenQASM 2.0；
- 输出完整声明，包括 `include`、`qreg`、`creg`；
- 按用户要求测量；
- 只使用当前项目支持的门；
- 不硬编码公开 GHZ 示例的固定答案。

允许模型把 JSON 包裹在 Markdown `json` 代码块中，解析器应能处理纯 JSON 和单个 fenced JSON。

### 3. 模型响应读取

封装可独立测试的响应读取逻辑：

- 读取 `choices[0].message.content`；
- 校验 `choices`、`message`、`content`；
- content 必须是非空字符串；
- JSON 必须是对象；
- `task_type` 在本任务中只接受 `generate_qasm`；
- `qasm` 必须是非空字符串；
- `explanation` 缺失时允许使用空字符串。

异常要求：

- 给出稳定、可理解的 `RuntimeError` 或项目自定义错误；
- 不回显完整原始响应；
- 不包含 API Key、Authorization Header 或 Python traceback；
- 不尝试无限容错或猜测破损 JSON。

### 4. QASM 提取与校验

新增：

```python
def extract_qasm(text: str) -> str | None:
    ...


def validate_qasm(qasm: str) -> None:
    ...
```

要求：

- 支持纯 QASM；
- 支持 Markdown `qasm` / `openqasm` fenced code block；
- 必须从 `OPENQASM 2.0;` 开始提取完整程序；
- 使用现有 `loomq.parser.parse_qasm()` 校验；
- 不复制第二套 QASM Parser；
- 本任务遇到非法 QASM 直接失败，不调用第二次模型，修复留给 Task 11B。

### 5. 最终返回格式

合法时返回：

```text
简短说明

```qasm
OPENQASM 2.0;
...
```
```

要求：

- 最终文本中只有一个完整 QASM 程序；
- 程序已通过现有 Parser；
- 官方 evaluator 能从回复中提取 `OPENQASM 2.0;`；
- 说明保持简短，不把解释插入代码块内部。

### 6. 测试注入

生产代码应允许测试通过 `unittest.mock.patch` 替换模型调用函数。

不要：

- 增加生产环境的 `mock` 开关；
- 根据测试 prompt 返回固定结果；
- 启动公网请求。

## 自动化测试

新增独立 L2 测试模块，至少覆盖：

1. 模拟模型返回合法 3 比特 GHZ QASM，`adapter.agent_chat()` 返回可解析 QASM；
2. 纯 JSON 响应可解析；
3. fenced JSON 响应可解析；
4. QASM 字段为纯程序时可提取；
5. QASM 字段为 fenced code 时可提取；
6. 缺少 `choices`；
7. `content` 为空；
8. content 为非法 JSON；
9. 缺少或非法 `task_type`；
10. QASM 无法通过 Parser 时稳定失败；
11. 异常信息不包含测试 Key；
12. 模型只调用一次。

测试不得访问公网。

## 回归验证

至少执行：

```bash
cd starter_kit
python -m unittest tests.test_l2_agent -v
python -m unittest discover -s tests -v
```

测试模块名可按实际文件名调整。

本任务不要求运行官方 L2 evaluator，因为还没有真实模型配置，也尚未实现修复和后端选择。

## 修改边界

允许修改或新增：

- `starter_kit/adapter.py`
- `starter_kit/loomq/` 下轻量 L2 模块
- `starter_kit/tests/` 下 Task 11A 测试
- 必要时对 `llm_client.py` 做极小的契约兼容修复

不要修改：

- L1 Parser、IR、Serializer、Runner、evaluator；
- `backend_capabilities.json`；
- `submission.yaml`；
- Dockerfile 和依赖文件；
- 真机证据；
- L3 代码。

不要 commit 或 push。

## 验收标准

- `adapter.agent_chat()` 已委托至独立 L2 模块；
- 每次请求确实调用一次 `llm_client.chat_completion()`；
- 合法结构化响应可生成经过 Parser 校验的最终 QASM；
- 非法结构或非法 QASM 稳定失败；
- 异常不泄露凭证；
- L2 专项测试和全量测试通过；
- 未实现 Task 11B、11C 内容；
- `submission.yaml` 的 L2 仍为 `false`。

## 完成后汇报

只需汇报：

1. 新增模块及职责；
2. 模型 JSON 协议；
3. QASM 提取与校验流程；
4. 异常与凭证保护；
5. 专项及全量测试结果；
6. 是否修改 `llm_client.py`、依赖或 Docker；
7. Task 11B 开始前需要注意的问题。
