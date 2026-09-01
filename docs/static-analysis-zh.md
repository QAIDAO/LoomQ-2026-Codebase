# LoomQ 2026 逐人静态分析报告

本报告覆盖聚合仓库 `https://github.com/QAIDAO/LoomQ-2026-Codebase` 在固定基线 `998cd4e67b1b29f0f1eb8bafdc155072dfda2980`（默认分支 `main`）上的全部 58 位正式选手。权威名单来自 `archive/submissions.json` 的唯一 `contestant_id`。snapshot 根为 `archive/generated/snapshots/<contestant_id>/`，上游 commit-object 为 `archive/generated/commit-objects/<contestant_id>.obj`。

本阶段未运行任何选手代码、脚本、二进制、Notebook、宏或生成器；未安装依赖，未构建、测试、启动 Docker/服务，也未通过选手代码联网。大型媒体只记录 Git/blob 元数据，不打开或播放。可执行 Shell 只记录路径，不执行。疑似凭据只描述风险类别与仓库相对位置，不复制内容。

## 覆盖范围

- 基线分支：`main`
- 基线完整 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 正式集合：58 个唯一 `contestant_id`，与 manifest / snapshot / commit-object 三套集合一致，差分为空
- 排除项、重复项、空目录、不可读目录：无
- 结构例外（仍属正式集合）：`infiniteHY` 使用 `starter-kit/`（连字符）；其余 57 份使用 `starter_kit/`（下划线）。`casccjy67` 与 `3dmove` 的根结构/配套材料偏离多数模板，但对象链路完整

README 导航（[`README.md`](../README.md)）与本报告使用同一名单、同一顺序。每位选手在 README 中恰好出现一次，在本报告中恰好有一个对应章节。

## 方法

1. 只读确认 `HEAD == 998cd4e67b1b29f0f1eb8bafdc155072dfda2980`，并核对 manifest / snapshot / commit-object 集合仍为上述 58 项。
2. 读取 `submission.yaml`、README、adapter/evaluator 源码、依赖清单、目录树、测试与证据文件名，以及文本文件中的静态特征（import、函数定义、配置字段、风险模式）。
3. 不 `import` 选手模块，不执行选手源码。Python 解析限于文本正则与 YAML 子集读取。
4. 相对链接目标做存在性检查；二进制与媒体只引用路径、mode、size，不解码内容。
5. 与 Stage 1 Scout 报告对照技术栈与入口候选，但每位选手的判断仍以本基线上的独立静态阅读为准。

## 统一判断口径

- **高（A）**：manifest、Git object/tree、直接源码或配置字段能单独证明。措辞：「可确认」「静态可见」。
- **中（B）**：README 与实现、或两个独立静态证据互相印证，但未运行。措辞：「静态证据表明」「按文档与实现对照」。
- **低（C）**：仅由文件名、目录名、注释或单一文档声明推断。措辞：「候选」「可能」「无法静态确认」。

禁止把「文件存在」写成「已经跑通」，禁止把「声明 L2」写成「L2 完成」，禁止给出排名、分数、性能或真机结论。`submission.yaml` 的 `levels` 字段是选手声明，不是评测结果。

「未发现」一律限定为：在该 exact SHA 的受检路径与规则下未静态发现。

## 未运行代码的限制

无法静态确认：可运行性、依赖可安装性、测试是否通过、算法正确性、性能、真实硬件/云端调用、证据截图/视频是否对应真实运行、外部链接/LFS/gitlink payload、交互体验、比赛排名。

## 目录

1. [`infiniteHY`](#1-infinitehy)
2. [`savannahyuan17-afk`](#2-savannahyuan17-afk)
3. [`cycyotw`](#3-cycyotw)
4. [`everest-an`](#4-everest-an)
5. [`Muhongfan`](#5-muhongfan)
6. [`WilderNoTrack`](#6-wildernotrack)
7. [`AphrixZjr`](#7-aphrixzjr)
8. [`lyl2222`](#8-lyl2222)
9. [`Jimmy658`](#9-jimmy658)
10. [`tale03`](#10-tale03)
11. [`AzureWynn`](#11-azurewynn)
12. [`hongwei-2026`](#12-hongwei-2026)
13. [`zhangxinyang-z`](#13-zhangxinyang-z)
14. [`xinruliuresearch-maker`](#14-xinruliuresearch-maker)
15. [`EndlessTR`](#15-endlesstr)
16. [`2IKK12`](#16-2ikk12)
17. [`mayloveless`](#17-mayloveless)
18. [`0Dionysus0`](#18-0dionysus0)
19. [`Huxingyu`](#19-huxingyu)
20. [`haiyun919`](#20-haiyun919)
21. [`arw131072`](#21-arw131072)
22. [`yiyuanrvk77`](#22-yiyuanrvk77)
23. [`UokyI`](#23-uokyi)
24. [`orange-city`](#24-orange-city)
25. [`noh1204`](#25-noh1204)
26. [`BEER7LN`](#26-beer7ln)
27. [`zhangsiyue343-hub`](#27-zhangsiyue343-hub)
28. [`elenawia`](#28-elenawia)
29. [`talk2joan`](#29-talk2joan)
30. [`33ClayLesley`](#30-33claylesley)
31. [`alicewangzm`](#31-alicewangzm)
32. [`qianqiu0926`](#32-qianqiu0926)
33. [`Yolanlanlanda`](#33-yolanlanlanda)
34. [`Andante397`](#34-andante397)
35. [`iiixiscientia`](#35-iiixiscientia)
36. [`LinXuan2576`](#36-linxuan2576)
37. [`CloverLiu03`](#37-cloverliu03)
38. [`arwenlinzhaoqing`](#38-arwenlinzhaoqing)
39. [`softeight`](#39-softeight)
40. [`zhaoqianyuan24`](#40-zhaoqianyuan24)
41. [`jessicaruan6688-byte`](#41-jessicaruan6688-byte)
42. [`wronps`](#42-wronps)
43. [`lil4notfound`](#43-lil4notfound)
44. [`xueerlin20-stack`](#44-xueerlin20-stack)
45. [`qwer-asdftg`](#45-qwer-asdftg)
46. [`LouisYye`](#46-louisyye)
47. [`betsywbx`](#47-betsywbx)
48. [`zmath01`](#48-zmath01)
49. [`BH2-4`](#49-bh2-4)
50. [`Duanice`](#50-duanice)
51. [`danjituya`](#51-danjituya)
52. [`WayneYu1212`](#52-wayneyu1212)
53. [`HpIahtcthocw`](#53-hpiahtcthocw)
54. [`casccjy67`](#54-casccjy67)
55. [`Pennie514`](#55-pennie514)
56. [`JunkaiWang-TheoPhy`](#56-junkaiwang-theophy)
57. [`PHTPSN`](#57-phtpsn)
58. [`3dmove`](#58-3dmove)

---

## 1. `infiniteHY`

### 身份与路径
- 选手标识：`infiniteHY`
- snapshot 相对路径：`archive/generated/snapshots/infiniteHY/`
- 上游 URL：`https://github.com/infiniteHY/LoomQ-2026`
- 上游 SHA：`4e56f109cb1cad925e7c32688403bb945b9c98d7`
- starter 目录名：`starter-kit`（连字符；Scout 表中 58 份里唯一使用该拼写）
- 文件规模（fact card）：41 个文件 / 17 个 Python 文件；证据计数 1、测试计数 2

### 技术栈与结构
- 静态技术栈：Python 3.11（`submission.yaml` 声明，A）+ 量子 SDK 适配（Scout 表，A）。源码直接导入 `spinqit` / `pyqpanda3` / `braket`（A）；`llm_client` + OpenAI-compatible 环境变量协议（B）。fact card 的 qiskit/openai/deepseek 标签主要来自赛题文档与注释命中，不代表已安装（C）。
- 目录与模块地图：
  - 评测入口：`starter-kit/adapter.py`（`transpile` / `run` / `agent_chat` / `compile_hybrid`）
  - 核心：`transpiler.py`（QASM 解析与三后端发射）、`agent.py`（L2）、`hybrid_compiler.py`（L3）
  - Web/CLI：未静态识别独立 Web/CLI；根目录 `LoomQ-赛题.html` 为赛题发布页，不是选手 UI
  - 硬件适配：`adapter.py` 中 `_run_spinq` / `_run_originq` / `_run_braket` 走本地模拟器路径
  - 证据文件名：`starter-kit/evidence/README.md`（无 `files/` 附件）
  - 测试文件名：`tests/test_submission_tools.py`、`tests/test_l2_contract.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。这是声明，不是完成度。

### 方案概述
- README 声称（C）：根 `README.md` 与 `starter-kit/README.md` 仍是赛题发布包 / Starter Kit v1.1.0 模板，未改写成选手方案说明；只描述提交结构、公开自测与 adapter 契约。
- 源码静态可见实现（A）：`adapter.transpile` 经 `parse_qasm` 后分别调用 `to_spinq_qasm2` / `to_originir` / `to_braket_openqasm3`；`run` 按 target 分发到三个 `_run_*`。SpinQ 路径用 `importlib.import_module("spinqit")`，失败则回退 OriginQ 模拟并改写 `backend` 字段。L2 转发给 `agent.agent_chat`；L3 转发给 `hybrid_compiler.compile_hybrid_qasm`。
- 静态架构：OpenQASM 2.0 文本 → `transpiler.parse_qasm` 得到 `Circuit` IR → 三后端字符串发射 → SDK 本地模拟（或 OriginQ 回退）→ 统一 JSON（`backend`/`job_id`/`shots`/`counts`/`bit_order=little`）。L2：自然语言 → `llm_client.chat_completion` + 关键词分类与 QASM 重试。L3：剥离 `classical {}` → 递归下降 AST → RISC-V 汇编。文档未单独描述该流水线。
- L1 实现面：可见 `SUPPORTED_TARGETS = ("spinq","originq","braket")`、`transpiler.py` 12 门白名单与门分解注释、公开电路 `circuits/bell.qasm` 与 `ghz3.qasm`。L2：`agent.py` 的 `_classify_task` / `_has_valid_qasm` / 最多 2 次重试。L3：`hybrid_compiler.py` 的 tokenizer/parser。不推断得分。额外 Python：`agent.py`、`hybrid_compiler.py`、`transpiler.py`（另有模板 `llm_client.py` / `evaluator.py` / `prepare_submission.py` / `riscv_emulator.py`）。

### 优点
- adapter 契约四函数均有实现体，而不是 `NotImplementedError`。
- L1 解析/发射与 L2/L3 拆到独立模块，评测入口保持薄封装。
- `requirements.txt` 对 `amazon-braket-sdk==1.124.3`、`pyqpanda3==0.4.0` 精确钉版本。
- 保留 `Dockerfile`、`evaluator.py`、`submission.yaml`、公开电路 `bell.qasm` / `ghz3.qasm`。
- SpinQ SDK 缺失时有显式 fallback 与 `meta.fallback` 标记，而不是静默失败。

### 质量问题与风险
- 根 README 与 starter README 仍为赛题模板残留；选手方案需从源码反推。
- 缺少 `__init__.py`（fact card `missing_py`）；与多数 `starter_kit` 包导入约定不一致。
- `VERSION` 文件内容为 `1.1.0`，与 starter README 标题一致，说明工具包版本字段未改成选手发行号。
- `runtime.version` 声明 `3.11`，而 starter README 推荐 3.10（spinqit 仅提供 cp310 wheel）——版本声明与常见评测镜像可能冲突，无法静态确认实际构建结果。
- `requirements.txt` 未钉 `spinqit`，注释写「PyPI 不可用」；`_run_spinq` 依赖动态导入。
- 需复核的静态命中：`transpiler.py` 对门参数使用 `eval(..., {"__builtins__": {}})`；`adapter.py` 使用 `importlib.import_module`；`prepare_submission.py` 使用 `subprocess.run`（模板预检脚本）。上述均为静态命中，不写成已确认漏洞。
- 证据包全部复选框仍为 `[ ]`，无 `evidence/files/` 附件。
- 根级 `tests/` 仅为公开契约测试，未见针对 `transpiler`/`agent`/`hybrid_compiler` 的选手自测。

### 完整性 / 可维护性 / 安全性观察
- 完整性：`adapter.py`、`evaluator.py`、`submission.yaml`、`Dockerfile`、`requirements.txt` 均存在。
- 可维护性：模块切分清晰但文档未同步；无选手侧单元测试；`adapter.py` 122 行把执行逻辑与契约放在同一文件。
- 安全性：未静态发现 `.env` 或密钥文件（在该 SHA 受检路径下）。动态导入与受限 `eval` 需人工复核。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/infiniteHY/starter-kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L22 — 声明 contract 1.0、entrypoint `adapter.py`、L1/L2/L3 均为 true、runtime Python 3.11、L2 需 `LOOMQ_LLM_*`
[E-2] `archive/generated/snapshots/infiniteHY/starter-kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L12-L58 — `transpile`/`run` 三后端分发；SpinQ 动态导入失败则 fallback OriginQ
[E-3] `archive/generated/snapshots/infiniteHY/starter-kit/transpiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L29-L35 — 门参数表达式走受限 `eval`
[E-4] `archive/generated/snapshots/infiniteHY/starter-kit/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L39-L73 — L2 关键词分类 + `chat_completion` + QASM 完整性重试
[E-5] `archive/generated/snapshots/infiniteHY/starter-kit/hybrid_compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L9-L66 — L3 剥离 classical 块并手写 tokenizer
[E-6] `archive/generated/snapshots/infiniteHY/starter-kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 五项人工评分全部未勾选
[E-7] `archive/generated/snapshots/infiniteHY/starter-kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L4 — 仅钉 braket 与 pyqpanda3；spinqit 以注释说明

### 结论置信度
- 总体 **B**：契约实现与模块边界可从源码直接读出（A），但根文档为模板、证据未填、自测面窄，方案叙述依赖源码反推。
- 无法静态确认：可运行性、三后端正确性、SpinQ fallback 是否被评测接受、L2 模型调用是否满足正式用例、L3 汇编是否被模拟器接受、真机、性能、排名。

## 2. `savannahyuan17-afk`

### 身份与路径
- 选手标识：`savannahyuan17-afk`
- snapshot 相对路径：`archive/generated/snapshots/savannahyuan17-afk/`
- 上游 URL：`https://github.com/savannahyuan17-afk/LoomQ-2026`
- 上游 SHA：`86682462dc93c32c43ce5721b79d624a0c017d0f`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：47 个文件 / 20 个 Python 文件；证据计数 1、测试计数 2

### 技术栈与结构
- 静态技术栈：Python 3.10（A）+ 纯标准库 L1 模拟器（源码，A）。Scout 表记「Python、量子 SDK」；源码注释讨论 qiskit/numpy 为未采用方案，`requirements.txt` 无已钉第三方包（B）。L2 可选走 `LOOMQ_LLM_*`（B）。
- 目录与模块地图：
  - 入口：`starter_kit/adapter.py` 薄封装，转发 `transpiler` / `engine` / `agent` / `compiler`
  - 核心：`transpiler.py`（tokenize→parse→decompose→emit）、`engine.py`、`simulator.py`（statevector）、`agent.py`、`compiler.py`
  - Web/CLI：`setup.sh` 一键脚本；无独立 Web 服务。根 `LoomQ-赛题.html` 为赛题页
  - 硬件适配：`engine.py` 明确用自研模拟器而非厂商 SDK
  - 证据文件名：`starter_kit/evidence/README.md`（无 `files/` 附件）
  - 测试文件名：`tests/test_submission_tools.py`、`tests/test_l2_contract.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（C/B）：根 README 自称「OpenQASM 2.0 到 SpinQ / Braket / OriginQ 的统一编译、执行与 LLM 智能体」，并列出 L1/L2/L3「✅」进度表（进度表本身是文档声称，C）。`ARCHITECTURE.md` 给出模块图与数据流，可与源码文件名互相印证（B）。
- 源码静态可见实现（A）：adapter 四个契约函数均委托包内模块。`simulator.py` 实现纯 Python 状态向量；`engine.py` 将 IR 直接交给模拟器并 `normalize_result`。`agent.py` 写明两档策略：无 LLM 凭据时规则模板，有 `LOOMQ_LLM_*` 时走生成→run→校验。`compiler.py` 拆 Hybrid-QASM 的 `classical {}` 并生成 RISC-V。
- 静态架构：QASM 文本 → tokenizer/parser IR → 12 门分解 → `emit_{spinq,braket,originq}` → 自研模拟采样 → 统一 JSON。L2：classify → 规则引擎或 LLM。L3：split hybrid → ClassicalParser → asm。文档架构图与文件布局一致；「6/6 公开电路通过」仅为 README 声称。
- L1/L2/L3 实现面：可见上述模块与符号，以及 `setup.sh`、`ARCHITECTURE.md`。额外 Python：`agent.py`、`compiler.py`、`engine.py`、`simulator.py`、`transpiler.py`。不推断评测得分。

### 优点
- 根 README + `ARCHITECTURE.md` 把模块职责和数据流写清楚，与源码文件一一对应。
- L1 核心零第三方依赖的设计在 `requirements.txt` 与 `simulator.py` 中一致。
- adapter 仅 37 行，契约与实现分离。
- `setup.sh` 提供一键自测入口（脚本存在；是否跑通无法静态确认）。
- 证据 README 至少填写了工程与产品化启动命令，而不是完全空白模板。

### 质量问题与风险
- 根目录另有 `LoomQ-赛题模块拆解.md`，属赛题拆解笔记，不是运行入口。
- `requirements.txt` 无已钉 SDK；注释中出现 `openai>=1.0.0` 形式的未钉示例。正式评测若要求厂商 SDK 执行，本快照未提供锁定依赖。
- 根 README 进度表使用「通过」措辞，属于文档声称，不能当作评测结果。
- 证据未申报 L1 真机 / L2 交互 / RISC-V Bonus / 新手引导；`evidence/files/` 无附件。
- 需复核的静态命中：根 `tests/` 使用 `importlib` 与 `http.server`（公开契约测试）；`prepare_submission.py` 的 `subprocess.run`。源码实现路径上未静态命中 `eval`/`exec`/`shell=True`。
- starter README 仍为 v1.1.0 模板，与根 README 的方案叙述分层，读者需同时看两份。

### 完整性 / 可维护性 / 安全性观察
- 完整性：`adapter.py` / `evaluator.py` / `submission.yaml` / `Dockerfile` / `requirements.txt` 均存在；含 `__init__.py`。
- 可维护性：五模块切分清楚，架构文档完整；测试仍主要是公开契约两份。
- 安全性：在该 SHA 受检路径下未静态发现密钥文件。`setup.sh` 为 bash 入口，仅记录路径，未执行。

### 关键证据位置
[E-1] `archive/generated/snapshots/savannahyuan17-afk/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L44 — 选手方案 README：三后端、agent 闭环、L1/L2/L3 进度表
[E-2] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L36 — 契约四函数分别委托 transpiler/engine/agent/compiler
[E-3] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L9-L67 — 文档中的模块图与 L1 数据流
[E-4] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/simulator.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L52 — 声明纯 Python statevector、零外部依赖
[E-5] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L47 — L2 两档策略与 LLM 环境探测
[E-6] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — L3 Hybrid-QASM → RISC-V 管线声明
[E-7] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L9-L19 — 仅勾选工程与产品化；L1 真机未申报
[E-8] `archive/generated/snapshots/savannahyuan17-afk/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 核心依赖为空；SDK/openai 仅出现在注释

### 结论置信度
- 总体 **B**：架构文档与源码互相印证（B/A），但无锁定 SDK、无真机证据、无选手单元测试，运行与正确性无法确认。
- 无法静态确认：自研模拟器与隐藏电路的一致性、L2 规则档是否覆盖正式用例、L3 正确性、真机、性能、排名。README「6/6 通过」无法静态确认。

## 3. `cycyotw`

### 身份与路径
- 选手标识：`cycyotw`
- snapshot 相对路径：`archive/generated/snapshots/cycyotw/`
- 上游 URL：`https://github.com/cycyotw/LoomQ-2026`
- 上游 SHA：`6e0556e389885f70a435483acf3c5b4cc2158829`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：84 个文件 / 41 个 Python 文件；证据计数 12、测试计数 2

### 技术栈与结构
- 静态技术栈：Python 3.10 + Shell + 量子 SDK（Scout，A）。`requirements.txt` 为 pip freeze 风格锁定，含 `amazon-braket-sdk==1.110.1`、`pyqpanda==3.8.5`、`antlr4-python3-runtime==4.13.2` 等（A）。注释明确不安装 `spinqit` 以避免 antlr 冲突（A）。
- 目录与模块地图：
  - 入口：根 `loomq.sh`（可执行，mode 0o755）；`starter_kit/loomq_cli.py`；评测入口 `adapter.py`
  - 核心包：`starter_kit/loomq/`（`qasm_parser`/`emitters`/`backends`/`agent`/`hybrid*`）
  - Web/CLI：终端 CLI + 三关 guide；无选手 Web 服务
  - 硬件适配：`starter_kit/tools/run_on_hardware.py`、`run_on_spinq.py`；脚本另建 `.venv-hardware` / `.venv-spinq`
  - 证据文件名：`evidence/README.md`；`files/originq-tasks.json`、`originq-wukong-bell-platform-export.json`、`originq-wukong-bell-result.json`、`originq-wukong-bitorder-platform-export.json`、`originq-wukong-bitorder-result.json`、`originq-wukong-ghz3-platform-export.json`、`originq-wukong-ghz3-result.json`、`spinq-bell-result.json`、`spinq-bitorder-result.json`、`spinq-ghz3-result.json`、`spinq-tasks.json`
  - 测试文件名：`tests/test_l2_contract.py`、`tests/test_submission_tools.py`；工具侧还有 `tools/verify_l1.py`、`verify_l2.py`、`fuzz_l3.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`；注释强调 `required_for_l2: true`。

### 方案概述
- README 声称（C/B）：根 README 仍是赛题发布包。真正的方案说明在 `SUBMISSION.md`：一条 `bash loomq.sh`、模型只负责意图、确定性代码给答案、L1 中间层、L3 手写编译器（B，文档与包结构印证）。
- 源码静态可见实现（A）：adapter 转发 `loomq.emitters.transpile` / `backends.execute` / `agent.agent_chat` / `hybrid.compile_hybrid`。`backends.execute` 对 `spinq` **直接 raise `BackendUnavailable`**，理由是 spinqit 与 braket 的 antlr 版本互斥；`transpile(..., "spinq")` 仍返回 QASM2。L2 `agent.py` 主张模型输出结构化意图，选后端查表，生成电路用 L1 自验。
- 静态架构：用户话 → `loomq_cli` → `agent_chat` → 意图 JSON → 选后端/生成/纠错 → L1 parser→emitters→backends → 统一 Schema。L3：`hybrid.py` 扫描花括号 → lexer/parser/codegen；`hybrid_interp.py` 仅作对拍。文档与实现一致处标 B；`run(spinq)` 不可用是源码硬编码（A）。
- L1/L2/L3 实现面：可见完整 `loomq/` 包与 tools；不推断得分。证据勾选 L1 真机（本源悟空）与 L2/工程/新手引导；RISC-V Bonus 明确未申报。

### 优点
- 方案文档 `SUBMISSION.md` 与包结构、adapter 转发关系对齐。
- 依赖精确锁定，并在注释中记录 antlr 冲突的取舍。
- 真机证据目录含 OriginQ 任务 JSON / 平台导出以及 SpinQ 结果文件。
- L3 拆成 lexer/parser/codegen/interp，并有 fuzz 工具。
- 一键脚本与 CLI 入口清晰；`.env.example` 存在而源码声明不硬编码密钥。

### 质量问题与风险
- `loomq/` 额外模块包括 `backend_selector.py`、`envfile.py`、`gates.py`、`target_states.py` 以及 hybrid 四件套。
- `run(target="spinq")` 静态可见为不可用；若评测对 spinq 调用 `run`，该路径会抛异常。这是实现选择，不是文档遗漏。
- 根 README 仍为赛题模板；导航需依赖 `SUBMISSION.md`。
- 需复核的静态命中：`tools/fuzz_l3.py` 使用 `exec(compile(...), {"__builtins__": {}}, namespace)` 作为参考解释器；`tools/fake_llm_server.py` 使用 `http.server`；`tools/verify_l2.py` 与 `prepare_submission.py` 使用 `subprocess`。`loomq.sh` 为可执行 shell，仅记录路径，未执行。
- 根 `tests/` 仍是两份公开契约测试；大量校验逻辑在 `tools/`，不是标准 unittest 目录。
- `.env.example` 属环境模板类别（路径：snapshot 根 `.env.example`），不复制内容。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + 锁定 requirements 均存在。
- 可维护性：`loomq/` 模块化程度高；文档解释了为何不装 spinqit。测试入口分散在 shell/tools。
- 安全性：环境模板与真机脚本分离到独立 venv 的设计可见。`exec` 命中限于 fuzz 参考解释器且清空 builtins，需复核而非已确认漏洞。可执行脚本：`loomq.sh`。

### 关键证据位置
[E-1] `archive/generated/snapshots/cycyotw/SUBMISSION.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L8-L79 — 一键命令、架构图、L1/L2/L3 模块职责
[E-2] `archive/generated/snapshots/cycyotw/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L63 — 契约转发到 `loomq` 包
[E-3] `archive/generated/snapshots/cycyotw/starter_kit/loomq/backends.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L47-L68 — `run(spinq)` 显式 `BackendUnavailable`
[E-4] `archive/generated/snapshots/cycyotw/starter_kit/loomq/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L22 — L2「模型只负责听懂人话」的设计声明
[E-5] `archive/generated/snapshots/cycyotw/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L18 — L1/L2/L3 true，并注释 L2 必须声明联网
[E-6] `archive/generated/snapshots/cycyotw/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L34 — 勾选真机/L2/工程/新手引导；给出悟空 job ID 与结果路径
[E-7] `archive/generated/snapshots/cycyotw/loomq.sh`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L43 — 可执行一键入口；硬件/spinq 使用独立 venv
[E-8] `archive/generated/snapshots/cycyotw/starter_kit/tools/fuzz_l3.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L214-L219 — 受限 `exec` 参考解释器

### 结论置信度
- 总体 **B**：实现与文档完整度高，关键行为（spinq run 禁用、antlr 取舍、真机文件存在）可静态确认；正确性、真机真实性、可运行性仍无法确认。
- 无法静态确认：braket/originq `run` 是否满足隐藏电路与位序契约、L2 正式用例、L3 与官方模拟器一致性、证据 JSON 是否为真实平台返回、排名。

## 4. `everest-an`

### 身份与路径
- 选手标识：`everest-an`
- snapshot 相对路径：`archive/generated/snapshots/everest-an/`
- 上游 URL：`https://github.com/everest-an/LoomQ-2026`
- 上游 SHA：`145df7785554ea8ff8030299301cfdea98cc22e2`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：71 个文件 / 36 个 Python 文件；证据计数 7、测试计数 2

### 技术栈与结构
- 静态技术栈：Python 3.10 + 量子 SDK（Scout，A）。L1 执行栈在 adapter 文档字符串中声明为零第三方依赖（A）。`requirements.txt` 仍是 starter 占位模板，无已钉包（A）。SDK 交叉验证脚本位于 `examples/`（C，未运行）。
- 目录与模块地图：
  - 入口：`adapter.py`；交互 `cli.py`；Scout 亦列 `agent.py`
  - 核心：`qasm_parser.py`、`circuit_ir.py`、`simulator.py`、`codegen.py`、`hybrid_parser.py`、`riscv_codegen.py`、`riscv_emulator_quantum.py`
  - Web/CLI：CLI REPL，无 Web
  - 硬件适配：`examples/run_spinq_cloud.py` 等；`SPINQ_CLOUD_SETUP.md`、`ORIGINQ_CLOUD_NOTES.md`
  - 证据文件名：`evidence/README.md`；`files/braket-bell-result.json`、`braket-ghz3-result.json`、`final-submission-template.md`、`spinq-bell-result.json`、`spinq-ghz3-result.json`、`validation-report.md`
  - 测试文件名：`tests/test_l2_contract.py`、`tests/test_submission_tools.py`；starter 内另有 `selftest_fhb.py`、`selftest_l2_variants.py`、`selftest_l3.py`、`selftest_l3_fuzz.py`、`selftest_quantum_isa.py`、`selftest_roundtrip.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（C/B）：根 README 为赛题模板。`PROJECT.md` 声称零依赖中间层 + 自然语言智能体，并用 Fuxi Hypercube 闭式解作为转译验证基石（C 叙事 / B 与模块表印证）。
- 源码静态可见实现（A）：`transpile` 走 `parse_qasm2` + `codegen.to_*`；`run` 调用自研 `simulate` 并填统一 schema，`backend` 名称随 target 变化但采样同一模拟器。`compile_hybrid` 组合 `split_hybrid` / `parse_classic` / `compile_classic_block`。`qasm_parser.py` 声明参数求值用 AST 白名单、**不用** `eval`。
- 静态架构：自然语言 → `cli.py`/`agent.py` → QASM → parser → Circuit IR → codegen（三方言）或 simulator → JSON/ASCII 分布。L3 独立于 L1 模拟器。`run` 不调用厂商 SDK——与「零依赖 L1」一致；与证据里的云任务文件是不同路径。
- L1/L2/L3 实现面：契约函数、自测脚本、量子 ISA 文档 `riscv_quantum_isa.md` 均可见。证据五项均勾选。不推断得分。

### 优点
- L1 解析器明确拒绝未知门（`ValueError`），并避免 `eval`。
- adapter、parser、simulator、codegen、hybrid 分层清楚。
- 自测文件覆盖 FHB、L3 穷举/fuzz、roundtrip、L2 变体、量子 ISA。
- 证据目录含 spinq 结果 JSON 与 job ID 填写。
- CLI 面向零背景用户，带欢迎文本与可视化意图。

### 质量问题与风险
- 额外 Python 可见 `fhb_ref.py`、`riscv_emulator_quantum.py` 以及 `examples/verify_{braket,originir,spinq_sim}.py`、`run_spinq_cloud.py`。
- `requirements.txt` 未钉任何 SDK，与 `examples/verify_*.py` 所声称的官方 SDK 交叉验证不在同一依赖清单中。
- 根 README 模板残留；方案说明在 `PROJECT.md`。
- `PROJECT.md` 含模型服务基址类示例导出语句（文档示例类别，路径 `starter_kit/PROJECT.md`），不复制内容。
- 证据「L1 真机」填写了两个 SpinQ 任务；`files/` 另有 `braket-*-result.json`（本地模拟器结果候选，不能当作第二真机平台）。截图字段写「待补」。
- 需复核的静态命中：仅公开测试与 `prepare_submission.py` 的 `importlib`/`subprocess`/`http.server`。实现路径未静态命中 `eval`/`exec`/`shell=True`。
- `run()` 对三 target 共用自研模拟器：转译字符串不被 `run` 消费，和「transpile 与 run 互相掩护」类风险需评测侧复核，无法静态确认是否扣分。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + requirements（空模板）均存在。
- 可维护性：模块与自测命名清楚；根测试目录仍是公开两份。
- 安全性：在该 SHA 受检路径下未静态发现密钥文件。云 setup 文档与示例脚本仅记录路径。

### 关键证据位置
[E-1] `archive/generated/snapshots/everest-an/starter_kit/PROJECT.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L52 — 零依赖模块表、自测命令、CLI 入口
[E-2] `archive/generated/snapshots/everest-an/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L104 — 零依赖 L1；`run` 调 `simulate`；L3 组合 hybrid_parser/riscv_codegen
[E-3] `archive/generated/snapshots/everest-an/starter_kit/qasm_parser.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L29 — AST 白名单求值、未知门报错、不用 eval
[E-4] `archive/generated/snapshots/everest-an/starter_kit/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L46 — L2 交互 CLI 入口
[E-5] `archive/generated/snapshots/everest-an/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true，Python 3.10
[E-6] `archive/generated/snapshots/everest-an/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L45 — 五项均勾选；SpinQ job ID 与结果路径
[E-7] `archive/generated/snapshots/everest-an/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 仍为 starter 占位，无已钉包

### 结论置信度
- 总体 **B**：零依赖 L1 与 L3 管线在源码中可见；真机文件存在但不能验证；SDK 交叉验证不在锁定依赖内。
- 无法静态确认：模拟器正确性、FHB 闭式验证是否被执行、云任务真实性、L2 正式用例、量子 ISA bonus 是否满足评分口径、排名。

## 5. `Muhongfan`

### 身份与路径
- 选手标识：`Muhongfan`
- snapshot 相对路径：`archive/generated/snapshots/Muhongfan/`
- 上游 URL：`https://github.com/Muhongfan/LoomQ-2026`
- 上游 SHA：`e26b81a01dde0dda49612c4509c88396e25bac73`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：67 个文件 / 38 个 Python 文件；证据计数 3、测试计数 15

### 技术栈与结构
- 静态技术栈：Python 3.10 + 量子 SDK（Scout，A）。`requirements.txt` 钉 `spinqit==0.2.4`、`antlr4-python3-runtime==4.9.2`、`amazon-braket-sdk==1.99.0`、`pyqpanda==3.8.5` 等（A），并注释 antlr 冲突。
- 目录与模块地图：
  - 入口：`adapter.py`；Scout 列 `l2_agent.py`、`runner.py`；另有 `chat_cli.py`
  - 核心：`circuit_ir.py`、`validator.py`、`lowering.py`、`emitters.py`、`runner.py`、`hybrid_compiler.py`、`riscv_emulator_ext.py`
  - Web/CLI：`chat_cli.py` 终端入口，无 Web
  - 硬件适配：`runner.py` 调 spinqit/braket 本地 SDK，并手写位序归一化；证据含 SpinQ 真机 JSON/QASM
  - 证据文件名：`evidence/README.md`；`files/spinq-real-chip-bell-result.json`、`files/spinq-real-chip-bell.qasm`
  - 测试文件名：`tests/reference_simulator.py`、`test_adapter.py`、`test_chat_cli.py`、`test_circuit_ir.py`、`test_emitters.py`、`test_gate_identities.py`、`test_hidden_style_circuits.py`、`test_hybrid_compiler.py`、`test_l2_agent.py`、`test_l2_contract.py`、`test_lowering.py`、`test_riscv_quantum_extension.py`、`test_runner.py`、`test_submission_tools.py`、`test_validator.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（C）：根 README 与 starter README 均为赛题/工具包模板，未写选手叙事。
- 源码静态可见实现（A）：`transpile` = parse → validate → lower → `EMITTERS[target]`。`run` = parse → `runner.run`。`runner.py` 长注释记录 spinqit/braket 忽略 `measure -> c[j]` 的实测行为，并用 IR 中的 qubit→clbit 映射重建 little-endian key。`compile_hybrid` 复用 L1 白名单校验量子半边，经典块生成 Tiny RISC-V。`l2_agent.py` 含超时预算、QASM 抽取与自验重试；文件头注释写「not wired yet」，但 `adapter.agent_chat` **已经调用** `l2_agent.agent_chat`——注释与接线不一致。
- 静态架构：QASM → Circuit IR → validate/lower → emitter 字符串；执行走 SDK + 归一化。L2：LLM → 抽取/校验 → 回复。L3：brace-count 切分 classical 块，保持测量与后续门的原始交错。文档声称弱，实现面强。
- L1/L2/L3 实现面：上述符号与 `custom_riscv_isa.md`、`braket_local_stdlib/` 可见。不推断得分。

### 优点
- 根 `tests/` 数量明显多于公开契约两份，覆盖核心模块。
- 依赖钉版本并记录 antlr 共存策略。
- `runner.py` 把厂商位序差异写成可复核注释与归一化函数。
- L3 明确不通过拆开 gates/measurements 列表重建量子序列，以避免打乱 measure 后的门。
- 真机证据至少包含一条 SpinQ Bell 的 QASM 与 JSON。

### 质量问题与风险
- 根/starter README 模板残留，方案需从源码与测试名推断。
- 额外 Python 可见 `chat_cli.py`、`circuit_ir.py`、`emitters.py`、`gate_identities.py`、`hybrid_compiler.py`、`l2_agent.py`、`lowering.py`、`riscv_emulator_ext.py`、`runner.py`、`validator.py`。
- `l2_agent.py` 头部「尚未接线」与 adapter 实际委托矛盾，增加维护风险。
- `braket_local_stdlib/` 目录存在，用于本地 Braket include；是否与评测镜像一致无法静态确认。
- 证据五项虽勾选，但 L1 模板「[填写]」段落仍在；可见附件主要是 SpinQ 一条，第二平台材料在该目录下未静态看到对等文件。
- 需复核的静态命中：`circuit_ir.py` 使用受限 `eval` 做参数表达式；`prepare_submission.py` 的 `subprocess`；测试中的 `http.server`。
- 根 `.env.example` 为环境模板类别，不复制内容。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + 钉版本 requirements 均存在。
- 可维护性：IR/lowering/emitters/runner 分离良好，测试面宽；文档滞后。
- 安全性：环境模板与凭据边界按路径记录。受限 `eval` 需复核。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/Muhongfan/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L55 — parse/validate/lower/emit；run 委托 runner；L2/L3 委托
[E-2] `archive/generated/snapshots/Muhongfan/starter_kit/runner.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L80 — SDK 位序实测说明与 `_normalize_spinq_counts` / `_normalize_braket_counts`
[E-3] `archive/generated/snapshots/Muhongfan/starter_kit/hybrid_compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L48 — L3 切分策略与不重排量子语句的约束
[E-4] `archive/generated/snapshots/Muhongfan/starter_kit/l2_agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L37 — L2 实现；头部注释与 adapter 接线可能不一致
[E-5] `archive/generated/snapshots/Muhongfan/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L18 — spinqit/antlr/braket/pyqpanda 精确钉版本
[E-6] `archive/generated/snapshots/Muhongfan/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L50 — 五项勾选；SpinQ job `G-260807-0003` 与文件路径
[E-7] `archive/generated/snapshots/Muhongfan/starter_kit/chat_cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L30 — L2 人机 CLI 入口

### 结论置信度
- 总体 **B**：SDK 归一化与测试面可静态观察；README 缺方案叙述，L2 注释不一致，真机附件不完整。
- 无法静态确认：三 SDK 在评测镜像中是否可共存安装、位序修复是否覆盖隐藏电路、L2/L3 正式得分、真机真实性、排名。

## 6. `WilderNoTrack`

### 身份与路径
- 选手标识：`WilderNoTrack`
- snapshot 相对路径：`archive/generated/snapshots/WilderNoTrack/`
- 上游 URL：`https://github.com/WilderNoTrack/LoomQ-2026`
- 上游 SHA：`ed048b53ae930b0a9176e8e840a3d7d217edc9ed`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：129 个文件 / 86 个 Python 文件；证据计数 9、测试计数 11

### 技术栈与结构
- 静态技术栈：Python 3.10 + HTML/JS + 量子 SDK（Scout，A）。核心声明仅用标准库；厂商 SDK 钉在 `requirements-backends.txt`（B/A）。Web 为标准库 `http.server`。
- 目录与模块地图：
  - 入口：`adapter.py` 薄门面；`python3 -m loomq`（`loomq/__main__.py` / `cli.py`）；`loomq/web/server.py`
  - 核心：`loomq/qasm/`、`passes/`、`emitters/`、`backends/`、`execution.py`、`agent/`、`hybrid/`、`qisa/`、`sim/`
  - Web/CLI：CLI tour/selftest + localhost:8787 Web
  - 硬件适配：`loomq/backends/hardware.py`、`tools/hardware_run.py`
  - 证据文件名：`evidence/README.md`；`files/originq-bell-circuit.qasm`、`originq-bell-result.json`、`originq-ghz3-circuit.qasm`、`originq-ghz3-result.json`、`spinq-bell-circuit.qasm`、`spinq-bell-result.json`、`spinq-ghz3-circuit.qasm`、`spinq-ghz3-result.json`
  - 测试文件名：根 `tests/test_l2_contract.py`、`test_submission_tools.py`；`starter_kit/tests/__init__.py`、`test_l1_pipeline.py`、`test_l2_agent.py`、`test_l3_hybrid.py`、`test_peephole.py`、`test_qasm_frontend.py`、`test_qisa.py`、`test_routing.py`、`test_stabilizer.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（B）：`starter_kit/README.md` 已改写成选手方案——「一个中间层，三家平台」，并给出 tour/web/selftest 命令与管线图。
- 源码静态可见实现（A）：adapter 调 `loomq.execution.transpile_qasm` / `run_circuit`，L2/L3 延迟导入 `loomq.agent` / `loomq.hybrid`。`execution.py` 描述统一路径：parse → 12 门 lowering → emit → 执行 → 与参考分布交叉核对，位序失配则重键，翻译错误则回退参考结果。Web handler 复用同一套函数。
- 静态架构：QASM → lexer/parser → IR → passes（decompose/optimize/peephole/routing）→ emitters → backends（含 reference simulator）→ 归一化 JSON → CLI/Web。L2 在 `loomq/agent/` 分 llm/prompts/selection/synthesis。L3 在 `loomq/hybrid/`。文档管线与包布局一致（B）。
- L1/L2/L3 实现面：可见 QISA 文档 `QISA.md`、`riscv_emulator_loomq.py`。证据五项均勾选。不推断得分。

### 优点
- 包结构按编译器管线切分，adapter 保持薄。
- 核心零依赖与可选 SDK 分文件锁定。
- `starter_kit/tests/` 覆盖 pipeline/agent/hybrid/qasm/qisa/routing 等。
- Web 默认绑定 `127.0.0.1:8787`，并声明拒绝目录外静态文件。
- 真机证据同时给出量旋与本源的电路与结果文件名。

### 质量问题与风险
- 根 README 仍接近赛题模板；方案在 starter README / `INCLUSION.md` / `ARCHITECTURE.md`。
- 包内另有 `loomq/tour.py`、`diagram.py`、`qisa/`、`sim/stabilizer.py` 等；Scout 入口为 `loomq/cli.py` 与 `loomq/web/server.py`。
- 需复核的静态命中：`loomq/backends/spinq_backend.py` 使用 `subprocess.run` 调隔离 runner（非 `shell=True`）；`prepare_submission.py` 的 subprocess。Web `serve_forever` 为本地监听命中。
- `secrets.env.example` 为凭据模板类别（路径 `starter_kit/secrets.env.example`），不复制内容。
- 参考模拟器回退策略是否符合评测「必须返回目标后端执行结果」口径，无法静态确认。
- fact card `web: 2` 含赛题 HTML；选手 UI 实际是 `loomq/web/`。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + 主 requirements 与 backends/spinq 附加清单均存在。
- 可维护性：模块边界、测试与文档在本批中属于高切分样本。
- 安全性：localhost 绑定、路径限制在注释与 `serve()` 默认参数中可见。subprocess 隔离执行需复核。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/WilderNoTrack/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L75 — 选手方案 README：CLI/Web 入口与编译管线
[E-2] `archive/generated/snapshots/WilderNoTrack/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L61 — 薄门面；sys.path 注入；四契约函数
[E-3] `archive/generated/snapshots/WilderNoTrack/starter_kit/loomq/execution.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L40 — 统一 lowering/emit/交叉核对/回退策略说明
[E-4] `archive/generated/snapshots/WilderNoTrack/starter_kit/loomq/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L27 — 标准库 HTTP；默认 localhost
[E-5] `archive/generated/snapshots/WilderNoTrack/starter_kit/loomq/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L198-L211 — `serve(host="127.0.0.1", port=8787)`
[E-6] `archive/generated/snapshots/WilderNoTrack/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L40 — 五项勾选；SpinQ job ID 与结果路径
[E-7] `archive/generated/snapshots/WilderNoTrack/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L15 — 核心无第三方；SDK 指向 `requirements-backends.txt`

### 结论置信度
- 总体 **B**（实现结构偏 A）：包布局与入口可静态确认；回退策略、Web 行为、真机结果无法静态确认。
- 无法静态确认：可运行性、参考模拟器回退是否被评测接受、routing/peephole 对隐藏电路的影响、真机真实性、Web 体验、排名。

## 7. `AphrixZjr`

### 身份与路径
- 选手标识：`AphrixZjr`
- snapshot 相对路径：`archive/generated/snapshots/AphrixZjr/`
- 上游 URL：`https://github.com/AphrixZjr/LoomQ-2026`
- 上游 SHA：`2595fae0527b9f049d7d5d68cdfc9698ba481072`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：201 个文件 / 57 个 Python 文件；证据计数 81、测试计数 23

### 技术栈与结构
- 静态技术栈：Python 3.10 + HTML/JS + 量子 SDK（Scout，A）。`requirements.txt` 为长 freeze 清单，含 `spinqit==0.2.4`、`pyqpanda==3.8.5`、`pyqpanda3==0.4.0`、`amazon-braket-sdk==1.77.6`、`torch==2.2.2+cpu` 及 PyTorch extra-index（A）。Web 为标准库 HTTP；`compose.yaml` 暴露 8765。
- 目录与模块地图：
  - 入口：`adapter.py`；`web/server.py` + `web/static/index.html`；`docker compose up --build`
  - 核心：`loomq_l1.py`、`loomq_l2.py`、`loomq_l3.py`、`l1_{spinq,originq,braket}.py` 与对应 `*_hardware.py`
  - 硬件：`run_*_hardware.py`、`hardware.env.example`
  - 证据文件名（文本/JSON/QASM/PNG，未打开媒体内容）：`evidence/README.md`；`files/` 下含 `verification-manifest.json`、`evaluator-l1-current.txt`、`evaluator-l3-current.txt`、`l1-regression-current.txt`、多份 `l2-*-current.json`、`l2-ui-*.png`、以及 `files/hardware/originq/` 与 `files/hardware/spinq/` 中按 job ID 命名的 raw/summary/qasm/originir JSON；另有 `files/remediation-20260816/` 复核日志。PNG 只记文件名。
  - 测试文件名：根 `tests/test_l2_contract.py`、`test_starter_archive.py`、`test_submission_tools.py`；`starter_kit/tests/` 含 `test_archive_isolation.py`、`test_l1_braket.py`、`test_l1_braket_hardware.py`、`test_l1_core.py`、`test_l1_originq.py`、`test_l1_originq_hardware.py`、`test_l1_regression.py`、`test_l1_spinq.py`、`test_l1_spinq_hardware.py`、`test_l2_agent.py`、`test_l2_audit_regressions.py`、`test_l2_benchmark.py`、`test_l2_budget.py`、`test_l2_contract.py`、`test_l2_web.py`、`test_l3_and_quantum_riscv.py`、`test_l3_differential.py`、`test_quantum_riscv_e2e.py`、`test_verification_manifest.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（C/B）：根 README 为赛题模板。starter README 声称一条 `docker compose` 拉起 L1/L2/L3 与 Web，并列出归档内 unittest 文件名（B，与目录印证）。
- 源码静态可见实现（A）：adapter 把 `RUNNERS` 注册为三个 `run_*`，`transpile`/`run` 转发 `loomq_l1`，L2/L3 转发 `loomq_l2.agent_chat` / `loomq_l3.compile_hybrid`。`loomq_l1.py` 含 Circuit IR 与 AST 角度求值。`loomq_l2.py` 要求模型只返回 JSON，本地代码负责校验与后端事实。`loomq_l3.py` 做 Hybrid-QASM AST → Tiny RISC-V。Web 带 CSP 头、1MB body 限制、静态路径限制在 `STATIC` 下。
- 静态架构：QASM → `loomq_l1` IR → 各 SDK runner → 统一结果；硬件 runner 独立。L2：JSON intent → 本地验证 → 文本。L3：parser → lowering → 官方模拟器路径。证据 README 把得分项映射到文件，但写明「不是保证得分」。
- L1/L2/L3 实现面：可见 QISA 文档、`quantum_riscv.py`、浏览器检查脚本。不推断得分。

### 优点
- 测试与证据文件数量在本批最大；证据 README 带索引表、job ID 表和时间口径。
- L1 软件契约、硬件 runner、L2 agent、L3、Web 分层文件化。
- Docker Compose 把 LLM 环境变量透传，不把密钥写进镜像层（从 compose 字段可见）。
- Web 默认 `127.0.0.1:8765`，并设置 CSP / `X-Content-Type-Options`。
- 依赖精确锁定（尽管清单很长，含 torch）。

### 质量问题与风险
- 根 README 模板残留；体量主要在 `starter_kit/`。
- 额外可见 `browser_agent_flow_check.mjs`、`browser_responsive_check.mjs`、`l1_reference.py`、`quantum_riscv.py` 以及三套 `run_*_hardware.py`。
- `requirements.txt` 引入 PyTorch CPU wheel 与 `--extra-index-url`，评测镜像安装面偏大，能否安装无法静态确认。
- 需复核的静态命中：`generate_verification_manifest.py` 大量 `subprocess.run`/`Popen`；测试中的 subprocess；Web 监听。未静态命中 `eval`/`exec`/`shell=True`/`CORS`。
- `hardware.env.example` 为硬件凭据模板类别，不复制内容。
- 证据目录含大量「current」日志与截图文件名；存在不等于已验证。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + compose + 钉版本 requirements 均存在。
- 可维护性：测试按 L1/L2/L3/硬件拆分；文档声明开发稿不作为证据。体量大，入口需按 starter README 导航。
- 安全性：CSP、localhost 默认、凭据模板隔离可见。subprocess 清单生成器需复核。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/AphrixZjr/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L54 — 注册三 runner 并转发 L1/L2/L3
[E-2] `archive/generated/snapshots/AphrixZjr/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L55-L75 — docker compose 启动 Web 与三 SDK 的文档声称
[E-3] `archive/generated/snapshots/AphrixZjr/starter_kit/loomq_l2.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L50 — 模型只出 JSON，本地代码拥有校验
[E-4] `archive/generated/snapshots/AphrixZjr/starter_kit/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L53-L67 — 静态路径限制与 CSP
[E-5] `archive/generated/snapshots/AphrixZjr/starter_kit/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L158-L164 — 默认 host 127.0.0.1 port 8765
[E-6] `archive/generated/snapshots/AphrixZjr/starter_kit/compose.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L15 — 端口映射与 `LOOMQ_LLM_*` 环境透传
[E-7] `archive/generated/snapshots/AphrixZjr/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L49 — 得分项-实现-证据索引；SpinQ job 表
[E-8] `archive/generated/snapshots/AphrixZjr/starter_kit/loomq_l1.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L13-L80 — 12 门签名、Circuit IR、AST 角度求值

### 结论置信度
- 总体 **B**（静态完整度偏 A）：文件、测试、证据索引可确认；任何「xx/xx 通过」只存在于证据文本中，本阶段不采信为运行结果。
- 无法静态确认：Docker 构建、三 SDK+torch 可安装性、硬件任务真实性、L2 live benchmark、浏览器脚本结果、排名。

## 8. `lyl2222`

### 身份与路径
- 选手标识：`lyl2222`
- snapshot 相对路径：`archive/generated/snapshots/lyl2222/`
- 上游 URL：`https://github.com/lyl2222/LoomQ-2026`
- 上游 SHA：`c4a1573388fec98cf3abbfe50bacd22fae7805c7`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：78 个文件 / 33 个 Python 文件；证据计数 13、测试计数 10

### 技术栈与结构
- 静态技术栈：Python 3.10 + HTML/JS + 量子 SDK（Scout，A）。主 `requirements.txt` 声明 adapter 只用标准库；`requirements-{spinq,originq,braket}.txt` 分清单钉 SDK，Dockerfile 装入隔离层（B/A）。
- 目录与模块地图：
  - 入口：`adapter.py`；`web_app.py`；`Makefile` 的 `unit`/`verify`
  - 核心：`loomq/circuit.py`、`targets.py`、`execution.py`、`sdk_worker.py`、`agent.py`、`ideal.py`、`interpret.py`
  - Web/CLI：标准库 Web；无独立 CLI 菜单
  - 硬件适配：隔离 worker 调 SDK；证据含 SpinQ msgpack/JSON 与 OriginQ 概率文本
  - 证据文件名：`evidence/README.md`；`files/9DFE2160F08B6E9D53137E8F28A117A3_probability.txt`、`originq-circuit.qasm`、`originq-composer.png`、`originq-logical-circuit.png`、`originq-mapped-circuit.png`、`originq-result.json`、`originq-screenshot.png`、`spinq-circuit-diagram.png`、`spinq-circuit.qasm`、`spinq-result.json`、`spinq-screenshot.png`、`task_result_G-260817-0006.msgpack`（PNG/msgpack 只记文件名）
  - 测试文件名：根 `tests/test_l2_contract.py`、`test_submission_tools.py`；`starter_kit/tests/__init__.py`、`test_agent.py`、`test_execution.py`、`test_ideal.py`、`test_interpret.py`、`test_sdk_integration.py`、`test_transpiler.py`、`test_web_app.py`
- `submission.yaml` 声明：**L1 true、L2 true、L3 false**。这是声明，不是完成度。

### 方案概述
- README 声称（B）：根 README 前部写明评测入口、`make unit`/`make verify`、不要提交 `.env`。starter README 描述共享 IR、三 SDK 因 ANTLR 冲突而隔离安装。
- 源码静态可见实现（A）：`transpile` = `parse_qasm2` + `render_target`；`run` = parse + `execute`。`compile_hybrid` **raise `NotImplementedError`**，与 yaml `l3: false` 一致。`execution.py` 用 `subprocess.run([sys.executable, sdk_worker.py, ...])` 在隔离环境执行，timeout 捕获。`web_app.py` 可从 `.env` 填充缺失的 `LOOMQ_*`（已存在的环境变量不覆盖）。
- 静态架构：QASM → 中立 Circuit → 目标渲染；执行为隔离 worker → JSON。L2：`loomq/agent.py` 抽取 QASM、最多 3 次尝试、用 `execute` 自验。L3：未实现。文档与 yaml/源码三者在「不参加 L3 / SDK 隔离」上一致（A/B）。
- L1/L2 实现面可见；L3 显式缺席。证据勾选真机/L2/工程/新手引导，RISC-V Bonus 未勾选。

### 优点
- L3 声明与实现同时为「不参加」，避免 yaml/代码漂移。
- SDK 隔离是针对 antlr 冲突的工程化处理，并有 Makefile/Dockerfile 入口。
- `starter_kit/tests/` 覆盖 agent/execution/transpiler/web。
- 真机证据含两平台 job ID、截图与原始结果文件名（含 msgpack）。
- Web 从 adapter 复用契约函数。

### 质量问题与风险
- 根 README 后半仍拼接赛题模板。
- 额外 Python：`loomq/{agent,circuit,execution,ideal,interpret,sdk_worker,targets}.py`、`web_app.py`、`verify.py`。
- 需复核的静态命中：`loomq/execution.py` 与 `verify.py` 的 `subprocess.run`（隔离 worker / docker 验证）；`prepare_submission.py` 同类命中。Web 为 `ThreadingHTTPServer`。
- `.env.example` 为环境模板类别（含公开模型基址占位与空 API_KEY 字段），路径 `starter_kit/.env.example`，不复制内容。README 已提示不要提交 `.env`。
- L3 未实现，若评测误开 l3 会走 `NotImplementedError`。
- msgpack 原始结果需专用解码；可读性依赖同时提交的 JSON。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + 主/分 requirements 均存在。
- 可维护性：包小而切分清楚；Makefile 把 unit 与容器 verify 分开。
- 安全性：subprocess 无 `shell=True` 命中。环境模板与「不覆盖已注入变量」可见。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/lyl2222/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L3 声明为 false
[E-2] `archive/generated/snapshots/lyl2222/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L22-L43 — transpile/run/agent_chat；`compile_hybrid` 明确 NotImplementedError
[E-3] `archive/generated/snapshots/lyl2222/starter_kit/loomq/execution.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L93-L137 — 隔离 `sdk_worker` 的 subprocess 调用与超时
[E-4] `archive/generated/snapshots/lyl2222/starter_kit/web_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L75 — 零依赖 Web；`.env` 只填补缺失变量；`/chat` 走 `adapter.agent_chat`
[E-5] `archive/generated/snapshots/lyl2222/starter_kit/Makefile`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L11 — `verify` 走 docker；`unit` 走 unittest
[E-6] `archive/generated/snapshots/lyl2222/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L47 — 真机两平台 job ID 与文件路径；L3 bonus 未勾选
[E-7] `archive/generated/snapshots/lyl2222/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L10 — 本地验证命令与「不要提交 .env」

### 结论置信度
- 总体 **B**：L3 缺席可确认；L1/L2 结构与隔离执行可确认；隔离 worker 与真机结果无法静态验证。
- 无法静态确认：三隔离环境在 Docker 中是否构建成功、位序/隐藏电路、L2 正式用例、真机真实性、Web 体验、排名。

## 9. `Jimmy658`

### 身份与路径
- 选手标识：`Jimmy658`
- snapshot 相对路径：`archive/generated/snapshots/Jimmy658/`
- 上游 URL：`https://github.com/Jimmy658/LoomQ-2026`
- 上游 SHA：`a006046090dbe71e51e2ad8204020b00de11b648`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：49 个文件 / 24 个 Python 文件；证据计数 1、测试计数 4

### 技术栈与结构
- 静态技术栈：Python 3.10 + 量子 SDK（Scout，A）。adapter 文档写明 L1 自研解析与 statevector，`run` 不依赖 SDK（A）。`requirements.txt` 仍为 starter 占位（A）。L2 走 `llm_client` + `LOOMQ_LLM_*`（B）。
- 目录与模块地图：
  - 入口：`adapter.py`（L1 实现内嵌）；`beginner_cli.py`；Scout 列 `l2_agent.py`
  - 核心：adapter 内 `CircuitIR`/`GateOp`；`l2_agent.py`；`l3_hybrid_compiler.py`
  - Web/CLI：beginner CLI 菜单，无 Web
  - 硬件适配：未见独立硬件 runner；证据未勾选真机
  - 证据文件名：`starter_kit/evidence/README.md`（无 `files/` 附件）
  - 测试文件名：`tests/test_submission_tools.py`、`tests/test_l2_contract.py`；`starter_kit/examples/l2_real_api_smoke_test.py`、`l2_real_api_robustness_test.py`、`beginner_cli_checks.py`、`l1_local_checks.py`、`l2_local_checks.py`、`l3_local_checks.py`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（B）：根 README 是选手方案，定位 Beginner Assistant；强调「LLM 输出不等于正确程序」，由确定性代码与 L1 校验。`ARCHITECTURE.md` 用流程图画出 CLI→agent→L1 与独立 L3。
- 源码静态可见实现（A）：`transpile`/`run` 在 adapter 内完成 parse/emit/simulate。`agent_chat` 转 `l2_agent.agent_chat_impl`：源码静态可见正式模式的 LLM 调用点（意图理解，以及可选的 QASM 修复调用）；已知任务（Bell/GHZ）与后端选择由确定性逻辑收口；无 LLM 配置时走本地路径。未验证模型是否实际接触、请求是否发出或完成。`compile_hybrid` 转 `l3_hybrid_compiler.compile_hybrid_impl`。`beginner_cli.py` 只调用 `adapter.agent_chat`。
- 静态架构：自然语言 → CLI → `agent_chat` → LLM 理解 + 已知任务生成器/修复 → L1 parser/simulator 校验 → 文本。L1：QASM → CircuitIR → OpenQASM2/3 或 OriginIR / 本地 counts。L3：classical tokenizer/parser → Tiny RISC-V。文档与模块职责一致（B）。
- L1/L2/L3 实现面可见。证据仅勾选 L2 交互与工程化。不推断得分。

### 优点
- 根 README + `ARCHITECTURE.md` 把产品对象与校验边界写清楚。
- L1/L2/L3 文件职责分离；CLI 不绕过 adapter。
- L2 明确 `MAX_TOTAL_LLM_CALLS = 2` 与语义 fidelity 阈值常量（存在不等于有效）。
- `examples/` 含本地检查与「real api」命名的冒烟/鲁棒脚本。
- beginner CLI 用 `getpass` 读密钥且检查脚本断言密钥不打印。

### 质量问题与风险
- 额外 Python：`beginner_cli.py`、`l2_agent.py`、`l3_hybrid_compiler.py` 以及 `examples/` 下多份 local/real-api 检查脚本。
- `requirements.txt` 无已钉第三方包；L1 可自洽，但与 Scout「量子 SDK」标签的关系主要是文档/能力表，不是锁定依赖。
- 证据无真机附件，L1 真机 / RISC-V / 新手引导未勾选。
- L1 全部逻辑堆在 `adapter.py`，文件较长，可维护性弱于分包方案。
- 需复核的静态命中：`prepare_submission.py` subprocess；公开测试 importlib/http.server。`examples/beginner_cli_checks.py` 含硬编码测试口令字符串，fact card 标为 `hardcoded_keyish`——静态可见为合成测试值 `test-secret-not-real`，不是生产凭据；仍属凭据处理测试路径，需复核是否被误提交到正式环境。
- 根 `tests/` 仍以公开契约为主，L1 解析器缺少独立测试目录。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + requirements（空模板）均存在。
- 可维护性：架构文档好；L1 单体 adapter 偏重。CLI 与 L3 分离是加分项。
- 安全性：密钥经 getpass、示例脚本使用假口令。在该 SHA 受检路径下未静态发现真实密钥文件。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/Jimmy658/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L72 — Beginner Assistant 方案、CLI 菜单、L2 环境变量表
[E-2] `archive/generated/snapshots/Jimmy658/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L40 — L1/L2/L3 责任分离与数据流
[E-3] `archive/generated/snapshots/Jimmy658/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L96 — 内嵌 IR 与模拟器；L2/L3 委托
[E-4] `archive/generated/snapshots/Jimmy658/starter_kit/l2_agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L80 — 正式模式强制 LLM 理解 + 确定性收口
[E-5] `archive/generated/snapshots/Jimmy658/starter_kit/l3_hybrid_compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L50 — 独立 L3 AST 节点
[E-6] `archive/generated/snapshots/Jimmy658/starter_kit/beginner_cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L34 — CLI 只经 adapter；getpass
[E-7] `archive/generated/snapshots/Jimmy658/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 仅 L2 交互与工程化勾选
[E-8] `archive/generated/snapshots/Jimmy658/starter_kit/examples/beginner_cli_checks.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L201-L217 — 合成测试口令路径；断言不打印密钥

### 结论置信度
- 总体 **B**：方案文档与 L1/L2/L3 符号完整；无锁定 SDK、无真机、L1 测试面偏薄。
- 无法静态确认：自研模拟器正确性、L2 已知任务覆盖正式用例、L3 汇编可执行性、CLI 体验、排名。

## 10. `tale03`

### 身份与路径
- 选手标识：`tale03`
- snapshot 相对路径：`archive/generated/snapshots/tale03/`
- 上游 URL：`https://github.com/tale03/LoomQ-2026`
- 上游 SHA：`d3edb684d4ac975d1d6ac08a0186efd642738e2a`
- starter 目录名：`starter_kit`
- 文件规模（fact card）：51 个文件 / 17 个 Python 文件；证据计数 5、测试计数 4

### 技术栈与结构
- 静态技术栈：Python 3.10 + Flask + HTML + 量子 SDK（Scout，A）。`requirements.txt` 钉 `spinqit==0.2.4`、`amazon-braket-sdk==1.110.1`、`pyqpanda==3.8.5`、`flask==3.1.3`（A）。
- 目录与模块地图：
  - 入口：`app.py`（Flask）；评测入口仍是 `adapter.py`
  - 核心：L1/L2/L3 均写在 `adapter.py`（537 行）
  - Web/CLI：`templates/index.html` + `static/`；README 声称 `python app.py` → `http://localhost:5000`
  - 硬件适配：`run` 调 Braket LocalSimulator / spinqit BasicSimulator / pyqpanda；证据含 SpinQ Cloud 与悟空 JSON
  - 证据文件名：`evidence/README.md`；`files/originq-circuit.qasm`、`originq_wukong_result.json`、`spinq-circuit.qasm`、`spinq_cloud_result.json`
  - 测试文件名：`tests/test_submission_tools.py`、`tests/test_l2_contract.py`；`starter_kit/test_l3.py`；`starter_kit/circuits/test_all_gates.qasm`
- `submission.yaml` 声明：L1/L2/L3 均为 `true`。

### 方案概述
- README 声称（C/B）：根 README 前部将作品命名为「Qat / 喵子」，声称中英自然语言 → QASM → 三后端 → 猫主题结果展示，并列出 L1 真机两台、L2 智能体、L3、自定义 RISC-V、双语前端。后半拼接赛题模板。AI 辅助声明写明前端由 Claude 协助、核心逻辑由参赛者实现（文档声称，C）。
- 源码静态可见实现（A）：`transpile` 按行做字符串替换（OPENQASM 2→3、qreg→qubit、cx→cnot、cu1 展开等），**未见独立 Circuit IR**。`run` 先 `transpile` 再调各 SDK；SpinQ 把**原始** `qasm_str` 写入临时文件交给编译器。`agent_chat` 直接 `chat_completion` + 长 system prompt（角色「喵子/Qat」、12 门、后端能力）。`compile_hybrid` 用花括号/分号替换做行切分，再 `translate_assignment` / `translate_classical` 拼 RISC-V。
- 静态架构：Web POST `/chat` → `adapter.agent_chat`；POST `/run` → `adapter.run`。与「IR 中间层」类方案不同，本快照 L1 以文本改写为主。文档「通用中间层」是声称（C）；源码可见的是按 target 分支的行变换（A）。
- L1/L2/L3 实现面：均在 adapter 内可见；另有 `quantum_riscv_spec.md`。证据五项均勾选。不推断得分。

### 优点
- 根 README 有明确产品名、启动命令与 AI 辅助声明。
- 依赖四包均精确钉版本。
- 真机证据同时给出 SpinQ 与 OriginQ 的 job ID、QASM 与 JSON 路径。
- Flask 路由很薄，评测契约与 UI 共用 adapter。
- 存在 `test_l3.py` 与 `test_all_gates.qasm` 作为额外静态测试资产。

### 质量问题与风险
- L1 以逐行字符串改写实现，缺少共享 IR；对空白、多寄存器、非预期格式的稳健性无法静态确认。
- `adapter.py` 还包含 `convert_var` / `translate_assignment` / `translate_classical` 等 L3 辅助符号。
- `app.py` 在 `__main__` 使用 `app.run(debug=True, port=5000)`——Flask debug 监听命中，需复核（不是已确认漏洞）。
- `/chat` 与 `/run` 直接读取 `request.json[...]`，未见鉴权或速率限制（静态观察）。
- adapter 同时承担转译、执行、agent、L3，可维护性弱。
- 需复核的静态命中：Flask debug；`prepare_submission.py` subprocess；adapter 文件头模板提及 subprocess（实现未调用）。临时 QASM 文件写入 `/run` 的 spinq 路径。
- 根 README 后半赛题模板残留。starter README 仍为 v1.1.0 模板。

### 完整性 / 可维护性 / 安全性观察
- 完整性：契约四件套 + Dockerfile + 钉版本 requirements 均存在。
- 可维护性：产品文档较好，代码结构偏单文件；L1 与文档「中间层」表述不完全同构。
- 安全性：debug 模式、JSON 直接取值、临时文件为需复核项。证据 JSON 只记录路径，不复制内容。在该 SHA 受检路径下未静态发现密钥文件。无可执行 shell 记录。

### 关键证据位置
[E-1] `archive/generated/snapshots/tale03/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L36 — Qat/喵子产品说明、`python app.py`、L1/L2/L3 功能列表、AI 辅助声明
[E-2] `archive/generated/snapshots/tale03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L18-L106 — braket/spinq 分支的行级字符串转译
[E-3] `archive/generated/snapshots/tale03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L176-L238 — `run` 调 LocalSimulator / spinqit 临时文件执行
[E-4] `archive/generated/snapshots/tale03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L295-L329 — L2 system prompt 与 `chat_completion`
[E-5] `archive/generated/snapshots/tale03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L497-L518 — L3 花括号切分
[E-6] `archive/generated/snapshots/tale03/starter_kit/app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L25 — Flask `/` `/chat` `/run`；`debug=True`
[E-7] `archive/generated/snapshots/tale03/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L49 — 五项勾选；SpinQ `G-260818-0009` 与悟空 job 路径
[E-8] `archive/generated/snapshots/tale03/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L4 — spinqit/braket/pyqpanda/flask 钉版本
[E-9] `archive/generated/snapshots/tale03/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true，Python 3.10

### 结论置信度
- 总体 **B**：Web 入口、依赖锁定、真机文件与单文件实现均可静态观察；行级转译的正确性与 Flask debug 运行面无法确认。
- 无法静态确认：三后端转译/位序、L2 正式三类任务、L3 汇编可执行性、真机结果真实性、Flask 服务行为、排名。

## 11. `AzureWynn`

### 身份与路径

- contestant_id：`AzureWynn`
- snapshot：`archive/generated/snapshots/AzureWynn/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/AzureWynn/LoomQ-2026` @ `68935f8e5c7328fde5ee4e6a9841852191826687`
- starter 目录名：`starter_kit/`（下划线）
- 规模：60 个文件，24 个 `.py`；扩展名还含 `.md` 14、`.json` 5、`.qasm` 4、可执行 `.sh` 2
- 测试 3、证据 6、Web 文件计数 1（赛题 HTML，非产品站点）
- yaml 声明：L1/L2/L3 全 true；可见实现含 `agent.py`/`hybrid.py`/`backends.py`，无 `NotImplementedError` 占位
- 评测契约入口：`starter_kit/adapter.py`（`submission.yaml` `entrypoint`）
- 适配器类型：CLI（`cli.py`）+ 硬件脚本（`real_machine.py`）；无独立 HTTP 服务

### 技术栈与结构

静态可见 Python 3.10、Qiskit/Braket/SpinQ/OriginQ SDK 名、OpenAI-compatible LLM 客户端。根目录保留赛题发布包与 `competition/`，实现集中在 `starter_kit/`。额外模块包括 `backends.py`（Strategy/Factory）、`qasm_parser.py`、`normalize.py`、`agent.py`、`cli.py`、`hybrid.py`、`real_machine.py`、`riscv_quantum_emulator.py`。根级 `setup_local.sh`、`retry_originq.sh` 为 Git mode `0755` 可执行 Shell，仅记录路径，未执行。存在 `.env.example`，未见随仓真实密钥文件。Dockerfile 与 `evaluator.py`、`llm_client.py` 仍在 starter 根，符合工具包基线。公开电路 `circuits/bell.qasm`、`ghz3.qasm` 与证据 QASM 并存。

### 方案概述

`submission.yaml` 声明 L1/L2/L3 均为 `true`，`network.required_for_l2: true`。`adapter.py` 将 `transpile`/`run` 委派给 `get_backend(target)`，`compile_hybrid` 委派 `hybrid.py`；`agent_chat` 以模块导入方式从 `agent.py` 再导出。starter README 声称同一套 OpenQASM 2.0 驱动量旋/本源/Braket 本地模拟器，L2 带生成→自验→重试闭环，L3 编译 Hybrid-QASM 经典块，Bonus 扩展量子 RISC-V。根 README 仍是赛题发布包模板，产品叙述在 `starter_kit/README.md` 与 `ARCHITECTURE.md`。CLI 候选入口为 `cli.py`；未见独立 Web 服务（`web_files` 仅赛题 HTML）。硬件路径在 `real_machine.py`，凭据走环境变量。`hybrid.py` 自写 tokenizer，把 `r1..r9`/`c[k]` 映射到 Tiny RISC-V 寄存器。yaml 声明与可见 `agent.py`/`hybrid.py`/`backends.py` 一致，不存在 Level 勾选但函数仍 `NotImplementedError` 的情况。

### 优点

- adapter 薄、后端可替换：L1 契约与 Strategy 类分离，位序归一化集中在 `normalize.py`。
- L2 以装饰器重试 + 任务分类（生成/修复/选后端）组织，环境未配置时文档声称可降级到确定性生成。
- 依赖 `requirements.txt` 精确钉死 `spinqit==0.2.4`、`pyqpanda==3.8.5`、`amazon-braket-sdk==1.90.2`。
- 证据清单五项均勾选；`evidence/files/` 可见 SpinQ Cloud 的 QASM 与 result JSON。
- Bonus 模拟器文件与 `riscv_quantum_spec.md`、`test_quantum_riscv.py` 成套出现。

### 质量问题与风险

- 根 README 未描述本提交架构，导航需读 starter README，易与模板包混淆。
- `backends.py` 的 `run_raw` 直接 `import spinqit` / `pyqpanda`；无 SDK 时 `run()` 行为无法静态确认。
- `real_machine.py` 同时描述 SpinQ 与 OriginQ，但 `evidence/files/` 静态列表仅见 `spinq-cloud-*`；第二平台是否随 commit 归档无法静态确认。
- 风险模式命中（需复核，非已确认漏洞）：`prepare_submission.py` 的 `subprocess`；测试里的 `importlib`；`riscv_quantum_emulator.py` / `backends.py` 的 `listen`/`run` 字面匹配。
- 可执行 Shell `setup_local.sh` 会 `uv pip install` 并 `import spinqit`；本阶段未执行。
- `cli.py` 在展示 counts 时打印 “fidelity 自检通过”：这是产品文案，**无法静态确认**自检是否每次发生或阈值多少。
- `backends.py` 注释写 “Verified 2026-08-17 against local simulators”：属源码自称，未在本阶段复现。

### 完整性 / 可维护性 / 安全性观察

契约函数 `transpile`/`run`/`compile_hybrid` 静态可见；`agent_chat` 经导入再导出，与 yaml `l2: true` 一致。测试 3 份（根 `tests/` + `test_quantum_riscv.py`），公开 evaluator 仍在 starter 中。`.env.example` 使用占位符，未复制其内容。硬件脚本要求密钥文件位于仓外。模块职责清楚，adapter 仅 54 行，可维护性较好。可运行性、真机 job 真实性、自验闭环是否在正式评测中触发模型调用、macOS rpath 补丁在 Linux 评测镜像是否有副作用，均无法静态确认。

对照口径：根 README 多为赛题发布包；产品主张以 starter README / ARCHITECTURE 为准。
未打开 PDF/PNG/媒体，也未把证据 JSON 的存在写成真机已验证。
未执行 `setup_local.sh` / `retry_originq.sh`。

### 关键证据位置

- [E-1] `archive/generated/snapshots/AzureWynn/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 声明 L1/L2/L3 全 true，入口 `adapter.py`，L2 需网络与 `LOOMQ_LLM_*`
- [E-2] `archive/generated/snapshots/AzureWynn/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L54 — 薄入口：导入 `agent_chat`，`transpile`/`run` 走 backend factory，`compile_hybrid` 转发
- [E-3] `archive/generated/snapshots/AzureWynn/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L14 — README 声称 L1 三后端中间层、L2 闭环、L3 与量子 RISC-V Bonus
- [E-4] `archive/generated/snapshots/AzureWynn/starter_kit/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 零基础 CLI 候选入口，调用 `agent.agent_chat`
- [E-5] `archive/generated/snapshots/AzureWynn/starter_kit/real_machine.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L18 — 硬件提交脚本，凭据来自环境变量
- [E-6] `archive/generated/snapshots/AzureWynn/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 五项人工评分框均为 `[x]`

### 结论置信度

结构、yaml 字段与契约函数签名为高（A）。README 与模块划分互证为中（B）。SDK 本地模拟、真机回执、L2 降级路径与 Shell 安装结果无法静态确认（C）。本段未运行、未安装、未联网。

## 12. `hongwei-2026`

### 身份与路径

- contestant_id：`hongwei-2026`
- snapshot：`archive/generated/snapshots/hongwei-2026/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/hongwei-2026/LoomQ-2026` @ `3abe28253ea2965cda4b7d1463ba70d133b84a3c`
- starter 目录名：`starter_kit/`
- 规模：57 个文件，23 个 `.py`；`.qasm` 6、`.json` 7
- 测试 3、证据 7、无 `.env*`、无可执行 Shell
- yaml 声明：L1/L2/L3 全 true；`requirements.txt` 无钉死安装行，与“标准库默认路径”叙述一致
- 入口：`starter_kit/adapter.py`；产品文档另见 `PRODUCT.md`
- 适配器类型：CLI（`loomq_cli.py`）+ stdlib Web（`loomq_web.py`）+ 云脚本；adapter 默认不调云

### 技术栈与结构

Python 3.10，静态命中 qiskit/braket/spinq/originq 与 openai/deepseek 字面。核心不在三套 SDK 硬编码，而在 `loomq_core.py` 自研 IR + 态矢模拟。额外模块：`loomq_agent.py`、`loomq_cli.py`、`loomq_web.py`、`run_origin_cloud.py`、`run_spinq_cloud.py`、`selftest_extra.py`、`test_quantum_riscv.py`。根 README 为赛题模板；starter README 主体仍是工具包说明，产品叙事在 `PRODUCT.md`。无 `.env*`、无可执行 Shell。Web 不占独立 html 文件（页面字符串写在 py 内），故 inventory `web_count=1` 只统计赛题 HTML。另有 `QUANTUM_RISCV.md` 与 `test_quantum_riscv.py`。

### 方案概述

yaml 声明 L1/L2/L3 全 true。`adapter.transpile`/`run` 默认走 `loomq_core` 解析与 `simulate_counts`；仅当环境变量 `LOOMQ_USE_NATIVE_SDK` 为真时才尝试 `_run_braket/_run_spinq/_run_originq`，异常则静默回落到自研模拟器。`agent_chat` 内含最多 3 次 LLM 尝试与 QASM 自验，并对 recommend 任务拼接确定性 backend id。`loomq_web.py` 用标准库 `ThreadingHTTPServer` 绑定 `127.0.0.1:8765`，页面内嵌 HTML，POST 表单触发 `agent_chat` 再 `adapter.run`。云端脚本分别提交 SpinQ / OriginQ。`requirements.txt` 仅注释可选 SDK 版本（braket 1.90.1、spinqit 0.2.2、pyqpanda 0.3.2.288 出现在注释中），无已安装钉死行。这与 AzureWynn 的精确 pin 策略不同：本提交默认路径宣称标准库即可。

### 优点

- L1 语义源明确写成“一份 parser/simulator”，目标后端只做序列化。
- 同时提供 CLI（`loomq_cli.py`）与 stdlib Web（`loomq_web.py`），Web 对 HTML 做了 `&`/`<` 转义。
- 证据五项勾选；`evidence/files/` 含 `spinq-circuit.qasm` 与 `originq-circuit.qasm`。
- 云端脚本把用户名/私钥路径放在环境变量，默认私钥探测 `~/.ssh`，不把密钥写入仓内。

### 质量问题与风险

- `requirements.txt` 没有实际 `package==` 行；若评测镜像不预装 SDK，原生路径无法静态确认，而默认路径依赖自研模拟器。
- `run()` 在原生 SDK 分支 `except Exception: pass`，失败原因被吞掉，排障困难。
- `loomq_core.eval_angle` 对过滤后的算术串调用 `eval(..., {"__builtins__": {}})`：需复核，不是已确认 RCE。
- `listen` 命中 `adapter.py`、`loomq_web.py` 的 `serve_forever`：本地 HTTP 服务，需复核绑定与输入面。
- starter README 目录树未列出 `loomq_*.py` / `PRODUCT.md`，文档与实现不完全同步。
- Web 把异常 `str(exc)` 写入 HTML：需复核是否可能回显内部路径；对 reply 做了转义，对 exception 路径需复核。
- `selftest_extra.py` 存在，是否被 evaluator 调用无法静态确认。

### 完整性 / 可维护性 / 安全性观察

契约四个函数均在 `adapter.py` 定义。测试 3 份偏工具包合同，另有 `selftest_extra.py`。Web 默认 loopback。硬件是独立脚本而非 `adapter.run` 的默认路径。核心 IR 集中在 `loomq_core.py`，L2 辅助在 `loomq_agent.py`，结构中等可维护。自研模拟器与官方隐藏用例是否一致、云端 job 是否真实、原生 SDK 开关在评测中是否开启，无法静态确认。`PRODUCT.md` 标题含竞赛口号为文档自称，不构成成绩判断。

对照口径：starter README 目录树仍是工具包模板，产品入口以 `PRODUCT.md` 与 `loomq_*.py` 为准。
未执行 Web 或云脚本，未开启 `LOOMQ_USE_NATIVE_SDK`。
`eval_angle` 仅作需复核记录。

### 关键证据位置

- [E-1] `archive/generated/snapshots/hongwei-2026/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 全 true，L2 需网络
- [E-2] `archive/generated/snapshots/hongwei-2026/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L33-L70 — `transpile`/`run`；原生 SDK 由环境开关控制并回落态矢引擎
- [E-3] `archive/generated/snapshots/hongwei-2026/starter_kit/loomq_core.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L22-L31 — 角度表达式经字符白名单后 `eval`
- [E-4] `archive/generated/snapshots/hongwei-2026/starter_kit/loomq_web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L113-L121 — CLI/Web：缺 `LOOMQ_LLM_*` 则退出；HTTP 绑 127.0.0.1
- [E-5] `archive/generated/snapshots/hongwei-2026/starter_kit/PRODUCT.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L26 — README 声称的一分钟启动与 `python loomq_web.py`
- [E-6] `archive/generated/snapshots/hongwei-2026/starter_kit/run_spinq_cloud.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L42 — SpinQ 云提交读环境用户名与私钥路径

### 结论置信度

yaml 与 adapter 控制流为高（A）。“统一 IR + 可选原生 SDK”为中（B）。原生 SDK 回落是否掩盖错误、Web/云脚本运行结果无法静态确认（C）。本段未运行、未安装、未联网。

## 13. `zhangxinyang-z`

### 身份与路径

- contestant_id：`zhangxinyang-z`
- snapshot：`archive/generated/snapshots/zhangxinyang-z/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/zhangxinyang-z/LoomQ-2026` @ `68e297ff2f37198503fb4a65e498f026680af2ba`
- starter 目录名：`starter_kit/`
- 规模：53 个文件，21 个 `.py`；根 `tests/` 2 + starter `tests/` 2（inventory 测试计数 5）
- 证据 6；`BEGINNER_GUIDE.md` 存在
- yaml 声明：L1/L2/L3 全 true；L1 执行路径为进程内态矢，不调用 SDK
- 入口：`adapter.py`；交互 CLI：`chat.py`；硬件仅 `examples/`

### 技术栈与结构

Python 标准库实现 L1 解析/态矢模拟，无强制第三方运行时依赖。额外模块：`chat.py`，`examples/run_originq_qpu.py`、`run_spinq_cloud_qpu.py`，`tests/test_adapter_transpile.py`、`test_quantum_riscv_extension.py`。另有 `BEGINNER_GUIDE.md`（文件存在，与 README 链接一致）、`ARCHITECTURE.md`、`RISCV_QUANTUM_EXTENSION.md`。根 README 为赛题模板；starter README 在工具包正文中插入了 L2 CLI 说明。inventory 测试计数 5，含 starter 内测试。证据 6 项文件。

### 方案概述

yaml L1/L2/L3 全 true。`adapter.py` 自包含约 286 行：`_parse`/`_simulate`/`_counts` 做 L1，`transpile` 对 spinq 直接返回原 QASM 字符串，对 braket 拼 QASM3，对 originq 拼 OriginIR；`run` 调用 `transpile` 后仍用 `_counts` 填 schema，不执行厂商引擎。`agent_chat` 直接调 `llm_client.chat_completion`，带一次格式修复重试，不把 QASM 再送回 L1 模拟器做保真度闭环。`compile_hybrid` 在同文件后部用嵌套函数切 classical 块。`chat.py` 是零基础 CLI，失败时指向 `BEGINNER_GUIDE.md`。硬件示例脚本使用 `ORIGINQ_API_KEY` 等环境变量，并把 key 前缀打印到 stdout。

### 优点

- L1 无第三方依赖，adapter 单文件可读，便于对照题面门集。
- 提供 `chat.py` 直方图预览与中文恢复提示，以及 `BEGINNER_GUIDE.md`（文件确实存在）。
- 证据五项勾选；`evidence/files/` 含 SpinQ QASM/result 与三份 L2 文本输出。
- starter 内自测覆盖 transpile 与量子 RISC-V 扩展。

### 质量问题与风险

- `_expr` 对白名单字符调用 `eval`：需复核。
- `run()` 的 `job_id` 使用 `hash(qasm_str)`，CPython 盐化哈希使 ID 跨进程不稳定。
- L2 主要把模型原文返回，缺少与 L1 parser 的强制闭环（与部分选手不同）；行为无法静态确认。
- `run_originq_qpu.py` 打印 API key 前 8 位：需复核日志泄露面（值为环境注入，未见仓内明文密钥）。
- 根 README 仍是发布包，不指向 `chat.py`。
- `transpile(spinq)` 返回原始 `qasm_str.strip()`，与“规范化 IR 再发射”的部分选手不同；是否满足 `target_ir_contract.md` **无法静态确认**。
- 单文件同时承担 parser/simulator/L2/L3，行密度高，后续改门集易漏。

### 完整性 / 可维护性 / 安全性观察

yaml 与四个契约函数同文件齐全。L1 三目标序列化静态可见；执行路径不调用厂商 SDK。硬件只在 `examples/`。测试数量相对实现规模尚可。`BEGINNER_GUIDE.md` 与 `chat.py` 交叉引用成立。模拟分布、LLM 修复质量、真机脚本是否在赛程内跑通、打印 key 前缀的实际日志，无法静态确认。

对照口径：`chat.py` 与 `BEGINNER_GUIDE.md` 交叉引用成立。
未把 `examples/*qpu*` 当成 adapter 默认路径。
`eval` 角度解析与 `hash(qasm)` job_id 仅作需复核记录。

### 关键证据位置

- [E-1] `archive/generated/snapshots/zhangxinyang-z/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/zhangxinyang-z/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L19 — 角度 `eval` 带空 `__builtins__` 与字符白名单
- [E-3] `archive/generated/snapshots/zhangxinyang-z/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L130-L152 — `transpile` 三方言；`run` 返回本地 counts
- [E-4] `archive/generated/snapshots/zhangxinyang-z/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L154-L213 — `agent_chat`：系统提示 + 一次 QASM 格式重试
- [E-5] `archive/generated/snapshots/zhangxinyang-z/starter_kit/chat.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L37 — CLI 入口与 `BEGINNER_GUIDE.md` 恢复文案
- [E-6] `archive/generated/snapshots/zhangxinyang-z/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L82-L91 — README 声称 `python -m starter_kit.chat`

### 结论置信度

单文件契约与 yaml 为高（A）。“依赖自由 L1 + LLM 直出 L2”为中（B）。正确性、真机、L2 重试是否足够，无法静态确认（C）。本段未运行、未安装、未联网。

## 14. `xinruliuresearch-maker`

### 身份与路径

- contestant_id：`xinruliuresearch-maker`
- snapshot：`archive/generated/snapshots/xinruliuresearch-maker/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/xinruliuresearch-maker/LoomQ-2026` @ `dbe2f60f0da8e8f537c295b7f29d7d047a84f194`
- starter 目录名：`starter_kit/`
- 规模：143 个文件，84 个 `.py`；`.md` 30，Web 相关 html/css/js/svg
- 测试约 19、证据 9、Web 文件计数 4
- yaml 声明：L1/L2/L3 全 true；证据 **未勾选 L1 真机**
- 入口：`adapter.py` → `loomq` 包；Web `loomq.ui.server`；Bonus `loomq.bonus.demo`

### 技术栈与结构

分层 Python 包 `loomq/`：`qasm/`（lexer/parser/AST/normalize）、`targets/`、`runtime/`、`hybrid/`、`agent/`、`ui/`、`hardware/`、`bonus/`。adapter 仅 44 行转发。Web：`python -m loomq.ui.server`，stdlib HTTP + CSP 头。硬件：`loomq/hardware/{spinq,originq}.py` 与 `scripts/hardware/`。测试约 19 个 `test_*.py`。starter README 已改写为产品名 “LoomQ Pegasus”。静态资源含 `index.html`/`styles.css`/`app.js`/`mark.svg`。`scripts/run_l2_stub_evaluator.py`、`run_random_differential_tests.py` 为额外检查入口，未执行。

### 方案概述

yaml L1/L2/L3 全 true。README 声称正式离线路径用自研理想态矢参考模拟器，生成三目标方言但不冒充厂商 SDK；真机仅在有可核验 job ID 时申报。证据 README 明确 **未勾选 L1 真机**，并写明 hardware 测试不联网。`facade.run` 对 QASM 做 256KB 上限、shots∈[1,100000]，并用 SHA-256 派生模拟种子。`compile_hybrid` 同样有字节上限。UI 默认 127.0.0.1:8765，非 loopback 时打印无鉴权警告。README 用 mermaid 描述“自然语言→AST→三方言→参考执行→证据清单”；评测 adapter 保持无状态，产品界面才写请求级工作目录。这与 yaml `entrypoint: adapter.py` 不冲突。

### 优点

- 包边界清晰，adapter 不含业务逻辑；输入长度与 shots 有硬限制。
- UI 设置 CSP、`X-Frame-Options`、`nosniff` 等响应头。
- 测试面覆盖 qasm/hybrid/bonus/hardware/ui，并有 `scripts/run_all_checks.py`。
- 证据对 L1 真机保持未申报，与 README 真实性边界一致，避免口头宣称真机。
- Bonus `demo.py` 给出可阅读的量子 RISC-V 程序文本。

### 质量问题与风险

- 体量 84 个 py，评测阅读成本高；`run_all_checks.py` 使用 `subprocess`：需复核。
- `hardware/spinq.py`、`originq.py` 动态 `importlib`：需复核（设计上仅真实执行路径导入厂商包）。
- UI `do_OPTIONS` 与可配置 host：需复核跨源与绑定面。
- README 声称 “23/23 hardware tests”——测试文件存在，**结果无法静态确认**。
- 根 README 仍是赛题包，与 starter 产品 README 双轨。
- README 声称“不用 eval”：需与实现交叉时抽检 `loomq/qasm` 表达式求值，本阶段未逐行证明全包无 eval。
- `MAX_HTTP_BODY = 600_000` 大于 QASM 256_000 上限，UI 还可能传工作流 JSON：需复核。

### 完整性 / 可维护性 / 安全性观察

yaml 与四个契约函数齐全。L1 离线路径静态可见为自研 runtime；L2/L3/Bonus/Web 均有对应包。L1 真机未申报，与代码里的 dry-run/runbook 并存。凭证在 `SpinQCredentials.__repr__` 中标红。包内错误类型（`InputValidationError` 等）有利于契约失败信息。可运行性、参考模拟器与隐藏用例一致性、19 份测试是否通过，无法静态确认。

对照口径：L1 真机未勾选与 hardware dry-run 并存，不以脚本存在推断已提交 QPU job。
未运行 `run_all_checks.py`，未启动 8765 端口。
CSP 头为静态可见配置，不是已验证的浏览器行为。

### 关键证据位置

- [E-1] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L44 — 薄转发 + hybrid 256000 字节上限
- [E-3] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L24 — Pegasus 定位与 `python3 -m loomq.ui.server`
- [E-4] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/loomq/facade.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L15-L44 — L1 校验、种子化参考执行
- [E-5] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/loomq/ui/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L25-L44 — CSP 等安全头
- [E-6] `archive/generated/snapshots/xinruliuresearch-maker/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L15 — L1 真机未勾选，其余四项勾选

### 结论置信度

包结构、yaml、未申报真机为高（A）。“参考模拟器 + 审计工作流”为中（B）。测试通过与否、UI 体验、硬件 dry-run 之外的行为无法静态确认（C）。本段未运行、未安装、未联网。

## 15. `EndlessTR`

### 身份与路径

- contestant_id：`EndlessTR`
- snapshot：`archive/generated/snapshots/EndlessTR/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/EndlessTR/LoomQ-2026` @ `10febabd97785055f239d8f24716fb053d9f95b7`
- starter 目录名：`starter_kit/`
- 规模：110 个文件，29 个 `.py`；**.html 20**、**.png 18**、js/css 配套
- 测试 9、证据 26、Web 文件计数 24；存在 `.env.example`
- yaml 声明：L1/L2/L3 全 true；实现集中在超长 `adapter.py`
- 入口：`adapter.py`（单体）；Web：`quantumhelper_web/server.py`（默认 8000）

### 技术栈与结构

几乎全部 L1/L2/L3 逻辑写在 **4820 行、223 个 def/class** 的 `adapter.py` 中；Web 编排在 `quantumhelper_web/`（`server.py`、`web_agent.py`、`backend_selector.py`、`qasm_extract.py`、`runtime_config.py`、`selfcheck.py`）。starter README 在模板后追加 “QuantumHelper Web” 启动说明。存在 `quantumhelper_web/.env.example`。测试 9 份，证据文件 26。html/png 数量显著高于本批多数提交，属于重前端交互。`adapter.py` 同时定义 Gate/Circuit、角度 AST 求值、三后端 execute、L2 JSON 语义、Hybrid lexer/parser。

### 方案概述

yaml L1/L2/L3 全 true。adapter 文件头仍保留 starter 模板句 “intentionally contains no scoring implementation”，但随后实现完整解析、三后端 execute、L2 语义结构化与 Hybrid 编译。`agent_chat` 注释写明每个 case 先统一调用一次 LLM，以满足有效模型调用，并避免规则提前 return 导致 0 次调用。Web 默认 `HOST=127.0.0.1`、`PORT=8000`，可用环境变量改绑定；另有 `REQUESTS_PER_MINUTE=60`、`RUN_SLOTS` 信号量、`MAX_BODY_BYTES=128KiB`。README 声称需 `QUANTUMHELPER_ENABLE_LLM=1` 才启用真实 Agent，且生成 QASM 会再走 `parse_qasm` 与三目标 `transpile`。契约入口与 Web 编排分离，但业务仍在 adapter 单文件。

### 优点

- L2 Web 资源完整（多页 HTML/PNG），与 adapter 解耦的 HTTP 包装含超时/并发槽。
- `agent_chat` 对空 prompt、类型做校验；`run` 拒绝无测量电路。
- 证据五项勾选，附件量大（截图/页面）。
- 提供 `selfcheck.py` 与多份 `test_*.py` 面向 web 层。

### 质量问题与风险

- **可维护性**：近五千行单文件，模板头与实现矛盾，审查与回归成本高。
- `warnings.filterwarnings` 忽略 NumPy 初始化失败：可能掩盖环境问题。
- `server.py` 的 `HOST` 默认可被环境覆盖：需复核非 loopback 暴露。
- `runtime_config.load_env_file(.env)`：需复核本地密钥加载（example 存在，真实 `.env` 未随仓列出）。
- `listen`/`openai` 命中多处：服务与 LLM 客户端，需复核而非定罪。
- 角度求值使用 AST `evaluate(node)`（约 L166+）：需复核是否限制节点类型。
- `/agent.html` 兼容旧链接：路由与静态文件是否都存在需对照 `quantumhelper_web/static`，未打开全部 HTML。

### 完整性 / 可维护性 / 安全性观察

yaml 与契约函数（约 L3810+）齐全。Web 是明确 L2 交互面。L1 同时含内置模拟与可选 SDK 函数名（`run_spinq`/`run_originq`/`run_braket`）。单文件堆叠使缺陷定位困难，是本批最突出的可维护性观察。页面静态资源不能代替评测通过。可运行性、LLM 语义解析是否覆盖隐藏 case、速率限制是否在评测外生效，无法静态确认。

对照口径：adapter 文件头模板句与 4820 行实现并存，以函数定义为准。
未启动 QuantumHelper 端口，未加载 `.env`。
html/png 附件未打开、未当已验证 UX。

### 关键证据位置

- [E-1] `archive/generated/snapshots/EndlessTR/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/EndlessTR/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L39 — 模板头 + 实际 `SUPPORTED_TARGETS` 与 llm_client 导入
- [E-3] `archive/generated/snapshots/EndlessTR/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L3810-L3858 — 契约 `transpile`/`run`/`agent_chat` 起始
- [E-4] `archive/generated/snapshots/EndlessTR/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L139-L158 — README 声称 QuantumHelper 启动命令与 LLM 开关
- [E-5] `archive/generated/snapshots/EndlessTR/starter_kit/quantumhelper_web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L55 — HTTP 包装、定位 adapter、加载 `.env`
- [E-6] `archive/generated/snapshots/EndlessTR/starter_kit/quantumhelper_web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1818-L1830 — 默认 127.0.0.1:8000，`serve_forever`

### 结论置信度

文件体量、yaml、Web 入口为高（A）。“单体 adapter 实现全部 Level”为中（B）。功能正确性与 Web 安全配置运行态无法静态确认（C）。本段未运行、未安装、未联网。

## 16. `2IKK12`

### 身份与路径

- contestant_id：`2IKK12`
- snapshot：`archive/generated/snapshots/2IKK12/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/2IKK12/LoomQ-2026` @ `bdb6d4b6b8631b0e56e81a03b263077ea119fa7e`
- starter 目录名：`starter_kit/`
- 规模：87 个文件，27 个 `.py`；png 21、证据 29
- 测试 8、Web 文件计数 4
- yaml 声明：L1/L2/L3 全 true；硬件网关不在默认 `adapter.run`
- 入口：`adapter.py`；Web：`web_app.py`；Agent：`loomq_agent.py`

### 技术栈与结构

L1 在 `loomq_l1.py`，L2 在 `loomq_agent.py`，L3 在 `hybrid_compiler.py`，Bonus 在 `quantum_riscv.py`。adapter 41 行转发。`web_app.py` 为 stdlib `ThreadingHTTPServer`，静态根 `web/`。`hardware_runner.py` 可选 AWS Braket QPU，默认不进入 adapter。根 `tests/` 另有 `test_l1.py`、`test_l2_agent.py`、`test_l3.py`、`test_web_app.py`、`test_quantum_riscv.py`。starter README 从首行起写本队实现说明，并链到 `docs/L1_ARCHITECTURE.md`、`docs/L2_AGENT.md`、`docs/L3_HYBRID.md`、`docs/REAL_HARDWARE.md`、`docs/QUANTUM_RISCV_EXTENSION.md`。证据 29 份、png 21 张，体量偏证据展示。

### 方案概述

yaml L1/L2/L3 全 true。README 声称 `run()` 用无依赖态矢执行器；L2 以官方能力表做后端选择，生成 QASM 经 L1 校验并最多一次 validator 引导修复；Web 可带有界多轮历史，但正式 `agent_chat(prompt)` 保持无状态。Web 默认 `127.0.0.1:8765`。真机网关默认关闭，需 SDK + 环境 ARN/S3，且 ARN 必须含 `/qpu/`。证据五项勾选。`loomq_l1.py` 用 `SUPPORTED_GATES`/`GATE_ARITY` 白名单，并 `hashlib` 参与 job 标识。L3 注释称量子部分由 L1 校验而非当纯文本。

### 优点

- 模块按 Level 切开，adapter 无业务；文档分 L1/L2/L3/硬件。
- Web 明确 `vendor_execution_verified: False`，避免把转译输出写成厂商已执行。
- 硬件路径拒绝用云模拟器 ARN 冒充 QPU。
- 请求体上限 `MAX_REQUEST_BYTES = 256KiB`。
- 测试文件覆盖 L1/L2/L3/Web/量子 RISC-V。

### 质量问题与风险

- `--host` 可改绑定：需复核。
- `hardware_runner` 在 Web POST 中可触发付费 QPU：需复核确认/鉴权（代码注释要求二次确认，**交互是否强制无法静态确认**）。
- `listen` 命中 `web_app.serve_forever`。
- 大量 PNG 证据存在不等于已核验。
- adapter 文件头仍是 starter 免责声明，与转发实现并存。
- Web POST 500 响应拼接 `type(exc).__name__: {exc}`：需复核错误信息面（注释称 LLM 客户端不含凭据）。
- `l2_smoke_test.py` 存在于 starter，与根测试关系无法静态确认。

### 完整性 / 可维护性 / 安全性观察

yaml 与可见实现一致。L1/L2/L3/Bonus/Web/可选硬件均有文件。密钥不进浏览器的声称与 `hardware_runner` 只读环境变量相符。Web 多轮历史与评测无状态接口分离，设计意图清楚。文档树完整，可维护性较好。运行、付费提交、测试结果、截图是否对应本 SHA 的 UI，无法静态确认。

对照口径：正式 `agent_chat` 无状态，Web 多轮是产品层。
未调用 Braket QPU，未打开证据 PNG。
`--host` 可改绑定仅作需复核记录。

### 关键证据位置

- [E-1] `archive/generated/snapshots/2IKK12/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/2IKK12/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L41 — 转发 `loomq_l1` / `loomq_agent` / `hybrid_compiler`
- [E-3] `archive/generated/snapshots/2IKK12/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L3-L47 — README 声称 L1 管道、L2 闭环、Web 端口 8765、可选 Braket 网关
- [E-4] `archive/generated/snapshots/2IKK12/starter_kit/web_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L34-L57 — 转译证据标注非厂商执行
- [E-5] `archive/generated/snapshots/2IKK12/starter_kit/hardware_runner.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L68 — 可选 QPU，校验 ARN 含 `/qpu/`
- [E-6] `archive/generated/snapshots/2IKK12/starter_kit/web_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L207-L219 — 默认 host/port 与 `serve_forever`

### 结论置信度

分层文件与 yaml 为高（A）。Web/硬件边界叙述为中（B）。二次确认是否强制、QPU 是否真正调用，无法静态确认（C）。本段未运行、未安装、未联网。

## 17. `mayloveless`

### 身份与路径

- contestant_id：`mayloveless`
- snapshot：`archive/generated/snapshots/mayloveless/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/mayloveless/LoomQ-2026` @ `9b1fe15596f8c63f51ddd08caaa323ca51dbcf77`
- starter 目录名：`starter_kit/`
- 规模：234 个文件，100 个 `.py`；`.md` 69，`.tsx` 12，`.ts` 7
- 测试 38、证据 21、Web 文件计数 22
- yaml 声明：L1/L2/L3 全 true；证据五项勾选
- 入口：`adapter.py`；Web 前端 `web/src/main.tsx`；后端 `loomq/debug_web.py`

### 技术栈与结构

Python 包 `loomq/`（parser/IR/serializers/runners/l2_agent/l3/real_hardware）+ React/TypeScript 前端 `web/` + Bonus `bonus/quantum_riscv/` + 大量 `scripts/audit_*.py` 与 `tests/`。adapter 按 `__package__` 切换导入。README 已完全改写，含 Docker 复现命令与 Web 启动（示例把 host 设为 `0.0.0.0`）。证据 21、测试 38。另有 gif 4、originir、originq-cloud 扩展名文件。`debug_web.py` 默认 host `127.0.0.1:8765`，与 README Docker 示例的 `0.0.0.0` 不同，需同时记录。

### 方案概述

yaml L1/L2/L3 全 true。`transpile` 经统一 parser 再按目标 serializer；`run` 路由到 `run_spinq`/`run_braket`/`run_originq`。L2 要求模型只返回 JSON，含 115s case 时限、敏感文本脱敏、失败诊断写到 `runtime/l2-debug`（注释称不作为比赛证据）。还包含独立的 target-judge 系统提示，试图在不看候选 QASM 的情况下抽取纯态规格。Web 由 `debug_web` 提供 HTTP API 并可选 serve `web/dist`。`real_hardware.py` 通过 subprocess 调 `scripts/submit_spinq_cloud.py`，并隔离解释器以免 ANTLR 冲突。README 声称 clean Docker 公开审计 75 passed——**不得当作正式分数，且本阶段未运行**。

### 优点

- 分层完整，测试与 audit 脚本数量在本批最多之一。
- L2 对 token/key 模式做红线脱敏，并分离 debug 目录与 evidence。
- README 区分公开审计记录与正式评测，未把 “75 passed” 写成官方分数（仍属文档自称，未运行）。
- 真机与 Bonus、教学解释器均有独立模块。
- 前端工程化（React StrictMode 入口）。

### 质量问题与风险

- Docker 文档使用 `--host 0.0.0.0`：需复核暴露面。
- `real_hardware` / 云提交 `subprocess`：需复核。
- `l2_agent` 动态写 debug trace：需复核日志是否可能含提示词或电路。
- 前端 `web/dist` 是否已构建进 snapshot：**无法静态确认**打包产物与 tsx 源同步。
- 体量 234 文件，认知负荷高；根 README 仍为赛题包。
- `l2_agent.py` 从 `starter_kit import llm_client` 再回退 `import llm_client`：双路径合理，但增加评测根切换复杂度。
- `MAX_REQUEST_BYTES = 64KiB`（debug_web）小于部分选手 Web 上限，属实现选择，不是缺陷。

### 完整性 / 可维护性 / 安全性观察

yaml 与契约函数齐全。L1 runners 静态指向三平台；是否在无 SDK 时回落无法仅凭 adapter 确认，需读各 runner（本阶段未宣称运行结果）。Web 同时存在 CLI debug 与 TS 应用。证据五项勾选。测试 38 份是完整性加分项，但执行结果无法静态确认。任何 Docker/单元测试数字均无法静态确认。

对照口径：README 中的 Docker 审计数字只作文档自称。
未构建镜像，未执行 unittest，未确认 `web/dist` 与 tsx 同步。
`0.0.0.0` 仅出现在 README Docker 示例。

### 关键证据位置

- [E-1] `archive/generated/snapshots/mayloveless/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/mayloveless/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L76 — 包/评测根双导入；三 serializer + 三 runner + L2/L3
- [E-3] `archive/generated/snapshots/mayloveless/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L36 — 产品概述与模块地图
- [E-4] `archive/generated/snapshots/mayloveless/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L68-L80 — README 声称 Docker Web 映射 8000→8765 且 host `0.0.0.0`
- [E-5] `archive/generated/snapshots/mayloveless/starter_kit/loomq/l2_agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L46-L54 — case 时限与敏感串脱敏正则
- [E-6] `archive/generated/snapshots/mayloveless/starter_kit/web/src/main.tsx`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L10 — React 前端入口
- [E-7] `archive/generated/snapshots/mayloveless/starter_kit/loomq/real_hardware.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — SpinQ 真机经 subprocess 隔离 SDK

### 结论置信度

仓库地图与 yaml 为高（A）。前后端分工为中（B）。审计数字、Docker、真机、前端构建态无法静态确认（C）。本段未运行、未安装、未联网。

## 18. `0Dionysus0`

### 身份与路径

- contestant_id：`0Dionysus0`
- snapshot：`archive/generated/snapshots/0Dionysus0/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/0Dionysus0/LoomQ-2026` @ `e9c273dab15447827df8ca093bdea43b6fef8101`
- starter 目录名：`starter_kit/`
- 规模：80 个文件，38 个 `.py`；png 6、html/js/css、ps1 2
- 测试 2、证据 12、Web 文件计数 4；仓内无 `.env`
- yaml 声明：L1/L2/L3 全 true；L1 包与 L2 包分离
- 入口：`adapter.py`；Web：`web_chat.py` → `loomq_l2/webapp.py`；CLI：`loomq_l2/cli.py`

### 技术栈与结构

L1 包 `loomq/`（qasm/ir/gates/targets/hybrid/simulate）；L2 独立包 `loomq_l2/`，避免覆盖 L1。adapter 按 target 字典分发 `emit`/`execute`。Web 默认端口 8877，stdlib HTTP，页面在 `web/`。存在 `.ps1` 辅助脚本（非 0755 可执行 shell 列表）。根与 starter README 仍偏模板，交互说明主要在模块 docstring。另有 `chat.py`、`loomq/riscv_quantum_emulator.py`、`loomq_l2/{deutsch,sessions,tasks,turn,viz,webapp}.py`。证据 12、png 6。

### 方案概述

yaml L1/L2/L3 全 true。`transpile`/`run` 经 `TARGETS[target]`。`agent_chat` 延迟导入 `loomq_l2.agent`。`compile_hybrid` 走 `loomq.hybrid.compile_program`。CLI 提供编号体验任务、条形图与环境未就绪的纯文本错误。`webapp._load_local_env` 若进程缺少键则读取 `starter_kit/.env` 或仓根 `.env`（注释称 gitignore）；snapshot 的 `env_like` 列表为空，故仓内无 `.env` 文件。Web 还加载 Deutsch 教程模块。证据五项勾选。starter README 未列出 `loomq/` 或 `web_chat.py`，与实现脱节属于文档问题而非缺文件。

### 优点

- L1/L2 包分离，adapter 注释说明协作边界。
- CLI 面向零基础：菜单、任务编号、读图说明。
- Hybrid 编译复用 L1 QASM 解析，避免第二套量子 parser。
- Web 对静态资源与 JSON API 分开；默认端口文档化。

### 质量问题与风险

- 风险清单命中 `web/main.js` 的 `exec(`：阅读为 **RegExp.exec**，不是动态执行；仍记需复核扫描假阳性。
- `.env` 自动灌入 `os.environ`：需复核本地密钥进入 Web 进程的方式（snapshot 未列出 `.env` 文件）。
- `listen` 命中 webapp/agent/turn：本地服务。
- starter README 未描述 `web_chat.py`/`loomq_l2`，与实现脱节。
- 根级测试仅工具包 2 份，相对 38 个 py 偏少。
- `web_chat.py` 把 starter 目录插入 `sys.path`：评测根切换时需注意与包导入并存。
- PowerShell 脚本仅记录路径，未读内容中的命令（避免把脚本当已执行）。

### 完整性 / 可维护性 / 安全性观察

契约函数齐全。Web/CLI/硬件相关文件（png、originir、csv）存在于证据区。`.ps1` 未执行。L1/L2 分包装降低协作冲突，可维护性中上。L2 agent 文件很长（listen 命中约 L627），维护面集中。交互体验与 Deutsch 教程页是否覆盖评分任务、`.env` 在开发机如何使用，无法静态确认。

对照口径：L1/L2 分包装是源码结构事实。
`.env` 加载逻辑存在但仓内无 `.env` 文件。
未启动 8877 端口；`RegExp.exec` 命中不是动态执行。

### 关键证据位置

- [E-1] `archive/generated/snapshots/0Dionysus0/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/0Dionysus0/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L56 — target 分发 + 延迟导入 L2 + hybrid
- [E-3] `archive/generated/snapshots/0Dionysus0/starter_kit/web_chat.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L22 — 一键 Web 入口
- [E-4] `archive/generated/snapshots/0Dionysus0/starter_kit/loomq_l2/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L42 — 零基础 CLI 菜单
- [E-5] `archive/generated/snapshots/0Dionysus0/starter_kit/loomq_l2/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L29-L57 — 可选加载 `.env`
- [E-6] `archive/generated/snapshots/0Dionysus0/starter_kit/loomq/hybrid.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L14 — L3 复用 L1 解析器的设计说明

### 结论置信度

包分离与 yaml 为高（A）。Web/CLI 角色为中（B）。`.env` 实装、教程页与评测对齐无法静态确认（C）。本段未运行、未安装、未联网。

## 19. `Huxingyu`

### 身份与路径

- contestant_id：`Huxingyu`
- snapshot：`archive/generated/snapshots/Huxingyu/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/Huxingyu/LoomQ-2026` @ `d6cc9225571e3685bed4c8e04b35d7a9e34cf0ce`
- starter 目录名：`starter_kit/`
- 规模：70 个文件，32 个 `.py`；json 8、qasm 5、originir 2
- 测试 13、证据 11、无独立 Web
- yaml 声明：L1/L2/L3 全 true；`adapter.run` 标注本地模拟器
- 入口：`adapter.py`；面向用户 CLI：`loomq_cli.py`；硬件在 `examples/`

### 技术栈与结构

L1 核心 `qasm_core.py`，L2 `agent_engine.py`，L3 `hybrid_compiler.py`，CLI `loomq_cli.py`。adapter 78 行：transpile 渲染三方言，`run` 用 `sample_counts` 做参考态矢，backend 字段写 `*_simulator`，`job_id` 为 `local-{target}-{digest}`。根 `tests/` 含 l1/l2/l3/cli/evidence/stress/private-like 等约 10 个用例文件。根 README 增加流程图目录名勘误。starter README 以本队入口开头，并指向 `SOLUTION.md`。`test_quantum_riscv_extension.py` 同时出现在 starter 与根 tests。无独立 Web（scout 入口为 CLI）。

### 方案概述

yaml L1/L2/L3 全 true。README 声称一条命令 `python3 starter_kit/loomq_cli.py --demo bell` 无需依赖/账号。CLI 内置 Bell/GHZ3 QASM、ASCII 直方图与 follow-up 上下文拼接（中英前缀列表）。硬件不在 adapter.run，而在 `examples/spinq_cloud_submit.py`（`requests.post` 登录，RSA 签名用户名）与 `originq_cloud_submit.py`。证据 README 自称两份主证据来自 SpinQ 与 OriginQ 真机，并保留 originir 与 result JSON。`sample_counts` 使用 `target + native` 字符串参与采样种子，使三目标本地 counts 可区分但均为模拟器。

### 优点

- CLI 可离线 demo，与 LLM 路径分开（`/demo` 无需 Key）。
- 测试面明显宽于工具包默认的 2 个合同测试。
- 证据同时归档 QASM、OriginIR、result JSON。
- adapter `run` 明确 meta.simulator 为参考态矢，不把本地结果标成 QPU。
- 根 README 修正 `starter-kit` vs `starter_kit` 命名，减少提交踩坑。

### 质量问题与风险

- `examples/spinq_cloud_submit.py` 使用 `requests.post` 登录并签名：需复核（私钥文件读取、token 处理）。
- `tests/test_cli.py` `subprocess`：需复核。
- `listen` 命中 examples 与 evaluator：含云提交脚本。
- 证据勾选五项；**job 真伪无法静态确认**。
- CLI follow-up 把上一轮回复拼进 prompt，评测 `agent_chat` 是否同样有状态：adapter 路径是无状态转发，需区分产品 CLI 与契约。
- `test_l2_stress.py`、`test_private_like_evaluator.py` 文件名暗示压力/私有用例仿品：内容未当测试结果引用。
- 根 README 勘误 `starter-kit/` 名称，与 58 人集合中 `infiniteHY` 的真实连字符目录不是同一件事，此处只说明本提交文档。

### 完整性 / 可维护性 / 安全性观察

yaml 与四函数齐全。无独立 Web（scout 列 CLI）。硬件示例与证据文件对应两平台命名。模块中等规模，较单体 adapter 易读；测试文件多，可维护性较好。公开自测与私有评测差异、RSA 签名登录是否仍有效、直方图文案是否满足新手 Bonus，无法静态确认。

对照口径：`adapter.run` 的 backend 字段写模拟器名，与证据 README 的真机申报不是同一路径。
未执行 requests 登录，未把 result JSON 当已验证 QPU。
CLI `--demo` 离线路径与 `agent_chat` 契约路径需分开读。

### 关键证据位置

- [E-1] `archive/generated/snapshots/Huxingyu/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 true
- [E-2] `archive/generated/snapshots/Huxingyu/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L27-L78 — 三目标渲染 + 本地 sample_counts + L2/L3 转发
- [E-3] `archive/generated/snapshots/Huxingyu/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L3-L13 — README 声称 `loomq_cli.py --demo bell`
- [E-4] `archive/generated/snapshots/Huxingyu/starter_kit/loomq_cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L18-L63 — 离线 demo 电路与命令
- [E-5] `archive/generated/snapshots/Huxingyu/starter_kit/examples/spinq_cloud_submit.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L41-L59 — `requests.post` 登录
- [E-6] `archive/generated/snapshots/Huxingyu/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L11 — 五项均 `[x]`

### 结论置信度

CLI/adapter/yaml 为高（A）。真机示例与证据文件对应关系为中（B）。请求库调用是否成功、证据是否来自真机，无法静态确认（C）。本段未运行、未安装、未联网。

## 20. `haiyun919`

### 身份与路径

- contestant_id：`haiyun919`
- snapshot：`archive/generated/snapshots/haiyun919/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/haiyun919/LoomQ-2026` @ `694c5e24a4db4d7d75539ee905609f69f46f1407`
- starter 目录名：`starter_kit/`
- 规模：55 个文件，21 个 `.py`
- 测试 3、证据 5、无 Web/CLI 产品入口
- yaml 声明：**仅 L1 true**，L2/L3 false；与 adapter `NotImplementedError` 一致
- 入口：`adapter.py`；后端实现 `starter_kit/backends/`
- originq 在 `SUPPORTED_TARGETS` 中出现但函数体未实现

### 技术栈与结构

L1 定向实现：`qasm_parser.py` + `backends/braket_backend.py` + `backends/spinq_backend.py` + `backends/spinq_runner.py`。**无 originq 后端模块**。两份互斥依赖锁：`requirements.txt`（Braket/antlr 4.13.2 栈）与 `requirements-spinq.txt`（antlr 4.9.2 / spinqit 栈）。L2/L3 在 adapter 中保持 `NotImplementedError`。证据 README 五项均未勾选；另有本地/容器 L1 验证 markdown/json。根 README 为赛题模板；starter README 补充双 venv 复现说明。`circuits/` 除 bell/ghz3 外还有 `l1_partial_measurement.qasm`、`l1_asymmetric_measurement.qasm`、`l1_all_gates.qasm`。无 Web/CLI 产品入口。

### 方案概述

yaml：**`l1: true, l2: false, l3: false`**，`network.required_for_l2: false`。这与 adapter 中 `agent_chat`/`compile_hybrid` 抛 `NotImplementedError` 一致，也是本批 11–20 中唯一把 L2/L3 标 false 的提交。但 `SUPPORTED_TARGETS` 仍含 `"originq"`，而 `transpile`/`run` 对 originq 直接 `NotImplementedError("OriginQ backend not yet implemented")`。SpinQ 执行经 `subprocess.run` 调用独立解释器上的 `spinq_runner.py`，QASM 作为 argv 传入，超时 120s。公开 `evaluator.py` 仍含 L2/L3 函数，会按 yaml `declared_levels()` 跳过未声明 Level。Docker 文档要求 `--platform linux/amd64`。

### 优点

- 明确放弃 L2/L3，yaml 与 NotImplemented 对齐，避免空实现申报。
- 用进程隔离处理 SpinQ/Braket 的 antlr 冲突，README 写明不要混装。
- L1 自测材料（public/container json+md）与 hardening 测试 `tests/test_l1_hardening.py` 存在。
- 依赖两份文件均大量 `==` 钉死。

### 质量问题与风险

- **yaml `l1: true` 与 originq 未实现**：`transpile`/`run` 在 originq 分支静态可见为 `NotImplementedError`；评测是否调用该目标、调用后的进程结果，无法静态确认。
- `subprocess.run(..., qasm_str 作为 argv)`：需复核命令行长度与注入面（runner 从 `sys.argv[1]` 取整段 QASM）。
- 证据五项空白，与“只做 L1 工程验证、不申报人工分”一致，但人工分材料缺失。
- 仍保留 `llm_client.py`、`riscv_emulator.py`、`l2_policy.json` 等工具包文件，`layer_file_hints` 会把 L2/L3 标真，与 yaml 不一致。
- 无交互入口；scout 所列入口即 evaluator 与 backends。
- `spinq_runner.py` 从 `sys.argv[1]` 读取整段 QASM：需复核超长电路与 shell 转义（调用方用 list argv 而非 `shell=True`，风险面低于拼接字符串）。
- 证据目录有 evaluator json，但勾选框全空：文档自称验证记录，**不是**已核验分数。

### 完整性 / 可维护性 / 安全性观察

完整性应按 yaml 解读为 **仅参赛 L1 的 spinq/braket**，不是三 Level 全做。Docker 文档要求 `linux/amd64`。`spinq_runner` 写临时 `.qasm` 再编译。未发现仓内密钥。backends 包边界清楚，可维护性对 L1 子集足够。L1 在双环境下是否都能过公开分布、originq 是否故意不参赛、容器 json 是否可复现，无法静态确认（yaml 未提供 per-target 开关）。

对照口径：yaml 的 L2/L3 false 优先于残留的 `llm_client.py`/`riscv_emulator.py`。
未安装双 venv，未跑 subprocess runner。
originq `NotImplementedError` 与 `l1: true` 的目标覆盖范围需评测方复核。

### 关键证据位置

- [E-1] `archive/generated/snapshots/haiyun919/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — **仅 L1 true，L2/L3 false**，L2 不要求网络
- [E-2] `archive/generated/snapshots/haiyun919/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L69 — braket/spinq 转发；originq 与 L2/L3 为 `NotImplementedError`
- [E-3] `archive/generated/snapshots/haiyun919/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L53-L67 — README 声称双 venv 与 antlr 版本冲突
- [E-4] `archive/generated/snapshots/haiyun919/starter_kit/backends/spinq_backend.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L9 — 设计说明：subprocess 隔离 SpinQit
- [E-5] `archive/generated/snapshots/haiyun919/starter_kit/backends/spinq_backend.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L146-L159 — `subprocess.run` 调 runner
- [E-6] `archive/generated/snapshots/haiyun919/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 五项人工评分均未勾选

### 结论置信度

yaml 与 NotImplemented 对齐、双 requirements 存在为高（A）。“L1 只覆盖 spinq+braket”为中（B）。隔离执行是否成功、originq 评测影响、容器验证 json 含义，无法静态确认（C）。本段未运行、未安装、未联网。

## 21. `arw131072`

### 身份与路径

- 选手标识：`arw131072`
- snapshot：`archive/generated/snapshots/arw131072/`（starter 目录为 `starter_kit/`）
- 上游仓库：`https://github.com/arw131072/loomQ-submission`
- 上游 SHA：`ef58b3387b8c942581f4a507fdf1f06fd929006f`
- 聚合仓库基线：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 规模（事实卡计数）：约 49 个文件、18 个 `.py`；定制面中等
- `submission.yaml` 声明 `levels.l1/l2/l3` 均为 true，`entrypoint:
  adapter.py`，`runtime.version: "3.10"`，`team_id: "arw131072"`
- 静态入口候选：`starter_kit/l2_web_flask.py`、`starter_kit/adapter.py`、`starter_kit/evaluator.py`（均未执行）
- `evaluator.py` 仍为公开自测器形态（约 226 行），未当作本队独有评分器

### 技术栈与结构

静态可见 Python 3.10、Flask Web、以及 Braket / SpinQit / pyqpanda3 / OpenAI 兼容客户端的
import。根目录仍是赛题发布包模板（`competition/`、题面 PDF/HTML/DOCX、流程图 PNG）；选手增量主要落在
`starter_kit/adapter.py`（约 711 行）与 `starter_kit/l2_web_flask.py`（约 817 行，内嵌 HTML 模板与
matplotlib 柱状图）。`requirements.txt` 为长清单精确钉版本，除量子 SDK 外还含 Flask/Streamlit/FastAPI/Altair
等，更接近整环境 freeze，而非最小评测依赖。测试除 starter 合同测外另有
`tests/test_adapter.py`、`tests/test_originq_sim.py`。证据目录含 `gemini_vp/` 下的
QASM、`result.json`、`job_id.txt` 与四张 PNG。本 snapshot 在 Git mode 下未静态见到 `100755` 可执行
Shell。Dockerfile 仍位于 `starter_kit/`。

### 方案概述

L1：`transpile()` 按 target 分支把 OpenQASM 2.0 转为 Braket QASM3、SpinQ 原串或 OriginIR；`run()`
再分别调用 `_run_braket` / `_run_spinq` / `_run_originq`。Braket 路径用 `LocalSimulator` +
`Program(source=ir_str)`；OriginQ 路径在真机模式下把 `result.json`/`job_id.txt`/`circuit.qasm` 写进
evidence 目录，本地模式走 `CPUQVM`。L2：`agent_chat()` 直接构造 `OpenAI(...)` 客户端，默认
`LOOMQ_LLM_BASE_URL` 为 DeepSeek，缺 `LOOMQ_LLM_API_KEY` 时抛 `RuntimeError`，并用 L1 `run()`
做自验重试（`MAX_RETRIES = 2`）。Web 入口 `l2_web_flask.py`
提供模板化实验（Bell/GHZ/Grover/QFT）与物理解释/参考文献占位。L3：`compile_hybrid()` 抽取含 `q[`/`measure`
的行，并对评测样例形态写出固定 RISC-V 片段；另有 `translate_statement()` 处理 `r1 = ...` 一类赋值，但
`compile_hybrid` 主路径并未普遍调用它。根 README 仍是赛题分发文案；人工评分说明写在 `evidence/README.md`，并声称量旋 Gemini
VP 真机证据。`network.required_for_l2` 为 false，与已实现的 LLM 调用并存。

### 优点

- 契约四函数均有具体实现，而不是 `NotImplementedError`（A）。
- L1 三后端 SDK 路径与 QASM2→QASM3 / OriginIR 文本变换在同一文件内可读（A）。
- 另附 Flask 单文件 Web 与四张界面截图、一份带 `job_id` 的证据子目录，人工评分材料不是空模板（A 对文件存在）。
- 额外合同向测试文件表明作者至少静态意识到 adapter 与 OriginQ 模拟路径需要自测（A）。
- `submission.yaml` 额外列出 `l2_runtime.required_environment` 与一条 `evidence`
  记录，比多数模板清单更具体（A）。

### 质量问题与风险

- `compile_hybrid()` 对 `if (c[0] == 1) { r1 = 7; } else { r1 = 3; }` 写出硬编码汇编，并在无
  `classical` 块时返回空串；通用编译面无法从源码确认（A 对硬编码，无法静态确认对隐藏用例）。
- `l2_web_flask.py` 以 `debug=True, host='0.0.0.0', port=5000` 启动，属未约束监听面，需人工复核（A 对字面量）。
- `submission.yaml` 声明 L2 但 `network.required_for_l2: false`，与 `agent_chat` 必读
  `LOOMQ_LLM_API_KEY` 不一致（A）。
- `evidence/README.md` 标题与小节以字面 `\#`、`\##` 写成，Markdown 结构损坏（A）。
- `requirements.txt` 体积大且含本 adapter 未直接 import 的 Web 栈；评测安装面可能远超必要（B）。
- Flask 页把 `agent_chat`/`run` 结果填进模板；未运行故无法确认 XSS 或密钥泄漏，但 debug 模式本身提高暴露面（C 对利用，A 对
  debug）。

### 完整性 / 可维护性 / 安全性观察

完整性：声明三层均有对应函数；真机材料仅见 SpinQ `gemini_vp` 一组，未静态见到第二平台完整证据包。可维护性：逻辑集中在超长 `adapter.py` +
内嵌巨型 HTML 的 Flask 文件，缺少模块边界；`l2_web_flask.py` 以 `from starter_kit.adapter import ...`
导入，从 starter 目录直接 `python l2_web_flask.py` 是否成功取决于 `PYTHONPATH`，无法静态确认。安全性：OpenAI
客户端从环境变量读密钥，受检路径下未静态发现 `.env` 实文件；adapter 模块文档字符串提到可用 subprocess 委派，本文件未见实际 `subprocess`
调用。Flask `debug=True` 在误暴露到非回环地址时会放大交互面。无法静态确认 Web 能否启动、LLM 或真机是否可达。

本阶段明确无法确认：Flask 页面能否在评测镜像启动、DeepSeek 调用是否成功、Gemini VP 文件是否对应真实 QPU、硬编码 L3 片段对其它
Hybrid-QASM 的行为、`requirements.txt` 全量是否可安装。

### 关键证据位置

- [E-1] `archive/generated/snapshots/arw131072/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L26 — 声明 L1/L2/L3、entrypoint、`network.required_for_l2: false`，并列出 spinq_gemini_vp 证据路径与 job_id
- [E-2] `archive/generated/snapshots/arw131072/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L36 — 直接 import OpenAI，并 try-import pyqpanda3 / spinqit / braket
- [E-3] `archive/generated/snapshots/arw131072/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L508-L572 — `transpile`/`run` 三分支；`compile_hybrid` 含评测样例硬编码 RISC-V
- [E-4] `archive/generated/snapshots/arw131072/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L604-L624 — `agent_chat` 读 `LOOMQ_LLM_*` 并构造 OpenAI 客户端
- [E-5] `archive/generated/snapshots/arw131072/starter_kit/l2_web_flask.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L12 — Flask 入口，从 `starter_kit.adapter` 导入 `agent_chat`/`run`
- [E-6] `archive/generated/snapshots/arw131072/starter_kit/l2_web_flask.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L816-L817 — `app.run(debug=True, host='0.0.0.0', port=5000)`
- [E-7] `archive/generated/snapshots/arw131072/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — 标题写成字面 `\#`；后文声称一键启动 Flask 与真机证据

### 结论置信度

结构、声明层级、Flask 监听参数与硬编码 L3 片段为 A。Web/LLM/真机是否可用、保真度与截图是否对应真实会话无法静态确认。综合：A 描述实现面，B 描述「带
Web 的三层提交」，禁止任何得分或运行结论。

## 22. `yiyuanrvk77`

### 身份与路径

- 选手标识：`yiyuanrvk77`
- snapshot：`archive/generated/snapshots/yiyuanrvk77/`
- 上游：`https://github.com/yiyuanrvk77/LoomQ-2026` @
  `d85e5c2cd39f19082e640a435ec1a38d65844329`
- 规模：约 79 个文件、33 个 `.py`、10 个 Web 资源；定制面高
- `submission.yaml` 声明 L1/L2/L3 均为 true、`network.required_for_l2: true`，但未写 `entrypoint`
  字段
- 静态入口候选：`starter_kit/agent.py`、`starter_kit/web_demo.py`、`starter_kit/visualizations/index.html`、`starter_kit/loomq_cli.py`（均未执行）
- 未静态识别独立 Dockerfile 定制：仍使用 starter 内 Dockerfile 路径

### 技术栈与结构

Python 标准库为主的分层包：`qasm_parser.py` / `simulator.py` / `transpiler.py` / `backends.py` /
`agent.py` / `hybrid.py` / `circuit_gen.py` / `concepts.py`。交互入口为 `web_demo.py`（stdlib
`ThreadingHTTPServer`）与 `loomq_cli.py`；可视化在
`visualizations/`（`index.html`、`quantum-cave.html`、`toric-code.html`、`shor-code.html`、`steane-code.html`、`qec-lab.html`
等）。`requirements.txt` 仅注释，声明评测零第三方依赖、缺 SDK 时回退内置模拟器。存在 `.env.example`（空凭证模板，并注释
`adapter.run()` 不读硬件 token）。测试除合同测外另有 parser hardening、transpiler
roundtrip、hybrid、RISC-V 扩展、agent runtime、web demo 等共 8 个测试文件。证据含 SpinQ JSON/PNG 与
`reconcile_evidence.py`。`RISCV_EXTENSION.md` 定义 `quant rd, imm`
汇编。`assets/quantum-cave/` 下有多份超 1 MiB 的 MP4/PNG，只记录 blob 元数据，未打开。根上另有 `.release/qa/`
大图，与多份提交共享相同 blob OID，视为发布材料而非本队独有产物。

### 方案概述

README 与 `ARCHITECTURE.md` 声称：统一 IR 驱动转译与本地模拟，`run()` 不提交真机并以 `meta.is_hardware=false`
标识；内置状态向量以 20 比特和 1,000,000 shots 为资源上限。L2 每次真实调用 `LOOMQ_LLM_*`、无 mock 兜底，电路走「生成→12
门解析→本地自验→最多两次纠正」；后端约束由模型抽成 JSON，再查 `backend_capabilities.json`。L3
为手写词法/递归下降而非样例打表。`adapter.py` 是门面：`transpile` 调用 `emit(parse(qasm_str), target)`，`run` 含
`_normalize_backend_counts` 校验二进制键；同时 `from .agent import agent_chat`、`from .hybrid
import compile_hybrid` 再导出契约名。`agent.py` 的 system prompt 要求只返回 `task=circuit|backend` 的
JSON。`web_demo.py` 声称默认 `http://127.0.0.1:8000`，洞穴实验可无 Key，`/classic` 为开放工作台。证据 README
申报 SpinQ Cloud `gemini_vp` job `G-260816-0001`，并记录平台 shots 声明与 counts
合计不一致。这些是文档与源码对照，不是已验证结果。

### 优点

- 模块切分清楚，adapter 保持薄门面，契约名通过 import 再导出（A）。
- 自备 parser/simulator/transpiler 与多份针对性测试文件，工程完整性在静态层面高于「单文件 adapter」（A 对文件，无法静态确认测试结果）。
- `.env.example` 明确要求提交模板保持空密钥，并把硬件 token 与 `adapter.run()` 边界写进注释（A）。
- 可视化与教学页数量多，且 ARCHITECTURE 把「网页科普」与正式 L2 调用分开陈述（B）。
- 证据包对 shots/counts 不一致做了书面披露，而不是只放截图（A 对文字存在）。

### 质量问题与风险

- `submission.yaml` 缺少 `entrypoint` 字段，与多数正式提交的合同清单不一致；评测发现逻辑无法静态确认如何处理缺省（A 对缺字段）。
- `web_demo.py` 在找不到 `adapter.py` 时 `sys.exit(1)`，并从 `.env` 填环境变量；服务默认端口写在文档而非强制
  loopback 校验函数（B）。
- 大体积媒体（如 `ballerina-silhouette.mp4`，6,265,852 bytes）增加归档体积；内容未播放，不能当作演示已核验（A 对
  blob，无法静态确认内容）。
- 根 README 仍是赛题分发模板，产品叙事主要在 starter `ARCHITECTURE.md` / evidence，评审入口分散（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：三层函数名可在包内静态解析到实现；真机申报静态可见一平台材料；可视化页与 RISC-V
规格文档齐全。可维护性：分层与测试文件有利于阅读，但可视化/媒体资产与评测核心耦合在同一 starter 树，snapshot 体积被洞穴 MP4
显著放大。安全性：`.env.example` 为空模板；受检路径未静态发现已填密钥。`web_demo.py` 用标准库 HTTP，未见 Flask
`0.0.0.0`。无法静态确认 Agent 无 mock、洞穴页无障碍或真机 JSON 与控制台一致。`submission.yaml` 缺 `entrypoint`
是否被评测工具默认成 `adapter.py`，本阶段不能回答。

本阶段明确无法确认：内置模拟器与官方隐藏电路是否一致、Agent「无 mock」在缺 Key 时的实际失败模式、Quantum Cave 无障碍与音画、真机 JSON
与控制台是否一致、洞穴 MP4 内容。

### 关键证据位置

- [E-1] `archive/generated/snapshots/yiyuanrvk77/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 声明三层与 `required_for_l2: true`，无 `entrypoint`
- [E-2] `archive/generated/snapshots/yiyuanrvk77/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L46 — 门面说明与 `transpile`；import `agent_chat`/`compile_hybrid`
- [E-3] `archive/generated/snapshots/yiyuanrvk77/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L37 — README 声称分层、本地/真机边界、L2 无 mock
- [E-4] `archive/generated/snapshots/yiyuanrvk77/starter_kit/web_demo.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L12 — 文档声称 stdlib Web 入口与端口 8000
- [E-5] `archive/generated/snapshots/yiyuanrvk77/starter_kit/.env.example`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 空的 LLM/硬件/AWS 占位，注释禁止把凭证写入仓库
- [E-6] `archive/generated/snapshots/yiyuanrvk77/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L21 — 申报 SpinQ job 与 shots/counts 不一致说明
- [E-7] `archive/generated/snapshots/yiyuanrvk77/starter_kit/assets/quantum-cave/ballerina-silhouette.mp4`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — Git blob mode=100644，oid=`e860c76b0554c3798f034e08d8c023819a72ffd7`，size=6265852；未打开/播放

### 结论置信度

缺 `entrypoint`、分层文件与空 `.env.example` 为 A。ARCHITECTURE 与实现互相印证为 B。运行、真机、可视化体验无法静态确认。

## 23. `UokyI`

### 身份与路径

- 选手标识：`UokyI`
- snapshot：`archive/generated/snapshots/UokyI/`
- 上游：`https://github.com/UokyI/LoomQ-2026` @ `6fbd578dd749eaf785f687ca90ce783ed3693afe`
- 规模：约 49 个文件、19 个 `.py`；定制面中等
- `submission.yaml` 声明 L1/L2/L3 true，`entrypoint: adapter.py`，`network.required_for_l2:
  true`
- 静态入口候选：`starter_kit/run_wukong.py`、`starter_kit/chat_cli.py`、`starter_kit/adapter.py`（均未执行）
- 未静态识别 Web 前端；交互面是 CLI 而非 HTML 服务

### 技术栈与结构

核心实现几乎全部在 `starter_kit/adapter.py`（约 914 行）：`Gate`/`Circuit` dataclass、`ast`
安全求值参数、自写状态向量模拟、三方言 emitter、`urllib` LLM 客户端、递归下降经典块编译。额外模块：`chat_cli.py`（自然语言
CLI，支持交互与单次参数）、`run_wukong.py`（本源悟空
`submit`/`query`）、`qriscv_emulator.py`、`qisa_test.py`、`QISA_SPEC.md`（custom-0 opcode
`0b0001011`）、`ARCHITECTURE.md`。`requirements.txt` 明确写明 L1/L2 用标准库、评测无需第三方。证据目录含悟空
QASM、`wukong-result.json`、`wukong-job-id.txt`。公开电路仍为 `circuits/bell.qasm` 与
`ghz3.qasm`。根 README 仍为赛题模板。根上另有 `.release/` 与 `NEXT.md`。

### 方案概述

`ARCHITECTURE.md` 声称目标用户是「只会说一句话」的跨界创作者；数据流为 OpenQASM 2.0 → 统一 Circuit IR →
`transpile`（纯文本，零依赖）或 `simulate` → 统一 Schema。文档强调 `cu1→cp` 是 QASM3 路径上「唯一真转译」。L2 经
`agent_chat` 调 OpenAI-compatible 服务并复用 `parse_qasm2` 自验；CLI 可再调用 `run` 画直方图。L3 在同一文件内用
`_ClassicalParser`（IF/ASSIGN/表达式）生成 RISC-V。`run_wukong.py` 从环境变量 `QUANTUM_API` 读
token，硬编码 180 比特芯片与 Origin 控制台 URL，用 `pyqpanda.QCloud` 异步测 Bell，分 `submit`/`query`
两阶段写证据文件。证据 README 勾选全部人工项，并填写悟空 job `A7C58462C717A6873FF1AEF6B8728213`、shots
8192。这些仅为静态申报。

### 优点

- L1 转译/模拟与参数求值（`ast` 白名单节点，文档明确不使用 `eval`）集中且可读（A）。
- `requirements.txt` 与「零第三方依赖」声明一致，降低评测安装面（A）。
- 真机采集脚本与评测 `run()` 分离，token 只从环境变量读取（A）。
- 另有 Q-extension 规格文档 `QISA_SPEC.md` 与 `qriscv_emulator.py`，Bonus 材料不是空标题（A 对文件）。
- CLI 入口 `chat_cli.py` 把三类用户任务写进横幅，和赛题 L2 UX 口径对齐（B）。

### 质量问题与风险

- 单文件 900+ 行承担解析、模拟、转译、Agent、编译器，后续修改冲突面大（A）。
- `run_wukong.py` 写死 API URL 与芯片型号；平台变更时脚本会过时，且该脚本不在契约 `run()` 路径上（A）。
- 证据包静态可见本源一侧材料，未见第二真机平台的对等文件集（A 对目录）。
- `ARCHITECTURE.md` 声称隐藏电路已用 pyqpanda 交叉验证：这是文档断言，仓库内未见对应运行日志，无法静态确认（C）。
- 根 README 未改写，评审若只看仓库首页会看不到本队架构（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：契约函数、CLI、悟空脚本、QISA 文档与一份真机证据文件集均存在；L2/L3 未再拆文件。可维护性：标准库实现有利于沙箱，但 900+ 行单文件使
IR、Agent、编译器的回归边界不清。安全性：受检路径无 `.env` 实文件；`run_wukong.py` 缺 token
时抛错而不是内嵌密钥。`urllib.request` 会在 L2 出网，与 yaml 的 `required_for_l2: true` 一致。`chat_cli.py` 把
`sys.path` 插到 starter 目录再 import adapter，适合「在 starter_kit
下直接跑」，与包导入两种用法并存。无法静态确认模拟器与官方隐藏电路一致，也无法确认 job 文件来自该脚本。

本阶段明确无法确认：`urllib` LLM 客户端在评测注入下的协议兼容性、`chat_cli.py` 直方图体验、悟空脚本与证据 JSON
的因果关系、Q-extension 模拟器是否被 L3 契约路径调用。

### 关键证据位置

- [E-1] `archive/generated/snapshots/UokyI/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 三层声明、entrypoint、L2 网络与 `LOOMQ_LLM_*`
- [E-2] `archive/generated/snapshots/UokyI/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L26 — 设计说明：QASM2 为唯一源语言，IR 再分转译/模拟
- [E-3] `archive/generated/snapshots/UokyI/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L53-L80 — `_parse_param` 用 `ast` 求值，拒绝未知节点
- [E-4] `archive/generated/snapshots/UokyI/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L712-L768 — L3 递归下降 `_ClassicalParser`
- [E-5] `archive/generated/snapshots/UokyI/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L20-L72 — 声称架构、零依赖与 CLI 复现命令
- [E-6] `archive/generated/snapshots/UokyI/starter_kit/run_wukong.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L52 — 从 `QUANTUM_API` 读 token，覆盖本源 API URL
- [E-7] `archive/generated/snapshots/UokyI/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L28 — 勾选全部人工项并填写悟空 job 字段
- [E-8] `archive/generated/snapshots/UokyI/starter_kit/QISA_SPEC.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L19 — 自定义量子 RISC-V 扩展编码规格

### 结论置信度

标准库 adapter、CLI、悟空脚本与证据文件为 A。文档中的交叉验证与「零基础可用」为 C。禁止推断真机分或 L3 正确性。

## 24. `orange-city`

### 身份与路径

- 选手标识：`orange-city`
- snapshot：`archive/generated/snapshots/orange-city/`
- 上游：`https://github.com/orange-city/LoomQ-2026` @
  `6c2b5fda10e24c20b1f718f9f3b43a7abb5fafb9`
- 规模：约 55 个文件、23 个 `.py`；定制面高
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`starter_kit/cli.py`、`starter_kit/agent.py`、`starter_kit/evaluator.py`（均未执行）
- 未静态识别 HTML/JS Web；L2 UX 入口是 CLI

### 技术栈与结构

`adapter.py` 仅 42 行，三重 import 回退后把契约转给
`transpilers.py`、`backends.py`、`agent.py`、`hybrid_compiler.py`。另有
`qasm_engine.py`（无噪声模拟）、`cli.py`（stdin
REPL）、`PROJECT_README.md`、`QUANTUM_RISC_V.md`、`starter_kit/tests/test_quantum_riscv.py`。`transpilers.py`
含 OriginIR 门名映射表（`h→H`、`cx→CNOT`、`sdg→SDAG` 等）。`requirements.txt` 精确钉
`numpy==1.26.4`、`spinqit==0.2.4`、`amazon-braket-sdk==1.86.2`、`pyqpanda3==0.2.0`。证据含
SpinQ Bell QASM/JSON/控制台 PNG 与 CLI 截图。根上有 `NEXT.md` 与 `.release/`。根 README 仍为赛题模板；本队说明在
starter README 与 `PROJECT_README.md`。`report.json` 也出现在 starter 顶层，本阶段不把它当作官方分数。

### 方案概述

本队 README 声称面向「只会 Python 的开发者」，一键自测 `evaluator.py` 与 `cli.py`，无 SDK
时回退内置模拟器。数据流：OpenQASM 2.0 → `transpilers.py` 三方言 → `qasm_engine.py` 模拟或 `backends.py`
SDK 执行。SpinQ 路径把转译后的 QASM 写入临时文件再 `get_compiler("qasm")`；OriginQ 路径
`convert_originir_string_to_qprog`；Braket 路径 `BraketCircuit.from_qasm`。`backends.py`
对三后端各 `try` SDK，`except Exception` 后调用 `simulate_counts`。`_result()` 的 `job_id` 来自电路
sha256。L2 `cli.py` 调 `agent_chat`，若回复含 `OPENQASM` 则本地 `run(..., "spinq", 1024)` 画 ASCII
直方图。L3 在 `hybrid_compiler.py` 用括号深度抽取 `classical {}` 再按 IF/REG/EQ 等规则分词。证据 README 申报量旋
`triangulum_vp` job `S-260824-0006`，并列出三条 UX
任务（文档自称「已实测通过」，本阶段不采信为运行结果）。`PROJECT_README.md` 把 DeepSeek 环境变量示例写进 L2 调试步骤。

### 优点

- adapter 真正薄门面，职责拆到独立模块（A）。
- 依赖清单短且全部 `==` 钉版本（A）。
- CLI 作为 L2 交互入口，源码路径短、无需浏览器（A）。
- 证据目录同时有电路、原始 JSON、控制台图与 CLI 截图，字段表完整（A 对文件）。
- `QUANTUM_RISC_V.md` + 专项测试文件使 Bonus 材料可定位（A）。

### 质量问题与风险

- `qasm_engine.py` 对门参数使用 `eval(token, {"__builtins__": {}}, {"pi": math.pi})`。空
  builtins 降低风险，仍属动态求值，需人工复核表达式面（A）。
- `backends.py` 宽 `except Exception` 静默回退内置模拟器，失败原因可能被吞掉；返回的 backend
  名称仍可能是平台标签，需对照是否诚实标注引擎（A 对回退，C 对是否伪装）。
- `job_id` 取 QASM 的 sha256 前 16 位，同一电路重复执行会碰撞，且不是平台任务号（A）。
- 证据 README「已实测通过」是作者陈述，不是本阶段验证（A 对文字，无法静态确认）。
- 根 README 未改，产品叙事入口在 `PROJECT_README.md`（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：三层模块、CLI、钉版本依赖、一份 SpinQ 真机材料与 RISC-V 文档均在；未见第二真机平台对等文件。可维护性：分层清晰，三重 import 回退增加「脚本 /
`starter_kit.` / 相对包」三种路径组合，测试与评测若混用容易踩错。安全性：CLI 文档用 `<YOUR_KEY>` 占位；受检路径无实密钥文件。`eval`
与宽 except 是主要静态风险点。临时 QASM 文件在 `_run_spinq` 中 `delete=False`，是否清理无法静态确认。无法静态确认 SDK
路径是否被走到，也无法确认 CLI 三条任务。

本阶段明确无法确认：钉版本 SDK 在评测镜像是否安装成功、宽 except 是否掩盖真实错误、`eval` 参数面是否被恶意表达式打到、CLI 截图是否来自本
`cli.py`、job `S-260824-0006` 的真实性。

### 关键证据位置

- [E-1] `archive/generated/snapshots/orange-city/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L41 — 薄门面，三重 import 后转发四契约函数
- [E-2] `archive/generated/snapshots/orange-city/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L20 — 本队实现说明、自测命令与模块职责
- [E-3] `archive/generated/snapshots/orange-city/starter_kit/qasm_engine.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L126-L131 — 参数 `eval` 且 `__builtins__` 为空
- [E-4] `archive/generated/snapshots/orange-city/starter_kit/backends.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L42-L98 — SDK try/except 后回退 `simulate_counts`
- [E-5] `archive/generated/snapshots/orange-city/starter_kit/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L46 — REPL 调 `agent_chat` 并本地自验直方图
- [E-6] `archive/generated/snapshots/orange-city/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L4 — 四条精确钉版本依赖
- [E-7] `archive/generated/snapshots/orange-city/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L40 — 申报 CLI/真机/RISC-V，含 job `S-260824-0006`

### 结论置信度

模块结构、`eval`、依赖钉版本与证据文件为 A。SDK 回退是否在评测中触发、UX 任务是否成立无法静态确认。

## 25. `noh1204`

### 身份与路径

- 选手标识：`noh1204`
- snapshot：`archive/generated/snapshots/noh1204/`
- 上游：`https://github.com/noh1204/LoomQ-2026` @
  `73412621a51b9b7fe6e3ba9f135039c2b2d6dc75`
- 规模：约 41 个文件、15 个 `.py`；额外 Python 模块为空，接近官方 starter
- `submission.yaml` 声明 `l1: true`，`l2: false`，`l3: false`
- 静态入口候选：`starter_kit/evaluator.py`、`starter_kit/adapter.py`（均未执行）
- 未静态识别 Web、CLI、Agent 实现或硬件 runner

### 技术栈与结构

目录树与 starter
高度同构：`adapter.py`、`evaluator.py`、`llm_client.py`、`riscv_emulator.py`、合同测试与赛题文档。根上多出
`.vscode/`。`adapter.py` 约 113 行 / 3,869 bytes，是本提交几乎唯一的逻辑改动；事实卡 `extra_py`
为空。`requirements.txt` 仍是官方注释模板，无已钉第三方包。证据 `README.md` 全部复选框为未勾选，正文仍是「平台名称：[填写]」占位。另有
`starter_kit/report.json`，`generated_at` 为
`2026-08-24T12:32:28Z`，`summary.passed=4`，`notice` 写明「Public self-check only; this
report is not an official score」。未静态见到 Web、CLI、额外测试、硬件脚本或真机附件。公开电路仍只有
`bell.qasm`/`ghz3.qasm`。

### 方案概述

`transpile()` 对三 target 均 `return qasm_str.strip()`，即透传 OpenQASM 2.0，不做 OriginIR/QASM3
变换。`run()`：仅 `braket` 尝试 `LocalSimulator` + `braket.ir.openqasm.Program`，失败或非 braket（含
`spinq`/`originq` 全部分支）时走 `_simulate_qasm()`——按 `qreg` 宽度构造全 0 / 全 1 两个比特串，把 shots
对半切开；`job_id` 为 `loomq-job-` + uuid 前 8 位。返回字典含 `status: SUCCESS` 与
`raw_response`。`agent_chat` / `compile_hybrid` 保持 `NotImplementedError`，与 yaml 关闭 L2/L3
一致。公开电路 Bell/GHZ 的理想分布恰好是 00/11 各半，因此该启发式在文件层面就能让 `report.json` 里四条 L1 用例显示
`PASS`/`fidelity: 1.0`；这只说明 JSON 字段如此，不能证明通用中间层或评分器已运行成功，更不能外推到隐藏电路。

### 优点

- 层级声明诚实：只报 L1，可选接口保持未实现（A）。
- 改动面极小，评测入口仍是官方 `adapter.py` / `evaluator.py`，路径无歧义（A）。
- `report.json` 自带「非正式分数」声明，未把公开自测包装成官方成绩（A）。

### 质量问题与风险

- `_simulate_qasm()` 与输入门序列无关，只生成 00/11 对半计数；对非 Bell/GHZ 族电路在静态上即可判断会偏离真实分布（A）。
- `transpile()` 透传，不满足「三平台原生 IR」的合同文本要求；是否被评分器拒绝无法静态确认（A 对透传，无法静态确认评测结果）。
- Braket 分支把 OpenQASM 2.0 直接交给 `Program(source=qasm_str)`，与常见 QASM3 期望可能不匹配；失败则回退启发式（B）。
- 无额外测试覆盖「非 00/11 电路」；合同测试不能揭示该启发式（A）。
- 证据包未申报任何人工项（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：作为「仅 L1、接近模板」提交是自洽的，但 L1 实现面是启发式 counts 而非通用转译/模拟；L2/L3
按声明关闭，证据未填。可维护性：文件少、易读，后续若补真实模拟器只需替换 `_simulate_qasm`。安全性：无 Web 监听、无 LLM
调用、无硬件脚本；adapter 顶部文档字符串提到 subprocess 委派，本实现未调用。`report.json` 的 PASS 字段不得写成「测试通过」。无法静态确认
braket SDK 在其环境是否存在，也无法确认该 JSON 是否由本树 `evaluator.py` 生成。

本阶段明确无法确认：公开自测 JSON 的生成过程、启发式 counts 在隐藏电路上的表现、透传 IR 是否被官方解析器接受。不得把 `report.json` 的
`PASS` 写成测试已通过。

### 关键证据位置

- [E-1] `archive/generated/snapshots/noh1204/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 仅 L1 为 true，L2/L3 false
- [E-2] `archive/generated/snapshots/noh1204/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L26-L51 — `transpile` 透传；`_simulate_qasm` 固定 00/11 对半
- [E-3] `archive/generated/snapshots/noh1204/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L54-L112 — `run` 的 braket try/except 与 L2/L3 `NotImplementedError`
- [E-4] `archive/generated/snapshots/noh1204/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 仍为官方空模板注释
- [E-5] `archive/generated/snapshots/noh1204/starter_kit/report.json`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L36 — 公开自测 JSON 含 4 条 PASS 与非正式分数声明
- [E-6] `archive/generated/snapshots/noh1204/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L16 — 人工评分五项均未勾选

### 结论置信度

「接近 starter、只声明 L1、启发式 00/11 模拟」为 A。公开 JSON 的 PASS 不得外推为正确性或得分。综合：实现面 A，完成度评价禁止。

## 26. `BEER7LN`

### 身份与路径

- 选手标识：`BEER7LN`
- snapshot：`archive/generated/snapshots/BEER7LN/`
- 上游：`https://github.com/BEER7LN/LoomQ-2026` @
  `49856178c93fd686ff592409e5848097c669d2dd`
- 规模：约 145 个文件、68 个 `.py`、16 个 Web 资源；定制面高；snapshot 体积约 40 MiB
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`start.ps1`、`starter_kit/l2.cmd`、`starter_kit/l2_app.py`、`starter_kit/web/index.html`、`starter_kit/scripts/verify_all.py`（脚本只记录路径，未执行）
- 未静态识别 `100755` 可执行 Shell；Windows 入口 mode=100644

### 技术栈与结构

`adapter.py` 薄门面，转调
`loomq.pipeline.trace_transpilation`、`loomq.backends.run`、`loomq.l2.agent_chat`、`loomq.hybrid.compile_hybrid`。包内还有
`qasm.py` / `simulator.py` / `transpilers/{spinq,originq,braket}.py` / `verification.py`
/ `web_hardware.py` / `synthesis.py` / `gate_policy.py` /
`riscv_quantum_extension.py`。Web：`l2_app.py`（stdlib HTTP，默认 loopback 8765）+
`web/index.html`（无障碍 skip-link、主题切换、studio 导航）；动效目录 `motion/remotion/`（React/Remotion
4.0.434）、`motion/hyperframes/`（含压缩
`gsap.min.js`）、`webgl/`。脚本：`scripts/verify_all.py`、`preflight_*_hardware.py`、`submit_*_hardware.py`（路径记录，未执行）。Windows
入口 `start.ps1`、`starter_kit/l2.cmd` 的 Git mode 均为 `100644`，不是本基线那 7 个 `100755`
Shell。依赖：`requirements.txt` 钉 `spinqit==0.2.4` / `pyqpanda==3.8.5` / `pyqpanda3==0.4.0`
/ braket SDK，另有 `requirements-lock.txt`。`.env.l2.example` 为占位模板（`REPLACE_ME`）。根 README
按手册分项列出实现索引，并链接 `video.mp4`。另有 `curriculum/`、`learning.py`。

### 方案概述

根 README 声称完成 L1 三平台中间层、L2 Agent+Web、L3 Hybrid 编译、两平台真机、自定义 RISC-V 与视觉叙事，并给出 `python
scripts/verify_all.py` / Docker 复现命令——均为文档声称。`loomq/pipeline.py` 静态可见
canonical/public/runtime 三份 IR 与 sha256 stage trace，`transpile()` 返回
`trace_transpilation(...).public_ir`。`l2_app.py` 拒绝非 loopback 的 `--host`，并列出
Origin/SpinQ 硬件环境所需环境变量名。证据 README 勾选全部人工项：SpinQ `G-260807-0011` 与 Origin
`E03FE919C438D14649B3C227CB6979D8` 的 Bell 材料路径写在 `evidence/files/`，并说明公开原始响应不含
token/用户名。测试夹具 `tests/test_l2_web_hardware.py` 含伪造 PEM（重复字母填充）与 mock token，用于本地凭证
API，不是提交的真实私钥。`l2.cmd` 以 `powershell -ExecutionPolicy Bypass` 调用
`scripts\l2-service.ps1`（未执行）。

### 优点

- 包结构完整，adapter 保持四行级转发，pipeline 带可审计 stage digest（A）。
- Web 绑定显式限制 loopback（A）。
- 同时有短 `requirements.txt` 与 lockfile，依赖策略比 freeze 更可复核（A）。
- 文档体系（`docs/HARDENING_DESIGN.md` 等，README 索引）与 `scripts/verify_all.py` 统一入口在静态上齐全（A
  对文件）。
- 证据目录同时出现 SpinQ 与 OriginQ 的 QASM/OriginIR/原始 JSON/标准化 JSON（A 对存在）。
- `l2_app.py` 把硬件环境所需环境变量名列成元组，而不是把 token 写进源码（A）。

### 质量问题与风险

- 根 README 含分值表与「申报覆盖全部评分项」：这是作者口径，不得当作得分（A 对文字）。
- `scripts/verify_all.py` 使用 `subprocess` 拉起 evaluator/测试；本阶段不执行（A 对存在）。
- `web/app.js` 等前端命中 `exec` 扫描（含第三方 GSAP 压缩文件）；需人工区分业务代码与依赖（C 对漏洞，A 对命中）。
- `video.mp4` 35,776,667 bytes，只记录 blob，不播放，不能验证「完整演示」（A）。
- `start.ps1` 默认打开 `http://127.0.0.1:$Port/`；脚本本身未设可执行 bit（A）。
- 测试夹具中的 PEM/token 形态会触发密钥扫描；对照源码为 `"A" * 80` 填充与 `"origin-secret-a"`
  类占位，未静态识别为真实凭据（A）。若后续发现真实密钥应停止传播。

### 完整性 / 可维护性 / 安全性观察

完整性：三层代码、Web、动效、lockfile、双平台证据文件与大量 `starter_kit/tests/`
均在。可维护性：模块多、文档多，阅读成本高但边界清楚；adapter 不承载业务，有利于评测契约稳定。安全性：loopback 限制优于本组若干 `0.0.0.0`
提交；硬件凭证设计走被 gitignore 的本地文件（文档声称，未运行）。`verify_all.py` 会 `subprocess` 拉起公开
evaluator，本阶段不执行。无法静态确认 `verify_all.py`、Remotion 构建或真机 JSON 的真实性。可执行 Shell：本选手树内未静态见到
`100755`；`start.ps1` / `l2.cmd` 仅记录路径。大型 JS `quantum-story.iife.js`（1,135,271 bytes）只记
blob，不执行。

本阶段明确无法确认：`verify_all.py` 与 Docker 构建、Remotion/WebGL 是否可构建、loopback Web 的实际 UX、两平台 JSON
是否来自所声称 QPU、`video.mp4` 画面内容。`start.ps1` / `l2.cmd` 只记录路径，未执行。

### 关键证据位置

- [E-1] `archive/generated/snapshots/BEER7LN/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L28 — 产品 README、视频链接与分项声称
- [E-2] `archive/generated/snapshots/BEER7LN/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L44 — 门面转发 pipeline/backends/l2/hybrid
- [E-3] `archive/generated/snapshots/BEER7LN/starter_kit/l2_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L492-L495 — 只允许绑定 127.0.0.1/localhost
- [E-4] `archive/generated/snapshots/BEER7LN/starter_kit/loomq/pipeline.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L19-L50 — StageTrace/PipelineTrace 与 sha256 meta
- [E-5] `archive/generated/snapshots/BEER7LN/start.ps1`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L30 — PowerShell 一键入口，调用 `starter_kit\scripts\l2-service.ps1`（未执行）
- [E-6] `archive/generated/snapshots/BEER7LN/starter_kit/l2.cmd`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — cmd 包装同一 PowerShell 服务脚本（未执行）
- [E-7] `archive/generated/snapshots/BEER7LN/video.mp4`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — Git blob mode=100644，oid=`04ccb04d1b3ce2b750d6b738726bbaccbf6e4bba`，size=35776667；未打开/播放
- [E-8] `archive/generated/snapshots/BEER7LN/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L70 — 勾选全部人工项并填写两平台 job 字段
- [E-9] `archive/generated/snapshots/BEER7LN/starter_kit/tests/test_l2_web_hardware.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L31-L35 — 测试夹具伪造 PEM（重复字母），非真实私钥材料
- [E-10] `archive/generated/snapshots/BEER7LN/starter_kit/motion/remotion/package.json`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L18 — Remotion/React 依赖声明

### 结论置信度

工程结构、loopback 限制、双平台证据文件与视频 blob 元数据为 A。README 分值表与「全部完成」为作者声称（C
若当成绩）。运行、构建、真机与视频内容无法静态确认。

## 27. `zhangsiyue343-hub`

### 身份与路径

- 选手标识：`zhangsiyue343-hub`
- snapshot：`archive/generated/snapshots/zhangsiyue343-hub/`
- 上游：`https://github.com/zhangsiyue343-hub/LoomQ-2026` @
  `1c35b7c28c16366efe0b3366895a0c4b183c6374`
- 规模：约 91 个文件、49 个 `.py`；定制面高
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`starter_kit/cli.py`、`starter_kit/runner.py`、`starter_kit/adapter.py`（均未执行）
- 未静态识别 HTML Web；UX 入口是 CLI

### 技术栈与结构

存在两套并列实现面。契约入口 `starter_kit/adapter.py`（约 1547 行 / 57,102 bytes）是标准库自洽实现：QASM 解析、12
门分解、三方言发射、状态向量 `run()`、`agent_chat`、递归下降 `compile_hybrid`；该文件顶部 import 仅有 stdlib，未引用
`plugin_loader`/`runner`/`di`。另一套在
`lexer.py`/`parser.py`/`ir.py`/`gates.py`/`plugins/{spinq,originq,braket}_plugin.py`/`runner.py`/`di.py`/`agent_fp.py`/`hybrid_compiler.py`/`cli.py`/`cli_agent.py`/`quantum_riscv/`，由根目录
`ARCHITECTURE.md` 描述为「插件 + asyncio / 函数式 L2 / DI」。starter 内另有一份较短的 `ARCHITECTURE.md`
讲「说人话的智能体」。`requirements.txt` 仍是空模板；`requirements-real.txt` 钉
`spinqit==0.2.4`、`pyqpanda==3.8.5`。测试文件多（parser/simulator/hybrid/quantum_riscv/agent_fp/adapter_contract
等，含根 `tests/` 与 `quantum_riscv/test_*.py`）。证据含两个 SpinQ triangulum job 的 QASM/JSON 与 CLI
SVG/TXT。根上有 `docs/`、`NEXT.md`、`.release/`。

### 方案概述

评测若只 `import adapter`，静态可见走自洽模拟器：`transpile` 经 `parse_qasm` 再
`_spinq_ir`/`_originq_ir`/`_braket_ir`；`run()` 用固定种子 `random.Random(12345)` 采样，backend
名称映射到本地 simulator id。同文件后部还有意图启发式 `_is_selection_prompt`（中英关键词）以及 L3 `_split_hybrid` +
`_ClassicalParser`。`ARCHITECTURE.md` 则声称 L1 由插件 `emit`/`run` 与 `asyncio.gather` 并发，原生
SDK 不可用时标注 `builtin:statevector`，并写「adapter.py 是薄壳」。`cli.py` 提供
REPL、`:demo`、`:backend`、`:run` 直方图，并从 `plugin_loader`/`di.bootstrap` 读能力表——即 CLI 走插件树，契约
`adapter.py` 走另一棵树。证据 README 勾选全部人工项，填写 `S-260824-0002` / `S-260824-0003`。根 README
仍为赛题模板。

### 优点

- 契约 adapter 零第三方依赖，三层函数与经典块编译器都在同一可读文件内（A）。
- 插件/DI/函数式 L2 的第二套代码与 10+ 测试文件显示有意识的架构实验（A 对文件）。
- CLI 作为无浏览器 UX 入口，命令说明完整（A）。
- 真机材料按 job id 分文件存放，Bell 与 GHZ-3 成对出现（A 对路径）。
- `ARCHITECTURE.md` 明确写「诚实降级、不伪装真机」，即使它未必接到 `adapter.run`（A 对文字）。

### 质量问题与风险

- **双实现分叉**：`adapter.py` 不 import 插件系统；ARCHITECTURE 描述的 L1 并不是契约入口实际代码。评测与
  CLI/文档可能展示不同行为（A）。
- `plugin_loader.py` 用 `importlib` 动态加载 `*_plugin.py`，属动态导入面（A）。
- `requirements.txt` 为空而 `requirements-real.txt` 才有 SDK，评测默认安装路径可能装不到插件原生后端（A）。
- ARCHITECTURE 声称「121 个标准库 unittest」：测试文件存在，计数与是否通过无法静态确认（C 对 121）。
- `adapter.run()` 固定 RNG 种子，结果可复现但不是真随机硬件（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：声明三层在 adapter 内都有实现；另有插件树、CLI、双电路真机文件与 RISC-V 子目录。可维护性：两套架构并存是主要风险，后续修改容易改错树；文档「薄壳」与
57 KB adapter 正文直接矛盾。安全性：动态导入限定在 `plugins/` 约定文件名，仍需防额外插件目录配置被改。无 Web 监听。`runner.py` 的
asyncio 路径是否被契约调用：从 adapter import 列表看是否定的。无法静态确认评测走哪条路径的「插件并发」或「自洽模拟器」，也不能确认 121 条
unittest 计数。

本阶段明确无法确认：官方评测 import 的是自洽 adapter 还是文档中的插件树、固定种子模拟与原生 SDK 的分布差异、CLI `:demo` 体验、两个 SpinQ
job 文件的真实性。

### 关键证据位置

- [E-1] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L29 — 仅 stdlib import，无插件/DI
- [E-2] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L573-L741 — `transpile` 三方言；`run` 内置模拟 + 固定种子
- [E-3] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1531-L1546 — `compile_hybrid` 调用文件内解析器/发射器
- [E-4] `archive/generated/snapshots/zhangsiyue343-hub/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L8-L40 — 文档声称插件+asyncio 为 L1 落点，adapter 为薄壳
- [E-5] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/plugin_loader.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L26 — 运行时发现 `register()` 插件
- [E-6] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L27 — CLI 入口；后续从 plugin_loader 读能力表
- [E-7] `archive/generated/snapshots/zhangsiyue343-hub/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L20 — 勾选全部人工项并填写两个 SpinQ job

### 结论置信度

双树分叉、adapter 自洽实现与插件文件存在为 A。「评测将使用插件架构」为 C（与入口源码冲突）。禁止把文档架构图当成已接线实现。

## 28. `elenawia`

### 身份与路径

- 选手标识：`elenawia`
- snapshot：`archive/generated/snapshots/elenawia/`
- 上游：`https://github.com/elenawia/LoomQ-2026` @
  `85bd251723b269b3095c6efd5cb0cc9d6b371b29`
- 规模：约 74 个文件、27 个 `.py`、4 个 Web 资源、约 20 个证据文件；定制面高
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`starter_kit/loomq/web/server.py`、`starter_kit/adapter.py`（均未执行）
- 未静态识别第三方 Web 框架；服务为标准库 HTTP

### 技术栈与结构

`adapter.py` 约 802 行，标准库实现 QASM 子集解析、状态向量、三方言格式化、L2 本地/LLM 混合应答、L3 经典块编译。包
`loomq/agent/`（`service.py`/`selector.py`/`examples.py`）与 `loomq/web/server.py` +
`static/{index.html,styles.css,app.js}` 构成「LoomQ Lab」。`llm_client.py` 仍作为 L2 传输层被
adapter import。`requirements.txt` 仍为官方空模板。测试覆盖 adapter QASM、L2 agent、L3 hybrid、bonus
RISC-V、lab，另保留合同 `test_l2_contract.py`。证据含量旋与本源的 PNG、QASM、msgpack/JSON 及
`bonus_quantum_riscv.md`；文件名带实验名、job 短号与 `probability`/`task`/`detail` 等角色。starter
README 被改写成提交说明。根上有 `.release/` 与 `NEXT.md`。

### 方案概述

starter README 一句话：把「一句好奇或一段出错的步骤」变成可运行、可检查、可解释的实验。L1 在 adapter 内完成 `_parse_qasm2` →
`_format_*` / `_simulate_public_subset`。解析要求恰好一个 qreg/creg，非白名单门抛 `QASMParseError`。L2
`agent_chat` 与 `loomq.agent.service.handle_prompt` 为 Web `/api/experiment` 所用；service 层把
prompt 分类成 random/bell/ghz 等并生成中文解释块。`server.py` 默认 `127.0.0.1:8765`，但未像 BEER7LN 那样拒绝非
loopback host。角度解析 `_parse_angle` 使用 `eval(expression, {"__builtins__": {}}, {"pi":
pi})`。证据 README 申报两平台 Bell/GHZ3，并说明量旋侧以截图+job id 为主、本源侧有原始 JSON。L3 由 `compile_hybrid` 与
`tests/test_l3_hybrid.py` 覆盖（文件存在，结果未跑）。Docker 复现命令写在 starter README。

### 优点

- starter README 被改成评审可读的提交说明书，入口、结构、声明层级集中（A）。
- 标准库 L1 解析对非白名单门直接 `QASMParseError`，合同边界清楚（A）。
- Web 前后端分离，agent service 把计数解释成中文概念块（A）。
- 证据附件数量多，且同时出现两个平台命名规则（A 对文件名）。
- 额外测试文件与 `bonus_quantum_riscv.md` 使 Bonus 可定位（A）。

### 质量问题与风险

- `_parse_angle` 的 `eval` 即使清空 builtins，仍是动态求值面（A）。
- `loomq/web/server.py` 的 `--host` 默认为 127.0.0.1，但无白名单校验，若传入 `0.0.0.0` 会按参数绑定（A）。
- POST `/api/experiment` 把异常字符串写回 JSON，可能回显内部错误（A 对代码，C 对信息泄漏）。
- `requirements.txt` 为空：与「标准库为主」一致，但 Web 静态资源之外若评审想装 SDK 无清单（A）。
- 量旋结果含 `.msgpack`；本阶段不解码内容，不能确认 schema（A 对存在，无法静态确认内容）。

### 完整性 / 可维护性 / 安全性观察

完整性：三层函数、Lab Web、双平台证据文件、RISC-V 文档与测试均在。可维护性：adapter 仍偏长，但 web/agent 已拆包；starter README
把评审路径写清楚，优于本组仍用赛题模板首页的提交。安全性：未见硬编码密钥；角度 `eval` 与可选非 loopback 绑定需复核。`server.py` 关闭 access
log（`log_message` 空实现），减少控制台噪声但不改变绑定面。无法静态确认两平台「主峰命中」或页面体验，也不能解码 `.msgpack` 是否符合官方
Schema。

本阶段明确无法确认：Lab 页面与 `/api/experiment` 的实际往返、受限 `eval` 的表达式覆盖面、`--host`
被改成非回环后的暴露、双平台截图/JSON 与 job 的对应关系。

### 关键证据位置

- [E-1] `archive/generated/snapshots/elenawia/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L36 — 提交说明、目录地图与一句话定位
- [E-2] `archive/generated/snapshots/elenawia/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L18-L78 — 12 门白名单与 QASM 子集解析
- [E-3] `archive/generated/snapshots/elenawia/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L221-L227 — `_parse_angle` 使用受限 `eval`
- [E-4] `archive/generated/snapshots/elenawia/starter_kit/loomq/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L62 — Lab HTTP 服务与 `/api/experiment`
- [E-5] `archive/generated/snapshots/elenawia/starter_kit/loomq/agent/service.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L36 — Web 使用的解释/推荐服务层
- [E-6] `archive/generated/snapshots/elenawia/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 勾选人工项并说明两平台申报口径

### 结论置信度

标准库 adapter、Lab 入口与证据文件清单为 A。真机「主峰命中」与 UX 为文档声称（无法静态确认）。`eval` 风险为 A（存在），利用性为 C。

## 29. `talk2joan`

### 身份与路径

- 选手标识：`talk2joan`
- snapshot：`archive/generated/snapshots/talk2joan/`
- 上游：`https://github.com/talk2joan/LoomQ-2026` @
  `116e5511f1691ca808a56b5e81c9c39ef6542729`
- 规模：约 112 个文件、75 个 `.py`（含 vendored antlr）；定制面高
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`starter_kit/webapp.py`、`starter_kit/web/index.html`、`starter_kit/demo.html`（均未执行）
- 未静态识别 `100755` Shell；Braket 委派走 Python `subprocess`

### 技术栈与结构

`adapter.py` 约 1500 行，描述「单管线 + 能力表驱动」。因 spinqit 锁定 antlr 4.9 而 braket 需要 ≥4.10，源码用
`_vendor/antlr49` 影子导入 spinqit，并把 Braket 执行放到 `_braket_worker.py` 子进程。Web：`webapp.py` +
`web/{index.html,style.css,app.js}`，另有大型 `demo.html`（79,540 bytes，内含浏览器端状态向量
`simulate()`）。`requirements.txt` 钉
`amazon-braket-sdk==1.125.0`、`spinqit==0.2.4`、`pyqpanda==3.8.5`、`antlr4-python3-runtime==4.13.2`、`numpy==1.26.4`。证据含
SpinQ gemini 与 triangulum 的 JSON/PNG/QASM。`ARCHITECTURE.md` 把 adapter 称作「量子方言翻译机」，Web 带
Kitty 引导。另有 `test_quantum_riscv.py`。根上有 `.release/`。事实卡对 `demo.html` 的 `exec` 命中对应 JS
`RegExp.exec`，不是 Python `exec`。

### 方案概述

L1：`_parse_qasm` → GateRewriter → 方言 emit → BackendDriver；文档列出
`cx→cnot`、`cu1→cphaseshift`、`sdg→si` 等别名。Braket 优先本进程 `LocalSimulator`（并剥掉 `include`
行），失败则 `subprocess.run` 候选解释器（`LOOMQ_BRAKET_PYTHON`、邻近
`Python312/311/310/python.exe`），最后 `shell=True` 调用 `py -3.12`。L2：大量 `_l2_*`
辅助函数做生成/自验/选后端；`webapp.py` 提供 `POST /api/chat` 与 `/api/run`，在环境变量缺失时尝试读取仓库外
`loomq_secrets.json`（注释写明不入库），默认绑定 `127.0.0.1`，端口可由 `LOOMQ_WEB_PORT` 覆盖。L3 与量子 RISC-V
测试文件 `test_quantum_riscv.py` 同树。前端 `app.js` 对用户/模型文本走 `esc()` 再 `innerHTML`。证据 README
勾选全部人工项，主申报量旋 gemini job，并注明本源悟空维护中；字段中出现平台账号标识类信息。

### 优点

- 把 antlr 版本冲突写成可定位的工程方案：vendor 4.9 + worker 子进程，而不是假装两套 SDK 可共处（A 对代码意图）。
- 依赖五条均精确钉版本（A）。
- Web 聊天对回复做 HTML 转义，降低直接注入模型文本的风险（A 对 `esc` 使用）。
- `ARCHITECTURE.md` 与 adapter 模块文档一致，评审可读（B）。
- 真机材料覆盖同一云平台两台机器的文件名（A 对路径）。

### 质量问题与风险

- `_braket_via_subprocess` 末路 `subprocess.run(..., shell=True)`，即使参数字面量为固定 `py -3.12` 与
  worker 路径，仍属 shell 调用面，需复核（A）。
- 自验模拟路径对门参数 `eval(..., {"pi": ..., "e": ..., "__builtins__": {}})`（A）。
- `webapp.py` 设计从仓库外 JSON 填入 API key；snapshot 内未静态见到该文件，但加载逻辑存在（A 对逻辑，未发现已提交密钥）。
- 证据 README 含平台 `userId` 等账号标识，属隐私暴露面，不在此复制具体值（A）。
- `demo.html` 体积约 79 KB，文本扫描易把 JavaScript `RegExp.exec` 误报为 `exec`；对照为正则 `.exec(`，不是
  Python `exec`（A）。
- `web/app.js` 多处 `innerHTML` 拼接自有 HTML 模板；用户消息路径有 `esc`，其它 DOM 更新需人工过一遍（B）。

### 完整性 / 可维护性 / 安全性观察

完整性：三层、Web、vendor、worker、双机证据与架构文档均在。可维护性：单文件过长 + vendor 树使 diff 噪音大，但冲突原因被写清楚；Windows
风格 `python.exe` 候选路径对 Linux 评测镜像多半无效，真正依赖 `LOOMQ_BRAKET_PYTHON` 或末路 `py`
启动器。安全性：shell=True、eval、外置 secrets 加载、证据中的账号标识是主要观察点。`webapp.py` 绑定 loopback，优于 Flask
`0.0.0.0`。无法静态确认子进程在评测镜像里能找到 Python 3.12，也无法确认 Kitty 页面体验或 `demo.html` 离线模拟与 adapter 一致。

本阶段明确无法确认：vendor antlr 影子导入在干净环境是否成功、`shell=True` 末路是否被走到、仓库外 secrets
文件是否存在于作者机器、证据中的账号标识是否应脱敏、两台 SpinQ 机器结果的真实性。

### 关键证据位置

- [E-1] `archive/generated/snapshots/talk2joan/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L77 — 管线说明、worker/vendor 路径、`_import_spinqit` 影子 antlr
- [E-2] `archive/generated/snapshots/talk2joan/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L392-L414 — Braket 子进程；末路 `shell=True`
- [E-3] `archive/generated/snapshots/talk2joan/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L689-L691 — L2 参考模拟参数 `eval`
- [E-4] `archive/generated/snapshots/talk2joan/starter_kit/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L59 — Web 入口与仓库外 `loomq_secrets.json` 回填逻辑
- [E-5] `archive/generated/snapshots/talk2joan/starter_kit/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L143-L154 — 绑定 `127.0.0.1`
- [E-6] `archive/generated/snapshots/talk2joan/starter_kit/web/app.js`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L36-L58 — `esc()` 后再 `innerHTML`
- [E-7] `archive/generated/snapshots/talk2joan/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L48 — 架构总览与 antlr 冲突方案
- [E-8] `archive/generated/snapshots/talk2joan/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L35 — 勾选人工项；含平台账号标识字段（不复制具体值）
- [E-9] `archive/generated/snapshots/talk2joan/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 五条钉版本依赖

### 结论置信度

antlr 隔离方案、shell=True、eval、Web 转义与证据隐私字段为 A。子进程在评测环境是否可用、真机分布是否成立无法静态确认。

## 30. `33ClayLesley`

### 身份与路径

- 选手标识：`33ClayLesley`
- snapshot：`archive/generated/snapshots/33ClayLesley/`
- 上游：`https://github.com/33ClayLesley/LoomQ-2026` @
  `4b7799c371aaf19f32e5f0222fab65d5b0d98364`
- 规模：约 59 个文件、24 个 `.py`；定制面高（相对文件数，逻辑仍集中在少数模块）
- `submission.yaml` 声明三层 true，`entrypoint: adapter.py`，`required_for_l2: true`
- 静态入口候选：`starter_kit/web/app.py`（Streamlit）、`starter_kit/adapter.py`（均未执行）
- 未静态识别真机 runner 或已填写的 L1 job 附件

### 技术栈与结构

L1/L2 以 Qiskit + Aer + Streamlit 为主。`adapter.py` 约 398 行：`transpile` 透传 QASM；`run` 先
`qiskit.qasm2.loads`，失败则手写正则搭 `QuantumCircuit`，再 `Aer.get_backend('qasm_simulator')`。L2
在同一文件用 `openai` 风格 `chat.completions.create` 做自愈闭环。`web/app.py` 为 Streamlit「量子游乐场」，页面配置
`page_title="LoomQ · 量子游乐场"`，并 import `plot_histogram` / `plot_bloch_multivector` /
`plot_state_qsphere`。`agent/loop.py` 是另一份自愈循环（2,140
bytes）；`agent/__init__.py`、`core/__init__.py`、`core/parser.py` 三个 blob size=0（空文件，oid
`e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`）。`requirements.txt` 为长 freeze，含
`qiskit==2.5.1`、`qiskit-aer==0.17.2`、`streamlit==1.61.1`、`openai==2.53.0`、`matplotlib`、`numpy`
等。根目录另有 `test_agent.py`、`test_agent_chat.py`、`test_custom_circuit.py`、`test_L3.py`。证据为 8
张 UX PNG（`ux_screenshot1.png`…`8.png`）；L1 真机与 RISC-V Bonus 未勾选。starter README
仍是官方模板。公开电路除 bell/ghz3 外还有 `ccx.qasm`/`cu1.qasm`/`swap.qasm`。

### 方案概述

`load_dotenv` 读取 starter 上一级 `.env`。Qiskit import 失败时 `print` 缺失依赖但继续定义函数。`agent_chat`
读后端能力 JSON，无文件时用硬编码备用列表（含 spinq_taurus / originq_wukong / braket_local_simulator
等）；若回复不含 ` ```qasm ` 则当作后端推荐直接返回，否则本地 Aer 校验最多重试 2 次。`compile_hybrid` 用栈匹配 `classical
{}`，再对去空白后的 `if(c[i]==v){r=...}else{r=...}` 正则生成 RISC-V，并可选匹配后续
`rN=rN+K`；量子操作列表只保留门名字符串。Web/证据声称 `streamlit run starter_kit/web/app.py`，地址
`http://localhost:8501`。`web/app.py` 把项目根插入 `sys.path` 后 `from starter_kit.adapter
import agent_chat, run`。这些是源码与文档对照。

### 优点

- Streamlit 游乐场把能力表、直方图、Bloch/Qsphere 等可视化库接线到 `agent_chat`/`run`，交互面完整可见（A 对 import
  与页面配置）。
- L2 自愈闭环与后端推荐分岔在 adapter 内可读（A）。
- 根目录有多份自写测试文件名，针对 agent/L3/自定义电路（A 对存在）。
- 证据勾选与材料一致：未勾 L1 真机，也无 job JSON；勾了 L2/工程/视觉并附 8 张截图（A）。
- `compile_hybrid` 至少处理括号匹配，而不是完全空实现（A）。

### 质量问题与风险

- `transpile()` 透传，三平台原生 IR 变换未在该函数出现（A）。
- `run()` 的 fallback `eval(param_str, {'pi': math.pi})` **未**清空 `__builtins__`，比受限
  `eval` 面更宽（A）。
- `agent/`、`core/parser.py` 为空包/空模块，目录名暗示的解析层并不存在（A）。
- `agent/loop.py` import 了 `subprocess` 但可见逻辑走 Aer；疑似未完成拆分，与 adapter 内闭环重复（A 对重复/空模块，C
  对是否死代码）。
- `requirements.txt` 混入 uvicorn/starlette 等，像整环境 freeze（A）。
- L3 正则针对单一 if-else 模板，通用 Hybrid-QASM 无法从源码确认（A 对模板，无法静态确认隐藏用例）。
- 根 README 与 starter README 仍为赛题模板，Streamlit 入口主要写在 evidence（A）。

### 完整性 / 可维护性 / 安全性观察

完整性：声明三层均有函数体；真机与 RISC-V Bonus 按勾选为未申报，与缺失 job JSON 一致。可维护性：空 `core/parser.py` 与双份 agent
循环降低可信度，目录结构像未完成重构；Qiskit/Streamlit freeze 使沙箱评测安装面显著。安全性：`.env` 加载路径指向仓库父目录，snapshot
内未静态见到已填 `.env`；宽 `eval` 是主要代码风险。`run()` 在 Qiskit 缺失时仍可能走到 `loads`/`Aer`
名称，属于导入失败后的脆弱路径。无法静态确认 Streamlit 能启动、Aer 与官方位序一致，或截图来自该 `app.py`。

本阶段明确无法确认：Qiskit/Aer/Streamlit freeze 能否在评测镜像安装、透传 `transpile` 是否被官方 IR 检查拒绝、宽 `eval`
的可达性、空 `core/parser.py` 是否曾被引用、L3 正则对其它 classical 块的行为。

### 关键证据位置

- [E-1] `archive/generated/snapshots/33ClayLesley/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L13-L62 — dotenv、能力表、Qiskit import；`transpile` 透传
- [E-2] `archive/generated/snapshots/33ClayLesley/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L64-L190 — `run`：loads 失败则正则建电路，`eval` 解析 cu1 参数后走 Aer
- [E-3] `archive/generated/snapshots/33ClayLesley/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L278-L394 — L2 自愈闭环；L3 正则 if-else 编译
- [E-4] `archive/generated/snapshots/33ClayLesley/starter_kit/web/app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L31 — Streamlit 页面，导入 `agent_chat`/`run`
- [E-5] `archive/generated/snapshots/33ClayLesley/starter_kit/core/parser.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — 空 blob，size=0，oid=`e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`
- [E-6] `archive/generated/snapshots/33ClayLesley/starter_kit/agent/loop.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 第二份自愈循环；文件头 import `subprocess`
- [E-7] `archive/generated/snapshots/33ClayLesley/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L50 — 未勾 L1/RISC-V；勾选 L2 并写 Streamlit 启动命令
- [E-8] `archive/generated/snapshots/33ClayLesley/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L50-L61 — 钉住 qiskit/qiskit-aer/streamlit/openai

### 结论置信度

透传 transpile、Aer `run`、空 `core/parser.py`、Streamlit 入口与证据勾选为 A。L3
仅覆盖模板、游乐场能否运行无法静态确认。禁止把截图或 freeze 清单写成评测通过。

## 31. `alicewangzm`

### 身份与路径

- contestant ID：`alicewangzm`
- snapshot：`archive/generated/snapshots/alicewangzm/`
- 聚合仓库基线：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：`https://github.com/alicewangzm/LoomQ-2026`
- 上游 SHA：`ce2d7af67732daf1774f26e0e2c3fe3e46f92798`
- 契约入口：`starter_kit/adapter.py`；`submission.yaml` 声明 `l1: true`、`l2: true`、`l3: false`，运行时 Python 3.10，L2 需要网络与 `LOOMQ_LLM_*`
- 根目录含赛题发布包、`competition/`、`starter_kit/`、`tests/`；starter 额外包为 `loomq/`
- 契约文件：`submission.yaml`、`adapter.py`、`evaluator.py`、`Dockerfile`、`requirements.txt` 均在 `starter_kit/`

### 技术栈与结构

静态可见 Python + 标准库 HTTP 服务 + HTML；依赖锁定 `spinqit==0.2.4`、`pyqpanda==3.8.5`，并在注释中说明不装 `amazon-braket-sdk`，以避免与 spinqit 的 antlr 冲突。
`SUPPORTED_TARGETS` 仍列出 `braket`，但运行时实现只覆盖 spinq / originq。
定制面集中在 `starter_kit/loomq/`：parser、emitters、runtime、agent、webapp、测试与 `index.html`。
官方 `evaluator.py` 行数与 starter 模板一致（226 行），adapter 仅 48 行，转调 loomq 包。
根 README 仍是赛题发布包模板；产品说明写在 `starter_kit/loomq/README.md`。
Dockerfile 与 `l2_policy.json`、`llm_client.py` 仍在 starter 顶层。
公开电路仍为 `circuits/bell.qasm`、`ghz3.qasm`。

### 方案概述

README 声称目标用户是零量子背景读者：自然语言 → 可运行电路 → 图示讲解 → 本地模拟。
L1 走「OpenQASM 2.0 → 中性 IR → 后端方言」：`parser.parse_qasm` 产出寄存器与 ops 列表，`emitters` 生成 SpinQ QASM 2.0 与 OriginIR，`runtime.run` 调本地模拟器并把 counts 归一到 little-endian。
L2 `agent_chat` 用官方 `llm_client`，单一系统提示覆盖 GENERATE / FIX / RECOMMEND / GUIDE，再用 L1 parser 做自校验环路（最多 2 次重试）。
`webapp.py` 提供 `GET /`、`POST /api/chat`、`POST /api/run`，默认执行 target 为 originq。
`compile_hybrid` 显式 `NotImplementedError`，与 yaml 的 `l3: false` 一致。
证据 README 勾选 L2 交互、工程与产品化、新手引导 Bonus，未申报真机与 RISC-V Bonus。

### 优点

- 契约入口薄、实现分模块，parser / emitter / runtime / agent / UI 边界清楚。
- L2 不只把模型原文当最终答案：生成电路后用同一套 L1 parser 校验并回喂错误。
- Web UI 仅标准库 `HTTPServer`，默认绑定 `127.0.0.1`；文档明确无 CDN。
- 依赖注释直接记录 antlr 冲突，避免把三后端硬塞进同一环境。
- 自带 `loomq/test_parser.py`、`test_emitters.py`、`test_agent.py` 与 `run_tests.py`，测试面超出官方两份契约测试。

### 质量问题与风险

- `transpile()` 在 `target == "braket"` 时抛 `ValueError`，与 `SUPPORTED_TARGETS` 三元组不一致；yaml 虽未强制三后端同时可装，但入口集合与实现集合漂移。
- `parser._parse_params` 使用 `eval(..., {"__builtins__": {}}, {"pi": math.pi})` 解析角度。空 builtins 降低风险，仍属动态求值，复杂表达式或非数字输入行为无法静态确认。
- `webapp.do_POST` 按 `Content-Length` 整段读入，未见上限；`/api/run` 把请求里的 QASM 直接交给模拟器。
- `emit_originir` 把 `sdg`/`tdg` 写成等效 RZ，文档称测量分布不变；这是近似映射，相位语义是否被评测器接受无法静态确认。
- 证据包无截图/files；L2 体验依赖现场注入 LLM，无法静态确认交互质量。

### 完整性 / 可维护性 / 安全性观察

完整性：L1 两个后端 + L2 agent + 网页入口齐全；L3 按声明缺席。
`evidence/files/` 未出现。可维护性：loomq README 有模块表与命令；
adapter 通过 `sys.path.insert` 导入扁平模块，包导入与脚本导入混用。
`emitters.emit_spinq` 取 `list(ir["qreg"])[0]` 作为唯一量子寄存器名，多 qreg 输入会丢失名称。
安全性：未发现 `.env` 或硬编码密钥；LLM key 走环境变量。`subprocess` 仅出现在 `LOOMQ_DEV` 热重载监督进程，正式路径不启动子进程。
监听地址为本地回环。`/api/chat` 与 `/api/run` 异常只回传最后一行 200 字符。
在受检路径下未静态发现真实凭据。无法静态确认 Windows 文档中的 `.venv/Scripts/python` 在 Linux 评测镜像上的对应关系。

### 关键证据位置

- [E-1] `archive/generated/snapshots/alicewangzm/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L21 — 声明 L1/L2、关闭 L3，L2 需 `LOOMQ_LLM_*`
- [E-2] `archive/generated/snapshots/alicewangzm/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L20-L47 — adapter 转调 loomq；`compile_hybrid` 未实现
- [E-3] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/runtime.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L23-L31 — `transpile` 只实现 spinq/originq
- [E-4] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/parser.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L51-L69 — 角度参数走受限 `eval`
- [E-5] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L154-L187 — L2 自校验重试环
- [E-6] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L124-L128 — 默认监听 `127.0.0.1:8000`
- [E-7] `archive/generated/snapshots/alicewangzm/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L15 — 勾选 L2/工程/视觉，未申报真机
- [E-8] `archive/generated/snapshots/alicewangzm/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — 锁定 spinqit/pyqpanda，刻意省略 braket
- [E-9] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L18-L32 — 模块表与数据流（自然语言→IR→后端）
- [E-10] `archive/generated/snapshots/alicewangzm/starter_kit/loomq/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L95-L118 — chat/run API 与异常截断

### 结论置信度

结构、yaml 字段、入口函数与未实现 L3 为高（A）。「零基础产品」叙事为 README 声称，与 webapp/agent 对照为中（B）。无法静态确认：依赖可安装性、公开/隐藏电路行为、网页交互体验、自校验对评测用例的效果。

## 32. `qianqiu0926`

### 身份与路径

- contestant ID：`qianqiu0926`
- snapshot：`archive/generated/snapshots/qianqiu0926/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/qianqiu0926/LoomQ-2026` @ `75974ad3b82c63f5d1e26dabebf796575cb1e3da`
- yaml 声明 L1/L2/L3 全开，Python 3.10，L2 需网络；入口 `adapter.py`
- 额外树：`starter_kit/loomq/`（IR、pipeline、hybrid、web、quantum_riscv）、`starter_kit/docs/`、`starter_kit/tests/`、`verify_submission.py`
- 契约文件齐全；evaluator 仍为 226 行公开自测模板

### 技术栈与结构

`requirements.txt` 正文写明「只用 Python 3.10 标准库、无第三方运行时依赖」。
L1 执行走自研态矢量模拟器，不在依赖清单中出现 spinqit/pyqpanda/braket。
adapter 47 行，把 `transpile`/`run`/`agent_chat`/`compile_hybrid` 委托给 `loomq.ir`、`emitters`、`pipeline.verified_run`、`agent`、`hybrid`。
另有零依赖 Web（`loomq/web.py` + `web_assets/`）和 CLI（`python -m loomq`）。
文档面很大：`ARCHITECTURE.md`、`QUANTUM_RISCV_SPEC.md`、`VERIFICATION.md` 等。
`simulator.py` 将三 target 映射到不同 `backend` 字符串，但执行核是同一份态矢量。
`MAX_QUBITS = 20`。根目录另有 `.release/`、`NEXT.md`。

### 方案概述

核心论点是「单一语义 IR + 翻译验证」：源 QASM 解析为 `Circuit` 后，emitter 生成目标文本，`verification.certify_translation` 再独立回读目标伪代码，比较操作轨迹、测量映射与状态向量，证书通过后才 `execute`。
`run()` 的 meta 写入 `translation_certificate` 与 `executed_ir=independently-reparsed-target`。
L2 要求模型返回 JSON 计划，已知态族用确定性 builder，后端推荐用 `backend_capabilities.json` 本地筛选。
L3 是 Hybrid-QASM 递归下降编译到 RISC-V；Bonus 另有 `custom-0` 量子指令编码（`quantum_riscv.py`，opcode `0x0B`）。
证据勾选 L2、工程、RISC-V Bonus、视觉 Bonus，明确不申报真机，本地 job 前缀 `loomq-local-`。

### 优点

- L1 不依赖互斥 SDK，三 target 共用同一模拟器，从依赖层面回避 antlr 冲突。
- 翻译验证与「先发证书再执行」在源码和架构文档中互相印证，可审计。
- Web 有请求 1 MiB 上限、静态资源 `resolve()` 后限制在 `web_assets`、默认 `127.0.0.1:8765`。
- L2 把用户文本定义为数据，硬约束由本地规则保护，而不是全权交给模型。
- 提交包内有 `verify_submission.py` 与多份单元测试文件（agent/hybrid/transpiler/web/quantum_riscv）。

### 质量问题与风险

- 三后端 `run()` 在静态阅读下都落到同一 `simulator.execute`；「三个平台原生执行」并未出现，评测若要求真实 SDK 路径，行为无法静态确认。
- `verify_submission.py` 用 `subprocess.run` 调 unittest 与 `evaluator.py`，属本地自检编排，不是评测入口。
- 证据无截图；L2/视觉申报依赖「工作人员直接运行」。
- RISC-V Bonus 实现与官方 `riscv_emulator.py` 的关系是「扩展编解码 + 文档规格」，官方模拟器是否识别 `custom-0` 无法静态确认。

### 完整性 / 可维护性 / 安全性观察

完整性：yaml 三级均有对应函数；真机证据按文档主动留空。可维护性：docs 把威胁模型、IR 约束、寄存器映射写清楚；
adapter 用 try/except 兼容包导入与平铺导入。`cli.py` 内置 Bell 示例与字符直方图。
安全性：架构文档列出 QASM 注入、prompt injection、路径穿越、key 泄露等控制；
源码侧可见路径限制与 1 MiB 上限。Web 错误 JSON 含 `recovery` 字段。
在受检路径下未静态发现真实密钥。`allowed_hosts` 为空数组，与「L2 需要网络」同时出现，实际放行策略无法静态确认。
官方 `evaluator.py` 仍为 226 行模板。

### 关键证据位置

- [E-1] `archive/generated/snapshots/qianqiu0926/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L21 — 声明三级全开，L2 需环境变量
- [E-2] `archive/generated/snapshots/qianqiu0926/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L46 — 四级入口全部委托 loomq
- [E-3] `archive/generated/snapshots/qianqiu0926/starter_kit/loomq/pipeline.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L20 — 认证后再执行独立回读目标
- [E-4] `archive/generated/snapshots/qianqiu0926/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L2 — 声明无第三方运行时依赖
- [E-5] `archive/generated/snapshots/qianqiu0926/starter_kit/loomq/web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L18-L18 — 请求体上限 1 MiB
- [E-6] `archive/generated/snapshots/qianqiu0926/starter_kit/loomq/web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L92-L111 — 静态路径限制在 assets；默认 127.0.0.1:8765
- [E-7] `archive/generated/snapshots/qianqiu0926/starter_kit/docs/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L28-L70 — 翻译验证、L2 闭环与威胁模型
- [E-8] `archive/generated/snapshots/qianqiu0926/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L3-L13 — 不申报真机；勾选 L2/工程/RISC-V/视觉
- [E-9] `archive/generated/snapshots/qianqiu0926/starter_kit/loomq/quantum_riscv.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L28 — custom-0 编码常量
- [E-10] `archive/generated/snapshots/qianqiu0926/starter_kit/verify_submission.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L35 — 本地 subprocess 编排 unittest 与公开 evaluator
- [E-11] `archive/generated/snapshots/qianqiu0926/starter_kit/loomq/simulator.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L19 — 自研模拟器与三 backend 字符串映射

### 结论置信度

模块地图、yaml、无第三方依赖声明、Web 绑定与路径限制为高（A）。「翻译验证能抓住相位错误」为文档与代码结构对照，中（B）。无法静态确认：自研模拟器与官方 SDK 语义是否等价、L2 JSON 计划在隐藏集上的表现、custom-0 指令能否被官方模拟器执行。

## 33. `Yolanlanlanda`

### 身份与路径

- contestant ID：`Yolanlanlanda`
- snapshot：`archive/generated/snapshots/Yolanlanlanda/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/Yolanlanlanda/LoomQ-2026` @ `91a484ce9a5b822ba3aaf408735b1933e802e112`
- yaml 声明 L1/L2/L3 全开；额外 Python 仅 `hybrid_compiler.py`、`interactive.py`，主体实现压在 910 行 `adapter.py`
- 契约文件齐全；证据目录 `starter_kit/evidence/files/` 非空

### 技术栈与结构

Python + 标准库网页「量语」。依赖 `spinqit==0.2.4`、`pyqpanda==3.8.5`；
requirements 注释说明 braket 与 spinqit 的 antlr 锁冲突，提交环境以 spinq+originq 为双后端，braket 代码仍留在 adapter。
L1 为逐行 QASM 改写（braket QASM3、spinq 文件编译、originq OriginIR）。
L2 意图分类 + 可选自检生成 + 约束抽取后本地筛选后端。L3 委托 `hybrid_compiler.compile_hybrid`。
证据目录含 SpinQ/OriginQ 电路、json/msgpack、截图、架构 SVG 与 L2 聊天截图。
adapter 内 `_transpile_to_braket` 会去掉 include 再交给 LocalSimulator，同时保留 include 以满足契约。
无独立 `src/` 包。

### 方案概述

adapter 顶部写明三后端 transpile/run「均已实现」，同时警告 antlr 无法共存。
L2 `agent_chat` 组合关键词意图与模型分类，电路路径可走 `_generate_with_selfcheck`，后端路径用 LLM 抽 JSON 约束再过滤 `backend_capabilities.json`。
`interactive.py` 内嵌单文件 HTML，`POST /chat` 把最近 6 轮历史拼进 prompt 后调 `agent_chat`。
证据勾选 L1 真机（SpinQ NMR job `G-260819-0002`、本源悟空 job `E782EA6B30439B7EE5199CC750DD0382`）、L2、工程；
未勾选 RISC-V 与视觉 Bonus，尽管 L3 编译器源码存在。

### 优点

- L1 三个 target 的转译与执行函数在同一文件内可定位，位序反转有注释。
- L2 把「选后端」做成约束抽取 + 本地表筛选，而不是只靠模型自由发挥。
- 交互入口零第三方依赖，绑定 `127.0.0.1`，缺 key 时返回中文错误。
- 真机证据同时给出 job ID、QASM、原始结果和截图路径，材料形态完整（真实性无法静态确认）。
- L3 迷你文法、寄存器映射与官方七条指令子集写在 `hybrid_compiler.py` 模块文档中。

### 质量问题与风险

- braket 实现存在但未进入 `requirements.txt`，同一容器内三后端共存按作者自己的注释不可行。
- `interactive.py` 设置 `Access-Control-Allow-Origin: *`。服务默认只绑回环，风险面小于 0.0.0.0，仍是开放 CORS。
- Scout 扫描命中的 `exec` 实为前端 `RegExp.exec`，不是 Python `exec`。
- adapter 体量 910 行，L1/L2 工具函数与 prompt 字符串耦合，后续修改面大。
- 证据未勾选 RISC-V Bonus，与已实现的 `compile_hybrid` 申报口径不一致（不一定是缺陷，但是声明面缺口）。

### 完整性 / 可维护性 / 安全性观察

完整性：yaml 三级均有实现函数；真机与 L2 截图文件存在于 `evidence/files/`。
可维护性：L2 逻辑未拆包，prompt 与筛选规则内嵌。`hybrid_compiler` 使用 `x30`/`x29` 作临时寄存器。
安全性：证据声明「Key 绝不写入仓库」；受检路径未见 `.env` 或真实 token。
监听 `127.0.0.1`。`_selfcheck_available` 失败时静默回退单次调用，自检是否实际启用无法静态确认。
端口可由 `LOOMQ_PORT` 覆盖。无法静态确认 NMR 概率主峰描述是否满足人工核验规则。

### 关键证据位置

- [E-1] `archive/generated/snapshots/Yolanlanlanda/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L21 — 三级全开
- [E-2] `archive/generated/snapshots/Yolanlanlanda/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — 作者说明 antlr 冲突与双后端策略
- [E-3] `archive/generated/snapshots/Yolanlanlanda/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L819-L909 — `agent_chat` 意图组合与 `compile_hybrid` 委托
- [E-4] `archive/generated/snapshots/Yolanlanlanda/starter_kit/hybrid_compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L17 — L3 输入输出与迷你文法
- [E-5] `archive/generated/snapshots/Yolanlanlanda/starter_kit/interactive.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L60-L67 — CORS `*`
- [E-6] `archive/generated/snapshots/Yolanlanlanda/starter_kit/interactive.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L586-L591 — `TCPServer(("127.0.0.1", PORT), ...)`
- [E-7] `archive/generated/snapshots/Yolanlanlanda/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L42 — 勾选真机/L2/工程，填写双平台 job
- [E-8] `archive/generated/snapshots/Yolanlanlanda/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L11 — 不装 braket 的原因
- [E-9] `archive/generated/snapshots/Yolanlanlanda/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L120-L128 — braket 运行时剥离 include
- [E-10] `archive/generated/snapshots/Yolanlanlanda/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L56-L77 — L2 启动命令与三则现场任务

### 结论置信度

文件树、yaml、CORS/监听地址、L3 委托为高（A）。真机 job 与截图为选手申报材料，对「确实在真机上跑过」为低（C）。无法静态确认：双后端在评测容器是否可共存、L2 自检是否启用、截图与当前代码是否对应。

## 34. `Andante397`

### 身份与路径

- contestant ID：`Andante397`
- snapshot：`archive/generated/snapshots/Andante397/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/Andante397/LoomQ-2026` @ `4012e5d69745401e3515e0daffeebf0990d2accc`
- yaml **仅声明 L1**（`l2: false`、`l3: false`），`network.required_for_l2: false`
- `extra_py` 为空：定制集中在 `adapter.py`（328 行），starter 其余 Python 文件保持工具包骨架。这是定制面观察，不是完成度或态度评价。
- 契约文件齐全；无选手自测目录增量

### 技术栈与结构

Python。`requirements.txt` 锁定 `amazon-braket-sdk==1.125.0`、`pyqpanda3==0.4.1`，未列 spinqit。
adapter 自建 `Circuit`/`Gate`/`Measure` IR，`parse_qasm` 支持整寄存器广播。
后端插件：`BraketBackend`（Braket Circuit API + LocalSimulator）、`OriginQBackend`（OriginIR 文本 + `pyqpanda3` CPUQVM）。
`BACKENDS` 字典只有 `braket` 与 `originq`，spinq 以注释 TODO 留空。
`agent_chat` / `compile_hybrid` 为 `NotImplementedError`，与 yaml 关闭 L2/L3 一致。
证据 README 仍为空白模板。starter 仍含 `examples/run_spinq.py` 等官方示例，但 adapter 未接线。
根目录有 `NEXT.md`、`.release/`。相对官方 starter 的 Python 文件增量约为零。

### 方案概述

L1 路径：QASM 子集 → IR → `Backend.codegen` / `execute` → `normalize` 把测量位序转到 `c[n-1]...c[0]`。
Braket 执行前对每个量子比特铺 `I` 门，注释称避免未参与运算的比特从结果串消失。
OriginQ 用 `DAGGER` 块表达 `sdg`/`tdg`，`cu1` 映射为 `CP`。
`run()` 返回统一 schema，`job_id` 为 uuid 前 8 位，`meta.depth` 注释为 TODO（目前等于门数）。
公开电路 `bell.qasm`/`ghz3.qasm` 仍在 `circuits/`。

### 优点

- yaml 声明与未实现入口一致，没有「声明了却 raise」的层级错位。
- IR 与后端插件分离，三元组门白名单写在 `WHITELIST`。
- 位序归一化单独成 `normalize()`，而不是散落在各 SDK 调用里。
- 对 pyqpanda3 API 的选择是显式的（`convert_originir_string_to_qprog`），与多数选手的 pyqpanda 2.x 路径不同，属于可观察的技术选型。

### 质量问题与风险

- `transpile("...", "spinq")` / `run(..., "spinq")` 会 `KeyError`，因为 `BACKENDS` 无 spinq。若评测默认 target 含 spinq，该路径静态可见不可用。
- `_evaluate` 用 `eval` 解析 `pi/2` 一类角度，builtins 已清空，仍是动态求值。
- `meta.depth` 被赋成门计数，注释已标明不是真正深度。
- 无额外测试、无填写证据、无 Web/CLI。官方 `tests/test_l2_contract.py` 仍在树中，但 yaml 关闭 L2。
- 依赖 `pyqpanda3` 而非清单里更常见的 `pyqpanda==3.8.5`，与官方 examples 是否兼容无法静态确认。

### 完整性 / 可维护性 / 安全性观察

完整性：按自身 yaml，L1 两后端有实现，L2/L3 按声明缺席；spinq 在 L1 集合内缺失。
可维护性：单文件、注释密度高，TODO 未隐藏。`transpile` 对未知 target 直接 `BACKENDS[target]`，无事先白名单错误信息。
安全性：无网络服务、无 LLM 调用实现；`eval` 是主要静态风险点。在受检路径下未静态发现凭据文件。
接近官方 starter 的 Python 文件集合，不等于「未作 L1」——adapter 已从占位改成 IR+双后端。
官方 `tests/test_submission_tools.py` 与 `test_l2_contract.py` 仍在，属于发布包残留。

### 关键证据位置

- [E-1] `archive/generated/snapshots/Andante397/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L14 — 仅 L1，L2 网络关闭
- [E-2] `archive/generated/snapshots/Andante397/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L131-L134 — 角度 `eval`
- [E-3] `archive/generated/snapshots/Andante397/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L283-L287 — 注册表缺 spinq
- [E-4] `archive/generated/snapshots/Andante397/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L317-L326 — L2/L3 未实现
- [E-5] `archive/generated/snapshots/Andante397/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L2 — braket + pyqpanda3
- [E-6] `archive/generated/snapshots/Andante397/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 人工评分项均未勾选
- [E-7] `archive/generated/snapshots/Andante397/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L172-L211 — Braket 铺 I 门后 LocalSimulator 执行
- [E-8] `archive/generated/snapshots/Andante397/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L268-L278 — OriginQ 走 pyqpanda3 OriginIR 编译器

### 结论置信度

yaml 仅 L1、spinq 缺席、L2/L3 NotImplemented 为高（A）。无法静态确认：braket/originq 执行正确性、pyqpanda3 在评测镜像中的可安装性、整寄存器广播是否被隐藏集使用。

## 35. `iiixiscientia`

### 身份与路径

- contestant ID：`iiixiscientia`
- snapshot：`archive/generated/snapshots/iiixiscientia/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/iiixiscientia/LoomQ-2026` @ `bbe5f1ce1baffc5109304776742f351f234f7708`
- yaml 三级全开；starter 缺顶层 `__init__.py`（fact card `missing_py`）
- 结构：`src/`（ir/parser/codegen/backends/agent/hybrid）、`web_app.py`、`real_hardware/`、`circuits/coverage/`、`tests/`、`docs/quantum_riscv_isa.md`
- 契约文件齐全；另有 `requirements-spinq.txt` 与改过的 Dockerfile

### 技术栈与结构

Python。主环境 `pyqpanda==3.8.5`、`amazon-braket-sdk==1.110.1`、`antlr4-python3-runtime==4.13.2`；
另备 `requirements-spinq.txt` 与 Dockerfile 中的 `spinq_env` venv。
`src/backends/spinq_backend.py` 经 subprocess 调 `spinq_env/bin/python3` + `spinq_runner.py`。
adapter 说明 transpile 产物与本地可执行产物可分离（braket 去掉 `stdgates.inc`，originq 用 `pyqpanda_compat`）。
L2 在 `src/agent/` 做 function calling 闭环；L3 在 `src/hybrid_compiler.py`；
Bonus 另有 `src/quantum_riscv_emulator.py`（opcode custom-0 / 十进制 11）。
Web 为单文件 HTML，Chart.js 来自 jsDelivr CDN。`circuits/coverage/` 含 14 份门覆盖 QASM。
`real_hardware/` 另有 originq/spinq 提交脚本。

### 方案概述

统一 IR + 三后端 codegen；`run()` 先 `transpile` 再执行，但 braket/originq 本地执行使用兼容开关，对外 IR 保持契约拼写。
L2 用 urllib 直连 OpenAI-compatible 接口，工具里含 `run_circuit` 自验与 `find_backends`。
L3 花括号配对切 `classical {}` 后递归下降。证据勾选全部人工项；
真机只完整填写量旋 `G-260730-0005`，并说明本源悟空卡在平台 maintenance。
`real_hardware/results/` 有 json。`SUBMISSION_README.md` 仍描述「submission/ 目录草稿」与 `spinq_runner.py`，与当前 snapshot 布局不完全一致。

### 优点

- 12 门覆盖电路与 `gate_coverage_test.py`、`smoke_test.py` 等测试文件数量明显多于官方两份契约测试。
- 明确记录 antlr 冲突并用独立 venv + Dockerfile 步骤固化（是否在评测机生效无法静态确认）。
- transpile 契约文本与 SDK 可执行文本分开，注释解释了 LocalSimulator 对 include 的文件查找行为。
- L2 缺环境变量时错误信息不回显 key；hybrid 与 quantum RISC-V 有独立模块文档。
- 真机结果 json 与非对称 `swap_basic` 交叉材料被单独标注「不重复计平台分」。

### 质量问题与风险

- `spinq_backend.py` 引用 `starter_kit/spinq_runner.py`，该 snapshot 的 starter 根目录**没有** `spinq_runner.py` 文件。spinq 子进程路径在静态意义上不完整。
- `web_app.py` 监听 `0.0.0.0`，且页面加载外部 CDN 脚本；离线或禁网环境 UI 图表会缺依赖。
- starter 顶层无 `__init__.py`，`import starter_kit.adapter` 是否成立取决于评测导入方式。
- `SUBMISSION_README.md` / 部分 README 树状图仍写 `spinq_runner.py`、旧目录名，文档滞后。
- 证据 job 时间为 2026-07-30，早于多数选手材料中的 8 月日期；只记录申报文本，不推断真伪。

### 完整性 / 可维护性 / 安全性观察

完整性：L1/L2/L3 源码入口齐全，但 spinq runner 脚本缺失构成实现链断裂。
Dockerfile 会建 `spinq_env`，却仍 COPY 不到不存在的 runner。
可维护性：`src/` 分层清楚，根 README 与 SUBMISSION_README 有重复且过时。
`web_app.py --cli` 提供终端回退。安全性：CDN 与 `0.0.0.0` 是主要观察点；
硬件脚本从环境读 token。在受检路径下未静态发现真实密钥。`evidence/files/` 未放截图，真机 json 在 `real_hardware/results/`。
官方 `evaluator.py` 仍为模板 226 行。

### 关键证据位置

- [E-1] `archive/generated/snapshots/iiixiscientia/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L21 — 三级全开
- [E-2] `archive/generated/snapshots/iiixiscientia/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L27-L96 — 四级入口与兼容执行说明
- [E-3] `archive/generated/snapshots/iiixiscientia/starter_kit/src/backends/spinq_backend.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L29-L50 — 依赖缺失的 `spinq_runner.py` 与 subprocess
- [E-4] `archive/generated/snapshots/iiixiscientia/starter_kit/Dockerfile`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L15-L19 — 构建 `spinq_env`
- [E-5] `archive/generated/snapshots/iiixiscientia/starter_kit/web_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L38-L38 — CDN Chart.js
- [E-6] `archive/generated/snapshots/iiixiscientia/starter_kit/web_app.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L954-L954 — `HTTPServer(("0.0.0.0", args.port), ...)`
- [E-7] `archive/generated/snapshots/iiixiscientia/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L32 — 全选人工项；仅完整填写量旋 job
- [E-8] `archive/generated/snapshots/iiixiscientia/starter_kit/src/agent/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L37-L44 — 缺环境变量时报错且不回显 key
- [E-9] `archive/generated/snapshots/iiixiscientia/starter_kit/src/quantum_riscv_emulator.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L27 — 官方模拟器 fork 与 custom-0 编码
- [E-10] `archive/generated/snapshots/iiixiscientia/starter_kit/SUBMISSION_README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L9-L33 — 仍列出当前树中不存在的 `spinq_runner.py`

### 结论置信度

缺失 `spinq_runner.py`、`0.0.0.0`、CDN、yaml 字段为高（A）。
「本源卡在 maintenance」仅为文档声称（C）。无法静态确认：覆盖测试结果、function calling 是否被评测模型支持、`real_hardware` json 是否对应本次代码。

## 36. `LinXuan2576`

### 身份与路径

- contestant ID：`LinXuan2576`
- snapshot：`archive/generated/snapshots/LinXuan2576/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/LinXuan2576/LoomQ-2026` @ `49e88391754d7f7a17d5702eecffff7cbd4df4af`
- yaml 三级全开，但 `network.required_for_l2: false`（与 L2 实际走 LLM 的实现对照，属于配置漂移）
- 额外模块：`cli.py`、`l2_agent.py`、`hybrid_compiler.py`、`originq_backend.py`、`riscv_emulator_qext.py`、证据目录内的探测脚本
- 契约文件齐全；另有 `.env.local.example`、`docs/FIRST_RUN.md`、`docs/riscv-quantum-ext.md`

### 技术栈与结构

Python + numpy 自写 statevector（spinq 降级路径）。
依赖 `amazon-braket-sdk==1.110.1`、`numpy==1.26.4`、`pyqpanda==3.8.5`。
adapter 458 行：spinq 优先编程式 Circuit，失败（缺包或 antlr ATN）降级 `_run_spinq_sim`；
braket 做 QASM2→3 文本改写；originq 全部委托 `originq_backend.py`。
L2 在 `l2_agent.py`（JSON 信封 + 模拟器自验）；交互入口是 CLI 而非网页。
L3 `hybrid_compiler` 三段式；Bonus `riscv_emulator_qext.py` opcode `0x77`。
另有 `.env.local.example` 与 `docs/FIRST_RUN.md`。
证据文件数量多（json、msgpack、png、qcloud_reports）。
`sdg`/`tdg` 在 Braket 路径改写为 `rz(-pi/2)` / `rz(-pi/4)`。
numpy 模拟器注释上限 25 比特。

### 方案概述

作者在 adapter 文档记录了 antlr 死锁、SpinQ counts 位序、OriginQ 位序和 ry 分解等问题的修复日期。
L2 要求模型第一行输出 JSON（action/qasm/expected_states/backend），再用自家模拟器比对期望态。
CLI 支持自然语言、粘贴 QASM、`/run` 离线执行。证据申报双平台真机（量旋 `G-260823-0016`、本源悟空 `7214912EA38E2E609F7FE5E70E7C0B29`），并保留硅臻 PQPUMESH8 对照失败报告。
yaml 虽把 L2 网络设为 false，实现仍读取 `LOOMQ_LLM_*` 或 `.env.local`。

### 优点

- spinq 路径对 antlr 冲突有显式降级，而不是直接 ImportError 退出。
- 角度解析用 `ast.parse` 白名单节点，再 `eval` 编译结果，比裸 eval 可审计。
- 真机证据同时包含官方 msgpack、json、电路图、对照实验说明。
- 零基础 CLI 指南与 Q-Ext 规格文档分开存放。
- originq 后端独立成模块，adapter 体积被部分拆出。

### 质量问题与风险

- `compile_hybrid` 返回 `_parse_qasm2(...)[2]`，元素是元组而非契约注释中的「量子操作序列字符串列表」，与 `Tuple[List[str], str]` 可能不一致。
- yaml `required_for_l2: false` 与 L2 实现需要 LLM 环境变量矛盾。
- `l2_agent` 启动时读取 `.env.local`；模板含占位 key 字符串，真实文件若被误提交会有泄露面（当前可见的是 `.env.local.example`）。
- originq 模块 `from pyqpanda import *` 并配置 `logging.basicConfig`，副作用面较大。
- 无独立 Web；视觉 Bonus 依赖 CLI 直方图与 FIRST_RUN 文档，是否满足「视觉叙事」无法静态确认。

### 完整性 / 可维护性 / 安全性观察

完整性：三级函数存在；证据勾选全部人工项且 files 非空。可维护性：adapter 仍较长，但 originq/L2/L3 已外置；
注释含排障时间线。`cli.py` 在 Windows 上 `reconfigure` UTF-8。
安全性：example 环境文件是占位符（`sk-在这里填你的key` 一类模板，不复制具体值）；
证据脚本 `run_qcloud_controls.py` 等存在于 evidence/files，可能含平台调用逻辑，未执行。
在受检路径下未静态确认真实密钥。监听仅 CLI，无 HTTP。无法静态确认 msgpack 是否为平台原始导出。

### 关键证据位置

- [E-1] `archive/generated/snapshots/LinXuan2576/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L14 — 三级 true，但 L2 网络字段为 false
- [E-2] `archive/generated/snapshots/LinXuan2576/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L84-L96 — AST 白名单解析角度
- [E-3] `archive/generated/snapshots/LinXuan2576/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L255-L272 — spinqit 失败则降级 numpy 模拟器
- [E-4] `archive/generated/snapshots/LinXuan2576/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L442-L457 — `compile_hybrid` 返回解析元组
- [E-5] `archive/generated/snapshots/LinXuan2576/starter_kit/l2_agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L56-L64 — 读取 `.env.local`
- [E-6] `archive/generated/snapshots/LinXuan2576/starter_kit/cli.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L18 — CLI 三种用法
- [E-7] `archive/generated/snapshots/LinXuan2576/starter_kit/riscv_emulator_qext.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — Q-Ext 指令与确定性坍缩
- [E-8] `archive/generated/snapshots/LinXuan2576/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L58 — 双平台真机申报与对照实验
- [E-9] `archive/generated/snapshots/LinXuan2576/starter_kit/docs/FIRST_RUN.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L23 — 零基础 CLI 首次运行指南
- [E-10] `archive/generated/snapshots/LinXuan2576/starter_kit/originq_backend.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L50 — 独立 OriginQ 模块与 `import *`

### 结论置信度

配置漂移、返回值类型、降级路径、证据文件存在为高（A）。真机概率表与「保真度 ≈ 0.9995」是选手自述（C）。无法静态确认：numpy 模拟器与 spinqit 分布是否一致、L3 元组返回是否被评测器接受、云对照实验是否可复核。

## 37. `CloverLiu03`

### 身份与路径

- contestant ID：`CloverLiu03`
- snapshot：`archive/generated/snapshots/CloverLiu03/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/CloverLiu03/LoomQ-2026` @ `cf8e943169d89e3a7e22fc34243a3d79398fe6fc`
- yaml：`l1: true`、`l2: false`、`l3: true`；`extra_py` 为空，定制面几乎全在 `adapter.py`（681 行）及证据文件。接近 starter 文件集合，不表示 adapter 未被改写。
- 契约文件齐全；增量主要是 `bell_without_measure.qasm`、`report.json`、`evidence/files/*.json`

### 技术栈与结构

Python。依赖 `amazon-braket-sdk==1.43.0`、`spinqit==0.2.4`、`pyqpanda==3.8.5`、`setuptools==69.5.1`。
L1：`parse_qasm` → 按 target 拼 SpinQ QASM / OriginIR / Braket QASM3，再调对应 SDK。
额外函数 `run_on_cloud` 读取 `SPINQ_USERNAME`/`SPINQ_KEYFILE`/`ORIGINQ_API_TOKEN`，不是契约入口。
`agent_chat` 未实现（与 yaml 关 L2 一致）。`compile_hybrid` **仍是 NotImplementedError**，与 yaml `l3: true` 不一致。
`circuits/bell_without_measure.qasm`、`report.json`、`evidence/files/` 为相对 starter 的少量增量。
braket SDK 版本 1.43.0 低于本段其他选手常见的 1.8x/1.1xx。
`_estimate_circuit_depth` 对每个门 +1，不是并行层深度。

### 方案概述

公开自测报告 `report.json` 自报 4/4 PASS（bell/ghz3 × spinq/originq），文件内 notice 写明「不是官方分数」。
证据勾选 L1 真机两平台：spinq job `83647256049186026`、originq job `6A81E0139F939EE6CC36C5FA529D5A65`，shots 8192，并附 json。
`run()` 在 spinq/braket/originq 的 `except Exception` 分支会生成近似 50/50 的 counts，originq 分支还把 backend 命名为 `originq_cpu_simulator_mock`。
OriginIR 门表把 `sdag` 映到 `SDAG`，白名单文档写的是 `sdg`，`sdg` 会走 `gate.upper()` 旁路。

### 优点

- yaml 关闭 L2 与 `agent_chat` 未实现一致。
- 真机申报有 job ID、时间、QASM 路径和 json 结果文件。
- 三后端本地执行代码路径可读，spinq 位序反转有注释。
- `report.json` 明确标注 public self-check，没有把它写成官方分。

### 质量问题与风险

- **声明 L3 但 `compile_hybrid` 未实现**：评测若因 yaml 进入 L3，静态可见会直接 NotImplemented。
- `run()` 宽 `except Exception` 后返回 50/50 counts，originq 路径带 `_mock` 后缀。这是结果完整性风险，不是「有 fallback 就更好」。
- OriginIR `sdg`/`sdag` 键名不一致。
- `run_on_cloud` 混用 pyqpanda / pyqpanda3，含 `print` 调试输出与未完成分支（`pass`）。
- 无 L2、无额外测试模块；人工项除真机外均为空模板。

### 完整性 / 可维护性 / 安全性观察

完整性：L1 本地路径 + 云函数 + 真机 json；L3 声明与实现断裂。可维护性：单文件 681 行，注释掉的 mock 与生效的 50/50 回退并存，阅读负担高。
spinq/braket 异常分支可能在 `backend_name` 赋值前失败，导致随后 `return` 引用未绑定名字——这是静态可见的控制流风险，是否触发无法静态确认。
安全性：云凭证只从环境变量读取，文档示例为占位用户名；在受检路径下未静态发现真实密钥。
`report.json` 的 PASS 不能当作本次静态分析的运行结论。无 Web、无额外测试模块。

### 关键证据位置

- [E-1] `archive/generated/snapshots/CloverLiu03/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L14 — L1+L3，关闭 L2
- [E-2] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L220-L221 — OriginIR 映射键为 `sdag` 而非 `sdg`
- [E-3] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L317-L331 — spinq 异常后仍填 50/50 counts
- [E-4] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L413-L416 — originq 异常走 `_mock` backend 名
- [E-5] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L669-L680 — L2/L3 均为 NotImplemented
- [E-6] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L433-L442 — `run_on_cloud` 非常规入口
- [E-7] `archive/generated/snapshots/CloverLiu03/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L38 — 仅勾选真机并填写双 job
- [E-8] `archive/generated/snapshots/CloverLiu03/starter_kit/report.json`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L36 — 公开自测自报 4/4，notice 否定官方分
- [E-9] `archive/generated/snapshots/CloverLiu03/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L651-L664 — 深度估计对每门 +1
- [E-10] `archive/generated/snapshots/CloverLiu03/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L3-L6 — 锁定 braket 1.43.0、spinqit、pyqpanda、setuptools

### 结论置信度

yaml/L3 不一致、mock 回退、真机文件存在为高（A）。无法静态确认：本地 SDK 路径是否真的算出 `report.json` 中的保真度、真机 json 是否对应本次归档代码、50/50 回退是否会被评测打中。

## 38. `arwenlinzhaoqing`

### 身份与路径

- contestant ID：`arwenlinzhaoqing`
- snapshot：`archive/generated/snapshots/arwenlinzhaoqing/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/arwenlinzhaoqing/LoomQ-2026` @ `c1d2a800984976720d9382ca9a196be3d3bff3d8`
- yaml 仅 L1（`l2/l3: false`，`required_for_l2: false`）
- `extra_py` 为空；starter 顶层 Python 文件集合接近官方工具包，定制集中在 549 行 `adapter.py`。这是定制面描述，不是贬义。
- 契约文件齐全；无证据 files、无额外测试

### 技术栈与结构

Python。`requirements.txt` 仍是 starter 注释模板，**没有钉死任何 SDK 版本**，但 adapter 按需 import `spinqit`、`pyqpanda`、`braket.devices` / `braket.ir.openqasm`。
实现是教科书式三段：`parse_qasm` → `CircuitIR` → `_to_spinq` / `_to_originq` / `_to_braket`，执行函数 `_run_*` 再规范化 counts。
L2/L3 入口保持 NotImplemented，与 yaml 一致。证据 README 未勾选任何人工项。
无 Web、无额外测试。`SUPPORTED_GATES` 与赛题 12 门白名单一致。
Dockerfile 仍为官方基线，未改。相对 starter 的 Python 增量文件数为 0。

### 方案概述

模块文档用中文逐步说明：去注释、拆语句、寄存器偏移、12 门白名单、整寄存器测量。
SpinQ 经临时 `.qasm` 文件走 QASMCompiler；OriginQ 优先 `convert_qasm_string_to_qprog`，否则写文件；
Braket 的契约 IR 保留 `stdgates.inc`，本地执行另用 `_to_braket_runtime`（`si`/`ti`/`cphaseshift`/`ccnot` 等 SDK 名）。
位序：spinq/braket 反转，originq 不反转。`job_id` 缺省时用 `*-local-` + uuid。

### 优点

- 声明层级、未实现入口、无 Web 服务三者一致，评测边界清楚。
- 三后端 L1 在静态阅读下都有完整 transpile+run，而不是 TODO。
- IR 共用、错误信息具体（未知寄存器、门白名单、参数个数）。
- 契约 IR 与 Braket 运行时 IR 分开，避免 include 文件问题。
- 注释把「为什么反转 counts」写在执行函数旁边。

### 质量问题与风险

- 依赖清单未钉版本：评测容器若只按该 `requirements.txt` 安装，SDK import 会失败。这是完整性风险，不是代码风格问题。
- 无选手自测、无证据填写、无硬件材料。
- 解析器假设门参数为字符串原样转出，不求值 `pi/2`；与会求值的实现相比，行为差异无法静态确认谁更符合隐藏集。
- 接近 starter 文件树意味着没有独立文档说明设计；读者只能读 adapter。

### 完整性 / 可维护性 / 安全性观察

完整性：按 yaml 只交付 L1；L1 三 target 源码齐全，但依赖未锁定。
可维护性：单文件结构清晰、函数短注释多。`_normalize_counts` 拒绝非 01 键。
安全性：无监听、无 LLM、无选手侧 subprocess（adapter 不 spawn）；
临时文件有 `unlink`。在受检路径下未静态发现凭据。官方 `evaluator.py`/`prepare_submission.py` 未改行数特征。
无法静态确认未锁定依赖在评测镜像预装集合中是否恰好可用。

### 关键证据位置

- [E-1] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L14 — 仅 L1
- [E-2] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L11 — 文档化 L1 流程，L2/L3 保持可选
- [E-3] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L273-L296 — transpile 分发
- [E-4] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L524-L547 — run 分发；L2/L3 NotImplemented
- [E-5] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 仍为未填写的模板注释
- [E-6] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 人工项均未勾选
- [E-7] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L319-L368 — SpinQ 临时文件编译与 counts 反转
- [E-8] `archive/generated/snapshots/arwenlinzhaoqing/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L479-L521 — Braket 运行时门名表（不含 stdgates include）

### 结论置信度

yaml 仅 L1、三后端函数存在、requirements 未钉版本为高（A）。无法静态确认：评测镜像是否预装 SDK、三后端 counts 位序是否都符合契约、未锁定依赖的解析结果。

## 39. `softeight`

### 身份与路径

- contestant ID：`softeight`
- snapshot：`archive/generated/snapshots/softeight/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/softeight/LoomQ-2026` @ `b00edb6281617db43ff1ca11a5fc92de8f53b310`
- yaml：`l1: true`、`l2: false`、`l3: true`
- `extra_py` 为空；相对 starter 多出 `stdgates.inc`。定制同样集中在 `adapter.py`（475 行）。接近工具包文件树，不等于 L3 未写。
- 契约文件齐全；无证据 files、无 Web

### 技术栈与结构

Python。依赖 `spinqit==0.2.4`、`pyqpanda==3.8.5`，未列 braket，但 `_run_braket` 直接 import `braket`。
L1：行级 QASM 解析，寄存器名写死为 `q`/`c`；OriginIR 参数写成 `NAME q[i], (θ)`。
L2 `agent_chat` NotImplemented，与 yaml 一致。
L3 在同一文件内实现：切 `classical {}`、token 化、递归下降、`_RiscVGen` 只发射 `li/add/sub/addi/beq/bne/j`。
证据为空白模板。`stdgates.inc` 位于 starter 根，可能供 Braket include 解析；
adapter 的 transpile 仍写出 `include "stdgates.inc";`。
无 Web、无额外测试。

### 方案概述

文件头声明 transpile/run 覆盖 12 门三 target，compile_hybrid 已实现，agent_chat 故意留空。
Braket 门表把 `cu1` 映为 `cphase`，并注释 stdgates 无 1:1 名、隐藏电路可能需要按 `gate_identities.md` 分解。
`job_id` 用 `hash(qasm_str)` 截断。无 classical 块时 L3 返回 `li x0, 0`。
`stdgates.inc` 是一份 OpenQASM 3 标准门文本，供 Braket include 使用的候选，是否被运行时打开无法静态确认。

### 优点

- yaml 关 L2、开 L3，与函数实现匹配（相对 CloverLiu03 的 L3 空实现，这里是对齐的）。
- L3 迷你语言有独立 tokenizer/parser/codegen，寄存器约定写在 `_RiscVGen` 文档字符串。
- OriginIR 参数位置与部分 SDK 习惯一致（角度在比特后）。
- 单文件内 L1+L3，没有悬空 import。

### 质量问题与风险

- braket 未写入 requirements，与 Andante397 相反：代码有、依赖清单无。
- 解析器只认 `qreg q[N]` / `creg c[N]`，多寄存器名会失败。
- `_GATE_LINE_RE` 用 `re.search(r'\d+', q).group()` 抽下标，异常输入可能 `AttributeError`。
- 无测试、无证据、无 UI。
- `cu1`→`cphase` 是否被评测 IR 契约接受，作者自己也标了不确定。

### 完整性 / 可维护性 / 安全性观察

完整性：L1+L3 源码在；L2 按声明缺席；braket 依赖未锁定。可维护性：L3 类结构清楚，L1 解析较脆。
`_run_originq` 把 `len(creg)` 写入 `meta.qubits_count`，字段名与量子比特数可能不一致。
安全性：无服务、无 LLM；hash 作为 job_id 不是密钥问题。在受检路径下未静态发现凭据。
接近 starter 的目录并不妨碍 L3 编译器作为主要增量被阅读。无法静态确认 `stdgates.inc` 是否被 LocalSimulator 真正打开。

### 关键证据位置

- [E-1] `archive/generated/snapshots/softeight/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L14 — L1+L3，关闭 L2
- [E-2] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L7 — 文件头声明覆盖范围
- [E-3] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L75-L81 — cu1 映射及不确定性注释
- [E-4] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L252-L254 — L2 未实现
- [E-5] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L463-L474 — L3 编译入口
- [E-6] `archive/generated/snapshots/softeight/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L2 — 仅 spinqit/pyqpanda
- [E-7] `archive/generated/snapshots/softeight/starter_kit/stdgates.inc`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L18 — 额外 OpenQASM 3 门库文本
- [E-8] `archive/generated/snapshots/softeight/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L15 — 人工项均未勾选
- [E-9] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L23-L65 — 仅解析名为 q/c 的寄存器
- [E-10] `archive/generated/snapshots/softeight/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L389-L460 — RISC-V 生成器与 if/赋值

### 结论置信度

yaml 与 L2/L3 实现对齐、braket 依赖缺口、L3 代码存在为高（A）。
无法静态确认：汇编能否被官方 `riscv_emulator.py` 执行、braket LocalSimulator 在未声明依赖时是否可用、`cu1→cphase` 是否被 IR 契约接受。

## 40. `zhaoqianyuan24`

### 身份与路径

- contestant ID：`zhaoqianyuan24`
- snapshot：`archive/generated/snapshots/zhaoqianyuan24/`
- 基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游：`https://github.com/zhaoqianyuan24/LoomQ-2026` @ `c5a7822b8bbe522cc334047838cfc50bc54e3357`
- yaml 三级全开，L2 需网络；运行时声明 Python 3.10
- 定制面大：`l1/` `l2/` `l3/` `hardware/` `frontend/` `product_service.py` `loomq_cli.py` `Dockerfile.playground` `compose.yaml`
- 契约文件齐全；另有 `start_playground.bat`、`requirements-hardware.txt`、`pyproject.toml`

### 技术栈与结构

Python + 静态 HTML/JS/CSS 前端。主依赖含 `spinqit==0.2.4`、`antlr4-python3-runtime==4.9.2`、`amazon-braket-sdk==1.83.0`、`amazon-braket-default-simulator==1.26.0`、`pyqpanda==3.8.5`；
另有 `requirements-hardware.txt`（`spinqit-mcp-tools==0.0.1`）。
adapter 212 行做门面：本地 canonical backend id 映射到 L1，`spinq_cloud_qpu` / `originq_wukong` / `braket_cloud` 走 `hardware.run_hardware`。
产品服务默认 `127.0.0.1:4173`，会话 Cookie `HttpOnly; SameSite=Lax`，请求体 64 KiB 上限。
`starter_kit/tests/` 下有多份 `check_l1_*` / `check_l2_*` / `check_l3_*`。
另有 `circuits/all_gates.qasm`、`report_l2.json`、`pyproject.toml`、`Dockerfile.playground`。
前端无外部 CDN。

### 方案概述

L1 包内 parser/ir/emitters/backends；L2 包含 policy、validator、backend_verifier、最多 3 次尝试与超时储备；
L3 独立 lexer/parser/compiler/runtime。Playground 把自然语言生成、后端选择、本地/云/真机运行放在同一 HTTP API。
证据勾选真机、L2、工程、视觉，未勾选 RISC-V Bonus（但 L3 源码存在）。
真机记录 SpinQ Cloud `gemini_vp`，job `61489` / 任务号 `G-260825-0008`，电路为 `X|0⟩`，并说明官方提交器不接受 measure 行。
文档中的 API Key 行为「填写你自己的 Key」占位，不是仓库内密钥。

### 优点

- 分层（l1/l2/l3/hardware/frontend）与 adapter 门面清楚，Playground 与评测入口共用 `adapter.run`。
- 远程 id 与本地模拟器显式分开，文档警告费用与排队。
- HTTP 层有体积限制、会话 Cookie 属性、错误分类（缺依赖 / 非法电路 / 远端失败）。
- 测试文件覆盖门、参数、非法输入、agent、backend 逻辑、L3 fuzz 等，数量在本段选手中最多。
- 真机材料含输入 QASM、去 measure 后 QASM、json、任务截图。

### 质量问题与风险

- `product_service.py` 超过两千行，产品逻辑与 HTTP 处理挤在单文件。
- adapter 顶部残留大段注释掉的 import/`_load_module`。
- L3 已实现但证据未申报 RISC-V Bonus，口径与 Yolanlanlanda 类似。
- 硬件文档要求环境变量 token；占位符扫描会命中 `hardcoded_keyish`，对照上下文为示例而非泄露。
- `start_playground.bat` / compose 会在真实使用时安装依赖并监听端口；本阶段未执行。

### 完整性 / 可维护性 / 安全性观察

完整性：契约四级函数 + 远程 run + 前端 + Docker playground + 证据 files 均存在。
可维护性：包划分好，但 product_service 与 adapter 注释债务并存。
`l2/agent.py` 有 `MAX_ATTEMPTS = 3` 与超时储备。
安全性：默认绑定回环；Cookie 带 HttpOnly；LLM 配置函数注释写明不把 key 写入 session。
在受检路径下未静态确认真实密钥。Tutor prompt 要求模型把用户文本当资料、禁止泄露 API Key。
SpinQ 云 shots 被服务端固定为 1000。无法静态确认 `report_l2.json` 是否由本次代码生成。

### 关键证据位置

- [E-1] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L4-L21 — 三级全开，L2 需 `LOOMQ_LLM_*`
- [E-2] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L109 — 本地/远程 backend id 分流
- [E-3] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L189-L211 — `run_hardware` 延迟导入
- [E-4] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/l1/api.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L17-L85 — L1 transpile/run 分发
- [E-5] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/product_service.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L45-L60 — 请求上限与环境 LLM 配置
- [E-6] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/product_service.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L2285-L2291 — 默认 `127.0.0.1:4173`
- [E-7] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/docs/PLAYGROUND_QUICKSTART.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L24-L29 — Key 占位说明，不写入镜像
- [E-8] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L40 — 勾选真机/L2/工程/视觉；SpinQ 任务元数据
- [E-9] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/hardware/api.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L22 — 远程执行需凭证、可能产生费用
- [E-10] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/frontend/index.html`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L23 — 本地静态前端，无 CDN
- [E-11] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/l2/agent.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L26-L45 — L2 最多 3 次尝试与超时检查
- [E-12] `archive/generated/snapshots/zhaoqianyuan24/starter_kit/product_service.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L2184-L2186 — SpinQ 云 shots 固定 1000

### 结论置信度

包结构、yaml、监听地址、证据文件存在、占位符而非实密为高（A）。L3 源码存在不等于 Bonus 已申报。无法静态确认：Playground 端到端体验、真机 job 与云计费路径、`check_l*` 测试是否通过。

## 41. `jessicaruan6688-byte`

### 身份与路径

- contestant_id：`jessicaruan6688-byte`
- snapshot：`archive/generated/snapshots/jessicaruan6688-byte/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/jessicaruan6688-byte/LoomQ-2026-Jessica
- 上游 commit：`981b725dd223e8f2b8c6073925072986683d445f`
- 评测根目录：`starter_kit/`；契约入口 `adapter.py`；`submission.yaml` 声明 `l1/l2/l3: true`，Python 3.10，L2 需网络。

### 技术栈与结构

- 静态可见：Python、HTML/JS、可执行 Shell、量子 SDK 引用、OpenAI-compatible LLM 客户端。
- 规模：约 97 文件、38 个 Python、7 个测试文件。
- 核心包 `starter_kit/loomq/`：`parse_qasm.py`、`circuit.py`、`gates.py`、`emit.py`、`backends.py`、`reference_sim.py`、`result.py`、`verify.py`、`agent.py`、`hybrid.py`。
- `adapter.py` 仅 34 行转发；Web 为 `web/{server.py,index.html,app.js,style.css}`。
- 工具：`l2_chat_cli.py`、`run_bell_evidence.py` 及 OriginQ 轮询脚本；架构说明在 `docs/ARCHITECTURE.md`。
- 依赖钉：`amazon-braket-sdk==1.50.0`、`spinqit==0.2.4`、`pyqpanda==3.8.5`。
- 可执行 Shell（仅记录路径、未执行）：`start_demo.sh`、`starter_kit/tools/start_l2_web.sh`、`starter_kit/tools/try_originq_bell.sh`。
- 根 README 仍为赛题发布包；产品入口写在 starter README。

### 方案概述

README 声称在官方骨架上实现统一 OpenQASM 中间层、自然语言 Agent 与 Hybrid→RISC-V。数据流按文档为：自然语言经 `agent_chat` 抽取 QASM 并本地校验，再 `parse_qasm` → 统一 IR → SpinQ QASM2 / OriginIR / Braket QASM3 发射与执行。`run()` 走 `loomq/backends.py` 的本地 SDK 路径，并可通过环境变量切换量旋云 / 本源悟空。L2 使用 `LOOMQ_LLM_*`，最多重试次数读 `LOOMQ_LLM_MAX_CALLS`。L3 在 `loomq/hybrid.py` 对经典块做词法/语法/代码生成。Web 文档声称默认 `http://127.0.0.1:8765/`，第一屏回放归档真机直方图，不表示本次静态复核已启动服务。

### 优点

- 契约入口薄、业务分层清楚：解析、发射、执行、Agent、Hybrid 分文件，便于对照 `target_ir_contract.md`。
- 参数表达式先做字符白名单再 `eval(..., {"__builtins__": {}})`，意图是限制为算术而非任意代码。
- L2 明确禁止按公开样例硬编码答案，失败时返回显式失败而非未校验 QASM。
- Web 对证据文件名做 allowlist，聊天有速率限制；`.env.example` 仅空占位，未见实填密钥。
- 证据包同时申报量旋 Bell/GHZ 与本源 Bell，并保留 QASM、JSON、截图与 REST 详情路径。
- 自测覆盖 L1 执行、L2 Web、Agent 单元、Hybrid 随机差分与量子 RISC-V 闭环。

### 质量问题与风险

- `parse_qasm.py` / `verify.py` 仍使用 `eval`；虽清空 builtins 并过滤字符，仍属动态求值，无法静态确认所有恶意输入均被挡住。
- `backends.py` 含云端提交路径（`LOOMQ_SPINQ_MODE`、`LOOMQ_ORIGINQ_*`）。正式评测 L1 声明禁网，若环境被误注入凭证，静态无法确认 `run()` 是否仍只走本地模拟器。
- `requirements.txt` 的 Braket 钉在 1.50.0，与同批其他提交的较新钉版本不同；共存性无法静态确认。
- 证据 README 含他队 Issue 对照表，属选手文档叙事，不是本报告排名。
- 可执行 Shell 仅记录路径，未执行；其实际绑定、探活与浏览器行为无法静态确认。

### 完整性 / 可维护性 / 安全性观察

四契约函数均实现；`evaluator.py`、Dockerfile、公开电路 `circuits/bell.qasm`/`ghz3.qasm` 与证据模板齐全。文档 `docs/ARCHITECTURE.md` 与代码目录一致。密钥约定走环境变量 / `.env`（gitignore）；`.env.example` 列出 OriginQ/SpinQ/LLM 空字段，无实填值。`tools/_fetch_originq_task_rest.py`、`_poll_originq_job.py`、`_archive_originq_bell.py` 为联网取证辅助，不在契约入口内。Web `L2WebHandler` 提供实验回放、backends 列表与 chat；`serve_forever` 在 `main` 中。未在受检路径静态发现实填 API Key 或私钥材料。公开电路与证据 QASM 并存，部分文件名含 `TODO`，是否为占位需人工打开核对，本阶段不打开二进制截图。

### 关键证据位置

[E-1] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/submission.yaml@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 声明 L1/L2/L3、入口 `adapter.py`、L2 需 `LOOMQ_LLM_*`
[E-2] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L34 — 四接口转发至 `loomq`
[E-3] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/loomq/pipeline.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L29 — `transpile`/`run` 解析后发射并调用后端
[E-4] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/loomq/parse_qasm.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L41-L52 — 角度表达式经过滤后 `eval`
[E-5] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/loomq/agent.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — L2 本地校验与有界重试，不硬编码隐藏题
[E-6] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/web/server.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L35-L47 — 默认端口 8765、证据文件 allowlist
[E-7] archive/generated/snapshots/jessicaruan6688-byte/start_demo.sh@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 可执行包装脚本，转调 `tools/start_l2_web.sh`（仅记录路径）
[E-8] archive/generated/snapshots/jessicaruan6688-byte/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L57-L79 — 申报双平台真机与 job ID 路径

### 结论置信度

路径、契约字段、模块地图与风险点为高（A）。产品叙事、真机结果含义、服务可启动性为中（B）或无法静态确认。未运行任何选手代码。

## 42. `wronps`

### 身份与路径

- contestant_id：`wronps`
- snapshot：`archive/generated/snapshots/wronps/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/wronps/LoomQ-2026
- 上游 commit：`621987e96029bb516b05af290ecbb70d042709f5`
- 评测根：`starter_kit/`；`submission.yaml` 声明 L1/L2/L3 均为 true，L2 需网络。

### 技术栈与结构

- 静态可见：Python、HTML、量子 SDK、OpenAI-compatible 客户端。
- 规模：约 57 文件、26 个 Python、8 个测试文件。
- 实现高度集中：`adapter.py` 约 2351 行，覆盖 `_parse_qasm2`、`_lower`、三后端 `_run_*`、`agent_chat`、`compile_hybrid`。
- 附加：`tools/loomq_web.py` + `tools/web/index.html`、`tools/loomq_chat.py`、`tools/run_hardware.py`。
- Bonus：`qx_compiler.py`、`riscv_emulator_qx.py`、`QX_EXTENSION.md`；架构在 `ARCHITECTURE.md`。
- 根 `tests/` 含 `loomq_oracle.py` 与 `test_adapter_l{1,2,3}.py`。
- 依赖钉：Braket 1.97.0 + default-simulator 1.27.0 + antlr 4.9.2 + spinqit/pyqpanda，并含 PyTorch CPU extra-index。
- 无 Git 可执行 Shell。starter README 接近官方模板，产品说明在根 README 与 ARCHITECTURE。

### 方案概述

根 README 把评委入口写成 unittest 与 `evaluator.py`，并指向网页/CLI。架构文档说明 `transpile()` 返回契约 IR、`run()` 使用 SDK 更窄的 native 方言，两套 profile 共用同一 lowering。角度解析用 `ast` 白名单而非 `eval`。L2 要求模型附 `LOOMQ-EXPECT`，再用内置参考模拟器核对并重试。`run_hardware.py` 明确不接入 `adapter.run()`，以免评分路径变成排队真机任务。Bonus 将 Hybrid-QASM 编译为融合 QX+RV32I 指令流。网页文档声称 `http://127.0.0.1:8760/`，标准库 `http.server`，绑定 localhost。

### 优点

- 对契约 IR 与 SDK 方言分叉有实测说明（Braket include/sdg、OriginIR 门名等），属于非显然设计记录。
- 参数求值用 AST 节点白名单，源码写明拒绝恶意角度表达式。
- 真机工具与评分 `run()` 隔离，Token 只读环境变量、不进参数与证据文件。
- 位序按 (qubit→clbit) 映射而非简单反转，并在文档中指出 Bell/GHZ 对称会掩盖位序错误。
- Bonus 规格、编译器与扩展模拟器三件套齐全；测试含独立 `loomq_oracle.py`。

### 质量问题与风险

- 单文件 `adapter.py` 体量很大，L1/L2/L3 与诊断状态混在一处，后续修改冲突面高。
- `requirements.txt` 引入 PyTorch CPU wheel 与 extra-index，容器体积与解析风险高于最小 SDK 集；无法静态确认与官方镜像兼容。
- 证据仅申报本源悟空 Bell 一平台；量旋未作为有效真机申报。是否满足“最多两平台”中的第二平台，属人工评分范畴，此处只记录材料范围。
- L2 网页会调用 `adapter.agent_chat` 并提供 `/api/run`；监听面与 CORS 行为无法静态确认。
- 根 README 声称“不装 SDK 也能跑部分测试”，具体跳过逻辑未在本阶段执行验证。

### 完整性 / 可维护性 / 安全性观察

四契约函数均在 `adapter.py` 定义（`transpile` L1002、`run` L1015、`agent_chat` L1351、`compile_hybrid` L2231）。`ARCHITECTURE.md` 与代码职责基本对应。硬件脚本拒绝把模拟器后端当作真机证据，Token 变量名为 `LOOMQ_ORIGINQ_TOKEN`。未见 `.env` 实填文件。依赖钉版本完整，但 antlr 共存策略写在文档而非自动化隔离脚本中（对比同批双 venv 方案）。网页绑定 localhost、无 CDN。根 README 提示 macOS 上 spinqit 需 `DYLD_LIBRARY_PATH`。未发现可执行 Shell。`run()` 要求电路含测量，否则显式报错。

### 关键证据位置

[E-1] archive/generated/snapshots/wronps/starter_kit/submission.yaml@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L1/L2/L3 声明与 L2 环境变量
[E-2] archive/generated/snapshots/wronps/starter_kit/ARCHITECTURE.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L48 — 单文件架构、契约 IR 与 native 双 profile
[E-3] archive/generated/snapshots/wronps/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1002-L1029 — `transpile`/`run` 走 `_compile_for` 后本地模拟
[E-4] archive/generated/snapshots/wronps/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1351-L1390 — `agent_chat` 生成/修复/选后端
[E-5] archive/generated/snapshots/wronps/starter_kit/tools/run_hardware.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 真机工具刻意不接入 `adapter.run()`
[E-6] archive/generated/snapshots/wronps/starter_kit/qx_compiler.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L33 — Bonus 融合指令流
[E-7] archive/generated/snapshots/wronps/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L62 — 本源 job 与 L2 入口命令

### 结论置信度

契约、架构文档与源码分层为高（A）。SDK 共存、网页行为、真机有效性无法静态确认。未运行选手代码。

## 43. `lil4notfound`

### 身份与路径

- contestant_id：`lil4notfound`
- snapshot：`archive/generated/snapshots/lil4notfound/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/lil4notfound/LoomQ-2026
- 上游 commit：`035af88f4a8237886177c2e6f585f9623897b596`
- 评测根：`starter_kit/`；`submission.yaml` 声明三级均为 true，L2 需网络。

### 技术栈与结构

- 静态可见：Python、HTML/JS、量子 SDK 引用、LLM 客户端。
- 规模：约 114 文件、57 个 Python、7 个 Web 资源，体积约 18 MB（含编织主题 PNG）。
- `loomq_core/`：`qasm2.py`、`model.py`、`renderers.py`、`simulator.py`、`verification.py`。
- `loomq_agent/`：`service.py`、`validation.py`、`backend_selector.py`、`response.py`。
- `loomq_app/`：`server.py` + `web/` 静态资源；另有 `loomq_hybrid/`、`loomq_bonus/{isa,encoder,emulator}.py`。
- 其它：`prompt_quality.py`、`run_docker_l2.py`。
- `requirements.txt` 仅注释、无第三方钉版本。
- 入口候选：`run_local.py`（文档默认 127.0.0.1:8765）、`loomq_app/server.py`。无 Git 可执行 Shell。
- starter README 被改写成产品说明书，根 README 仍为赛题包。

### 方案概述

产品名“织络”。README 声称面向无 QASM 背景的跨界创作者；L1 `run()` 使用本地状态向量，不向厂商云提交。网页单一输入框，Agent 结合最近两轮上下文；线路由本地解析器与理想分布验证，失败再重试一次。后端选择读官方 `backend_capabilities.json`。L3 `compile_hybrid_program` 与 Bonus 量子 RISC-V 隔离：契约路径只产出官方 7 指令子集。`run_local.py` 在缺省时交互收集 `LOOMQ_LLM_*`，API Key 用隐藏输入，退出时从进程环境删除自行写入的项。

### 优点

- L1 执行路径零第三方依赖，与“公开 evaluator 只需标准库”的赛题约束对齐。
- 包边界清楚，Bonus ISA 文档写明不污染 `adapter.compile_hybrid()`。
- Web 限制 POST 体大小、关闭默认 access log、静态资源白名单；会话只在浏览器内存。
- 证据对量旋 MessagePack 原始导出与本源 OriginIR 平台实际执行文本分别留档，并说明平台拒绝带 `measure` 的差异。
- 测试覆盖 core、roundtrip、agent、hybrid、bonus、web、本地/Docker 启动器。

### 质量问题与风险

- `requirements.txt` 为空：若评测容器或人工复现期望安装 spinqit/pyqpanda/braket，本提交的 `run()` 并不走这些 SDK，文档已声明；与“三厂商 SDK 真跑”的常见实现不同，属设计选择而非缺失，但隐藏测例若假设 SDK 语义则无法静态确认。
- `run_local.py` 在未配置时阻塞式 `input`/`getpass`，不适合非交互评测环境；契约 `agent_chat` 本身仍只读已有环境变量。
- 前端视觉素材由生成式 AI 辅助，属文档披露；无障碍与浏览器兼容性无法静态确认。
- 体积显著大于同批多数提交，主要来自 PNG 资源。

### 完整性 / 可维护性 / 安全性观察

四契约函数转发到 core/agent/hybrid。Dockerfile 与 `run_docker_l2.py` 并存。密钥不入库的约定与启动器清理逻辑一致。Agent 用正则粗分生成/修复/选后端请求，再交给模型与本地校验；隐藏措辞是否总能命中这些正则无法静态确认。证据截图路径声称不含账户信息，内容真实性无法静态确认。`loomq_hybrid/compiler.py` 限制源码长度 1_000_000。未见实填密钥文件。测试含 `test_l1_core.py`、`test_l1_roundtrip.py`、`test_l2_agent.py`、`test_l3_hybrid.py`、`test_bonus_riscv.py`、`test_web_app.py`。

### 关键证据位置

[E-1] archive/generated/snapshots/lil4notfound/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L36 — 四接口分别委托 core/agent/hybrid
[E-2] archive/generated/snapshots/lil4notfound/starter_kit/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L33 — “织络”定位与 `run_local.py` 入口
[E-3] archive/generated/snapshots/lil4notfound/starter_kit/loomq_core/service.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L15-L40 — `run` 为本地 statevector，backend 名含 `local-simulator`
[E-4] archive/generated/snapshots/lil4notfound/starter_kit/run_local.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L22-L48 — 交互注入 LLM 环境并在 finally 清理
[E-5] archive/generated/snapshots/lil4notfound/starter_kit/loomq_app/server.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L17-L69 — 静态白名单与 `/api/chat`
[E-6] archive/generated/snapshots/lil4notfound/starter_kit/BONUS_RISCV_ISA.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L3 — Bonus 与基础 L3 隔离
[E-7] archive/generated/snapshots/lil4notfound/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L41 — 双平台 job 与原始格式说明
[E-8] archive/generated/snapshots/lil4notfound/starter_kit/requirements.txt@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 无第三方钉版本

### 结论置信度

模块地图、本地执行语义与契约转发为高（A）。Web 体验与真机材料有效性无法静态确认。未运行选手代码。

## 44. `xueerlin20-stack`

### 身份与路径

- contestant_id：`xueerlin20-stack`
- snapshot：`archive/generated/snapshots/xueerlin20-stack/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/xueerlin20-stack/LoomQ-2026
- 上游 commit：`9ee663efdc7eb7dcbe92c0897838ec0b219e1a09`
- 评测根：`starter_kit/`；三级均声明；L2 需网络。

### 技术栈与结构

- 静态可见：Python、约 19 个 HTML/JS、量子 SDK、LLM 客户端。
- 规模：约 170 文件、76 个 Python。
- L1：`qasm_L1/{parser,emitter,runners,execution,ir,gates}.py`。
- L2：`l2_agent/` handler 注册表（`generate_qasm`、`repair_qasm`、`recommend_backend`、`explain_current`、`clarify`）及 `tools/qasm_validator.py`、`backend_selector.py`。
- Web：`web_backend/{application,http,chat,conversations}.py` + `web/`。
- L3：`L3/{lexer,parser,compiler,riscv_compiler}.py`；Bonus：`bonus_quantum_riscv/`。
- 入口：`run_l2.py`、`web_app.py`（文档 127.0.0.1:8765）。
- 配置样例：`.env.l2.example`；凭证样例仅 `qasm_L1/credentials/*.example`。starter README 仍偏官方模板。

### 方案概述

`adapter.py` 将 `transpile`/`run` 委托给一次解析 + `Translator.dispatch` + SDK runner；另提供 `run_real`/`--real` CLI，从环境变量与 `credentials/` 目录读真机凭证。L2 先让模型产出结构化意图，再由 handler 执行；模型结构不可靠时返回澄清而非猜测。Web 缺配置时把恢复交给浏览器 onboarding。公开电路除 Bell/GHZ3 外还有 `ghz5.qasm`、`QFT4.qasm`、`grover3.qasm`。

### 优点

- L2 以任务类型 handler 拆分，比单一巨函数更易对照三类赛题。
- 角度解析走 AST，而非 `eval`。
- 凭证目录仅有 `.example` 与 `.gitignore`，示例 Key 为 `placeholder`；测试里的 `test-secret-key` 是临时夹具。
- Web 资源拆成 onboarding、workspace、circuit visualizer 等模块，产品面完整。
- L3 与 Bonus 分目录，并带各自测试。

### 质量问题与风险

- `USAGE.md` 含本机绝对路径（用户主目录痕迹），属个人信息残留，不复述具体路径。
- `--real` 默认把 SpinQ 私钥路径指向 `credentials/spinq_private_key.pem`；当前快照只有 `.example`，但该约定增加误提交真实 PEM 的表面风险。
- `web_app.py` 在配置校验失败时 `pass` 后仍 `serve_forever`，把错误恢复交给前端；契约外行为无法静态确认。
- `run_l2.py` 可在检测到 `.venv` 时 `os.exec` 切换解释器，评测环境若存在残留 venv，路径解析需人工注意。
- 根/starter README 大量仍为官方模板，产品说明分散在 `USAGE.md` 与 evidence。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。测试覆盖 L1 real runners、L2 gateway/tools/web、本地配置、L3 compiler。`.env.l2.example` 含 DeepSeek URL 与 placeholder，不是实钥。凭证目录当前只有 example 与 `.gitignore`。未静态发现真实 token/PEM 载荷。Docker 与 `build_demo.py` 并存。`qasm_L1/parser.py` 用 AST 求数值参数。Web 还提供 `demo.html` 与 `web/workspace.html`。evidence 目录按 `L1-真机` 与 `L2-web-chatbot` 分子文件夹。

### 关键证据位置

[E-1] archive/generated/snapshots/xueerlin20-stack/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L31-L77 — `CREDENTIALS_DIRECTORY`、transpile/run 分发
[E-2] archive/generated/snapshots/xueerlin20-stack/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L162-L210 — `--real` 读环境/凭证文件；`agent_chat`/`compile_hybrid`
[E-3] archive/generated/snapshots/xueerlin20-stack/starter_kit/l2_agent/agent.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L57 — 意图理解 + handler 分发
[E-4] archive/generated/snapshots/xueerlin20-stack/starter_kit/web_app.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L37-L58 — 默认 127.0.0.1:8765 并 `serve_forever`
[E-5] archive/generated/snapshots/xueerlin20-stack/starter_kit/.env.l2.example@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L7 — 占位 LLM 配置
[E-6] archive/generated/snapshots/xueerlin20-stack/starter_kit/USAGE.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L3 — 文档含本机绝对路径
[E-7] archive/generated/snapshots/xueerlin20-stack/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L53 — 本源/量旋 job 与 Web 启动命令

### 结论置信度

目录、契约与凭证文件名模式为高（A）。真实 QPU 调用、Web onboarding 体验无法静态确认。未运行选手代码。

## 45. `qwer-asdftg`

### 身份与路径

- contestant_id：`qwer-asdftg`
- snapshot：`archive/generated/snapshots/qwer-asdftg/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/qwer-asdftg/LoomQ-2026
- 上游 commit：`928ccd01ecf8ddaaee1742057627cc283c6d2a28`
- 评测根：`starter_kit/`；三级均声明。`network.required_for_l2` 为 **false**（与多数 L2 提交不同）。

### 技术栈与结构

- 静态可见：Python、PowerShell、量子 SDK。
- 规模：约 121 文件、67 个 Python；starter 内测试按 `tests/l1|l2|l3` 分包。
- L1：`loomq_l1/{parser,normalize,expressions,model}.py` 与 `emitters/`、`runners/`。
- L2：`loomq_l2.py` + `l2_{cli,errors,probe,profiles,semantics}.py`。
- L3：`loomq_l3.py`；硬件：`hardware/run_qpu.py`；文档：`newcomer_guide.md`、`quantum_riscv_extension.md`。
- 根目录：`scripts/verify_submission.ps1`、`docs/superpowers/` 计划/规格。
- Dockerfile 将 SpinQ/OriginQ 与 Braket 装进分离的 Python 3.10 环境，并设置 `LOOMQ_BRAKET_PYTHON`。
- 无 Git 可执行 Shell；无独立 Web UI。

### 方案概述

README 强调严格解析 → 规范 IR → 精确发射 → 本地 runner → 规范 counts；L2 一次主请求加至多一次修复；L3 经典块 AST 降到官方 RISC-V 子集。Docker 被写成完整可运行依赖集的支持方式，因 spinqit 与 Braket antlr 运行时不兼容。`l2_cli --guide` / `--explain-counts` 不调用模型。`hardware/run_qpu.py` 写明暂不支持 live QPU 提交，只做本地 dry-run 与导入已校验的平台结果。证据 README 仍申报本源与量旋 job，并保留 provider-raw JSON。

### 优点

- 双运行时隔离写进 Dockerfile，直接回应 SDK 冲突，而不是只写在文档。
- 测试按 l1/l2/l3 分包，含 hidden-style 电路、deadline、profiles、hybrid parser。
- CLI 新手路线不依赖 Key；PowerShell 校验脚本明确不把宿主机源码挂进容器。
- `run()` 对 target/source/shots 做类型校验，拒绝 bool 冒充 int。
- 证据同时保留 submission QASM、native IR、provider-raw 与 metadata。

### 质量问题与风险

- `submission.yaml` 声明 L2 且实现调用 LLM，但 `required_for_l2: false`，与官方“勾 L2 则需声明网络”的常见口径不一致。
- `l2_profiles.py` 为本地 CLI 硬编码阿里云/OpenAI/DeepSeek **URL 与默认模型名**（密钥仍走环境变量）。正式 `agent_chat` 路径是否完全避开这些 profile，需对照调用链；静态可见本地快捷方式引入额外出口。
- `hardware/run_qpu.py` 与证据“已提交真机”并存：模块本身不提交，证据来自导入；二者关系只能按文档理解，不能静态确认提交过程。
- 根目录 `docs/superpowers/` 为过程文档，可能造成导航噪音。
- README 写有公开 evaluator 期望 `passed: 6`，属选手自述，本阶段不采信为实测结果。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。无 Web UI（Scout 入口为 CLI）。凭证环境变量名集中在 `hardware/run_qpu.py`（含 SPINQ/ORIGINQ/AWS 系列名称），模块声明 live 提交未实现。未见实填密钥。PowerShell 脚本只记录路径与内容，未执行。`l2_cli.py` 会尝试把 stdout 重配置为 UTF-8，以照顾 Windows 代码页。`loomq_l2.py` 含 120 秒 case 预算与 deadline 探测。公开电路与 evidence 中的 submission QASM 分开存放。

### 关键证据位置

[E-1] archive/generated/snapshots/qwer-asdftg/starter_kit/submission.yaml@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L2 声明为 true，但 `required_for_l2: false`
[E-2] archive/generated/snapshots/qwer-asdftg/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L94-L131 — 四契约函数
[E-3] archive/generated/snapshots/qwer-asdftg/starter_kit/Dockerfile@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L29 — SpinQ 与 Braket 分 venv
[E-4] archive/generated/snapshots/qwer-asdftg/starter_kit/l2_cli.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L49-L70 — `--guide` 不调用模型
[E-5] archive/generated/snapshots/qwer-asdftg/starter_kit/l2_profiles.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L37 — 本地 provider URL/模型快捷方式
[E-6] archive/generated/snapshots/qwer-asdftg/starter_kit/hardware/run_qpu.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L6 — 明确不支持 live QPU 提交
[E-7] archive/generated/snapshots/qwer-asdftg/scripts/verify_submission.ps1@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — PowerShell Docker 校验入口（未执行）
[E-8] archive/generated/snapshots/qwer-asdftg/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L17-L45 — 双平台 job 与原始 JSON 路径

### 结论置信度

契约字段冲突、Docker 隔离与模块职责为高（A）。真机导入链与 L2 网络实际需求无法静态确认。未运行选手代码。

## 46. `LouisYye`

### 身份与路径

- contestant_id：`LouisYye`
- snapshot：`archive/generated/snapshots/LouisYye/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/LouisYye/LoomQ-2026
- 上游 commit：`9e1f49feb17a8020531a82129c5979df81fc0c62`
- 评测根：`starter_kit/`；三级均声明，L2 需网络。

### 技术栈与结构

- 静态可见：Python、量子 SDK（含 Qiskit 2.5.2）、LLM 客户端。
- 规模：约 95 文件、50 个 Python。
- L1：`parser.py`（`qiskit.qasm2.loads`）+ `ir.py` + `emitters/` + `backend/`；SpinQ 经 `spinq_worker.py` 子进程。
- L2：`l2_agent.py` + `l2/{schema,normalize,simulate,synthesize,verify,backends,budget,render,reference}.py`。
- L3：`l3_compiler.py`。入口：`l2_cli.py`。另有 `examples/submit_originq_hardware.py`、`QUANTUM_RISCV.md`。
- 依赖拆成 `requirements.txt` 与 `requirements-spinq.txt`。
- 根目录另有 `L2_设计方案.md`、`L2_代码评审.md`、`report.json`、`tools/`。
- 无独立 Web UI；交互入口为 `l2_cli.py`。

### 方案概述

架构文档把模型限制为“理解意图”，语法、门集、分布与后端硬约束由本地代码检查。Agent 要求 JSON 输出，本地模拟保真度阈值 0.99，最多 3 次；常见目标可由 `synthesize.py` 确定性重建。CLI 强调闭式选项与“意义→证据→代码”的展示顺序。SpinQ 用隔离解释器避免与 Qiskit/Braket 冲突。已知限制写明：按比特下标描述目标时模型可能写反位序，并描述了裁决策略。

### 优点

- 对 SpinQ 依赖冲突给出独立 worker + 独立 requirements，而不是混装。
- L2 有 schema、参考分布、合成器与 CLI 多模块，职责边界清楚。
- `ARCHITECTURE.md` 主动记录位序失败模式与不影响的对称态，属于可维护的已知限制。
- 证据含量旋 msgpack 原始结果与本源 OriginIR/任务截图。
- 根目录设计/评审文档表明有独立于生成代码的审查痕迹。

### 质量问题与风险

- L1 解析依赖 Qiskit：官方公开 evaluator 号称标准库即可，本提交的 `parse_qasm` 在未安装 Qiskit 时无法按源码路径工作。
- `adapter.py` 对未知 target 抛 `NotImplementedError` 而非统一 `ValueError`。
- `backend/spinq.py` 使用 `subprocess.run` 调 worker；命令为固定解释器+脚本，但仍是进程边界。
- starter README 仍大量是官方模板，产品说明在 `ARCHITECTURE.md` 与 CLI 文档。
- `report.json` 存在于仓库，只能视为选手自备产物，不能当作本阶段评测结果。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。测试覆盖 braket/originq/spinq、L2 agent/cli/deterministic、L3、量子 RISC-V、originq hardware script。未见 Web UI。未见实填密钥。AI 辅助开发在 ARCHITECTURE 有披露。`l2_cli.py` 对缺失 qiskit/numpy 给出中文安装提示，避免被平坦导入的 `No module named l2` 掩盖。`transpile` 对 braket 在契约路径带 `include_stdlib=True`、执行路径 `False`，与 wronps 类似地处理 SDK/契约分叉。证据含 CLI 欢迎/错误恢复截图。

### 关键证据位置

[E-1] archive/generated/snapshots/LouisYye/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L48 — 按 target 分发 emit/run
[E-2] archive/generated/snapshots/LouisYye/starter_kit/parser.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L39 — 使用 `qiskit.qasm2.loads`
[E-3] archive/generated/snapshots/LouisYye/starter_kit/l2_agent.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L38-L67 — JSON 契约、3 次尝试、保真度阈值
[E-4] archive/generated/snapshots/LouisYye/starter_kit/l2_cli.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L14 — 新手 CLI 设计规则
[E-5] archive/generated/snapshots/LouisYye/starter_kit/backend/spinq.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L104-L116 — subprocess 调用 `spinq_worker.py`
[E-6] archive/generated/snapshots/LouisYye/starter_kit/ARCHITECTURE.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L59-L69 — 位序已知限制
[E-7] archive/generated/snapshots/LouisYye/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L50 — 双平台真机材料

### 结论置信度

Qiskit 解析依赖、worker 隔离与 L2 JSON 协议为高（A）。保真度阈值的实际效果无法静态确认。未运行选手代码。

## 47. `betsywbx`

### 身份与路径

- contestant_id：`betsywbx`
- snapshot：`archive/generated/snapshots/betsywbx/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/betsywbx/LoomQ-2026
- 上游 commit：`fea45fc143f4d5225bf1b07b0e73e41c94159ec5`
- 评测根：`starter_kit/`；三级均声明。`network.required_for_l2` 为 **false**。

### 技术栈与结构

- 静态可见：Python、Flask、HTML、量子 SDK（含 Qiskit 1.0.2）。
- 规模：约 65 文件、24 个 Python、仅 2 个测试文件。
- 结构较扁：`adapter.py` 路由到 `targets/{spinq,originq,braket}.py`，公共 `utils.py`。
- L2：`l2.py`；L3：`compiler.py`；Web：`app.py` + `index.html`。
- Bonus：`bonus/{demo_qxor_e2e.py,riscv_emulator_ext.py}`。
- 其它：`setup.sh`、`install.log`、`LOOMQ_README.md`、`report.json`。
- `requirements.txt` 同时钉 flask、scipy、两份 pyqpanda。
- `setup.sh` Git mode 为 0644（非可执行位）。根 README 为赛题包原文。

### 方案概述

产品 README 声称一份 OpenQASM 2.0 转三后端，并叠加自然语言 Agent 与 Hybrid 编译。`targets/spinq.py` 在模块级 `import spinqit`，transpile 侧以补寄存器/测量/头为主。L2 用系统提示词区分生成/修复/选后端，抽取 QASM 后对三 target 调用 `adapter.transpile`/`run` 做自测，最多再试 2 次。Flask 监听 `127.0.0.1:5000`，`/api/chat` 调 `agent_chat`，`/api/health` 只检查环境变量是否存在。

### 优点

- 后端文件按同一 `transpile_*` / `run_*` 模式对称，位序差异写在 README。
- L3 `compiler.py` 按抽块 → tokenize → AST → RISC-V 组织，而不是纯字符串替换。
- Flask health 接口便于判断 LLM 配置是否缺失。
- 证据含量旋、本源 Bell，以及额外的本源非对称电路 job。
- 明确披露 AI 辅助编程。

### 质量问题与风险

- `required_for_l2: false` 与实现调用 `chat_completion` 不一致。
- `app.py` 把异常类型与消息返回给前端，存在内部细节泄漏面。
- `install.log` 含本机用户路径与 venv 位置，属个人信息痕迹，不复述路径内容。
- `targets/spinq.py` 顶层导入 SDK：导入 `adapter` 即要求 spinqit 可导入，标准库-only 环境会失败。
- L2 自测对三后端各 `run(..., shots=256)`，若 SDK 缺失则 `import adapter` 失败后自测直接跳过（返回 None），校验可能空转。
- 根 README 仍为赛题包；starter 官方 README 与 `LOOMQ_README.md` 并存。测试文件仅 2 个，覆盖面偏窄。

### 完整性 / 可维护性 / 安全性观察

四契约函数存在。Flask 绑定 localhost、`debug=False`。未见 `.env` 实填。`setup.sh` 会创建 `.venv` 并 pip 安装（仅记录，未执行）；脚本检查 Python 3.8–3.11。Bonus 规格在 `bonus/qxor_isa_spec.md`。`compiler.py` 用括号深度抽取 `classical{}`，再生成 RISC-V。`install.log` 不应进入评测归档的必要性存疑。官方 `tests/` 几乎未扩展，质量信号主要依赖选手自述的本地验证。

### 关键证据位置

[E-1] archive/generated/snapshots/betsywbx/starter_kit/submission.yaml@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — L2 为 true 且 `required_for_l2: false`
[E-2] archive/generated/snapshots/betsywbx/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L56 — 路由到 targets/l2/compiler
[E-3] archive/generated/snapshots/betsywbx/starter_kit/app.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L22-L63 — Flask `/api/chat` 与 127.0.0.1:5000
[E-4] archive/generated/snapshots/betsywbx/starter_kit/l2.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L69-L117 — 用 adapter.run 自测并重试
[E-5] archive/generated/snapshots/betsywbx/starter_kit/targets/spinq.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 模块级导入 spinqit
[E-6] archive/generated/snapshots/betsywbx/starter_kit/LOOMQ_README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L19 — `setup.sh` 与 `python3 app.py`
[E-7] archive/generated/snapshots/betsywbx/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L57 — 双平台及非对称电路证据

### 结论置信度

Flask 入口、契约网络字段与顶层 SDK 导入为高（A）。自测空转条件与安装日志完整性无法静态确认。未运行选手代码。

## 48. `zmath01`

### 身份与路径

- contestant_id：`zmath01`
- snapshot：`archive/generated/snapshots/zmath01/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/zmath01/LoomQ-2026
- 上游 commit：`80c456562330d7b41efc08f5ceba339e2dbcddda`
- 评测根：`starter_kit/`；三级均声明，L2 需网络。根目录 `run.sh` 存在但 Git mode 为 0644（非可执行位）。

### 技术栈与结构

- 静态可见：Python、HTML、Shell 文本、量子 SDK 引用。
- 规模：约 94 文件、32 个 Python。
- L1 核心 `loomq_core/{qasm,simulator,transpilers,hybrid,agent}.py`，文档声称零第三方依赖。
- `adapter.run` 回读目标 IR 再采样；`backend` 字段为 `spinq_taurus` / `originq_local_simulator` / `braket_local_simulator`。
- 入口：`loomq_cli.py`、`loomq_web.py` + `webui/index.html`、`run_real.py`。
- 工程：`check_secrets.py`、`selftest.py`、`test_{l2_plumbing,quantum_riscv,web_api}.py`、`riscv_emulator_ext.py`。
- 依赖：`requirements.txt` 仅 `qiskit==1.4.6`（可视化可选），另附 `requirements_all.txt` / `requirements_qiskit252.txt`。
- 根 README 为赛题包；产品说明在 ARCHITECTURE/PRODUCT。根目录 `run.sh` mode 0644。

### 方案概述

架构主张“一个 IR、多个发射器”，且 `run()` 必须执行转译产物本身。L2 将能力表注入系统提示，抽取 QASM 后本地试跑，最多 3 轮。Web 绑定 127.0.0.1，文档端口 8000/8003。`run.sh` 声称依次：密钥扫描 → selftest → 量子 RISC-V 测试 → Web API 测试 → 启动 UI。`check_secrets.py` 扫描工作树/可选 git 历史中的 token/PEM 模式。`evidence/real_machine_runbook.md` 与 `run_real.py` **讨论** SpinQ 私钥应使用 PEM 格式而非带口令的 OpenSSH 格式——此为格式说明，**未发现私钥材料，此处不引用任何密钥头或密钥内容**。

### 优点

- `run()` 回读目标 IR 再模拟，使转译错误不能被执行器掩盖，设计意图清楚。
- 提交前密钥扫描器与 denylist（`.pem`/`.env` 等）是同批少见的工程卫生。
- 产品文档 `PRODUCT.md` 写目标用户与差异化，不只留官方模板。
- Web 注明不回显 API Key、限制 body 大小、只读 webui 目录。
- 自测脚本覆盖多电路 × 三后端与随机 L3 注入（存在性，不代表已执行通过）。

### 质量问题与风险

- 证据 README 出现路径笔误 `starer_kit/evidence/files/L1-real-machine`，与后文 `starter_kit/...` 不一致，人工核验时可能找不到目录。
- `run.sh` 无可执行位，文档 `./run.sh` 在默认 umask 下可能需 `bash run.sh`。
- `check_secrets.py` 被清单标为 env-like，实为扫描器源码，不是 dotenv。
- 真机 runbook 含本机 `~/.ssh/...` 生成命令示例；只说明格式，不构成仓库内密钥。
- Qiskit 作为可选可视化依赖，未安装时的回退写在 evidence，Web 路径无法静态确认。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。三份 requirements 可能造成“该装哪份”的歧义：L1 自称标准库，真机/可视化才需要 SDK。在受检规则下，PEM 命中仅出现在文档/扫描器/错误提示，未见私钥载荷。未执行 `run.sh`。Web `/api/run` 可一次返回三后端 IR 对比；`MAX_SHOTS = 100_000`。证据还指向 `files/L2-agent` 与 `files/guide-visualization`。`SUBMISSION_GUIDE.md` 在 snapshot 根目录，属额外导航。

### 关键证据位置

[E-1] archive/generated/snapshots/zmath01/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L63-L97 — `run` 转译后再 `parse_target_ir` 并本地采样
[E-2] archive/generated/snapshots/zmath01/starter_kit/ARCHITECTURE.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L34 — 单一 IR 与回读执行
[E-3] archive/generated/snapshots/zmath01/starter_kit/check_secrets.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L43-L61 — 密钥模式与文件 denylist（扫描器，非密钥）
[E-4] archive/generated/snapshots/zmath01/run.sh@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L30 — 一键自检叙事（mode 0644，未执行）
[E-5] archive/generated/snapshots/zmath01/starter_kit/loomq_web.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L22 — localhost、不回显 Key
[E-6] archive/generated/snapshots/zmath01/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L17-L27 — 真机状态与路径笔误 `starer_kit`
[E-7] archive/generated/snapshots/zmath01/starter_kit/PRODUCT.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L17 — 目标用户叙事

### 结论置信度

回读执行设计、密钥扫描器与 PEM **格式讨论** 为高（A）。自检脚本是否通过、真机目录是否与笔误路径一致，无法静态确认。未运行选手代码，未引用密钥材料。

## 49. `BH2-4`

### 身份与路径

- contestant_id：`BH2-4`
- snapshot：`archive/generated/snapshots/BH2-4/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/BH2-4/LoomQ-2026
- 上游 commit：`dc7849a3379652c3e72258327296b957a0da012c`
- 评测根：`starter_kit/`；三级均声明，L2 需网络。

### 技术栈与结构

- 静态可见：Python、量子 SDK 引用（评测路径文档声称标准库）。
- 规模：约 73 文件、40 个 Python。
- L1：`loomq/{qasm2,ir,sim,codegen}.py`。
- L2：`loomq_l2/{prompts,templates,validate,selector,repair}.py`。
- L3：`loomq_l3/{parser,classic,codegen,interp}.py`；Bonus：`qext_codegen.py`、`riscv_emulator_qext.py`。
- 入口与自测：`chat.py`、`selfcheck.py`、`l2_selftest.py`、`l3_selftest.py`。
- `requirements.txt` 为空注释。真机脚本在评测根之外的 `tools/qpu/`。
- 几乎无 Web（仅赛题 HTML）。根 README 明确 fork 身份与安全红线。

### 方案概述

设计铁律：LLM 只输出意图 JSON，电路由模板库确定性生成，本地模拟对拍，失败回喂修复。`adapter.run` 用纯标准库态矢量采样，backend 字段为 `{target}_local_statevector`。`chat.py` 提供交互、`--prompt`、`--doctor`、`--demo` 离线演示，回复含 ASCII 直方图与通俗解释。Bonus 在官方模拟器扩展 fork 上增加 QH/QX/QCX/QMS/QP，规格见 `l3_bonus_spec.md`。根 README 置顶安全红线：密钥只走环境变量。

### 优点

- L2“模型不写 QASM”把正确性从生成模型移到可测模板，设计目标明确。
- L1 零第三方依赖，与禁网评测约束一致。
- QASM 解析支持自定义门展开与较宽内置门表，超出 12 门白名单的输入会走展开或报错路径（具体覆盖无法静态确认）。
- 安全说明、`.gitignore` 模式与 `chat.py` 缺环境提示形成闭环。
- 真机采集工具与评分 `run()` 目录分离，降低误提交。

### 质量问题与风险

- 无浏览器 UI；L2 体验完全依赖 CLI，现场演示形态与 Web 提交不同。
- `requirements.txt` 为空：L1/L3 可自洽，但 `tools/qpu` 所需 SDK 不在评测依赖里（符合“工具不在 starter_kit”的声明）。
- ARCHITECTURE 中“live 25/25”等语句是选手自测叙述，本报告不采信为结果。
- `tools/qpu/README.md` 含环境变量占位与本机密钥路径提示，未发现密钥载荷。
- 官方测试目录仅 2 个文件；大量自测是 `selfcheck.py` / `l2_selftest.py` 脚本，是否纳入 `tests/` 发现器取决于调用方式。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。文档质量高（GETTING_STARTED、ARCHITECTURE、Bonus 规格、密钥红线）。未见实填密钥。未执行任何 QPU 脚本。`chat.py` 在缺 `LOOMQ_LLM_*` 时打印 `WELCOME_NO_ENV` 并仍提供 `--demo`。`adapter.run` 用 SHA256 前缀生成 `job_id`，不依赖外部队列。`loomq/qasm2.py` 词法支持注释、箭头与数值，遇 `if`/`reset` 显式报错。Bonus 测量采用确定性最大幅度读数并写明平局容差，属于可复核的语义选择，不是运行结果。

### 关键证据位置

[E-1] archive/generated/snapshots/BH2-4/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L29-L70 — 本地 statevector `run` 与 L2/L3 转发
[E-2] archive/generated/snapshots/BH2-4/starter_kit/ARCHITECTURE.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L23 — 三层与“模型只出意图 JSON”
[E-3] archive/generated/snapshots/BH2-4/starter_kit/loomq_l2/__init__.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L4 — LLM 不直接写电路
[E-4] archive/generated/snapshots/BH2-4/starter_kit/chat.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L11 — CLI/`--demo` 入口
[E-5] archive/generated/snapshots/BH2-4/starter_kit/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L24 — 密钥红线
[E-6] archive/generated/snapshots/BH2-4/starter_kit/l3_bonus_spec.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L15-L24 — QH/QX/QCX/QMS/QP
[E-7] archive/generated/snapshots/BH2-4/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L68 — 双平台 job 与 CLI 体验任务
[E-8] archive/generated/snapshots/BH2-4/tools/qpu/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L4 — 真机工具不属于评测物

### 结论置信度

标准库 L1、L2 模板策略与目录边界为高（A）。模板对隐藏措辞的覆盖、QPU 工具行为无法静态确认。未运行选手代码。

## 50. `Duanice`

### 身份与路径

- contestant_id：`Duanice`
- snapshot：`archive/generated/snapshots/Duanice/`
- 聚合仓库基线 SHA：`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`
- 上游仓库：https://github.com/Duanice/LoomQ-2026
- 上游 commit：`0b67a1fcb2ca6bf95a614a871edd8074313b42a5`
- 评测根：`starter_kit/`；三级均声明，L2 需网络。可执行 Shell 仅记录：`starter_kit/run_demo.sh`（mode 0755）。

### 技术栈与结构

- 静态可见：Python、HTML、Shell、量子 SDK。
- 规模：约 89 文件、42 个 Python。
- L1：`qasm_parser.py`、`emitters.py`、`simulator.py`、`platform_runners.py`（SpinQ 经 `spinqit_worker.py`；另有 `originq_cloud_worker.py`）。
- L2：`agent/{core,prompts,verifier,backends,explainer,presenter,server}.py` 与 `ui.html`。
- L3：`hybrid_compiler.py`。另有 `hardware_runner.py`、`examples/run_{spinq,originq}_hardware.py`。
- 防御脚本：`l1_defense.py`/`l3_defense.py` 及 `*-defense-report.json`；规格：`QUANTUM_RISCV_SPEC.md`、`L2_DESIGN.md`。
- 依赖拆为 `requirements.txt`、`requirements-spinq.txt`、`requirements-originq-cloud.txt`；根目录 `pyproject.toml`/`uv.lock`/`scripts/`。
- Web 入口 `agent/server.py`。可执行 Shell（未执行）：`starter_kit/run_demo.sh`。

### 方案概述

README 把一键体验写成 Docker：`./starter_kit/run_demo.sh` 构建 linux/amd64 镜像、选端口、等待 HTTP、打开浏览器；无 Docker 时打印官方安装教程且声称不擅自装系统软件。未配置模型时仍可看教程与标注的离线 Bell Demo，且文档写明离线示例不冒充 Agent。`L2_DESIGN.md`：模型出 JSON 计划，本地 verifier 用解析器+模拟器+保真度门槛决定是否接受；后端选择只返回一个规范 ID。`adapter.run` 先 emit 再交给各 platform runner。

### 优点

- 角度求值用 AST visitor，源码写明“不用 eval()”，比同批若干 `eval` 实现更收敛。
- SpinQ 依赖通过独立解释器 + worker JSON stdin 隔离，Dockerfile/环境变量 `LOOMQ_SPINQIT_PYTHON` 配套。
- L2 设计文档把评分路径与 UI 路径拆开，避免 UI 技能泄漏进 `agent_chat`。
- `run_demo.sh` 对 Docker 缺失/未启动有分支说明（仅记录，未执行）。
- 证据含量旋与本源的 raw/result/submission JSON 及截图。
- `l1_defense.py`/`l3_defense.py` 提供 hidden-style 差分测试脚本。

### 质量问题与风险

- `run_demo.sh` 为可执行 Shell，含 `docker`/`open -a Docker` 等宿主机副作用；本阶段只记录路径，不执行。
- `platform_runners.py` 对 worker 使用 `subprocess.run`；命令列表固定，但仍是外部进程。
- 测试中出现 `python -m agent.server --host 0.0.0.0` 字符串断言，需确认默认绑定是否仍为 127.0.0.1；`server.py` 文档示例为 127.0.0.1:8000。
- 扫描器曾在测试文件命中 keyish 模式，核对后为 `assertNotIn("LOOMQ_LLM_API_KEY=")`，不是实钥。
- 根 `uv.lock`/`pyproject.toml` 与 starter `requirements*.txt` 双轨，复现入口可能混淆。

### 完整性 / 可维护性 / 安全性观察

四契约函数齐全。文档强调 API Key 只经 Docker 环境转发、不进镜像/参数/日志。未见 `.env` 实填。`THIRD_PARTY_NOTICES.md` 存在。`agent/core.py` 设 `CASE_BUDGET_SECONDS = 115`、`CALL_TIMEOUT_SECONDS = 35`、最多 3 次候选。测试在 snapshot 根 `tests/` 与 `starter_kit/test_quantum_riscv.py` 两处。未执行 `run_demo.sh` 或任何 worker。`fix_spinqit_macos.py` 位于 snapshot 根，属平台变通脚本，不在契约入口内。

### 关键证据位置

[E-1] archive/generated/snapshots/Duanice/starter_kit/adapter.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L31-L73 — emit + platform run；L2/L3 延迟导入
[E-2] archive/generated/snapshots/Duanice/starter_kit/simulator.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L25-L44 — AST 求角度、明确不用 eval
[E-3] archive/generated/snapshots/Duanice/starter_kit/platform_runners.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L71-L128 — 独立 Python 调 `spinqit_worker.py`
[E-4] archive/generated/snapshots/Duanice/starter_kit/L2_DESIGN.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L19-L30 — 模型计划 + 本地 verifier
[E-5] archive/generated/snapshots/Duanice/starter_kit/agent/server.py@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L12 — 本地 UI 与离线 Bell 不冒充 Agent
[E-6] archive/generated/snapshots/Duanice/starter_kit/run_demo.sh@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — 可执行 Docker 启动脚本（未执行）
[E-7] archive/generated/snapshots/Duanice/starter_kit/evidence/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L66 — 双平台 job 与 `agent.server` 入口
[E-8] archive/generated/snapshots/Duanice/starter_kit/README.md@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L31 — Docker 一键叙事与离线 Demo 边界

### 结论置信度

契约、AST 求值、worker 隔离与可执行脚本路径为高（A）。Docker 一键是否成功、默认监听地址在所有入口是否均为 localhost，无法静态确认。未运行选手代码或 Shell。

## 51. `danjituya`

### 身份与路径

正式 roster 成员 `danjituya`。聚合仓库快照位于 `archive/generated/snapshots/danjituya/`，上游仓库
`https://github.com/danjituya/LoomQ-2026`，上游 commit
`83e0c5c2f511265a75d94ea2672134ce0f59ab8d`。本报告固定基线 SHA
`998cd4e67b1b29f0f1eb8bafdc155072dfda2980`。Starter 目录名为 `starter_kit/`（下划线）。事实卡统计约 64
个文件、34 个 Python 文件、1 个 Web 入口、14 个测试文件；根目录保留赛题 PDF/HTML/DOCX、提交流程图、`competition/`、
`tests/` 与 `NEXT.md`。

`submission.yaml` 为标准 v1.1.0 契约：`entrypoint: adapter.py`，`levels.l1/l2/l3` 均为 `true`，
运行时 Python 3.10，L1 不要求网络、L2 要求网络，`allowed_hosts` 为空列表，L2 协议为
`openai_chat_completions`，必填环境变量 `LOOMQ_LLM_BASE_URL/API_KEY/MODEL`。

### 技术栈与结构

静态可见技术栈为 Python 3.10、Flask 单页、Braket SDK 与 pyQPanda。`requirements.txt` 精确锁定
`numpy==1.26.4`、`amazon-braket-sdk==1.110.1`、`pyqpanda==3.8.5`、`flask==3.1.3`，
并在注释中明确不安装 `spinqit`（称其 antlr/numpy/torch 链与另外两家冲突）。核心实现几乎全部落在约 1415 行的 `adapter.py`：
自写 OpenQASM 2.0 解析、白名单分解、三目标渲染、`run()`、`agent_chat()`、`compile_hybrid()`。

额外模块：`webapp.py`（Flask，内嵌零 CDN HTML/SVG）、`cli.py`（终端对话）、`quantum_riscv_ext.py` 与
`QRVE_SPEC.md`、`structured_fallbacks.py`、`l2_oracle.py`、`verify_l2.py`、`stdgates.inc`，
以及根目录 `tests/` 下的门矩阵、L2 mock/real、L3 fuzz 等脚本。`evaluator.py` 仍是公开契约自测形态。Dockerfile 安装
`libcurl4`，默认 CMD 只评测 `braket,originq`。

### 方案概述

`ARCHITECTURE.md` 声称「一份电路、处处可跑」的中间层，并配自然语言 Agent 与 Hybrid-QASM 编译。源码静态可见的数据流是：QASM 文本
→ `_parse_qasm2` → 按目标 `_decompose_to_primitives` / `_apply_fallbacks` → spinq 归一化
QASM2、braket OpenQASM 3、originq OriginIR。`run()` 对 Braket 使用 `LocalSimulator` 且带
`concurrent.futures` 超时，对本源走 pyQPanda；文档还描述 Braket CNOT 比特对的自愈置换，该行为是否在隐藏电路上生效无法静态确认。

L2 通过官方 `llm_client.py` 读环境变量。产品入口有两个：证据 README 声称 `python starter_kit/webapp.py`
打开本机 Web，备用 `python starter_kit/cli.py`。页面声称客户端渲染电路 SVG 与测量柱状图，并内置「30 秒量子入门」。L3 在
`compile_hybrid()` 拆分量子语句与 `classical {}` 块后生成 RISC-V 文本。自定义量子 RISC-V 把 12 门映射到
`custom-0` 助记符（`Q.H`/`Q.CX`/`Q.MEAS` 等）。证据清单勾选 L2 交互、工程化、RISC-V Bonus 与新手引导，**未申报 L1
真机**。

### 优点

文档与实现边界写得清楚：为何放弃 spinqit、位序约定、12 门 fallback 表都在 `ARCHITECTURE.md` 与 `adapter.py` 同步出现。
L1 不满足于公开 Bell/GHZ，另有 `tests/l1_gate_matrix.py` 一类逐门对照脚本。L2 同时提供 Flask 单页和 CLI，Web
无外部 CDN。L3 与 QRVE 有规格和 `test_qrve_bonus.py`。依赖全部 `==` 钉死，Docker 默认目标与「不装 spinqit」一致，
减少官方构建因冲突失败的表面风险。证据 README 对真机项明确写「未申报」，没有用模拟器冒充真机。

### 质量问题与风险

`adapter.py` 把解析、转译、执行、Agent、混合编译放在同一文件，变更面宽，评审难以按层抽检。门参数半角计算使用内置 `eval(...,
{"__builtins__": {}}, {"pi": ...})`；OriginIR 参数另有 AST `_safe_eval`。两者都把电路文本当表达式求值，
属于不信任输入上的求值面，无法静态确认可利用性。Flask 默认 `LOOMQ_BIND_HOST=0.0.0.0`，文档虽写 `127.0.0.1:8765`，
进程默认监听全部接口。

spinq 的 `transpile()` 仍可归一化输出，但 `run("spinq")` 在缺 SDK 时按注释应抛错；该路径未进入 requirements，
官方容器内的 spinq 执行无法静态确认。证据目录几乎只有 README，没有 `evidence/files/` 截图或原始 job。README 中的「公开评测
4/4」是选手自述，不是本阶段复跑。`cli.py` 用法注释含 `sk-xxx` 形态占位符，不是可工作密钥。

### 完整性 / 可维护性 / 安全性观察

契约文件、Dockerfile、公开 evaluator、赛题配套文档齐全。测试文件数量多，但多为选手自写脚本，存在性不等于通过。L2 凭据只从环境变量读取。Web 把
Agent 输出拼进内嵌脚本字符串，静态未见 CSP。默认绑定 `0.0.0.0` 扩大本地演示暴露面。受检路径未发现嵌入私钥或 `.env` 实值。可维护性主要受巨型
adapter 与「spinq 转译保留、执行放弃」的双轨说明影响。未运行 Flask、未安装依赖、未执行 tests。

### 关键证据位置

[E-1] `archive/generated/snapshots/danjituya/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 声明 l1/l2/l3 全开、Python 3.10、L2 需 `LOOMQ_LLM_*`。
[E-2] `archive/generated/snapshots/danjituya/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L56-L93 — 自写 OpenQASM 2.0 解析器。
[E-3] `archive/generated/snapshots/danjituya/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L188-L197 — 门参数路径使用内置 `eval`。
[E-4] `archive/generated/snapshots/danjituya/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L352-L362 — OriginIR 参数的 AST `_safe_eval`。
[E-5] `archive/generated/snapshots/danjituya/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L404-L414 — `transpile()` 按 spinq/braket/originq 三路渲染。
[E-6] `archive/generated/snapshots/danjituya/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1391-L1414 — `compile_hybrid()` 拆分量子操作与经典汇编。
[E-7] `archive/generated/snapshots/danjituya/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L25 — 声称 L1 双模拟器、未申报真机、spinq 因依赖冲突未列入 requirements。
[E-8] `archive/generated/snapshots/danjituya/starter_kit/webapp.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L483-L487 — Flask 默认绑定 `0.0.0.0:8765`。
[E-9] `archive/generated/snapshots/danjituya/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L12 — 精确锁定四包，注释说明不装 spinqit。
[E-10] `archive/generated/snapshots/danjituya/starter_kit/Dockerfile`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L16 — 默认 evaluator 目标 `braket,originq`。
[E-11] `archive/generated/snapshots/danjituya/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L17 — 勾选 L2/工程/Bonus，明确未申报 L1 真机。

### 结论置信度

路径、yaml 字段、入口函数与 Flask 绑定为 **A（高）**。架构叙述与源码模块对应为 **B（中）**。门矩阵是否通过、Agent 自验闭环、L3 隐藏用例、
spinq 快速失败文案是否在运行时出现，均 **无法静态确认（C）**。本阶段未运行、未安装、未联网。

## 52. `WayneYu1212`

### 身份与路径

正式 roster 成员 `WayneYu1212`。快照 `archive/generated/snapshots/WayneYu1212/`，上游
`https://github.com/WayneYu1212/LoomQ-2026`，上游 commit
`3f8d8e65314e6a920a17bc611e8ab1e90aa328d7`。基线 SHA 同上。事实卡：约 233 个文件、96 个 Python、4 个
Web 文件、92 个证据文件、32 个测试，体积约 13.6 MiB，定制度 high。根目录含完整赛题材料、`competition/` 与 `.release/`。
媒体只按 blob 元数据处理，未打开或播放。

`submission.yaml` 为标准 v1.1.0 契约：`l1/l2/l3: true`，Python 3.10，L2 需网络，`allowed_hosts`
为空，入口 `adapter.py`。Starter README 自称面向无量子背景的人文/设计/产品用户。

### 技术栈与结构

Python 包化实现。`adapter.py` 仅 41 行，用 `importlib` 按 `__package__` 选择 `starter_kit.` 前缀，
把契约转交给 `loomq.compiler.parser`、`loomq.emitters`、`loomq.runners`、`loomq.agent.service`、
`loomq.hybrid`。`loomq/` 下另有表达式 AST、IR、validator、独立 `simulator.py`、三家 emitter/runner。
`hardware/` 含本源 QCloud 与 Origin runtime、Braket QPU 脚本；`scripts/` 含
`setup.sh`/`setup.ps1`、`run_web.ps1`、断层扫描与 L2 campaign 校验。Web 为
`loomq/web/server.py`（`ThreadingHTTPServer`）+ `static/{index.html,app.js,styles.css}`。

`requirements.txt` 为长锁且全部 `==`；本源现代 runtime 被隔离到
`requirements-originq-runtime.txt`（`qpanda3-runtime`/`pyqpanda3`）。启发式技术栈标签含 pennylane，
来自锁文件传递依赖，不表示选手主路径使用它。测试位于 `starter_kit/tests/` 与根 `tests/`。

### 方案概述

`ARCHITECTURE.md` 声称「一个 parser、一套冻结 IR、三个 emitter/runner」：注释剥离后解析声明与语句，
参数表达式只允许字面量/`pi`/四则与幂，任意名字与调用不执行。三家 runner 把原生计数归一成 `bit_order="little"`，
并区分二进制串与十进制串以免 pyQPanda `"11"` 被当成十一。独立 `simulator.py` 用标准库复数实现 12 门，文档声称最多 16 比特、
不作缺失 SDK 的自动替身。

L2 流程：`llm_client.chat_completion()` 非流式、温度 0 → JSON
`AgentPlan`（generate/repair/recommend）→ 同一 parser/validator/模拟器；失败向模型回灌一次消毒后的错误。
推荐后端只查官方 `backend_capabilities.json`。L3 `loomq.hybrid` 与 L1 编译器隔离，文档声称不用
`eval`/`exec`。Web 默认 `127.0.0.1`，请求体 64 KiB、shots 上限 8192；Bell/GHZ 本地示例标记为
`local_example`，仍走 parser 与 SDK。证据勾选全部人工项，canonical 真机为 Origin job
`D0C7F490B43D9B04FDF19ABF3DB8B342` 与 SpinQ job `G-260820-0008`；`originq_runtime_*`
被标为补充材料而非第三平台。

### 优点

契约层极薄，业务按编译/发射/执行/Agent/Web 分目录，适合对照 `target_ir_contract.md`。架构文明确禁止参考模拟器顶替 SDK，
并区分本地示例与自由 Agent。Web 默认回环、限制体量，文档声称用 `textContent` 插入模型文本、带限制性 CSP。证据链按平台拆
raw/normalized/metadata/截图，并有 `SECURITY_SWEEP.md`、`SCIENTIFIC_CLAIMS_AUDIT.md`、
`CLEAN_ROOM_REPRODUCTION.md`、`JUDGE_GUIDE.md`。Origin runtime 可选安装，降低三 SDK 同环境冲突。
科学诚实文档把 Z 基关联与纠缠证明分开写。

### 质量问题与风险

体量大：96 个 Python 与大量 JSON/PNG/MP4，抽取 `starter_kit/` 后仍很重。`adapter.py` 的动态导入依赖
`__package__`，从非包路径导入的行为无法静态确认。`scripts/*.ps1` 只记录路径，不执行。L2/真机文档含「499/500」「5/5」
等选手自测数字，不得当作官方分数；`JUDGE_GUIDE.md` 自己也保留 29/30 与随机残差说明。硬件 raw JSON/CSV/msgpack 需当敏感输出，
受检文本未见嵌入 API key。最大媒体 `loomq-final-demo.mp4` 为 8 817 627 bytes，只能作为存在性证据。

### 完整性 / 可维护性 / 安全性观察

契约文件、Dockerfile、公开 evaluator、赛题配套齐全。测试覆盖 parser、emitter、hybrid 对抗、web 资产、hardware
validator 等多个面。可维护性优点是文档索引，代价是阅读成本。Web 默认 `127.0.0.1`；LLM 凭据只从服务端环境读取。
`SECURITY_SWEEP.md` 自称对 token 形态与个人绝对路径扫描 PASS，这是仓库内报告，不是本阶段独立扫描。受检路径未发现嵌入私钥。
PowerShell 硬件 doctor 属于本机副作用面，未执行。未打开任何 PNG/MP4。

### 关键证据位置

[E-1] `archive/generated/snapshots/WayneYu1212/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 标准契约，三级全开。
[E-2] `archive/generated/snapshots/WayneYu1212/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L40 — 薄适配层，动态导入 loomq 子模块。
[E-3] `archive/generated/snapshots/WayneYu1212/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L12 — 声称单一 parser/IR，参数表达式走 AST 白名单。
[E-4] `archive/generated/snapshots/WayneYu1212/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L50-L74 — L2 JSON 计划、L3 不用 eval、Web 回环与 CSP。
[E-5] `archive/generated/snapshots/WayneYu1212/starter_kit/loomq/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L28-L31 — `MAX_REQUEST_BYTES=65536`、`MAX_SHOTS=8192`。
[E-6] `archive/generated/snapshots/WayneYu1212/starter_kit/loomq/web/server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L312-L328 — HTTP 服务默认 host `127.0.0.1`。
[E-7] `archive/generated/snapshots/WayneYu1212/starter_kit/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L15-L27 — README 声称三后端、12 门、双平台真机申报。
[E-8] `archive/generated/snapshots/WayneYu1212/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L36 — 勾选全部人工项，列出两个 canonical job。
[E-9] `archive/generated/snapshots/WayneYu1212/starter_kit/JUDGE_GUIDE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L22 — 60 秒核验表；L2 数字为选手自测。
[E-10] `archive/generated/snapshots/WayneYu1212/starter_kit/evidence/SECURITY_SWEEP.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L13-L23 — 仓库内安全扫表，浏览器不发送 API key。
[G-1] `archive/generated/snapshots/WayneYu1212/starter_kit/evidence/files/loomq-final-demo.mp4`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=8817627；仅元数据，未播放。
[G-2] `archive/generated/snapshots/WayneYu1212/starter_kit/evidence/files/v7.2-mobile-full-390.png`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=359261；未打开像素。
[G-3] `archive/generated/snapshots/WayneYu1212/starter_kit/evidence/files/spinq-hardware-bell.raw.qasm.gz`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob；provider 导出压缩件，未解压。

### 结论置信度

目录地图、薄 adapter、回环 Web 与 yaml 为 **A**。IR/自验/真机链路的设计叙述与文件布局互证为 **B**。任何 SDK 运行、L2 压力通过率、
真机主峰是否符合规则均 **无法静态确认（C）**。未运行代码，未打开媒体。

## 53. `HpIahtcthocw`

### 身份与路径

正式 roster 成员 `HpIahtcthocw`。快照 `archive/generated/snapshots/HpIahtcthocw/`，上游
`https://github.com/HpIahtcthocw/LoomQ-2026`，上游 commit
`c636a2a87bf7b6896268d7b73fa0e211c6c8b09f`。事实卡约 113 个文件、47 个 Python、4 个 Web 文件、26
个证据文件。根目录在标准赛题材料之外增加 `PLAN.md`、`RUNBOOK.md`、`start.sh`、`start.ps1`、`env.example.txt`、
`docs/quantum-riscv-extension.md`、`regression/`、`tools/`。

`submission.yaml` 标准三级全开，Python 3.10，L2 需网络。starter 内 `README.md` 仍是官方工具包模板目录树；
真正的产品导航在根 RUNBOOK/PLAN 与 `evidence/README.md`。

### 技术栈与结构

`adapter.py` 44 行，四函数全部委托 `loomq` 包：`qasm2_parser` → `ir` → `emitters` / `backends` /
`counts` / `agent` / `hybrid`，另有 `refsim.py`、`decompose.py`、`visualize.py`、`cli.py`。
Web 为 `loomq/web.py` 标准库 HTTP，静态资源在 `loomq/webui/{index.html,app.js,styles.css}`。
启发式标签中的 Flask/FastAPI 未在该 Web 入口出现。

`tools/` 含 selftest、真机探测、回归、`build_evidence_gif.py` 与 `make_spinq_key.py`（密钥生成器，
**本阶段未运行**）。`regression/circuits/` 提供 ghz5、grover3、qft4 与随机电路及
`ideal_distributions.json`。依赖锁体积大、版本钉死。根 `tests/` 仍是官方两份契约测试。

### 方案概述

PLAN/RUNBOOK 把路径写成「零基础网页 → 自然语言 → 真机」，并强调无模型时三个本地示例仍可走完。源码静态可见 `transpile` =
`emitters.emit(parse(...))`，`run` = `backends.execute(...)`。`start.sh` 若存在 `.env` 则
`set -a; . ./.env`，再 `cd starter_kit` 执行 `python -m loomq.web`。`web.py` 的 `serve()`
绑定 `127.0.0.1`，默认端口 8899（被占用则换端口）；证据 README 写的启动示例是 `start.ps1 --port 8898`。

`hybrid.py` 文件头说明对题面文法取超集：嵌套 if、无 else、多 classical 块、括号与一元负号。证据勾选全部人工项，申报量旋云
Gemini（`G-260808-0002`）与 Triangulum 两个 NMR 平台，并引用
`stranger-five-minute-test.md`——后者是文档声称。`env.example.txt` 只留空的 `LOOMQ_LLM_*` 与
`LOOMQ_SPINQ_*` 字段名。

### 优点

契约层与实现层分离清楚。启动脚本把「无配置也能看三个例子」写成默认路径。Web 默认回环。真机证据同时归档 QASM、统一 schema JSON、raw payload
与位序校准 JSON。RUNBOOK 把量旋 SDK 只接受 PEM、不接受 OpenSSH 私钥格式写成操作说明，并把私钥目录指定为仓库外 `~/.spinq/`。
回归电路说明作者考虑了隐藏形状，而不只是 Bell/GHZ。GIF 由已归档截图脚本生成的说法写在 evidence README，脚本路径可核对。

### 质量问题与风险

根 `PLAN.md` 含「已打满 / 24/24」等作战笔记，不能当评分。starter README 未改成项目说明，评委若只看该文件会误判为库存 kit。
`tools/make_spinq_key.py` 会在用户主目录写 PEM 私钥；静态可见生成逻辑，禁止运行。RUNBOOK 只讨论量旋 SDK
认 PEM、不认 OpenSSH 私钥**格式**，受检文件不是嵌入私钥，不得复制密钥材料。`tools/` 含联网探测脚本，未执行。事实卡
`private_key_pem` 命中应解读为文档/生成器，而非仓库内私钥。

### 完整性 / 可维护性 / 安全性观察

赛题配套、Dockerfile、契约 yaml、证据截图/GIF 均在。可维护性优点是 RUNBOOK 逐步操作；风险是 `tools/` 与
`starter_kit/` 双根，若评测只抽 `starter_kit/`，selftest 与真机脚本不随包走。`start.sh` 依赖 `.gitignore`
不提交 `.env`；快照内可见的是空值 example。Web 监听回环。未复制任何密钥内容。陌生人实测与 GIF 为归档材料，像素/动效未打开核验。`PLAN.md`
的「待找真人试」与 evidence 中陌生人记录并存，以 evidence 文本为准，两者是否同一事件无法静态确认。

### 关键证据位置

[E-1] `archive/generated/snapshots/HpIahtcthocw/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 标准三级声明。
[E-2] `archive/generated/snapshots/HpIahtcthocw/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L13-L43 — 薄适配，委托 loomq。
[E-3] `archive/generated/snapshots/HpIahtcthocw/starter_kit/loomq/__init__.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L14 — 分层：parser / IR / emitters / counts / backends。
[E-4] `archive/generated/snapshots/HpIahtcthocw/start.sh`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L22-L37 — 可选加载 `.env`，然后 `python -m loomq.web`。
[E-5] `archive/generated/snapshots/HpIahtcthocw/starter_kit/loomq/web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L503-L521 — `ThreadingHTTPServer(("127.0.0.1", port), ...)`，默认端口 8899。
[E-6] `archive/generated/snapshots/HpIahtcthocw/RUNBOOK.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L400-L404 — 文档讨论 PEM vs OpenSSH 格式，私钥放仓库外。
[E-7] `archive/generated/snapshots/HpIahtcthocw/tools/make_spinq_key.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L16 — 密钥生成器说明；未执行。
[E-8] `archive/generated/snapshots/HpIahtcthocw/env.example.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L19 — 示例环境变量名，API key 字段为空。
[E-9] `archive/generated/snapshots/HpIahtcthocw/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L13-L46 — 申报双量旋真机与完整 Bonus 清单。
[E-10] `archive/generated/snapshots/HpIahtcthocw/PLAN.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L25 — 作战计划中的模块状态表（非评分结论）。
[G-1] `archive/generated/snapshots/HpIahtcthocw/starter_kit/evidence/files/loomq-walkthrough.gif`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=764036；未播放。
[G-2] `archive/generated/snapshots/HpIahtcthocw/starter_kit/evidence/files/stranger-completion-poster.png`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=1385522；未打开。

### 结论置信度

包结构、薄 adapter、回环 Web、yaml 为 **A**。PEM 格式说明 vs 嵌入密钥的区分、启动脚本行为为 **B**。真机任务、陌生人 5 分钟测试、
selftest 通过与否 **无法静态确认（C）**。未运行 `make_spinq_key.py` 或任何选手脚本。

## 54. `casccjy67`

### 身份与路径

正式 roster 成员 `casccjy67`。Scout 已标明根结构偏离通用模板，但 manifest / snapshot / commit-object
链路完整，不得排除。快照 `archive/generated/snapshots/casccjy67/`，上游
`https://github.com/casccjy67/LoomQ-2026`，上游 commit
`bff6cd9503a49d2cf952686e049443ec6f9c1544`。事实卡约 34 个文件、24 个 Python，体积约 97 KiB。

根目录只有 `README.md`、`requirements.txt`、`setup.py`、`test_circuits.py`、
`competition/config.json`、`starter_kit/`。**缺少**多数快照中的赛题 PDF/HTML/DOCX、提交流程图、
`problem_statement.md`、根 `tests/`。`competition/` 仅余 `config.json`。事实卡
`levels_declared` 解析为全 `None`，与自定义 yaml 键有关。

### 技术栈与结构

Python。实现按包拆分：`transpiler/{parser,ir,base_backend,spinq,originq,braket}_backend.py`、
`agent/chat.py`、`hybrid_compiler/{lexer,parser,codegen,compiler}.py`。`adapter.py` 先
`sys.path.insert` 仓库根，再 `from starter_kit.transpiler ...` 导入。根 `requirements.txt`
全是范围约束（`numpy<2`、`spinqit>=0.2.3`、`pyqpanda3>=0.4.0`、`amazon-braket-sdk>=1.80.0`、
`openai>=1.0.0`、`pyyaml>=6.0`），未钉死。

`setup.py` **不是** setuptools 包装，而是 Windows 安装脚本：硬编码本机 Python 3.12 解释器绝对路径（提交材料含本机绝对路径残留；此处不复述盘符、用户名或个人目录），并用
`subprocess.run(..., shell=True)` 装包。`starter_kit/` 有 Dockerfile、`evaluator.py`、
`submission.yaml`、`prepare_submission.py`、`riscv_emulator.py`，但缺少官方 kit 的
`llm_client.py`、`l2_policy.json`、`backend_capabilities.json`、`VERSION`、`CHANGELOG.md`、
`examples/`。快照提交了 `__pycache__/*.pyc`（约 19 个）。starter README 目录树仍列出并不存在的
`llm_client.py`。

### 方案概述

根 README 声称 L1 三后端、L2 Agent、L3 Hybrid。源码静态可见四函数均有实现：`transpile/run` 走 `QASMParser` +
`BACKENDS[target]()`；Braket 后端优先 `braket.circuits.Circuit` 而非 OpenQASM Program。L2 用
`openai.OpenAI` 直连 `LOOMQ_LLM_*`，带 `verify_qasm` 工具循环，缺环境时走关键词
`_offline_fallback`（Bell/GHZ/「15 比特零排队」）。L3 lexer/parser/codegen 返回「量子操作 dict 列表 +
RISC-V 文本」。

`submission.yaml` 使用自定义键：`team_id: casccjy67`、`team_name: jovian`、
`levels.L1/L2/L3`（大写）、`python_version: ">=3.11"`、`network.L2_agent`、
`llm_config.env_*`。证据 README 仅勾选「工程与产品化」，真机、L2 交互、两个 Bonus 均为未填模板。

### 优点

相对库存模板做了明确包分层（IR、后端抽象基类、Agent、Hybrid），而不是全部堆在 adapter。根 README 给出安装、`python -m
starter_kit.tests.test_transpile` 与 Bell 运行短路径。`BaseBackend._build_result` 统一
little-endian schema。`tests/test_transpile.py` 覆盖 Bell/GHZ/QFT/Grover/Hybrid
解析用例（存在测试，未执行）。契约四文件（yaml、adapter、Dockerfile、starter README）仍在，因此仍是正式提交。

### 质量问题与风险

官方 `evaluator.py` 的 `declared_levels()` 用 `^\s*l1:\s*true\s*$`（忽略大小写）匹配；本 yaml 为 `L1:
true    # 注释`，行尾注释使正则无法锚定到行尾，静态上存在「声明了三级但公开自测读不到」的契约风险。Docker `COPY requirements.txt`
假定构建上下文有该文件，但该文件在快照根而不在 `starter_kit/`，若按官方「在 starter_kit 构建」则复制目标缺失。Dockerfile 基础镜像是
`python:3.10-slim`，yaml 却写 `>=3.11`。

三后端 `run()` 在 SDK 缺失时 `_run_fallback` 返回 **空 counts 且带正式 backend 名**，不是抛错。L2 离线
fallback 按关键词直接吐标准电路，可能绕过真实模型。QASM 与 Hybrid 参数使用 `eval`。`setup.py` 含个人绝对路径与
`shell=True`。L3 量子操作返回 dict 而非典型字符串列表，与公开契约示例形态不一致。

### 完整性 / 可维护性 / 安全性观察

完整性明显偏低：无赛题发布材料、无官方传输层 `llm_client.py`、无能力表 JSON、无 examples、证据无附件、提交字节码缓存。可维护性方面分层是优点，
但导入依赖仓库根路径，且 Python 版本声明与镜像冲突。安全性：未见嵌入 API key；`setup.py` 泄露本机用户路径；`eval` 与空 counts
fallback 是主要风险面。`openai` 直连而非官方 `llm_client.py`，超时/重试无法与组委会传输层对齐。未发现私钥文件。
`test_transpile.py` 用 `print("PASS")` 而非 unittest，评测发现方式不明。

### 关键证据位置

[E-1] `archive/generated/snapshots/casccjy67/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L50 — 自定义键名、大写 L1/L2/L3、Python `>=3.11`、team_id `casccjy67`。
[E-2] `archive/generated/snapshots/casccjy67/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L10-L18 — `sys.path.insert` 后按包导入 transpiler。
[E-3] `archive/generated/snapshots/casccjy67/starter_kit/transpiler/parser.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L143-L157 — 参数解析调用 `eval`。
[E-4] `archive/generated/snapshots/casccjy67/starter_kit/hybrid_compiler/parser.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L110-L113 — Hybrid 参数同样 `eval`。
[E-5] `archive/generated/snapshots/casccjy67/starter_kit/transpiler/braket_backend.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L118-L126 — SDK 缺失时返回空 counts 的 fallback。
[E-6] `archive/generated/snapshots/casccjy67/starter_kit/agent/chat.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L104-L188 — OpenAI 直连 + 无密钥时关键词离线兜底。
[E-7] `archive/generated/snapshots/casccjy67/starter_kit/hybrid_compiler/compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L35 — L3 返回 dict 列表。
[E-8] `archive/generated/snapshots/casccjy67/setup.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L11 — 硬编码本机 Python 路径，`shell=True`。
[E-9] `archive/generated/snapshots/casccjy67/starter_kit/Dockerfile`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L12 — `python:3.10-slim` 且 `COPY requirements.txt`。
[E-10] `archive/generated/snapshots/casccjy67/starter_kit/evaluator.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L182-L186 — 用行锚正则读取 `l1: true`。
[E-11] `archive/generated/snapshots/casccjy67/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L6 — 全部未钉死精确版本。
[E-12] `archive/generated/snapshots/casccjy67/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L10 — 仅勾选工程与产品化。

### 结论置信度

根结构偏离、自定义 yaml、缺失材料、`eval`/fallback/setup.py 路径为 **A**。Docker 构建上下文是否指向仓库根为 **B**。
四函数在隐藏电路/真模型下的行为 **无法静态确认（C）**。仍计入正式 58 人集合。

## 55. `Pennie514`

### 身份与路径

正式 roster 成员 `Pennie514`。快照 `archive/generated/snapshots/Pennie514/`，上游
`https://github.com/Pennie514/LoomQ-2026`，上游 commit
`bf7521ffc221f902b5bbd016ba11fd64b58de058`。事实卡约 73 个文件、28 个 Python、4 个 Web 文件、12
个证据文件、5 个测试文件。根目录含完整赛题材料与 `competition/`。`submission.yaml` 标准三级全开，Python 3.10，L2 需网络。

### 技术栈与结构

核心仍是约 1127 行 `adapter.py`：`_parse_qasm2`、三套 `_transpile_*` / `_run_*`、`agent_chat` 与
`compile_hybrid`。产品层拆出 `loomq_web.py` + `web/{index.html,app.css,app.js}`、
`loomq_cli.py`、`tutor.py`（八章教学数据）、`real_machine.py`、`quantum_riscv_emulator.py` /
`quantum_riscv_isa.md`。另有 `check_originq_chips.py`、`check_spinq_platforms.py`、
`demo_visual.py`、`verify_l2.py`、`verify_hidden_circuits.py`、`test_hybrid_fuzz.py`。

`requirements.txt` 钉死 `spinqit==0.2.4`、`pyqpanda==3.8.5`、`amazon-braket-sdk==1.99.0`。
文档有 `PROJECT_README.md`、`QUICKSTART.md`、`HARDWARE_ACCESS.md`、`HOW_TO_TEST.md`、
`VERIFICATION_GUIDE.md`。Web 为标准库 HTTP，默认 `127.0.0.1:8080`。

### 方案概述

`PROJECT_README.md` 声称一套 QASM 打三平台、Agent 三类任务、真机统一入口。源码静态可见 12 门映射到 Braket OpenQASM 3
原生名（`si`/`cnot`/`cphaseshift`/`ccnot`）与 OriginIR 大写名。`agent_chat` 含预算函数、意图分布与
`_self_verify`：解析失败即拒，并对中文「N 比特」做正则核对，再尝试 spinq/originq 双后端交叉。`compile_hybrid` 在同文件处理
if/else 与寄存器。

教学引擎用「预测→实验→揭示」与真/假纠缠对照；无真机凭证时 `REPLAY_SOURCES` 回放已存证的本源/量旋 JSON。证据勾选全部人工项，申报量旋
`G-260824-0002` 与本源 task `9080D4D192FDF69809FBDFDA9E19DB47`，并书面说明实际 `chip_id=180` 且
`is_amend=True`。`HARDWARE_ACCESS.md` 默认 chip 72 与证据中的 180 并存，作者把它写成「如实说明」而非笔误。配置 JSON
只含平台/shots/host，不含 token。

### 优点

产品文档完整。L2 Web 不只是聊天框，而是有课程结构的 `tutor.py`。真机入口与 adapter 分离，凭证只读 `SPINQ_CLOUD_*` /
`ORIGINQ_API_TOKEN` / AWS 链。证据对芯片编号与读出修正开关做了边界说明，避免把后处理分布写成裸数据。RISC-V Bonus 同时有 ISA
文档、扩展模拟器和 `test_quantum_riscv.py`。三 SDK 版本钉死。UX 五张 PNG 以元数据记录存在。无凭证也可走完课程的设计写在
`tutor.py` 文件头。

### 质量问题与风险

`adapter.py` 仍然过长，教学/真机虽外置，L1/L2/L3 主体仍单文件。`_self_verify` 对「N 比特」做中文正则，语言变化时的行为无法静态确认。
三 SDK 同锁一份 requirements，官方容器能否同时安装无法静态确认。证据 README 写出量旋用户名环境变量示例（账号标识，非密钥）。
`HARDWARE_ACCESS.md` 的 token 为占位中文。Web 一键真机在配置了环境变量后，代码路径将尝试提交硬件任务；本次未执行，是否真实提交无法静态确认。`check_*`
探测脚本未运行。

### 完整性 / 可维护性 / 安全性观察

契约、Dockerfile、赛题材料、证据 JSON/PNG 齐全。可维护性中等：文档好，核心文件大。Web 默认回环。证据
`config_spinq_cloud.json` 含平台 HTTP 主机名，无密码。未见嵌入私钥。截图最大约 337 KiB，仅作存在性记录。
`verify_hidden_circuits.py` / `verify_l2.py` 表明有选手自测入口，未运行。根 `tests/` 仍是官方两份契约测试。

### 关键证据位置

[E-1] `archive/generated/snapshots/Pennie514/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 标准三级声明。
[E-2] `archive/generated/snapshots/Pennie514/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L54 — 文件头声明 L1/L2/L3 与 12 门映射表。
[E-3] `archive/generated/snapshots/Pennie514/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L241-L270 — Braket 本地执行与 little-endian 计数反转。
[E-4] `archive/generated/snapshots/Pennie514/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L340-L340 — `agent_chat` 定义处。
[E-5] `archive/generated/snapshots/Pennie514/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L711-L738 — Agent 自验：解析 + spinq/originq 交叉。
[E-6] `archive/generated/snapshots/Pennie514/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L787-L787 — `compile_hybrid` 定义处。
[E-7] `archive/generated/snapshots/Pennie514/starter_kit/loomq_web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L16-L46 — 文档入口 `127.0.0.1:8080` 与无凭证回放源。
[E-8] `archive/generated/snapshots/Pennie514/starter_kit/loomq_web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L297-L305 — 默认 host `127.0.0.1`。
[E-9] `archive/generated/snapshots/Pennie514/starter_kit/real_machine.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L19-L22 — 凭证环境变量名，注释勿提交。
[E-10] `archive/generated/snapshots/Pennie514/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L8-L74 — 双平台 job 与 chip_id/is_amend 说明。
[E-11] `archive/generated/snapshots/Pennie514/starter_kit/evidence/config_spinq_cloud.json`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L10 — 平台配置无密钥字段。
[E-12] `archive/generated/snapshots/Pennie514/starter_kit/quantum_riscv_isa.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — LQ-Q 扩展规格入口。
[E-13] `archive/generated/snapshots/Pennie514/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L6-L8 — 三 SDK 精确锁定。
[G-1] `archive/generated/snapshots/Pennie514/starter_kit/evidence/files/ux/02-bell-test.png`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=336679；未打开。

### 结论置信度

yaml、模块布局、回环 Web、配置无密钥为 **A**。教学路径与真机「如实说明」为文档+代码互证 **B**。双平台真机主峰、Agent 自验在官方模型下的表现
**无法静态确认（C）**。

## 56. `JunkaiWang-TheoPhy`

### 身份与路径

正式 roster 成员 `JunkaiWang-TheoPhy`。快照
`archive/generated/snapshots/JunkaiWang-TheoPhy/`，上游
`https://github.com/JunkaiWang-TheoPhy/LoomQ-2026`，上游 commit
`e2b168d6bd6b853aa6631a6a5713fa3f0b4a3ca2`。事实卡约 160 个文件、87 个 Python。根目录含赛题材料、
`docs/TECHNICAL_REPORT.md`、`docs/LOOMQ_JUDGE_DECK.pptx`、`project_summary.md`、
`progress.md`。`submission.yaml` 标准三级全开，Python 3.10。

### 技术栈与结构

`adapter.py` 约 109 行，除契约四函数外还暴露 `transpile_with_proof`、`prooftrace`、
`cross_platform_agent`、`trace_hybrid`、`certify_hybrid_paths`、
`verify_hybrid_path_certificate`。实现集中在 `loomq/`：`qasm.py`、`emitters.py`、
`native_ir.py`、`runtime.py`、`simulator.py`、`prooftrace.py`、`semantic_equivalence.py`、
`witness.py`、`assertions.py`、`agent.py`、`prompt_contract.py`、`hybrid.py`、
`hybrid_paths.py`、`quantum_riscv.py`、`story_world.py`、`web.py`。CLI 为 `loomq_cli.py`。
前端在 `web/`（`app.js`、`inquiry.js`、`quantum-guide.js`）。

`starter_kit/requirements.txt` **只有注释、无第三方包**，与 `project_summary.md`「评分路径仅标准库」一致。可选
PyQuafu 交叉验证隔离在开发环境。`circuits/` 除 Bell/GHZ 外还有 Deutsch–Jozsa、Grover-3、QFT-4。测试同时存在于
`starter_kit/tests/` 与根 `tests/`。`verify_submission.py` 试图在抽取后的 starter 根自举。

### 方案概述

架构文档把自然语言 → Agent → 有界 QASM 解析 → 统一 Circuit → 三目标发射/回读/ProofTrace → Web/CLI 串起来，
并声明基础评分不依赖厂商 SDK。源码静态可见 `transpile` 走 `compile_target`，`run` 走
`execute(parse_qasm(...))`。Web 默认 `127.0.0.1:8765`。文档把 ProofTrace 分成三类边界：局部重写恒等式、≤8
qubit 全矩阵重算、native IR round-trip；Witness Chain 用 SHA-256 把 lineage 与反事实首门分歧绑在一起。

L2 声称官方能力表注入模型上下文，失败重试一次后才确定性回退；传输超时配置上限写在架构文。L3 解析赋值/算术/if-else/测量位，输出官方
`li/add/sub/addi/beq/bne/j` 子集。证据勾选全部人工项，申报本源悟空 180 job
`9D182FA1EF76FF3807697CDF69DE7483` 与 SpinQ 截图/JSON/msgpack。40 000 项离线断言与 500 例 L2
campaign 均在文档中标明：无凭据时不得申报为真实 DeepSeek 成绩。

### 优点

标准库核心路径降低容器依赖冲突。证书化把「翻译正确」写成可重算 JSON。Web/CLI 不复制解析逻辑，只调 adapter。
`verify_submission.py` 在 Node 存在时对 `web/app.js` 做 `--check`。科学边界写在
`SCIENTIFIC_CLAIMS_AUDIT.md`。证据有 manifest 与 `scripts/validate_hardware_evidence.py`。
资源上限（字符数、bit 数、稀疏基态、classical 块深度）在架构文中合同化。Story World / 量子导引把新手路径从实验台分开。

### 质量问题与风险

扩展 API 多，评测器若只调四函数，证书路径不会自动跑。`requirements.txt` 为空意味着 L1 `run()` 若内部走纯模拟器则可自洽，若某分支仍
import SDK 则会在干净容器失败——实际执行器无法静态确认。根与 starter 双份测试可能在抽取后丢失根目录用例。L2「500 例」在证据里已被作者降级为
runner/语料完整性，而不是官方分数。启发式 `hardcoded_keyish` 来自文档中的环境变量名，未见密钥值。PPT 裁判卡只记录存在，未打开。

### 完整性 / 可维护性 / 安全性观察

材料完整，测试文件极多，可维护性取决于 `JUDGE_GUIDE.md` / `ARCHITECTURE.md` 索引。Web 默认回环。未见嵌入私钥。截图/JPG
只记元数据。`scripts/quafu_cross_validate.py` 依赖可选第三方，不在正式 requirements 中。
架构文中的每条资源上限是否都在解析前强制执行，未逐行证明。`bonus_evaluator.py` 为 RISC-V Bonus 入口，未运行。

### 关键证据位置

[E-1] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 标准三级声明。
[E-2] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L41-L107 — 契约函数委托 loomq，并保留证书/跨平台入口。
[E-3] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L55 — 端到端流程与模块边界。
[E-4] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L58-L78 — 声称基础路径不依赖 SDK，并列出正确性保护。
[E-5] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L5 — 无第三方依赖行。
[E-6] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/loomq/web.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L626-L633 — 默认 `127.0.0.1:8765`。
[E-7] `archive/generated/snapshots/JunkaiWang-TheoPhy/project_summary.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L26 — 声称评分路径仅标准库，L2 只读 `LOOMQ_LLM_*`。
[E-8] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L40 — 全部人工项与本源 job ID。
[G-1] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/evidence/files/originq-task.jpg`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=80149；未打开。
[G-2] `archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit/evidence/files/counterfactual-desktop.jpg`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=154043；未打开。

### 结论置信度

包结构、空 requirements、扩展 adapter API、回环 Web 为 **A**。「标准库执行三目标」是否在 `runtime.py` 全覆盖为
**B**。证书重算、离线 40 000 项、真机统计 **无法静态确认（C）**。

## 57. `PHTPSN`

### 身份与路径

正式 roster 成员 `PHTPSN`。快照 `archive/generated/snapshots/PHTPSN/`，上游
`https://github.com/PHTPSN/LoomQ-2026`，上游 commit
`91d0cbfe899773f03345dc3e4723f73d0306bf51`。事实卡约 178 个文件、56 个 Python、5 个 Web 文件、47
个证据文件、17 个测试文件。根目录含赛题材料、`DEVELOPMENT.md`、`requirements/` 分后端锁、`scripts/*.ps1`、
`.env.example`。`submission.yaml` 标准三级全开，Python 3.10。

### 技术栈与结构

薄 `adapter.py` 把 L1/L2/L3 分到 `loomq_l1/`、`loomq_l2/`、`loomq_l3/`。L1 使用锁定 Qiskit
解析（`qiskit==2.5.2` 等），再经自己的 subset 验证与 emitters；`run()` 通过 `subprocess` 拉起隔离的
`sdk_worker.py`，解释器来自 `LOOMQ_SPINQ_PYTHON` / `LOOMQ_ORIGINQ_PYTHON` /
`LOOMQ_BRAKET_PYTHON` 或 `.venv-{target}`，Windows 与 POSIX 候选路径不同。L2 含 `agent.py`、
`robustness_eval.py`、`ui_server.py` 与本地 KaTeX vendor。L3 为独立 Hybrid 编译器。`hardware/`
放本源/量旋真机脚本、`Dockerfile.originq` 与独立 Origin 锁。`knowledge/spec/` 归档 gates.json、EBNF、
result schema。另有 `quantum_riscv.py` 与 `quantum_riscv_e2e.py`。

### 方案概述

`SOLUTION_ARCHITECTURE.md` 把问题定义为「一次规范 IR，三家发射 + 隔离执行」，模型只能建议不能绕过解析器。源码静态可见
`transpile` = `emit_target(parse_qasm2(...))`，`run` 校验正整数 shots 后 `run_isolated`；
worker 超时 180 s，stdout 最后一行必须是 JSON，且 counts 总和必须等于 shots。UI 默认 host 经
`_loopback_host` 限制，测试里显式拒绝 `0.0.0.0`。

证据勾选全部人工项，正式真机申报本源与 SpinQ，并另附 `SPINQ_DIAGNOSTICS.md`、跨平台比较 JSON、L2 36 案例鲁棒性报告、量子
RISC-V GPU 目录（Kaggle Tesla P100 声称，属文档）。另给出公网演示 URL，并写明公网为演示模式、不启用本地模拟。`.env.example`
空 token。PowerShell `scripts/setup.ps1` / `start-ui.ps1` 只记录不执行。

### 优点

把「三 SDK 不能同环境」做成一等设计：分 venv、分 lock、worker 进程隔离。知识层把 QASM 子集与翻译方法写成可审查 spec。
提交材料、日志或证据包记录了真机失败的单独诊断，而不是只交一份成功 Bell；上述记录的真实性与运行结果未验证。UI 强制回环。自定义量子指令有 32 位 `custom-0`（opcode `0x0B`）编码模块。仓库测试覆盖 L1
翻译、L2 agent/UI、L3、硬件与 setup workflow。L2 鲁棒性报告自己声明不是官方分数。

### 质量问题与风险

`adapter.run()` 的隔离 worker 依赖评测机上存在对应 Python；若官方容器只有一个解释器，会回退 `sys.executable`，三 SDK
共存问题是否再现无法静态确认。PowerShell 安装脚本未执行。公网 URL 是外部副作用声明，本阶段未访问。`katex.min.js` 被启发式打上 `exec`，
属压缩库误报面，不单独当成漏洞。GPU 证据含 `loomq_gpu_validation.py` 与 `subprocess`，未运行。SpinQ GHZ-3
目录在清单中偏「平台状态」而非完整结果包，是否构成正式第二电路无法静态确认。

### 完整性 / 可维护性 / 安全性观察

完整性高：锁文件、知识 spec、证据分目录、诊断 PNG。可维护性依赖 Windows 脚本与多 venv，Linux 评测路径需 `DEVELOPMENT.md`
中的环境变量覆盖。Web 回环。`.env.example` 无密钥。未见嵌入私钥。媒体最大约 130 KiB PNG，只记元数据。
`scripts/spinq_visitor.py` 等为真机访客脚本，未执行。`hardware/Dockerfile.originq` 表明 Origin
依赖被进一步容器隔离。

### 关键证据位置

[E-1] `archive/generated/snapshots/PHTPSN/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L21 — 标准三级声明。
[E-2] `archive/generated/snapshots/PHTPSN/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L21-L44 — 薄适配；`run()` 校验正整数 shots。
[E-3] `archive/generated/snapshots/PHTPSN/starter_kit/loomq_l1/runner.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L14-L78 — 按目标选择隔离 Python，`subprocess.run` worker，校验 counts 总和。
[E-4] `archive/generated/snapshots/PHTPSN/starter_kit/SOLUTION_ARCHITECTURE.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L12-L68 — 四层解法与「模型不能绕过解析器」边界。
[E-5] `archive/generated/snapshots/PHTPSN/DEVELOPMENT.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L16 — 分 venv 与 `LOOMQ_*_PYTHON` 覆盖。
[E-6] `archive/generated/snapshots/PHTPSN/starter_kit/loomq_l2/ui_server.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L640-L664 — 默认回环 host。
[E-7] `archive/generated/snapshots/PHTPSN/.env.example`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L9 — 空的 LLM/本源 token 字段。
[E-8] `archive/generated/snapshots/PHTPSN/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L9-L35 — 真机、诊断、L2 报告与公网演示声明。
[E-9] `archive/generated/snapshots/PHTPSN/starter_kit/quantum_riscv.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L15 — `custom-0` opcode `0x0B` 编码模块。
[E-10] `archive/generated/snapshots/PHTPSN/starter_kit/loomq_l3/compiler.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L11 — Hybrid-QASM 确定性编译器入口。
[G-1] `archive/generated/snapshots/PHTPSN/starter_kit/evidence/files/originq-bell/originq-bell-task.png`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=130077；未打开。
[G-2] `archive/generated/snapshots/PHTPSN/starter_kit/evidence/files/spinq-diagnostics/spinq-diagnostics-task-list.jpg`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=27636；未打开。

### 结论置信度

分层包、隔离 runner、回环 UI、yaml 为 **A**。官方单容器下 worker 回退行为为 **B**。真机诊断结论、36/36、GPU 数值差
**无法静态确认（C）**。未访问公网演示。

## 58. `3dmove`

### 身份与路径

正式 roster 成员 `3dmove`。Scout：缺少多数发布用办公文档，对象链路完整，不得排除。快照
`archive/generated/snapshots/3dmove/`，上游 `https://github.com/3dmove/LoomQ-2026`，上游
commit `fea9b3129317127d520be4791ba0e5deefa24de1`。事实卡约 44 个文件、15 个 Python、定制度 low。
根目录有 `README.md`（仍是赛题发布包模板，引用并不存在的 PDF/HTML/DOCX/PNG）、`problem_statement.md`、完整
`competition/` 脚本、`report.json`、`requirements_venv311.txt`、`starter_kit/`、`tests/`。
**未见** `LoomQ-赛题.pdf/docx/html` 与提交流程图。

`submission.yaml`：`l1: true`、`l2: true`、**`l3: false`**，Python 3.10，L2 需网络，
`allowed_hosts: ["api.deepseek.com"]`。与 casccjy67 不同，本份仍保留官方 `llm_client.py`、
`evaluator.py`、`examples/` 与根契约测试。

### 技术栈与结构

接近官方 kit 形状：无独立 `loomq/` 包。`adapter.py` 约 535 行，在同一文件内做正则门分解、三后端 `transpile/run`、
`agent_chat`，并带 `__main__` 命令行循环与 ASCII/柱状图辅助函数。额外电路有 `ghz5.qasm`、`grover-3.qasm`、
`QFT-4.qasm`。`requirements.txt` 同时钉了 `antlr4-python3-runtime==4.13.2` 与 `==4.9.2`，且
`qiskit>=1.0.0`、`openai>=1.0.0` 未钉死。`requirements_venv311.txt` 在事实卡中 packages 为空。事实卡
`listen` 命中的是 `LocalSimulator` 字样，不是套接字绑定。

### 方案概述

根 README 仍是组委会发布说明。选手方案主要写在 `adapter.py` 与 evidence README：正则展开 ccz/ccx/swap/相位门后，
Braket 改写成 QASM3（`phaseshift`/`cphaseshift`/`cnot`，`qreg`→`qubit`）；**originq 与 spinq
的 `transpile()` 直接返回分解后的 QASM 2.0**。`run()` 调 Braket
`LocalSimulator(backend="braket_sv")`、pyQPanda `CPUQVM`，以及 spinqit；另有
`remove_measure_statements()` 注释为量旋云不需要 measure。

L2 `agent_chat` 最多两轮，`_verify_qasm` 检查 counts 总和是否等于 1024。`compile_hybrid` 显式
`NotImplementedError("L3 not implemented")`，与 yaml `l3: false` 一致。`__main__` 提供自然语言循环，
检测到 OPENQASM 可询问是否在 Braket 本地跑 1024 shots，并尝试 Qiskit ASCII 图与 matplotlib 柱状图。证据勾选 L1
真机、L2 交互、工程化；L1 申报量旋 job `G-260825-0001/0005`，L2 入口写 `python starter_kit/adapter.py`。
根 `report.json` 是公开自测 4/4 PASS 归档，notice 写明不是官方分数。

### 优点

yaml 对未实现的 L3 标 `false`，与代码占位一致，避免「声明了却 NotImplemented」的契约谎言。保留官方
evaluator/llm_client/Dockerfile/examples。增加若干隐藏形状电路文件。命令行给零基础用户示例提示。真机证据至少有 job ID、时间、
shots 和三张图片文件。公开自测 JSON 带「非官方分数」声明。`competition/` 脚本仍在，根结构虽缺办公文档，但评测入口文件比 casccjy67
更接近模板。

### 质量问题与风险

`transpile("originq")` 静态返回 QASM2 而非 OriginIR 文本，与 `target_ir_contract.md` 的本源目标形态不一致。
Braket 结果 `backend` 字段为 `aws_local_simulator`（非常见 `braket_local_simulator`）。时间戳使用
`isoformat() + "Z"`，在 aware datetime 上可能得到 `...+00:00Z` 非法后缀。
`_apply_gate_decomposition` 基于正则，压缩/换行/多空格 QASM 的稳健性无法静态确认。同一 requirements 写入两个 antlr
版本，安装结果不确定。L2 校验把 shots 写死 1024，与评测常用 8192 不一致。根 README 仍链接缺失的赛题 PDF/流程图。证据「工程化」给出
Windows venv 与 conda 两套环境，说明作者也认为三 SDK 不能共存。

### 完整性 / 可维护性 / 安全性观察

契约四件套存在，但发布材料缺失、无独立架构文档、无 Web UI、测试仅官方两份。可维护性接近库存 kit 加单文件补丁。未见服务监听。未见嵌入密钥。三张真机图仅元数据：
`spinq_cloud_result_0001.png` 85 981 bytes、`0002.png` 69 531 bytes、`运行结果.jpg` 39 060
bytes。`report.json` 的 4/4 不得写成「测试通过」的本阶段结论。未运行 `adapter.py` 交互入口，未安装双 antlr 冲突是否在 pip
层爆发也无法静态确认。

### 关键证据位置

[E-1] `archive/generated/snapshots/3dmove/starter_kit/submission.yaml`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L22 — l1/l2 true、l3 false，允许 `api.deepseek.com`。
[E-2] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L12-L22 — 量旋云去 measure 辅助函数。
[E-3] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L79-L98 — 正则门分解（ccx/swap/相位门）。
[E-4] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L101-L158 — originq/spinq 原样返回 QASM2。
[E-5] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L197-L205 — Braket 结果 backend 名为 `aws_local_simulator`。
[E-6] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L406-L454 — `agent_chat` 两轮重试；`compile_hybrid` 抛 `NotImplementedError`。
[E-7] `archive/generated/snapshots/3dmove/starter_kit/adapter.py`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L457-L472 — `__main__` 命令行欢迎与示例。
[E-8] `archive/generated/snapshots/3dmove/starter_kit/requirements.txt`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L5-L13 — 双 antlr 版本与未钉死的 qiskit/openai。
[E-9] `archive/generated/snapshots/3dmove/starter_kit/evidence/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L11-L80 — 勾选真机/L2/工程；L2 入口为 adapter CLI。
[E-10] `archive/generated/snapshots/3dmove/README.md`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L7-L18 — 模板仍列出本快照根目录并不存在的 PDF/HTML/DOCX/PNG。
[E-11] `archive/generated/snapshots/3dmove/report.json`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980:L1-L8 — 公开自测归档 summary；notice 声明非官方分数。
[G-1] `archive/generated/snapshots/3dmove/starter_kit/evidence/files/spinq_cloud_result_0001.png`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=85981；未打开。
[G-2] `archive/generated/snapshots/3dmove/starter_kit/evidence/files/运行结果.jpg`@998cd4e67b1b29f0f1eb8bafdc155072dfda2980 — type=blob, size=39060；未打开。

### 结论置信度

yaml l3=false 与 `NotImplementedError`、缺失赛题办公文档、originq 仍返回 QASM2 为 **A**。真机图片与 job ID
的对应关系为 **B**（有路径与文档，未核验平台）。转译在隐藏电路上的保真度、CLI Agent、spinq 云去测量路径 **无法静态确认（C）**。未运行选手代码。

---

## 跨项目共性观察

以下观察只描述该 exact SHA 上 58 份 snapshot 的静态分布，不构成排名或质量总分。

### 集合与模板

- 58 份均静态可见 `adapter.py`、`evaluator.py`、`submission.yaml`、Dockerfile 与 starter README（A）。
- 57 份的 `requirements.txt` 位于 starter 目录；`casccjy67` 的 `requirements.txt` 位于 snapshot 根目录，并另有 `setup.py`（A）。
- 目录命名：仅 `infiniteHY` 使用 `starter-kit/`，其余 57 份使用 `starter_kit/`。导航与导入路径不能假设单一名字（A）。
- `casccjy67`、`3dmove` 缺少多数提交中的赛题 PDF/HTML/DOCX/流程图等配套材料，但不构成排除理由（A）。

### 声明层级与实现面

- 多数 `submission.yaml` 将 `levels.l1/l2/l3` 设为 true；少数明确关闭部分层级（例如 `Andante397`、`haiyun919`、`noh1204`、`arwenlinzhaoqing` 声明仅 L1；`CloverLiu03`/`softeight` 声明 L1+L3；`lyl2222`/`alicewangzm`/`3dmove` 声明 L1+L2）。这是配置声明，不是完成度（A 对字段，C 对「做完了没有」）。
- 相对 Andante397 的 starter Python 文件集合，约 44 份出现大量额外模块（Web、agent 包、硬件 runner、测试），约 13 份中等增量，`3dmove` 几乎没有额外 Python 模块。文件数量不等于可运行性（A 对计数，无法静态确认对行为）。

### 技术栈命中

- 58 份文本中均能静态命中量子 SDK 相关标识（Qiskit / Braket / SpinQ / OriginQ 等）以及 OpenAI-compatible / DeepSeek 配置字段或文档。命中表示字符串或 import 可见，不表示真机或模型服务已接通（A 对命中，无法静态确认对调用）。
- Web/UI 实现面分布不均：Flask/FastAPI/Streamlit/React/静态 HTML 都有出现；`mayloveless` 含 TypeScript/React 前端，`BEER7LN` 另有 Remotion/WebGL 相关文件名与大体积 JS/视频 blob。

### 工程与安全（需复核，不是已确认漏洞）

- 几乎所有 snapshot 都能命中 `subprocess`、动态导入、`listen`/`run` 一类服务入口，以及 LLM client。这与 starter kit 和 L2 协议本身有关，不能单独当成选手引入的漏洞。
- Git mode 显示的可执行 Shell（本基线）：`AzureWynn/retry_originq.sh`、`AzureWynn/setup_local.sh`、`Duanice/starter_kit/run_demo.sh`、`cycyotw/loomq.sh`、`jessicaruan6688-byte/start_demo.sh`、`jessicaruan6688-byte/starter_kit/tools/start_l2_web.sh`、`jessicaruan6688-byte/starter_kit/tools/try_originq_bell.sh`。只记录路径，未执行。
- 凭据模式命中主要为：`.env*.example`、文档中的 `export ...="你的 token"` 占位、测试夹具中的假 PEM（如重复字母填充）、以及 runbook 对 PEM/OpenSSH 格式差异的说明。在受检文本规则下未静态确认真实密钥、Cookie 或私钥材料被提交。若后续发现疑似真实凭据，应停止传播并上报。
- 最大可见媒体 blob：`BEER7LN/video.mp4`（35,776,667 bytes）。另有多份 MP4/GIF/PNG。均未打开或播放。

### 证据与测试

- 证据目录从「仅模板 README」到「大量截图/runbook/JSON」不等。证据文件存在不等于结果已验证。
- 测试文件数量跨度很大（2 到 40+）。测试文件存在不等于测试通过。

## 方法局限

- 未运行代码，因此正确性、性能、UX、真机 job、LLM 行为全部无法静态确认。
- 文本扫描会把文档示例、测试夹具、注释中的 `eval(`/`subprocess`/`BEGIN PRIVATE KEY` 算作命中；命中需要人工对照上下文。
- 以 Andante397 的 Python 文件集合作为「接近官方 starter」的对照基线，这是为了描述定制面，不是官方模板哈希证明。
- 未解包 PDF/DOCX，未播放媒体，未跟踪外部 URL，未验证 LFS/gitlink 外部对象（本基线 snapshot 中未静态命中 LFS pointer 文本与 gitlink，这不改变 manifest 的 pointer-only 策略）。
- 本报告不替代评测器，不给出分数或名次。

## 排除清单

无排除项。README 58 行与本报告 58 章一一对应，标识集合相等。
