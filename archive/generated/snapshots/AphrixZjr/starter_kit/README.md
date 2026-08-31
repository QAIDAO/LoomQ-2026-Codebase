# LoomQ Starter Kit v1.1.0

本工具包定义参赛提交协议，并提供公开自测。它不包含正式评分器、隐藏答案、Mock 得分路径或任何 Level 的参考解答。

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
├── generate_verification_manifest.py
├── browser_responsive_check.mjs
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
├── tests/                    # 正式归档内的完整回归与隔离检查
│   ├── test_l1_core.py
│   ├── test_l2_audit_regressions.py
│   ├── test_l3_differential.py
│   └── test_quantum_riscv_e2e.py
└── examples/
```

在正式 fork 中，本 `starter_kit/` 目录就是构建与评测根目录，必须保留并填写 `submission.yaml`，同时提供 `adapter.py`。非 Python 项目可以在 `adapter.py` 中通过 `subprocess` 调用自己的 CLI 或二进制。

全部评分相关测试也位于该目录内；复制或提取单独的 `starter_kit/` 后，
`python -m unittest discover -s tests -v` 仍可完整运行。

目录名使用下划线，因此从 fork 根目录编写测试时可以按标准 Python 包导入：

```python
from starter_kit import adapter
```

## 环境

### 一条命令构建全部环境并启动 L2

在 `starter_kit/` 目录运行：

```bash
docker compose up --build
```

该命令构建同一个 Python 3.10 镜像中的 L1、L2、L3 和量子 RISC-V Bonus
环境，并在 <http://127.0.0.1:8765> 启动 L2 用户界面。镜像同时安装
SpinQit Taurus、OriginQ pyQPanda 和 AWS Braket LocalSimulator；界面的“运行位置”
可直接选择三个 L1 本地后端。访问 `/api/health` 可查看三者的 `connected`
状态。`LOOMQ_WEB_PORT` 可修改宿主机端口；`LOOMQ_LLM_*` 会从当前环境
透传，未配置模型时不影响界面和本地量子后端。

停止环境使用 `docker compose down`。

公开 evaluator 的框架本身只使用 Python 标准库；执行本仓库的三个实际后端仍需要 `requirements.txt` 中固定的供应商 SDK。推荐直接使用 Docker，或在 Python 3.10 环境完整安装依赖（spinqit 最高只提供 cp310 wheel）：

```bash
python3 evaluator.py --level l1 --target spinq,originq,braket --json-out report.json
```

参赛项目使用第三方 SDK 时，必须把依赖写入 `requirements.txt` 并精确锁定版本，例如 `package==1.2.3`。不要提交 `package>=1.2`，正式评测不会替参赛队选择依赖版本。

也可以直接构建并启动同一个 Web 容器；Dockerfile 的默认命令与健康检查均指向
8765 端口：

```bash
docker build -t loomq-submission .
docker run --rm -p 8765:8765 loomq-submission
```

公开 evaluator 是显式的评分自测入口，不与产品启动混用。无需模型凭证的 L1/L3
示例为：

```bash
docker run --rm loomq-submission \
  python evaluator.py --level l1 --target spinq,originq,braket
docker run --rm loomq-submission python evaluator.py --level l3
```

L2 客观自测必须显式注入自己的 `LOOMQ_LLM_*` 配置，例如：

```bash
docker run --rm \
  -e LOOMQ_LLM_BASE_URL -e LOOMQ_LLM_API_KEY -e LOOMQ_LLM_MODEL \
  loomq-submission python evaluator.py --level l2
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

L3 实现位于 `loomq_l3.py`，支持题面限定的 `r1..r9`、`c[k]`、整数加减、顺序赋值和带 `else` 的嵌套分支，并输出原版 `TinyRISCVEmulator` 可执行的文本汇编。

