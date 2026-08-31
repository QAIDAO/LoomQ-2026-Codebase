# LoomQ Starter Kit v1.1.0

本工具包定义参赛提交协议，并提供公开自测。它不包含正式评分器、隐藏答案、Mock 得分路径或任何 Level 的参考解答。

## 本队 L1 实现

L1 的模块位置、三平台适配、位序规范和验证证据见 [`docs/L1_IMPLEMENTATION.md`](docs/L1_IMPLEMENTATION.md)。十二门白名单、public/runtime 双方言、exact-artifact runner、原生结果 acceptance/bit-order 诊断、八个公开家族代理电路和厂商验证见 [`docs/HARDENING_DESIGN.md`](docs/HARDENING_DESIGN.md)。开发期统一运行：

```bash
python scripts/verify_all.py
```

正式冻结使用严格闸门；它要求三套原生 SDK、禁止 fallback 与 skip，并复核本地真实模型 campaign 报告：

```bash
python scripts/verify_all.py --release
```

SpinQ 真机提交前先运行只读预检。该命令会登录、核对真机平台、编译 Bell 电路并生成本地 task payload 预览，但不会创建 job 或消耗额度：

```bash
python scripts/preflight_spinq_hardware.py
```

凭据只存放在 fork 根目录、被 Git 忽略的 `.env.hardware.local`。预检产物写入同样被忽略的 `local_docs/hardware_preflight/spinq/`，不能代替最终真机 `job_id` 和原始结果证据。

只有在明确确认消耗真机额度后才运行：

```bash
python scripts/submit_spinq_hardware.py --confirm-submit SPINQ_REAL_QPU
```

提交工具会在获得 job ID 后立即写入本地状态文件；再次运行时只恢复或返回同一 job，不会重复提交。

安装 `requirements.txt` 中的精确直接依赖后，可用 `LOOMQ_REQUIRE_NATIVE=1` 强制验证三家原生本地 SDK，禁止静默回退到内置参考模拟器。普通模式下的 fallback 原因、阶段摘要、bit-order probe 和 fidelity threshold 都会写入 `result.meta`。

## 本队 L2 实现

`agent_chat()` 使用组委会注入的 `LOOMQ_LLM_*` 环境变量完成至少一次 OpenAI-compatible 模型调用。模型负责理解用户意图并生成最终 QASM；Bell、GHZ、W、QFT、三比特 Grover 等已知意图会在模型调用后由本地确定性构造器产生独立参考电路和分布，用于校验与重试，但绝不替换模型 QASM。后端约束先做 schema/别名归一化，再由经过验证的 [`backend_capabilities.json`](backend_capabilities.json) 确定性筛选，不接受模型虚构的后端 ID。

模型摘要不能向官方 QASM 提取器注入第二份程序：含代码围栏或 `OPENQASM 2.0;` 的摘要会被丢弃。真实 DeepSeek 语义 campaign 使用 24 个固定生成/修复/选择案例、双模拟 oracle 与哈希证据：

```bash
python tests/live_l2_deepseek_harness.py --live --env-file .env.l2.local --suite baseline24
```

本地模型配置完成后，可直接运行公开 L2 自测：

```bash
python evaluator.py --level l2
```

零基础体验入口不需要安装额外 Web 依赖：

