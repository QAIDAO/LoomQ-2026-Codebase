# LoomQ

LoomQ 是一个面向具备编程基础开发者的多量子平台通用中间层与智能体工具。项目将 OpenQASM 2.0 解析为平台无关 IR，再统一转译和运行于 SpinQ、OriginQ 与 Braket；同时提供自然语言生成与修复、Hybrid-QASM 编译、Web 学习体验和量子 RISC-V 扩展。

![LoomQ Demo](evidence/files/l2-agent/home.png)

## 项目概览

本提交实现了 L1、L2、L3 以及自定义量子 RISC-V 扩展。统一执行入口为 `adapter.py`，内部采用统一的分层架构：

```text
OpenQASM 2.0
    -> Parser / 语义校验
    -> 平台无关 Circuit IR
    -> SpinQ / OriginQ / Braket Serializer
    -> 对应 Runner
    -> 统一结果 Schema（bit_order = little）
```

主要能力：

- **L1**：通过统一 Parser 和 Circuit IR，将同一份 OpenQASM 程序适配到 SpinQ、OriginQ 和 Braket，并统一不同平台的执行结果；完整支持题面 12 个白名单门。
- **L2**：`agent_chat()` 通过 `LOOMQ_LLM_*` 环境变量调用 OpenAI-compatible 模型服务，支持自然语言生成 QASM、程序修复和基于本地能力表选择后端；候选 QASM 会经过本地语法及语义验证，并提供一次有界修复机会。
- **L3**：`compile_hybrid()` 解析 Hybrid-QASM 的经典控制块，将量子部分返回为操作序列，将赋值、算术和 `if/else` 编译为官方 Tiny RISC-V 模拟器可执行的汇编。
- **交互入口**：提供 Learn、Explorer、程序修复和执行平台选择 Web 流程，并展示电路步骤、验证结果及错误恢复提示。
- **Bonus**：提供量子 RISC-V `custom-0` 指令编码、严格解码、协处理器派发、测量写回和端到端测试。
- **真机证据**：保留 Origin Quantum Cloud 与 SpinQ Cloud 的实际提交电路、平台原始响应、可追溯 job ID、元数据及辅助截图。

实现入口与材料：

- [`adapter.py`](adapter.py)：统一执行入口与路由层；
- [`loomq/`](loomq/)：Parser、IR、Serializer、Runner、L2 Agent 和 L3 编译器；
- [`web/`](web/)：提供 Learn、Explorer、Repair 等交互体验的 Web 前端；
- [`bonus/quantum_riscv/`](bonus/quantum_riscv/)：自定义量子 RISC-V 扩展；
- [`evidence/README.md`](evidence/README.md)：真机、交互体验、工程与 Bonus 的人工评分证据入口；
- [`evidence/files/docs/architecture.md`](evidence/files/docs/architecture.md)：完整架构说明。

### Clean Docker 复现

以下命令均以本目录 `starter_kit/` 为当前工作目录：

```bash
docker build -t loomq-final .
docker run --rm loomq-final
```

镜像默认运行三平台 L1 公开契约自测。进一步执行三平台公开兼容性审计：

```bash
docker run --rm loomq-final \
  python scripts/audit_l1_scoring.py \
  --shots 8192 \
  --targets spinq,originq,braket \
  --require-all
```

本提交在 clean Docker 中执行该公开审计的记录为 **75 passed、0 failed、0 missing targets**。该结果来自仓库内固定公开审计用例，不代表正式评测结果。

执行 Python 全量单元测试：

```bash
docker run --rm loomq-final \
  python -m unittest discover -s tests -v
```

Docker 归档不包含 Git 仓库元数据，因此 `test_git_drift_checks_pass_when_repository_metadata_is_available` 在镜像中显示 `SKIP` 属于预期行为；无 Git 元数据的可移植快照契约由独立测试覆盖。

### 启动 Web

启动时必须由运行环境提供 L2 模型配置，不得把 API Key 写入镜像或仓库：

```bash
docker run --rm -p 8000:8765 \
  -e LOOMQ_LLM_BASE_URL \
  -e LOOMQ_LLM_API_KEY \
  -e LOOMQ_LLM_MODEL \
  -e LOOMQ_LLM_TIMEOUT_SECONDS=120 \
  loomq-final \
  python -m loomq.debug_web --host 0.0.0.0 --port 8765 --serve-web
```

启动后访问 [http://localhost:8000](http://localhost:8000)。更完整的用户任务、真机可选配置和评分证据见 [`evidence/README.md`](evidence/README.md)。

## 提交结构

```text
starter_kit/
├── __init__.py
├── VERSION
├── CHANGELOG.md
├── submission.yaml
├── adapter.py
├── llm_client.py
├── l2_policy.json
├── evaluator.py
├── prepare_submission.py
├── riscv_emulator.py
├── backend_capabilities.md
├── backend_capabilities.json
├── QUANTUM_101.md
├── gate_identities.md
├── target_ir_contract.md
├── requirements.txt
├── Dockerfile
├── loomq/                    # Parser、IR、后端适配、Agent 与 L3 编译器
├── scripts/                  # 真机工具与公开审计
├── tests/                    # Python 单元和集成测试
├── web/                      # React/Vite 交互入口
├── bonus/
│   └── quantum_riscv/       # 自定义量子 RISC-V 扩展
├── evidence/
│   ├── README.md
│   └── files/                # 可选附件
├── circuits/
│   ├── bell.qasm
│   └── ghz3.qasm
└── examples/
```

## 统一接口

[`adapter.py`](adapter.py) 保持轻量，只负责官方入口和路由。L1 接口为：

```python
def transpile(qasm_str: str, target: str) -> str: ...
def run(qasm_str: str, target: str, shots: int) -> dict: ...
```

L2、L3 接口为：

```python
def agent_chat(prompt: str) -> str: ...
def compile_hybrid(hybrid_qasm_str: str) -> tuple[list, str]: ...
```

三个 `transpile()` 目标分别输出 SpinQ OpenQASM 2.0、OriginIR 和 Braket OpenQASM 3，具体格式见 [`target_ir_contract.md`](target_ir_contract.md)。`run()` 将后端结果统一为包含 `backend`、`job_id`、`shots`、`counts`、`bit_order` 和 `timestamp` 的字典，其中 `bit_order` 固定为 `little`。

## L2 模型配置

`agent_chat()` 不硬编码服务地址、凭据或模型名，运行时读取：

| 环境变量 | 含义 |
|---|---|
| `LOOMQ_LLM_BASE_URL` | OpenAI-compatible API 根地址 |
| `LOOMQ_LLM_API_KEY` | 当前运行凭证 |
| `LOOMQ_LLM_MODEL` | 当前模型 |
| `LOOMQ_LLM_TIMEOUT_SECONDS` | 可选的请求超时 |

缺少必要配置时程序会立即失败，错误信息不会包含 API Key。运行协议和配置约束见 [`l2_policy.json`](l2_policy.json)。

## 证据与详细文档

- 人工评分材料入口：[`evidence/README.md`](evidence/README.md)
- 系统架构：[`evidence/files/docs/architecture.md`](evidence/files/docs/architecture.md)
- 量子 RISC-V 规格：[`bonus/quantum_riscv/SPEC.md`](bonus/quantum_riscv/SPEC.md)
- 后端能力表：[`backend_capabilities.md`](backend_capabilities.md)
- 门分解说明：[`gate_identities.md`](gate_identities.md)
