# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

### 已验证：SpinQ Cloud gemini_vp

这条记录来自一次真实的 `/api/run` 云真机任务，不是平台列表查询，也不是本地模拟器结果。提交时可将本条作为一个 SpinQ 真机平台的申报证据：

```text
平台名称：量旋云 2Qubit 核磁量子计算机（SpinQ Cloud）
统一 backend ID：spinq_cloud_qpu
平台 code：gemini_vp
平台 job ID：61489
平台任务编号：G-260825-0008
运行时间：2026-08-24T22:12:04.376+00:00
shots：1000
实际执行的 QASM：evidence/files/spinq-gemini-vp-qasm.qasm
统一入口提交的 QASM（含测量）：evidence/files/spinq-gemini-vp-input.qasm
平台返回的原始结果：evidence/files/spinq-gemini-vp-result.json
归一化结果：{"1": 1000}
任务页截图：[`evidence/files/spinq-gemini-vp-task.png`](files/spinq-gemini-vp-task.png)；job ID 与平台原始结果为主要证据
```

本次电路是 `X|0⟩`，因此真机返回全为 `1` 与电路预期一致。SpinQ 官方提交器不接受 `measure` 行，`spinq-gemini-vp-qasm.qasm` 是适配层移除测量语句后实际交给云端的 QASM；统一入口版本保留在 `spinq-gemini-vp-input.qasm` 便于复现。此次目标是 `spinq_cloud_qpu`，未使用本地回退。

```text
平台名称：[填写]
平台 job ID：[填写]
运行时间：[填写，带时区]
shots：[填写]
实际执行的 QASM：[填写仓库内路径]
平台返回的原始结果：[填写仓库内路径]
任务页截图：[选填，填写仓库内路径]
```

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

### 三个平台统一接入架构

这部分对应赛题中的“L1 真机接入证据”和“工程与产品复核”架构要求。三个平台不各写一套产品提交入口：L2 只负责推荐官方能力表中的规范 `backend_id`，实际运行统一经过 Product Service 和公开的 `adapter.run()`。

```text
自然语言需求
  -> L2 agent_chat()
  -> backend_capabilities.json 中的规范 backend_id
  -> Product Service /api/run
  -> adapter.run(qasm, backend_id, shots)
       |-- 本地 ID -> l1.run_l1() -> SpinQit / pyQPanda / Braket LocalSimulator
       |-- spinq_cloud_qpu -> hardware.api -> hardware/spinq.py -> SpinQ Cloud
       |-- originq_wukong  -> hardware.api -> hardware/originq.py -> 悟空真机
       `-- braket_cloud    -> hardware.api -> hardware/braket.py -> AWS Braket
  -> provider 结果统一为 backend/job_id/shots/counts/bit_order/timestamp/meta
  -> 页面展示与 evidence/files/ 留证
```

| 平台 | 运行时规范 ID | 在本项目中的接法 | 必要配置 | 未配置时的本地回退 |
|---|---|---|---|---|
| 量旋云真机 | `spinq_cloud_qpu` | `hardware/spinq.py` 调官方 `spinqit_mcp_tools.qasm_submit()`，再按 task ID 查询结果 | `requirements-hardware.txt`、`PRIVATEKEYPATH`、`SPINQCLOUDUSERNAME`、真实 `LOOMQ_SPINQ_PLATFORM` | `spinq_taurus_simulator` |
| 本源悟空真机 | `originq_wukong` | `hardware/originq.py` 用 `pyqpanda` 构造 QProg，优先异步提交并轮询 task | `requirements.txt`、`LOOMQ_ORIGINQ_API_TOKEN`，可选 `LOOMQ_ORIGINQ_CHIP` | `originq_local_simulator` |
| AWS Braket 云端/QPU | `braket_cloud` | `hardware/braket.py` 将 QASM 转为 Braket OpenQASM 3，用 `AwsDevice.run()` 提交并读取 task ARN | `requirements.txt`、`LOOMQ_BRAKET_DEVICE_ARN`、`LOOMQ_BRAKET_S3_URI`，以及 AWS 凭证 | `braket_local_simulator` |

实际接入步骤：

1. 在运行 Product Service 的同一个 Python 3.10 环境中安装 `starter_kit/requirements.txt`；要接 SpinQ 云端，再安装 `starter_kit/requirements-hardware.txt`。
2. 只在进程环境中配置目标平台凭证，不把 Token、私钥、AWS 凭证或 Cookie 写入仓库。
3. 重启 Product Service，在页面生成电路；L2 可以推荐 `spinq_cloud_qpu`、`originq_wukong` 或 `braket_cloud`，用户确认后点击同一个 `Run Experiment`。
4. 若远端 SDK、凭证或设备配置不完整，默认 `LOOMQ_REMOTE_FALLBACK=local`：服务不会尝试提交真机，而是选择已就绪的本地模拟器，并在结果中写入 `fallback: true`。这种结果只能证明本地运行，不能作为 L1 真机分证据。
5. 申报真机分时，确认结果中的 `fallback` 不存在，保存实际 QASM、完整返回 JSON 和可追溯的 `job_id`；建议命名为 `evidence/files/<platform>-circuit.qasm`、`<platform>-result.json`。若要强制选中的远端未配置就报错，设置 `LOOMQ_REMOTE_FALLBACK=error`。

三个 provider 适配器只负责平台认证、提交/轮询、结果位序归一化和统一 Schema；L2、L1 parser/IR、前端结果展示和正式 `adapter.py` 契约不为某一家真机复制分支。详细环境变量和平台注意事项见 [`../docs/HARDWARE_QUICKSTART.md`](../docs/HARDWARE_QUICKSTART.md)。

## L2 交互体验

```text
启动界面或 CLI 的命令：Windows 双击 starter_kit/start_playground.bat；Linux 使用下方 Docker 命令
测试入口或页面地址：http://127.0.0.1:4173/
赛事 L2 三个基本任务（首页已经提供快捷入口）：
1. 意图生成：生成一个 3 比特 GHZ 态，并对三个量子比特全部测量。
2. 代码修复：修复错误 OpenQASM，使目标电路通过 Fidelity 验证。
3. 智能选后端：为 15 比特电路选择零排队等待的官方 `backend_id`，并说明理由。
截图或演示视频：可补充到 `evidence/files/`；真机任务页截图见 [`spinq-gemini-vp-task.png`](files/spinq-gemini-vp-task.png)

