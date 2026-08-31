# 织络（LoomQ）

织络是 LoomQ 2026 赛题的参赛实现，遵循合同版本 `1.0` 和 Starter Kit `1.1.0`。正式评测根目录为 `starter_kit/`，固定入口为 [`adapter.py`](adapter.py)。项目实现 L1、L2、L3，并提供与基础 L3 隔离的量子 RISC-V Bonus。

## 项目定位

织络面向没有量子物理或 QASM 编程经验、但希望理解和尝试量子计算任务的跨学科创作者。用户可以用自然语言生成或修复 OpenQASM 2.0 线路、询问量子概念，或根据比特数、费用和排队条件获得后端建议。

线上 LLM 负责理解自然语言、生成和修复代码及解释概念。本地确定性模块负责解析 QASM、验证线路、转译目标 IR、推导理想测量分布及编译 Hybrid-QASM。网页当前不向厂商云平台或真实 QPU 提交任务；真机结果只通过赛事规定的 L1 evidence 单独申报。

## 目标用户与使用场景

本项目回答的必答题是：让没有量子计算专业背景、不会编写 QASM、也不熟悉厂商 SDK 的跨界创作者，能够从一句自然语言目标开始，获得可以检查和继续使用的量子线路。

典型使用场景包括：

- 将“生成一个 3 比特 GHZ 态并测量全部比特”转换为完整 OpenQASM 2.0；
- 在保留 Bell、GHZ 等目标语义的前提下修复不完整或错误的 QASM；
- 按比特数、模拟器或 QPU、费用、账号和排队约束筛选后端；
- 查看线路图、理想结果纹样、概率和原始 counts，理解线路在理想条件下的行为；
- 将 Hybrid-QASM 的量子部分和经典控制部分分别编译为量子操作列表与官方 RISC-V 子集。

## 30 秒启动

要求 Python 3.10。L1、L3、本地服务和前端不依赖第三方 Python 包。L2 需要一个 OpenAI-compatible 模型服务；正式评测时由组委会注入配置。

从 fork 根目录运行：

```bash
python3 starter_kit/run_local.py
```

Windows PowerShell 可以运行：

```powershell
.venv\Scripts\python.exe starter_kit\run_local.py
```

启动器只在缺少配置时询问以下值，API Key 使用隐藏输入：

| 环境变量 | 用途 |
|---|---|
| `LOOMQ_LLM_BASE_URL` | OpenAI-compatible API 根地址 |
| `LOOMQ_LLM_API_KEY` | 当前运行凭证 |
| `LOOMQ_LLM_MODEL` | 模型名称；正式评测为 `deepseek-v4-flash` |
| `LOOMQ_LLM_TIMEOUT_SECONDS` | 可选的请求超时，默认 120 秒 |

终端显示启动地址后，打开 `http://127.0.0.1:8765/`。端口可通过 `--port` 修改。API Key 只存在于当前进程环境，不写入代码、浏览器存储、镜像层或日志。

若当前目录已经是正式评测根目录 `starter_kit/`，对应命令为：

```bash
python3 run_local.py
```

## 用户入口与使用流程

网页只提供一个自然语言输入框，不要求用户先选择“生成、修复或选后端”。处理流程如下：

1. 用户输入目标、问题或待修复代码。
2. Agent 结合当前输入和最近两轮上下文识别任务。
3. L2 通过赛事规定的环境变量调用线上模型服务。
4. 线路回答由本地解析器和理想状态向量模拟器验证；失败时将验证原因交给模型重试一次。
5. 后端选择由官方 [`backend_capabilities.json`](backend_capabilities.json) 数据确定性筛选，避免模型虚构平台能力。
6. `/api/chat` 返回版本化结构，前端分别展示中文回答、QASM、线路、理想结果纹样和诊断信息。

生成、修复、后端选择和概念解释共用同一入口。会话仅保存在当前浏览器内存中；刷新页面或点击“清空上下文”即删除。

## 前端设计说明

界面名称为“织络”。视觉系统的灵感来源于下述三个方面：

1. 编织和编程都通过有序规则把基础单元组织为可检查的结构，适合作为线路、操作和结果之间关系的视觉表达；
2. `LoomQ` 和主办方之一“织码女巫”的名称，为采用编织主题带来了一定启发；
3. 作者平时进行钩织创作，“织女”也是个人身份表达的一部分。