```bash
python l2_app.py --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。页面先通过经典 bit/qubit 对比和 Bell 实验建立直觉；6 节原创微课程均可进入，支持预测、切换对照电路、调整 shots 并查看真实 L1 概率与 counts。自由实验室面向学生自己的现象目标，提供自然语言生成和独立代码修复区；运行环境通过控件选择，只展示当前 Python 环境与本机凭据真正支持的选项。课程和智能体 QASM 均复用 L1 parser/statevector/counts 路径；服务失败时保留输入且不回退到伪造结果。实现、预算、安全边界与测试证据见 [`docs/L2_IMPLEMENTATION.md`](docs/L2_IMPLEMENTATION.md)。

日常开发可使用统一服务脚本。先复制 `.env.l2.example` 为被 Git 忽略的 `.env.l2.local` 并填写新 API Key，然后运行：

```powershell
.\l2.cmd start
.\l2.cmd status
.\l2.cmd restart
.\l2.cmd stop
```

直接双击 `l2.cmd` 等同于 `start`。底层 PowerShell 脚本只会关闭自身 PID 文件记录且进程名为 Python 的服务。

## L3 Hybrid-QASM and custom RISC-V extension

L3 is implemented through `adapter.compile_hybrid(source)`. It splits the quantum operations from one `classical { ... }` block, compiles the block into the instruction subset accepted by the supplied `riscv_emulator.py`, and maps `c[k]` to `x(10+k)`. The compiler is AST-driven and supports integer constants, `r1..r9`, `+`, `-`, `==`, `!=`, sequential assignments, and nested `if/else`. A separate source-level interpreter and fixed-seed generated corpus compare source semantics with compiled RISC-V without changing the public adapter API.

```bash
python -m unittest tests.test_l3_hybrid
python evaluator.py --level l3
```

The optional custom quantum RISC-V extension uses a documented `custom-0` encoding, a compatible executable emulator fork, and end-to-end tests. It executes the 12 L1 gates, seeded measurement collapse, `x(10+cbit)` classical write-back, and subsequent RISC-V branches; it does not alter the official `riscv_emulator.py` used for L3 scoring.

```bash
python -m unittest tests.test_l3_bonus_contract
```

See [`docs/L3_IMPLEMENTATION.md`](docs/L3_IMPLEMENTATION.md) and [`docs/L3_RISCV_EXTENSION.md`](docs/L3_RISCV_EXTENSION.md) for grammar boundaries, mapping, opcode layout, and verification evidence.
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
├── evidence/
│   ├── README.md
│   └── files/                # 可选附件
├── circuits/
│   ├── bell.qasm
│   └── ghz3.qasm
└── examples/
```

在正式 fork 中，本 `starter_kit/` 目录就是构建与评测根目录，必须保留并填写 `submission.yaml`，同时提供 `adapter.py`。非 Python 项目可以在 `adapter.py` 中通过 `subprocess` 调用自己的 CLI 或二进制。

目录名使用下划线，因此从 fork 根目录编写测试时可以按标准 Python 包导入：

```python
from starter_kit import adapter
```

## 环境

公开 evaluator 只使用 Python 标准库，无需安装依赖。推荐 Python 3.10，与官方基础镜像一致（spinqit 最高只提供 cp310 wheel）：

```bash
python3 evaluator.py --level l1 --target spinq,originq --json-out report.json
```

参赛项目使用第三方 SDK 时，必须把直接依赖写入 `requirements.txt` 并精确锁定版本，例如 `package==1.2.3`。不要提交 `package>=1.2`，正式评测不会替参赛队选择依赖版本。本仓库另外提交 `requirements-lock.txt`，记录 Python 3.10 Windows 原生 SDK 环境的完整传递依赖；用 `py -3.10 scripts/generate_requirements_lock.py --check` 审计它是否与 direct requirements 一致。Docker 继续使用跨平台的 `requirements.txt`。

也可以先验证基础容器：

```bash
docker build -t loomq-submission .
docker run --rm loomq-submission
```

## Adapter 契约

L1 必须实现：

```python
def transpile(qasm_str: str, target: str) -> str: ...
def run(qasm_str: str, target: str, shots: int) -> dict: ...
```

`transpile()` 的三个目标格式不是任意字符串，规范子集见 `target_ir_contract.md`。正式评测会由组织方解析并模拟返回的目标 IR。

L2、L3 为可选接口：

```python
def agent_chat(prompt: str) -> str: ...
def compile_hybrid(hybrid_qasm_str: str) -> tuple[list, str]: ...
```