量子自定义 RISC-V Bonus 是与 L3 执行路径隔离的最小机器码闭环。官方 `riscv_emulator.py` 在保持 `TinyRISCVEmulator` 兼容的同时，直接提供 `assemble()`、`decode()` 和 `QuantumRISCVEmulator`；旧 `quantum_riscv.py` 导入路径作为兼容层保留。编码规格见 `docs/loomq_qisa_v1.md`。它覆盖 12 门、四条量子控制指令和闭环所需的 RV32I 子集，不代表完整 RISC-V 或真实量子协处理器。验证命令（在 `starter_kit/` 内运行）：

```bash
python tests/test_quantum_riscv_e2e.py -v
```

正式归档内的完整回归与可哈希验收清单（在已安装 `requirements.txt` 的环境中）为：

```bash
python -m unittest discover -s tests -v
python generate_verification_manifest.py
```

清单生成器默认只运行确定性的本地命令，不调用真实模型或硬件，也不读取私有 Key；需要把 Docker 内的三平台命令纳入同一清单时，可按 `python generate_verification_manifest.py --help` 使用重复的 `--command` 参数。manifest 的 Git 状态是在写证据前捕获的源码快照；若证据要随 Git 提交，按帮助中的“干净源码提交→生成→证据专用提交”两阶段流程归档，避免要求 manifest 自己预言包含它的 commit SHA。

退出码：全部公开测试通过为 `0`，存在失败为 `1`。`report.json` 只表示公开契约自测结果，不是正式分数。

正式评测由组织方在隔离环境运行：每个 case 使用独立进程、私有随机种子和私有期望值；提交进程不会获得理想分布文件。组织方还会分别验证目标原生 IR、真机证据、架构与交互体验。

## 最终提交

截止时间为 **2026-08-25 12:00 UTC+8**。先在 fork 根目录运行：

```bash
python3 starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>
```

当前不使用预登记队伍名单。每队指定一个 GitHub 提交账号，该账号的用户名就是 Team ID；fork 必须归该账号所有，并由同一账号创建最终提交 Issue。其他成员仍可作为协作者参与开发。预检通过后，在上游 `QAIDAO/LoomQ-2026` 的“LoomQ 最终提交” Issue Form 中填写输出的 fork 地址和 40 位 commit SHA。出现 `submission:accepted` 标签与归档哈希回执后才算提交成功。更新代码后必须新建 Issue，截止前最后一次有效提交生效。

如申报 L1 真机、L2 交互体验、工程与产品化或 Bonus，只需填写 [`evidence/README.md`](evidence/README.md)。截图、原始结果或图表可以统一放入 `evidence/files/`。证据必须随最终 commit 归档；未提交某项证据只影响对应人工分，不影响自动评分。

人工验收入口见 [`evidence/README.md`](evidence/README.md)，当前代码的专用架构、产品化、交互与 Bonus 说明位于 [`docs/acceptance/`](docs/acceptance/)。开发计划和设计材料已归入 `docs/development/`，不作为验收证据。Issue 中的 40 位 SHA 必须在所有材料提交并 push 后重新取得。

## L2 统一模型与环境变量

### L2 引导式实验界面（主观体验与新手 Bonus）

正式评测会注入 `LOOMQ_LLM_*`，Web 的 Bell 黄金路径因此以 Agent 对话为唯一推进入口。没有模型凭证时仍可启动并完成流程，但只对界面生成的当前阶段精确指令使用明确标注的本地预置回退回复：

```bash
python web/server.py
```

打开 <http://127.0.0.1:8765>。首次运行、三项现场任务、键盘操作和验证命令见 [`web/README.md`](web/README.md)。该界面复用确定性 parser、参考模拟器和后端能力表，但不改变下述 `agent_chat(prompt: str) -> str` 客观评分契约。

正式 L2 客观评测统一使用 DeepSeek `deepseek-v4-flash`，最终答案仍由确定性的官方测试判定，不使用 LLM 充当裁判。组委会在赛前**不提供 API 地址、API Key、代理或调用额度**。选手本地可使用自己的 DeepSeek API，也可使用其他 OpenAI-compatible 服务调试；组委会只保证正式 DeepSeek 环境下的结果。

