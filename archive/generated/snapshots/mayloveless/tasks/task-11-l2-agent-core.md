# Task 11：L2 Agent 核心闭环（总览）

## 目标

实现官方可调用的：

```python
def agent_chat(prompt: str) -> str:
    ...
```

覆盖 L2 三类客观任务：

1. 根据自然语言生成 OpenQASM 2.0；
2. 修复错误 QASM，并保持用户声明的目标态语义；
3. 根据官方能力表推荐规范后端 ID。

为便于逐步实现和审查，本任务拆成三个独立阶段，必须按顺序执行。

## 子任务

### Task 11A：模型调用骨架与单次 QASM 生成

文件：`tasks/task-11a-l2-call-skeleton.md`

完成：

- `adapter.agent_chat()` 的模块边界；
- 调用现有 `llm_client.chat_completion()`；
- 解析结构化 JSON；
- 提取并校验一次成功的 QASM；
- 模型异常与凭证安全测试。

不包含二次修复和后端选择。

### Task 11B：QASM 校验与一次修复闭环

文件：`tasks/task-11b-l2-qasm-repair.md`

完成：

- 稳健提取 fenced QASM；
- 使用现有 Parser 校验；
- 第一次非法时最多再调用模型一次；
- 第二次仍非法则停止；
- GHZ、Bell 修复及调用次数测试。

### Task 11C：确定性后端选择

文件：`tasks/task-11c-l2-backend-selection.md`

完成：

- 加载 `backend_capabilities.json`；
- 模型只提取自然语言约束；
- 本地确定性筛选规范后端 ID；
- 覆盖比特数、真机、排队、费用、账号及无解场景。

## 全局边界

三个子任务均遵守：

- 不做网页或 CLI；
- 不开始 L3；
- 不修改 L1 Parser、IR、Serializer、Runner、测量映射或 evaluator；
- 不引入大型 Agent/RAG 框架；
- 不在仓库或测试中写入真实 API Key；
- 不用关键词分支硬编码 GHZ、Bell 或后端答案；
- 每个正式请求至少经过一次有效模型调用；
- 暂不把 `submission.yaml` 中 `levels.l2` 和 `network.required_for_l2` 改为 `true`；
- 每个子任务完成后先 review、测试，再进入下一步；
- Codex 不 commit、不 push。

## Task 11 总体验收

11A、11B、11C 全部完成后：

- `adapter.agent_chat(prompt)` 可处理三类 L2 任务；
- 生成和修复后的 QASM 均通过现有 Parser；
- 非法 QASM 最多修复一次；
- 后端答案由官方能力表确定性产生；
- 模型响应异常不泄露 Key、请求头或 traceback；
- L2 专项测试和全量单元测试通过；
- L1 无回归；
- `submission.yaml` 的 L2 仍保持关闭，等待真实模型回归。

## Task 11 完成后的下一阶段

进入 Task 12：真实 OpenAI-compatible 模型回归、Prompt 调整与公开 L2 evaluator。通过后再开启 `submission.yaml` 的 L2 和网络开关。