线路使用经纬线、梭子和线结呈现；理想概率分布转换为结果纹样。模型响应等待态使用编织动画反馈处理状态。界面同时保留 QASM、概率和原始 counts，视觉表达不替代精确数据。预览内容明确标为示意，实际结果明确标明来自本地理想推导，不表示云端或真机运行。具体视觉方案、图像素材与前端呈现由生成式 AI 辅助创作，并由作者确定方向、筛选、调整和测试。

## 系统架构

```text
自然语言
   │
   ├─ L2：OpenAI-compatible LLM ──→ 回答 / OpenQASM 2.0
   │                                      │
   │                               本地解析、验证、重试
   │                                      │
   │                              结构化 AgentResponse
   │                                      │
   └──────────────────────────────→ 本地 Web 界面

OpenQASM 2.0
   │
   └─ 单一解析器 ─→ 统一 Circuit 模型 ─┬→ SpinQ OpenQASM 2.0
                                       ├→ OriginIR
                                       └→ Braket OpenQASM 3

Hybrid-QASM ─→ 基础 L3 ─→ 量子操作列表 + 官方 RISC-V 子集
             └→ Bonus ─→ 自定义量子指令 + 32 位机器码 + 扩展模拟器
```

| 模块 | 职责 |
|---|---|
| [`loomq_core/qasm2.py`](loomq_core/qasm2.py) | 解析赛事 OpenQASM 2.0 子集 |
| [`loomq_core/model.py`](loomq_core/model.py) | 定义三个目标共享的规范线路模型 |
| [`loomq_core/renderers.py`](loomq_core/renderers.py) | 将统一模型渲染为三种目标 IR |
| [`loomq_core/simulator.py`](loomq_core/simulator.py) | 确定性状态向量计算和理想 counts 换算 |
| [`loomq_agent/service.py`](loomq_agent/service.py) | L2 提示词、模型调用、验证和一次纠错重试 |
| [`loomq_agent/backend_selector.py`](loomq_agent/backend_selector.py) | 依据官方能力表确定性筛选后端 |
| [`loomq_app/server.py`](loomq_app/server.py) | 本地 HTTP 服务、结构化响应和错误恢复信息 |
| [`loomq_app/web/`](loomq_app/web/) | 统一自然语言入口、上下文和可视化 |
| [`loomq_hybrid/`](loomq_hybrid/) | Hybrid-QASM 解析及基础 L3 编译 |
| [`loomq_bonus/`](loomq_bonus/) | 与基础 L3 隔离的量子 RISC-V 扩展 |

L1 不是三套独立的输入分支。所有输入只解析一次并进入同一个 `Circuit` 模型，目标差异仅存在于末端 renderer。随机差分测试会为 72 个线路同时验证三种目标的回读结构和模拟结果。

## Level 实现

### L1：通用中间层

`adapter.transpile(qasm_str, target)` 支持 `spinq`、`originq`、`braket`。解析器覆盖赛事规定的 12 个门、多个寄存器、参数表达式、逐位和整寄存器测量。目标输出符合 [`target_ir_contract.md`](target_ir_contract.md)。

`adapter.run(qasm_str, target, shots)` 使用内置理想状态向量模拟器返回统一 Schema。返回的 backend 名称包含 `local-simulator`，不会被表述为厂商真机结果。

### L2：说人话的智能体

`adapter.agent_chat(prompt)` 至少完成一次有效模型调用，并从 `LOOMQ_LLM_*` 读取全部服务配置。主要能力包括：

- 自然语言生成完整 OpenQASM 2.0；
- 按用户声明的目标修复语法和语义；
- 根据官方能力表选择后端；
- 解释量子概念和回答一般问题；
- 对生成线路进行本地验证，并在失败时自动纠正一次；
- 在网页中保留最近两轮上下文；
- 区分配置、鉴权、限流、网络、超时和线路验证错误，并给出恢复步骤。

网页 `/api/chat` 的结构化响应不改变赛事要求的 `agent_chat(prompt) -> str` 接口。正式客观评分仍直接调用 `adapter.agent_chat`。

### L3：Hybrid-QASM × RISC-V