L2 真实模型回归记录：[`evidence/files/l2-12case-regression.md`](files/l2-12case-regression.md)。本地 12-case 回归 12/12 通过；这不是组委会私有种子正式成绩，正式评测仍由评委注入模型环境并运行隐藏 case。
```

现场体验流程：

1. 双击 `starter_kit/start_playground.bat`。启动器创建或复用 `starter_kit/.venv`，安装依赖并检查 `adapter`、`spinqit`、`pyqpanda`、`braket`。
2. 浏览器打开 `http://127.0.0.1:4173/`。用户在右上角测试并应用自己的 OpenAI-compatible API。API Key 保存在 Product Service 内存中的当前浏览器 session。
3. 用户在统一输入框中输入自然语言或选择示例，点击 `发送`。前端先识别赛事任务意图，再识别普通问答：GHZ 生成和 QASM 修复进入 `/api/generate`；后端推荐也进入 `/api/generate`，即使提示词带问号；概念解释和结果追问才进入 `/api/ask`。生成流程由 L2 返回 QASM 或后端推荐，QASM 先经过 L1 parser/IR 校验。
4. 页面显示 Circuit、QASM 和步骤解释。用户查看推荐理由，并可切换 `backend_capabilities.json` 中的本地模拟器；配置远端环境后，同一选择器也会显示三个远端规范 ID。
5. 点击 `Run Experiment` 后，Product Service 将选中的规范 `backend_id` 交给 `adapter.run(qasm, backend_id, shots)`；本地后端或已配置的云端/真机均沿同一条链路运行，展示 backend、job ID、shots、耗时、counts、百分比图和 Raw counts。远端未配置时按上面的回退策略执行并明确标记。生成新实验时清除旧运行结果。
6. 服务、API、Model、SDK 或运行失败时，页面显示对应错误信息。

详细启动说明见 [`../docs/PLAYGROUND_QUICKSTART.md`](../docs/PLAYGROUND_QUICKSTART.md)。产品层与比赛核心的边界见 [`../docs/PLAYGROUND_INTEGRATION.md`](../docs/PLAYGROUND_INTEGRATION.md)。

### 评委启动方式：CLI、Docker、Windows

