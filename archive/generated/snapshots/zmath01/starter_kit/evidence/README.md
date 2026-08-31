# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

状态：
- 量旋（SpinQ）真机证据（bell × 5 + ghz3 × 1）；
- 本源（OriginQ）真机通过控制台跑通 bell (00+11≈97%)；ghz3 (000+111≈85%)；

一键运行：`.venv310/bin/python run_real.py all --circuit circuits/bell.qasm --shots 4096`（量旋/本源/AWS Braket 三平台：注入 SPINQ_CLOUD_USERNAME + SPINQ_CLOUD_KEYFILE / ORIGINQ_API_TOKEN / AWS 凭据即可）

操作手册：`starter_kit/evidence/real_machine_runbook.md`（注册、取密钥、提交、溯源、自查清单）

证据位置：`starer_kit/evidence/files/L1-real-machine`

## L2 交互体验

用于交互体验评测的 3 个用户任务：截图：`starter_kit/evidence/files/L2-agent`

Web 界面

1. 用户输入"帮我做一个两个比特永远同面的硬币"或者"帮我生成一个 3 比特的最大纠缠态（GHZ 态），并进行全测量"，观察助手生成电路，点击"验证"加载到"实验台"运行，并用人话解释纠缠直方图。

2. 用户粘贴一段报错的 QASM（门名大写、未声明寄存器），让助手修复并验证修复后电路可以直接运行。

3. 用户问"我需要运行一个 15 比特电路，且零排队等待、不想花钱，选哪个平台？"，检查助手给出规范后端 id 和理由。

错误恢复或无障碍引导：

- L2 智能体的"生成→自检→带错误信息重试"闭环（`loomq_core/agent.py`）。

- Web 界面在未配置 `LOOMQ_LLM_*` 时打开"对话"页，界面给出可操作的环境变量配置指引（而非报错崩溃）。

- 电路运行失败时列出常见原因。

- CLI 对文件缺失等给出下一步提示。

"5 分钟内第一个实验"：截图：`starter_kit/evidence/files/guide-visualization`

A. 首次进入看"开始"页的流程图 + 概念卡片；直接进"实验台"跑出贝尔态直方图 + 大白话解释

- 电路 - 图形编辑：拖到线上，或点击门再点线

- 电路 - Qiskit 标准图：用 Qiskit 开源标准渲染，未装 `qiskit` 时自动回退为 `QASM` 源码展示

B. 在"实验台"把同一电路切换 spinq/originq/braket 三后端各跑一次，查看各自的转译 IR 与结果

## 工程与产品化

- - 一键自测 `python3 starter_kit/evaluator.py --level all --target spinq,originq,braket`；

干净环境中的构建和启动命令：（启动 Web UI 或 CLI）

- 启动 Web UI 界面：**`python3 starter_kit/loomq_web.py --port 8000`**，浏览器打开 http://127.0.0.1:8000；

- - 无需构建，纯标准库 http.server，无 CDN、无第三方依赖，Python 3.10+；

- - 端到端自测：`python3 starter_kit/test_web_api.py --spawn`（27 项检查：三后端保真度/错误路径/chat 503 提示）

- 启动 CLI：`python3 starter_kit/loomq_cli.py`（交互模式；ask/run/guide/backends 子命令）

- 架构说明：**`starter_kit/ARCHITECTURE.md`**（单一 IR、纯函数发射器、run() 执行转译产物、位序归一化）

------

- 产品与竞品分析：**`starter_kit/PRODUCT.md`**（目标用户、竞品对比、差异化、用户旅程、必答题答案）-- 目标用户和使用场景：没有量子背景的跨界创作者/产品与设计背景参赛者，用自然语言完成第一个量子实验

## 自定义量子 RISC-V Bonus

指令编码规格：`starter_kit/quantum_riscv_spec.md`（custom-0 opcode，qinit/qh/qx/qcx/qmeas/qprob 六条指令）

模拟器扩展实现：`starter_kit/riscv_emulator_ext.py`（扩展官方 TinyRISCVEmulator，不改原文件）

端到端测试命令：`cd starter_kit && python3 test_quantum_riscv.py`

## 新手引导与视觉叙事 Bonus

零基础首次运行指南：

Web：`python3 starter_kit/loomq_web.py --port 8000`

看"开始"页流程图 + "量子计算入门"概念卡片（qubit/叠加/纠缠/测量），启动实验台一键跑出 Bell 直方图 + 运行后的解释；

CLI：`python3 starter_kit/loomq_cli.py guide`

CLI 每次运行后 explain_counts（例如"两枚永远同面的硬币"解释纠缠；"单比特叠加"不会再被误称为纠缠）；另见官方 QUANTUM_101.md

结果可视化：

- Web 界面"实验台"**右侧栏**常驻**直方图**（运行后实时显示）