`adapter.compile_hybrid(source)` 解析经典块的赋值、算术、比较、顺序语句和 `if/else`，输出量子操作列表及官方 `li`、`add`、`sub`、`addi`、`beq`、`bne`、`j` 子集。基础 L3 不导入 Bonus 包。

## 量子 RISC-V Bonus

Bonus 使用独立入口 `loomq_bonus.compile_hybrid_bonus()`，不会改变 `adapter.compile_hybrid()` 的返回语义。实现包括：

- 自定义 opcode、字段、角度和拒绝规则：[`BONUS_RISCV_ISA.md`](BONUS_RISCV_ISA.md)；
- 指令定义：[`loomq_bonus/isa.py`](loomq_bonus/isa.py)；
- 编码器和解码器：[`loomq_bonus/encoder.py`](loomq_bonus/encoder.py)、[`loomq_bonus/decoder.py`](loomq_bonus/decoder.py)；
- 扩展模拟器：[`loomq_bonus/emulator.py`](loomq_bonus/emulator.py)，继承官方 `TinyRISCVEmulator`；
- 状态向量执行：[`loomq_bonus/statevector.py`](loomq_bonus/statevector.py)；
- Hybrid-QASM Bonus 编译入口：[`loomq_bonus/compiler.py`](loomq_bonus/compiler.py)；
- 端到端测试：[`tests/test_bonus_riscv.py`](tests/test_bonus_riscv.py)。

从 fork 根目录运行：

```bash
python3 -m unittest starter_kit.tests.test_bonus_riscv -v
```

## 构建与验证

本地完整测试：

```bash
python3 -m unittest discover -s starter_kit/tests -t . -v
```

公开契约测试：

```bash
python3 starter_kit/evaluator.py --level l1 --target spinq,originq,braket
python3 starter_kit/evaluator.py --level l3
```

L2 需要先设置 `LOOMQ_LLM_*`：

```bash
python3 starter_kit/evaluator.py --level l2
```

Docker 构建和测试：

```bash
docker build -t loomq-submission:local starter_kit
docker run --rm loomq-submission:local python -m unittest discover -s tests -t . -v
docker run --rm loomq-submission:local python evaluator.py --level l1 --target spinq,originq,braket
docker run --rm loomq-submission:local python evaluator.py --level l3
```

Docker 内真实 L2 测试使用隐藏凭证的启动器：

```bash
python3 starter_kit/run_docker_l2.py --image loomq-submission:local
```

公开 evaluator 的输出只表示公开契约自测结果，不是正式分数。正式评测还包括隐藏线路、私有 prompt 变体、随机 L3 用例和人工复核。

## 安全与隐私

- API 地址、Key 和模型名不硬编码，均从环境变量读取；
- `run_local.py` 和 `run_docker_l2.py` 使用隐藏输入读取 Key；
- Key 不进入 URL、Docker build argument、代码、浏览器存储或测试报告；
- L1 和 L3 不需要网络，L2 只需要赛事注入的模型服务；
- 浏览器上下文只保存在页面内存中，刷新或清空后删除；
- 错误信息不回显凭证。

## 已知限制

- Web 界面不直接提交厂商云任务或真实 QPU job；
- 结果纹样和 counts 来自本地理想状态向量推导，不表示含噪硬件结果；
- 前端上下文最多保留最近两轮，刷新页面后不会恢复；
- 后端建议以赛事提供的静态能力表为准，不查询厂商实时队列或价格；
- 厂商 SDK 不属于核心依赖，正式评测路径只依赖 Python 标准库；
- 公开测试通过不代表隐藏评测或人工评分结果。

## 人工评分证据

L1 两个平台的真机证据、L2 交互体验、工程与产品化、量子 RISC-V Bonus 及新手引导与视觉叙事的申报入口为 [`evidence/README.md`](evidence/README.md)。

## 最终提交

在 fork 根目录运行：

```bash
python3 starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>
```

预检要求工作区干净、HEAD 已推送且 fork 所有者与 Team ID 一致。之后在上游仓库创建新的“LoomQ 最终提交” Issue，填写完整 40 位 commit SHA。只有 Issue 获得 `submission:accepted` 标签并出现归档回执，才构成有效提交；更新后必须重新创建 Issue。