三种入口启动的是同一个 Product Service，默认地址都是 `http://127.0.0.1:4173/`。没有远端凭证时，页面仍可使用本地模拟器；评委只需在页面右上角接入自己的 OpenAI-compatible API，或按正式评测环境注入 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL`。不要把 Key、Token、私钥或 AWS 凭证写入仓库。

#### A. CLI / Python 手动启动

从仓库根目录执行。Python 3.10 推荐使用仓库内的隔离环境：

```powershell
python -m venv starter_kit\.venv
.\starter_kit\.venv\Scripts\python.exe -m pip install -r .\starter_kit\requirements.txt
.\starter_kit\.venv\Scripts\python.exe .\starter_kit\product_service.py --host 127.0.0.1 --port 4173
```

Linux/macOS 对应命令：

```bash
python3 -m venv starter_kit/.venv
starter_kit/.venv/bin/python -m pip install -r starter_kit/requirements.txt
starter_kit/.venv/bin/python starter_kit/product_service.py --host 127.0.0.1 --port 4173
```

终端保持运行，浏览器打开上面的地址；按 `Ctrl+C` 停止服务。

#### B. Docker / Compose 启动（干净环境推荐）

从仓库根目录执行一条命令即可完成构建、安装依赖和启动：

```powershell
docker compose -f starter_kit/compose.yaml up --build
```

也可以使用纯 Docker CLI：

```powershell
docker build -f starter_kit/Dockerfile.playground -t loomq-playground:local starter_kit
docker run --rm --name loomq-playground -p 4173:4173 loomq-playground:local
```

访问 `http://127.0.0.1:4173/`；Compose 用 `Ctrl+C` 停止后可执行 `docker compose -f starter_kit/compose.yaml down` 清理容器。纯 Docker 用 `Ctrl+C` 停止。两种 Docker 方式都不要求远端真机凭证，默认可以运行三个本地模拟器。

#### C. Windows 一键启动

在资源管理器中双击：

```text
starter_kit\start_playground.bat
```

启动器会自动定位 Python 3.10，创建或复用 `starter_kit\.venv`，安装 `requirements.txt`，通过 `adapter`、`spinqit`、`pyqpanda`、`braket` 运行预检后再启动服务，并自动打开页面。首次初始化会请求确认；找不到 Python 3.10 或依赖安装失败时会明确停止，不会显示虚假的 Ready。关闭启动器打开的 Product Service 窗口即可停止。

干净环境的一条命令也可以直接使用上面的 Compose 命令；三种方式都指向同一个页面和同一套 `/api/generate`、`/api/ask`、`/api/run` 接口。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

### 评委一键复现与架构总览

评委从仓库根目录执行下面一条命令即可完成产品环境的 setup + run：

```powershell
docker compose -f starter_kit/compose.yaml up --build
```

系统边界清晰分成四层：

```text
零基础用户 / 评委
  -> Playground Web UI（自然语言、QASM、Circuit、counts、解释）
  -> Product Service（/api/generate、/api/ask、/api/run、session 配置）
  -> adapter.py（唯一公开入口：agent_chat / run）
       |-- L2 agent：模型协议、QASM 校验、后端能力工具、确定性重试
       |-- L1 parser/IR：统一 OpenQASM 2.0、转译和本地模拟器
       `-- hardware/：SpinQ、OriginQ、Braket 的提交/轮询/结果归一化
  -> 统一结果：backend + job_id + shots + counts + bit_order + timestamp + meta