`agent_chat(prompt: str) -> str` 接口不变。实现不得硬编码 URL、Key 或模型名，必须读取：

| 环境变量 | 含义 |
|---|---|
| `LOOMQ_LLM_BASE_URL` | OpenAI-compatible API 根地址 |
| `LOOMQ_LLM_API_KEY` | 当前运行凭证 |
| `LOOMQ_LLM_MODEL` | 当前模型；正式评测为 `deepseek-v4-flash` |
| `LOOMQ_LLM_TIMEOUT_SECONDS` | 单次请求超时 |
| `LOOMQ_LLM_MAX_OUTPUT_TOKENS` | 可选单次输出上限；默认 900，硬上限 1000 |

### L2 规则基准

本提交采用同一最终源码快照中的 `problem_statement.md` 与机器可读 `l2_policy.json`；后者 schema 为 `1.0`，固定正式模型、每 case 120 秒、两组私有种子共 12 个 case，并公开下述兼容性调用与 Token 上限。提交或验收时应引用最终 40 位源码 SHA，而不是沿用早期规则提交的哈希。

随项目流传的旧 PDF 仍包含 96 小时赛制、最多 3 次调用、累计 8000 输入 Token 和 2000 输出 Token，与当前题面公开字段存在历史差异；若组委会另行澄清，以其正式通知为准。为兼容两套口径，当前实现和 `l2_policy.json` 都采用更严格的共同边界：每 case 最多 3 次 transport attempt（其中最多一次瞬态重试和一次定向 repair）、累计输入 8000、累计输出 2000、单次请求默认 900 且硬上限 1000。每次请求的 `max_tokens` 还会收缩为“配置上限与累计剩余额度的较小值”，额度为零时在 transport 前拒绝。provider 返回 usage 时按 `prompt_tokens`/`completion_tokens` 记账；没有 usage 时，输入以 UTF-8 字节数作保守上界，输出按该次请求的 `max_tokens` 全额预留。瞬态失败不伪造成功输出消耗，但仍占 attempt 与输入预算。

`llm_client.py` 是可选的无依赖传输示例，不包含 Prompt、Agent 策略或参考答案。使用自己的 DeepSeek Key 调试时可设置：

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_OWN_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
export LOOMQ_LLM_TIMEOUT_SECONDS=120
python3 evaluator.py --level l2
```

本提交的客观分实现位于 `loomq_l2.py`，覆盖 QASM 生成、QASM 纠错和后端选择：模型负责自然语言理解，本地代码负责能力表求解、QASM 静态验证、可独立恢复的 Bell/GHZ 目标验证、最多一次定向修复及最终唯一输出。已被本地 oracle 判定为 Bell/GHZ 语义错误的候选不会进入 fallback；若已有一次有效模型响应而定向修复失败，则从同一 `TargetSpec` 生成 canonical 电路并再次通过同一 oracle 后返回。后端事实只读取 `backend_capabilities.json`；请求之间不共享 prompt、候选、预算或修复状态。

无真实凭证也可运行 L2 契约、假服务端到端和资源边界测试：

```bash
python -m unittest tests.test_l2_agent tests.test_l2_contract \
  tests.test_l2_web tests.test_l2_audit_regressions -v
```

真实模型自测仍使用上面的环境变量与 `python evaluator.py --level l2`。未配置真实凭证时不应伪造该项结果。

缺少配置时应立即失败，错误信息不得包含任何 Key。正式评测时，组委会将统一注入 DeepSeek 模型服务及调用预算；评测环境不保证能够访问其他外部网络服务。若参加 L2，请把 `submission.yaml` 中的 `levels.l2` 与 `network.required_for_l2` 同时改为 `true`；`allowed_hosts` 不用于申请正式评测中的任意公网访问。

## 版本政策

合同版本为 `1.0`。开赛后，`1.x` 只允许增加向后兼容的文档、诊断信息和公开测试，不改变已有接口语义；破坏性修改必须发布新的合同版本并为旧版保留评测通道。