未参赛的 Level 保持 `NotImplementedError`，并在 `submission.yaml` 中标为 `false`。Starter Kit 原样运行会失败，这是预期行为，也确保原样提交不会获得功能分。

## 公开自测

```bash
# 默认只测试 submission.yaml 中声明为 true 的 Level
python3 evaluator.py --json-out report.json

# 单独测试
python3 evaluator.py --level l1 --target spinq,originq,braket
python3 evaluator.py --level l2
python3 evaluator.py --level l3
```

退出码：全部公开测试通过为 `0`，存在失败为 `1`。`report.json` 只表示公开契约自测结果，不是正式分数。

正式评测由组织方在隔离环境运行：每个 case 使用独立进程、私有随机种子和私有期望值；提交进程不会获得理想分布文件。组织方还会分别验证目标原生 IR、真机证据、架构与交互体验。

## 最终提交

截止时间为 **2026-08-25 12:00 UTC+8**。先在 fork 根目录运行：

```bash
python3 starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>
```

当前不使用预登记队伍名单。每队指定一个 GitHub 提交账号，该账号的用户名就是 Team ID；fork 必须归该账号所有，并由同一账号创建最终提交 Issue。其他成员仍可作为协作者参与开发。预检通过后，在上游 `QAIDAO/LoomQ-2026` 的“LoomQ 最终提交” Issue Form 中填写输出的 fork 地址和 40 位 commit SHA。出现 `submission:accepted` 标签与归档哈希回执后才算提交成功。更新代码后必须新建 Issue，截止前最后一次有效提交生效。

如申报 L1 真机、L2 交互体验、工程与产品化或 Bonus，只需填写 [`evidence/README.md`](evidence/README.md)。截图、原始结果或图表可以统一放入 `evidence/files/`。证据必须随最终 commit 归档；未提交某项证据只影响对应人工分，不影响自动评分。

## L2 统一模型与环境变量

正式 L2 客观评测统一使用 DeepSeek `deepseek-v4-flash`，最终答案仍由确定性的官方测试判定，不使用 LLM 充当裁判。组委会在赛前**不提供 API 地址、API Key、代理或调用额度**。选手本地可使用自己的 DeepSeek API，也可使用其他 OpenAI-compatible 服务调试；组委会只保证正式 DeepSeek 环境下的结果。

`agent_chat(prompt: str) -> str` 接口不变。实现不得硬编码 URL、Key 或模型名，必须读取：

| 环境变量 | 含义 |
|---|---|
| `LOOMQ_LLM_BASE_URL` | OpenAI-compatible API 根地址 |
| `LOOMQ_LLM_API_KEY` | 当前运行凭证 |
| `LOOMQ_LLM_MODEL` | 当前模型；正式评测为 `deepseek-v4-flash` |
| `LOOMQ_LLM_TIMEOUT_SECONDS` | 单次请求超时 |

正式限制为每个 case 时限 120 秒；两组固定私有种子共 12 个 case。机器可读版本见 `l2_policy.json`。

`llm_client.py` 是可选的无依赖传输示例，不包含 Prompt、Agent 策略或参考答案。使用自己的 DeepSeek Key 调试时可设置：

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_OWN_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
export LOOMQ_LLM_TIMEOUT_SECONDS=120
python3 evaluator.py --level l2
```

缺少配置时应立即失败，错误信息不得包含任何 Key。正式评测时，组委会将统一注入 DeepSeek 模型服务及调用预算；评测环境不保证能够访问其他外部网络服务。若参加 L2，请把 `submission.yaml` 中的 `levels.l2` 与 `network.required_for_l2` 同时改为 `true`；`allowed_hosts` 不用于申请正式评测中的任意公网访问。

## 版本政策

合同版本为 `1.0`。开赛后，`1.x` 只允许增加向后兼容的文档、诊断信息和公开测试，不改变已有接口语义；破坏性修改必须发布新的合同版本并为旧版保留评测通道。