```

L2 推荐只输出 `backend_capabilities.json` 中的规范 `backend_id`；L2、L1 和远端 provider 不复制独立提交入口。用户最终确认后，Product Service 仍把同一个 `backend_id` 交给 `adapter.run()`。远端未配置时只回退到已就绪的本地模拟器并标记 `fallback: true`，真机证据只接受没有回退标记且有可追溯 `job_id` 的结果。

```text
干净环境中的构建和启动命令：`docker compose -f starter_kit/compose.yaml up --build`；Windows 也可双击 `starter_kit/start_playground.bat`；完整说明见 [`starter_kit/docs/PLAYGROUND_QUICKSTART.md`](../docs/PLAYGROUND_QUICKSTART.md)
架构说明：见 [`starter_kit/docs/PLAYGROUND_INTEGRATION.md`](../docs/PLAYGROUND_INTEGRATION.md) 和本节“三个平台统一接入架构”；真机配置见 [`starter_kit/docs/HARDWARE_QUICKSTART.md`](../docs/HARDWARE_QUICKSTART.md)
目标用户和使用场景：首次接触量子计算、QASM 或量子 SDK 的学习者与创作者
完整使用流程：统一自然语言输入 → 前端意图分流 → `/api/ask` 量子导师回答，或 `/api/generate` → L2 生成/修复 QASM 或推荐后端 → L1 parser/IR 校验 → Circuit/QASM/解释 → 用户选择规范 `backend_id` 与 shots → `adapter.run()` → 本地模拟器或已配置远程 provider → 统一 counts → Measurement 可视化
```

主要模块与边界：

- `starter_kit/frontend/`：HTML/CSS/JavaScript 界面。`api.js` 负责请求，`circuit.js` 绘制电路，`app.js` 管理页面状态和交互。
- `starter_kit/product_service.py`：提供静态页面、`/api/generate`、`/api/ask`、`/api/run` 和 LLM session 配置接口。
- `starter_kit/adapter.py`：比赛公开入口。Playground 调用 `agent_chat()` 和 `run()`。
- `starter_kit/l1/`：OpenQASM parser、统一 IR、三平台 emitter 与 SpinQ/OriginQ/Braket 本地执行路径。
- `starter_kit/hardware/`：三个远端 provider 的薄适配层，只由 `adapter.run()` 按规范远端 ID 调用，不是第二个提交器。
- `starter_kit/l2/`：模型调用、QASM 生成/修复、后端能力工具、确定性校验与重试。
- `starter_kit/l3/` 与 `starter_kit/riscv_emulator.py`：Hybrid-QASM 解析、经典控制流编译和轻量 RISC-V 执行验证。

必答题：我们服务的是第一次接触量子计算、不会写 QASM、也没有量子硬件账号的学习者。用户可以从自然语言和“我完全不懂量子计算，带我体验一次”开始，先在本地模拟器得到可解释 counts，再按需切换云端真机；因此学习门槛不再是先安装 SDK、理解寄存器语法或申请硬件账号。

可复现性与安全设计：

- Windows 启动器优先复用 `starter_kit/.venv`；环境缺失时，经用户确认后创建该环境并安装 `starter_kit/requirements.txt`。
- Product Service 启动前检查本地模拟器运行依赖；远端 provider 按需检查 SDK、凭证和设备配置，界面显示远端是否已配置。
- LLM 配置优先级为：当前浏览器 session、服务端完整 `LOOMQ_LLM_*`、未配置。session 配置使用 `ContextVar`，请求结束后恢复。
- API Key 不由 GET 接口返回，也不写入前端源码、Git、日志或 `localStorage`。Product Service 重启后 session Key 失效。
- `starter_kit/Dockerfile.playground` 与比赛 `starter_kit/Dockerfile` 相互独立，产品运行入口不会替换 evaluator 容器。
- Playground 的 Run 默认开放三个本地模拟器；配置远程 SDK、凭证和设备后，会在同一列表中开放 SpinQ Cloud、OriginQ 悟空或 AWS Braket 云端。远端未就绪时默认只在本地模拟器上运行，并通过结果字段标记回退。

公开验证入口：

```powershell
.\.venv\Scripts\python.exe starter_kit\evaluator.py --level l1 --target spinq,originq,braket
.\.venv\Scripts\python.exe starter_kit\evaluator.py --level l2
.\.venv\Scripts\python.exe starter_kit\evaluator.py --level l3
```

L2 evaluator 需要由运行者通过环境变量提供完整的 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL`。公开 evaluator 通过只代表公开契约自测通过，不等于正式隐藏评测分数。

本地 12-case 回归（使用自己的模型服务时）：

```powershell
$env:PYTHONPATH = "starter_kit"
python starter_kit/tests/check_l2_real_regression.py
```

正式评测不要求选手提交 Base URL 或 Key；评委环境会按 `submission.yaml` 注入 `LOOMQ_LLM_*`，并运行组织方持有的私有 case。

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：[填写文档路径]
模拟器扩展实现：[填写代码路径]
端到端测试命令：[填写命令或文档路径]
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/docs/PLAYGROUND_QUICKSTART.md；首页“我完全不懂量子计算，带我体验一次”按钮
量子概念解释：Gate Hover/Click Card、步骤时间线、状态顺序和测量位序说明
结果可视化：真实 counts 柱状图、bitstring/count/百分比 hover、Raw counts、结果与关键 gate 回看联动
错误恢复或无障碍引导：未接入或连接失败时自动打开 API 接入弹窗；Product Service、API、Model、SDK 和运行错误分别提示；弹层支持 Escape 关闭
```

界面位置：

- 首页提供量子硬币、量子纠缠、相位干涉示例，以及 `我完全不懂量子计算，带我体验一次` 按钮。
- Circuit Preview 直接标出每个 qubit 从 `|0⟩` 开始，并注明量子态顺序 `|q0 q1 ...⟩`。
- Hover 量子门时显示作用对象和简短解释。点击量子门后优先显示矩阵或态变换公式，再显示规范的门定义、前后态矢和 Bloch 球局部态轨迹。
- 步骤时间线按门的实际位置解释作用。小规模电路的 state trace 由产品层计算；电路过大或无法可靠推导时只显示局部规则。
- Measurement 根据测量前 statevector 显示 0/1 概率、classical bit 写入位置和 counts 位序 `c[n-1]...c0`。
- 结果区显示观测结果、原因和关键公式。`回看 H/CX` 会定位并高亮对应量子门。
- 结果不超过 16 种时显示 bitstring；超过 16 种时显示 `1 的数量分布`，Raw counts 保留完整数据。

建议审批后补充以下截图，文件实际加入仓库后再把“待补”替换为有效链接：

```text
evidence/files/01-home-and-api.png
evidence/files/02-circuit-and-gate-explanation.png
evidence/files/03-backend-selection.png
evidence/files/04-local-run-results.png
evidence/files/05-measurement-explanation.png
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
