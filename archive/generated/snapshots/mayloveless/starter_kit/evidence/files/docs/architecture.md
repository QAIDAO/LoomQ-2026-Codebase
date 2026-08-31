# LoomQ 系统架构说明

## 整体架构

LoomQ 采用分层架构，主要包含 Web 交互层、L2 Agent 层、平台无关的量子程序核心层、后端执行层以及运行环境层。`adapter.py` 只提供官方入口并完成目标路由，不包含平台 SDK 逻辑。

整体流程：

```
用户 / 官方 evaluator
          |
          v
Web 交互层 / adapter.py
          |
          v
OpenQASM 2.0 Parser + 语义校验
          |
          v
平台无关 Circuit IR
          |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
SpinQ Serializer       OriginQ Serializer     Braket Serializer
OpenQASM 2.0              OriginIR             OpenQASM 3
          |                    |                    |
          v                    v                    v
SpinQ Runner           OriginQ Runner          Braket Runner
          |                    |                    |
          v                    v                    v
  SpinQit Taurus       OriginQ CPUQVM       Braket LocalSimulator
          |                    |                    |
          +--------------------+--------------------+
                               |
                               v
         统一结果 Schema（counts 位序固定为 little）
```

---

## 1. Web 交互层

技术组成：

- 前端 Web 应用；
- Learn / Explorer / Repair 页面；
- Backend 执行平台选择。

负责：

- 用户输入自然语言需求；
- 展示生成结果；
- 展示验证过程；
- 发起量子程序执行。

---

## 2. L2 Agent 层

负责自然语言到量子程序的转换。

主要流程：

```

User Prompt
|
v
LLM Generation
|
v
OpenQASM
|
v
Semantic Verification
|
v
Repair (optional)

```

其中：

- LLM 负责理解需求和生成候选程序；
- 本地验证器负责判断程序正确性；
- 修复流程根据验证结果生成修正候选。

---

## 3. 平台无关量子程序核心层

Parser 只负责 OpenQASM 2.0 语法解析与语义校验，并生成不包含具体平台字段的 `Circuit` IR。L1 转译、模拟器执行、真机执行和 L2 本地验证复用同一套 Parser 与 IR，不为不同平台重复解析 OpenQASM。

包括：

- `loomq/parser.py`：OpenQASM Parser 与语义校验；
- `loomq/ir.py`：平台无关 `Circuit` IR；
- `loomq/serializers/`：将 IR 序列化为 SpinQ OpenQASM 2.0、OriginIR 或 Braket OpenQASM 3；
- `loomq/semantic_verifier.py`：L2 statevector、fidelity 与 repair candidate 验证。

---

## 4. 后端执行与结果归一化层

`loomq/runners/` 中的 Runner 负责调用后端 SDK，并将不同平台的原始结果统一为官方结果 Schema。`adapter.py` 根据 `target` 路由到对应 Serializer 或 Runner，不在入口层实现平台细节。

支持：

- SpinQit Taurus 本地模拟器；
- OriginQ CPUQVM 本地模拟器；
- AWS Braket LocalSimulator。

三个 Runner 均返回 `backend`、`job_id`、`shots`、`counts`、`bit_order` 和 `timestamp`；其中 `counts` 在中间层内归一化，`bit_order` 固定为 `little`。

Origin Quantum Cloud 与 SpinQ Cloud 真机接入由独立提交脚本和 Web 真机服务负责，复用 L1 的 Parser 与 Serializer 生成实际提交电路；真机原始结果和可追溯元数据保存到 `evidence/files/`，不把凭据写入镜像或证据文件。

---

## 5. 运行环境层

工程化设计：

- Docker 提供一致运行环境；
- 前端静态资源与后端服务统一部署；
- evaluator 提供自动化检查；
- 真机 SDK 采用隔离环境避免依赖冲突。