- **上方电路图**支持**两种视图**（**图形编辑器 + Qiskit 标准图**，同步对照）；

- CLI ASCII 直方图 + 概率百分比

截图：`starter_kit/evidence/files/guide-visualization/circuit_*.png`

悬停知识解释：Web 界面门板与电路库卡片的 `title` 悬停浮窗（中文）说明 12 个白名单门的物理意义和 4 个示例电路的构造与用途；位置：`starter_kit/webui/index.html` 的 `GATE_INFO / CIRCUIT_INFO`

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。

---

# zmath01 最终提交

以下为 `starter_kit/` 中的完整实现。

| 评分项 | 交付物 | 一键验证 |
|---|---|---|
| L1 通用中间层 | `starter_kit/adapter.py` + `loomq_core/`（零第三方依赖） | `./run.sh` 或 `python3 starter_kit/selftest.py` |
| L1 真机（10 分） | `starter_kit/run_real.py` + `evidence/real_machine_runbook.md`（无 Mock，凭据走环境变量） | `python3 starter_kit/run_real.py all --circuit starter_kit/circuits/bell.qasm` |
| L2 智能体（20 分） | `agent_chat` 契约实现（`loomq_core/agent.py`，读取 `LOOMQ_LLM_*`） | `python3 starter_kit/test_l2_plumbing.py` |
| L2 交互体验（10 分） | Web UI（`loomq_web.py` + `webui/`，零依赖）+ CLI（`loomq_cli.py`） | `python3 starter_kit/loomq_web.py --port 8000` |
|  |  Web 特色：LLM 自然语言→实验台加载 / 拖拽式图形编程 / 两种电路图同步对照 / 电路库知识页（12 门 + 4 电路 + 交互式布洛赫球） | 见下"Web UI 用法" |
| L3 混合编译（15 分） | `loomq_core/hybrid.py`（真递归下降解析 + RISC-V 代码生成） | `selftest.py` L3 段（25 组随机用例全注入） |
| 工程与产品化（10 分） | `starter_kit/PRODUCT.md`（竞品分析/差异化/用户旅程/必答题）+ `ARCHITECTURE.md` | 本 README 即入口 |
| 量子 RISC-V Bonus（+8） | `quantum_riscv_spec.md` + `riscv_emulator_ext.py` + `test_quantum_riscv.py` | `python3 starter_kit/test_quantum_riscv.py` |
| 新手引导与视觉叙事（+4） | 概念卡片 + 图形编程 + 电路可视化 + SVG 直方图 | 打开 Web UI 即体验 |

**安全性**：仓库不含任何 API Key / Token（凭据只经 `LOOMQ_LLM_*` / 平台环境变量注入），
提交前用 `python3 starter_kit/check_secrets.py --history` 全量扫描。证据与操作手册见
`starter_kit/evidence/README.md` 与 `starter_kit/evidence/real_machine_runbook.md`。

**AI 辅助声明**：本项目代码由 AI 辅助编写，系统各部分工作原理见 `starter_kit/ARCHITECTURE.md`
与 `starter_kit/PRODUCT.md`，可供异步审查。

### Web UI 用法

启动 `python3 starter_kit/loomq_web.py --port 8000`（建议用 `python3 -m venv .venv310` + `pip install qiskit` 以启用 Qiskit 标准电路图）。四大主交互：

- **自然语言 → 电路**：在"对话"页用中文描述需求（如"两个比特永远同面的硬币"），智能体生成 QASM 后点 ▶ 验证，**自动载入实验台 + 切到实验台标签 + 用当前所选后端运行**。生成电路可在三家本地模拟器中任意重跑。
- **拖拽式图形编程**：在实验台左栏拖 12 个白名单门（H/X/S/S†/T/T†/Rz(θ)/Ry(θ)/CX/Cu1(θ)/SWAP/CCX）到电路线上；参数门放置时弹输入框（支持 `pi/2`、`0.7`，默认 π/4）；点已放的门删除；`+ 加线` / `− 减线` 调比特数。
- **两种电路图同步对照**：上方是图形编辑器（拖放后即时刷新），下方是 OPENQASM 文本编辑器（防抖 300ms 解析后回写图）。中栏"图形编辑 | Qiskit 标准图"切换：标准图由 `Qiskit.QuantumCircuit.draw('text')` 渲染，做自绘的对照。
- **知识解释（电路库页）**：电路库集中展示 12 个白名单门的物理意义（知识卡网格）、4 个示例电路的构造说明，以及**交互式布洛赫球**（Canvas 2D，零依赖）——拖 θ/φ 滑杆实时看叠加态 |ψ⟩=cos(θ/2)|0⟩+e^(iφ)sin(θ/2)|1⟩ 在球上的位置与测量概率 P(0)/P(1)。门板与电路卡仍保留简版悬停提示。
