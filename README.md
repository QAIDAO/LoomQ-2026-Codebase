# LoomQ 2026 submission archive

This repository archives all 58 formal LoomQ 2026 submissions. Each entry records the organizer-supplied GitHub HTTPS URL and an exact 40-character commit SHA in `archive/submissions.json`.

# 优秀选手索引

- **选手：** lil4notfound
- **链接：** [archive/generated/snapshots/lil4notfound/starter_kit](archive/generated/snapshots/lil4notfound/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 用统一 Circuit IR 承接 OpenQASM 解析和三种目标表示生成，运行结果由自建模拟器计算。
    - **L2：** Agent 负责生成候选，本地 parser、模拟器和有限修复流程负责验证与收敛。
    - **L3：** 用独立 model、parser 和 compiler 将 Hybrid-QASM 编译为经典 RISC-V。
    - **Bonus：** 用 encoder、decoder、量子态和 emulator 执行量子机器字，并把测量写回经典控制流。
  - **亮点：**
    1. 通过目标表示回读验证转换前后的电路语义，避免平台代码能够生成但门、参数或操作数已经改变。
    2. 通过模拟候选电路并比较目标分布约束 Agent 输出，避免形式合法但没有完成用户任务的电路进入结果。

---

- **选手：** AphrixZjr
- **链接：** [archive/generated/snapshots/AphrixZjr/starter_kit](archive/generated/snapshots/AphrixZjr/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 以统一电路语义连接解析、目标生成和平台执行。
    - **L2：** 将 Agent 输出建模为待验证提案，并用 circuit revision 管理当前实验版本。
    - **L3：** 采用结构化解析和差分验证保证 Hybrid 编译后的经典控制语义。
    - **Bonus：** 从机器字进入量子执行后端，并以定点格式传递参数门角度。
  - **亮点：**
    1. 通过“提案—验证—确认”的状态边界控制 Agent 修改，避免未经确认的模型输出直接替换有效电路。
    2. 通过 revision 绑定异步请求和实验状态，避免旧响应覆盖用户已经完成的新修改。

---

- **选手：** Duanice
- **链接：** [archive/generated/snapshots/Duanice/starter_kit](archive/generated/snapshots/Duanice/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 用共享电路模型生成目标表示，并通过独立 worker 隔离存在依赖冲突的厂商 SDK。
    - **L2：** 将候选生成、验证、后端选择和结果解释拆成独立组件。
    - **L3：** 分开返回量子操作与经典 RISC-V，使两部分保持明确接口。
    - **Bonus：** 在量子态上执行机器指令，将测量结果写回寄存器并驱动经典分支。
  - **亮点：**
    1. 通过进程隔离、窄 JSON 协议和超时控制 SDK 运行，避免依赖冲突或后端故障拖垮主应用。
    2. 通过任务状态管理和错误脱敏覆盖真机提交全过程，避免把异步硬件调用误作同步执行，也避免凭据进入日志。

---

- **选手：** qianqiu0926
- **链接：** [archive/generated/snapshots/qianqiu0926/starter_kit](archive/generated/snapshots/qianqiu0926/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 用统一 IR 生成三种目标表示，并由本地模拟器计算可验证的概率与采样结果。
    - **L2：** 模型只输出结构化意图，本地工具负责电路构造、语义检查和设备能力筛选。
    - **L3：** 用 Hybrid parser/compiler 和差分用例验证经典控制编译结果。
    - **Bonus：** 实现量子指令编解码、状态演化、测量写回和非法编码检查。
  - **亮点：**
    1. 通过把可计算事实交给确定性工具裁决，避免模型同时扮演生成者和验证者而放过错误结果。
    2. 通过能力表匹配用户约束与设备属性，避免 Agent 凭记忆虚构后端或推荐不具备执行条件的设备。

---

- **选手：** BEER7LN
- **链接：** [archive/generated/snapshots/BEER7LN/starter_kit](archive/generated/snapshots/BEER7LN/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 将解析、目标生成、平台运行和本地参考模拟组织为统一执行入口。
    - **L2：** 课程直接调用 L1 电路与模拟核心，同时生成理论状态和有限采样结果。
    - **L3：** 用独立 Hybrid oracle 和压力用例比较源程序与编译结果。
    - **Bonus：** 用 custom 指令、内置量子态和测量反馈完成量子—经典闭环。
  - **亮点：**
    1. 通过让课程内容、理论结果和实际采样共享同一电路语义，避免教学说明与真实执行相互脱节。
    2. 通过独立解释路径验证编译结果，避免编译器与验证器复用同一逻辑后共同掩盖错误。

---

- **选手：** 2IKK12
- **链接：** [archive/generated/snapshots/2IKK12/starter_kit](archive/generated/snapshots/2IKK12/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 从统一 Circuit 生成三种平台目标表示；目标表示作为转换产物，采样由自建 statevector 模拟统一 Circuit 完成。
    - **L2：** 从多轮历史中识别最近一份能够通过 parser 的电路，并在该状态上继续修改。
    - **L3：** 用紧凑 Hybrid compiler 提取量子操作并生成经典 RISC-V。
    - **Bonus：** 将量子程序编码为机器字，由内置量子态执行测量并反馈经典寄存器。
  - **亮点：**
    1. 通过分离平台代码生成与参考执行，避免把“输出了目标程序”误认为“目标 SDK 已经执行成功”。
    2. 通过只继承经过解析验证的电路状态，避免无效候选污染后续对话和连续修改。

## 分层亮点

- **选手：** PHTPSN
- **链接：** [archive/generated/snapshots/PHTPSN/starter_kit](archive/generated/snapshots/PHTPSN/starter_kit)
- **优秀层级：** L1、L2
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 以共享 IR 生成平台目标表示，通过 SDK worker 运行厂商环境，并单独管理真机任务。
    - **L2：** 本地验证 Agent 候选语义，再依据设备能力和任务约束选择后端。
  - **亮点：**
    1. 通过在提交前检查活动量子位、门集和有向耦合，把语法转换继续推进到设备可执行性，避免不可路由电路进入真机队列。
    2. 通过隔离 SDK 环境并保留任务状态，将平台依赖与业务流程解耦，避免运行环境冲突和异步任务失去追踪。

---

- **选手：** WilderNoTrack
- **链接：** [archive/generated/snapshots/WilderNoTrack/starter_kit](archive/generated/snapshots/WilderNoTrack/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 建立 parser、IR、lowering pass、emitter、runtime 和 result 的完整多后端管线。
    - **L3：** 用独立 AST、源解释器和 RISC-V 生成器处理 Hybrid 经典控制。
    - **Bonus：** 在同一执行循环中维护量子态、执行测量、写回寄存器并驱动经典分支。
  - **亮点：**
    1. 通过按后端归一键类型、位序、宽度和测量映射，避免不同平台返回相同外观却代表不同经典位语义。
    2. 通过记录执行来源、回退原因和原始证据，避免用户把参考模拟结果误认为厂商后端结果。

---

- **选手：** xinruliuresearch-maker
- **链接：** [archive/generated/snapshots/xinruliuresearch-maker/starter_kit](archive/generated/snapshots/xinruliuresearch-maker/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 将词法、解析、规范化、目标序列化和结果归一分层，运行参考来自统一的本地模拟器。
    - **L3：** 用 AST、寄存器分配器、compiler 和独立解释器完成 Hybrid 编译与差分验证。
    - **Bonus：** 将 ISA、statevector 和 emulator 分层，并比较源助记符路径与二进制执行路径。
  - **亮点：**
    1. 通过显式保留测量寄存器、隔离临时寄存器并生成唯一标签，避免变量覆盖测量值或嵌套控制流跳转错位。
    2. 通过源语义、目标汇编和机器字执行之间的独立差分，避免单一路径内部自洽却整体语义错误。

---

- **选手：** jessicaruan6688-byte
- **链接：** [archive/generated/snapshots/jessicaruan6688-byte/starter_kit](archive/generated/snapshots/jessicaruan6688-byte/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 用共享 Circuit 生成目标表示，在当前进程调用三套厂商 SDK，并由独立 result 层整理返回值。
    - **L3：** 以紧凑 parser/compiler 生成经典控制代码，并验证嵌套结构和寄存器终态。
    - **Bonus：** 从机器字驱动内置量子态，完成测量写回和经典反馈。
  - **亮点：**
    1. 通过按 SDK 契约和测量映射分别投影结果，避免统一翻转 bitstring 造成静默的经典位错位。
    2. 通过隔离公共电路语义、平台 emitter 和结果归一，避免目标语法差异反向污染源 Circuit。

---

- **选手：** mayloveless
- **链接：** [archive/generated/snapshots/mayloveless/starter_kit](archive/generated/snapshots/mayloveless/starter_kit)
- **优秀层级：** L1、L3
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 分别建模 IR、解析、测量映射和结果协议，并以隔离运行路径处理平台依赖。
    - **L3：** 用独立 oracle、差分验证和资源边界检查验证 Hybrid 编译结果。
  - **亮点：**
    1. 通过让目标裁决路径独立于候选实现，避免编译器和验证器携带同一缺陷后互相证明正确。
    2. 通过显式区分外部测量注入与内部量子态执行，避免把接口/控制闭环误报为完整 Bonus 量子闭环。

---

- **选手：** 0Dionysus0
- **链接：** [archive/generated/snapshots/0Dionysus0/starter_kit](archive/generated/snapshots/0Dionysus0/starter_kit)
- **优秀层级：** L1
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 用共享 QASM 解析与 Circuit IR 统一三种目标表示和执行入口。
  - **亮点：**
    1. 通过让查询进入实际电路执行，避免黑盒交互退化为读取预设答案，并使转换结果与实验行为保持同一语义来源。
    2. 通过将失败状态直接返回而非伪造成功结果，避免平台异常被静默掩盖。

---

- **选手：** JunkaiWang-TheoPhy
- **链接：** [archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit](archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L1：** 将解析、共享电路、目标 emitter 和本地执行分层，并对目标表示执行整电路回读。
    - **L3：** 在 Hybrid 编译之外保留控制路径和执行 trace。
    - **Bonus：** 从量子机器字进入解码执行，维护量子态、测量结果和机器轨迹。
  - **亮点：**
    1. 通过可重算证书关联转换输入、输出和验证依据，避免目标程序只有生成结果而缺乏可审计证据。
    2. 通过明确区分结构证据、语义证据和运行证据，避免单一检查被夸大为对整体正确性的证明。

---

- **选手：** talk2joan
- **链接：** [archive/generated/snapshots/talk2joan/starter_kit](archive/generated/snapshots/talk2joan/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：**
    - **L2：** 用本地 lint、参考模拟和候选自检约束 Agent，并以浏览器量子模拟器计算关卡结果。
  - **亮点：**
    1. 通过让目标、用户操作和计算分布共同决定完成状态，避免游戏化与实际量子语义脱节。
    2. 通过保留失败后的电路与结果反馈，避免用户失去诊断依据而只能重新开始。

---

- **选手：** zmath01
- **链接：** [archive/generated/snapshots/zmath01/starter_kit](archive/generated/snapshots/zmath01/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：**
    - **L2：** 将当前编辑器内容作为每次运行的直接输入，并把已完成运行的结果证据单独保存。
  - **亮点：**
    1. 通过分离当前电路状态与历史结果状态，避免编辑器已经改变却仍运行缓存中的旧电路。
    2. 通过绑定 counts、目标表示和解释保留结果来源，避免后续运行覆盖此前证据；历史未保存 QASM，因此不将其表述为完整实验快照。

---

- **选手：** Pennie514
- **链接：** [archive/generated/snapshots/Pennie514/starter_kit](archive/generated/snapshots/Pennie514/starter_kit)
- **优秀层级：** L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：**
    - **L2：** 将预测、执行结果和解释组织为连续学习过程，并在本地验证 Agent 候选。
    - **L3：** 用随机生成的 Hybrid 程序比较源语义与目标执行终态。
    - **Bonus：** 实现量子指令编码、状态演化、测量写回和经典分支反馈。
  - **亮点：**
    1. 通过在结果出现前固定用户判断，使实验反馈能够暴露真实理解偏差，避免事后合理化。
    2. 通过随机组合控制结构扩展差分覆盖，避免固定测试样例漏掉寄存器与标签错误。

---

- **选手：** WayneYu1212
- **链接：** [archive/generated/snapshots/WayneYu1212/starter_kit](archive/generated/snapshots/WayneYu1212/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：**
    - **L2：** 将模型输出解析为结构化 AgentPlan，由本地 verifier 检查电路和后端约束，再渐进展示结果与证据。
  - **亮点：**
    1. 通过把结果现象、解释和代码证据按认知顺序展开，避免新手在理解实验前先被底层细节淹没。
    2. 通过键盘导航、读屏状态播报和减少动画支持，避免交互方式成为理解实验的额外障碍。

## License

The repository-maintained tooling and documentation are licensed under the [Apache License 2.0](LICENSE).

Archived contestant submissions and preserved Git objects under `archive/generated/` are excluded from that grant. They remain subject to the copyright and license terms of their upstream authors; inclusion in this archive does not relicense them.

## Exactness proof

`archive/generated/snapshots/<contestant_id>/` is the exact root Git tree from the recorded upstream commit. The sync tool grafts that tree object into this repository. It does not copy a checkout, run `git archive`, or rebuild the tree from files.

`archive/generated/commit-objects/<contestant_id>.obj` stores the canonical commit object bytes, including the Git object header. Offline verification proves both conditions for every submission:

```text
sha1(canonical commit object bytes) == manifest commit SHA
commit root tree OID == archived snapshot subtree OID
```

Verification also rejects missing or extra contestant paths and commit records.

## Update and verify the archive

Run these commands from the repository:

```sh
python3 tools/loomq_archive.py sync
python3 tools/loomq_archive.py verify --staged
git commit
python3 tools/loomq_archive.py verify
python3 tools/loomq_archive.py verify --remote
```

`sync` fetches only each exact SHA over HTTPS. It validates all 58 manifest rows before the first fetch. It builds the complete result in isolated bare repositories. After every submission passes, it replaces the generated worktree and stages `archive/submissions.json` with the complete generated archive. A second `sync` with unchanged inputs produces no staged or unstaged diff.

Edit only `archive/submissions.json` to change the roster. The sync tool owns all files under `archive/generated/` and removes stale generated paths.

## Untrusted content and external objects

All submission contents are untrusted. Do not run scripts, builds, package managers, tests, hooks, or discovery tools under `archive/generated/snapshots/`. The archive workflow and CI only read Git objects and file metadata.

The manifest uses the `pointer-only` policy for Git LFS pointers and gitlinks. Git LFS pointer files remain exact pointer blobs. Their external payloads are not part of this archive. Gitlinks retain the submitted commit OID, but nested repository contents are not part of this archive.

The tool preserves executable modes and symlink targets. It rejects paths that cannot be safely materialized, including `.git` components, prefix collisions, and case or Unicode-normalization collisions.

## Contestant code navigation

The table below lists every formal contestant on baseline `998cd4e67b1b29f0f1eb8bafdc155072dfda2980`. The roster is exactly the 58 unique `contestant_id` values in `archive/submissions.json`. There are no extra, missing, empty, or unreadable snapshot directories on this baseline.

Each directory link is a repository-relative path and opens the archived snapshot on GitHub. Stack and entry columns are static identifications (filenames, dependencies, and source features). They do not mean the submission runs, scores, or talks to real hardware.

Path note: `infiniteHY` uses `starter-kit/` (hyphen). The other 57 snapshots use `starter_kit/` (underscore). Do not hard-code a single starter directory name.

Excluded / duplicate / empty directories: none on this baseline.

| # | Contestant | Snapshot | Static stack | Static entry candidates |
|---:|---|---|---|---|
| 1 | `infiniteHY` | [archive/generated/snapshots/infiniteHY/](archive/generated/snapshots/infiniteHY/) | Python, quantum SDK | `starter-kit/agent.py`; baseline `starter-kit/{adapter.py,evaluator.py}` |
| 2 | `savannahyuan17-afk` | [archive/generated/snapshots/savannahyuan17-afk/](archive/generated/snapshots/savannahyuan17-afk/) | Python, quantum SDK | `starter_kit/agent.py` |
| 3 | `cycyotw` | [archive/generated/snapshots/cycyotw/](archive/generated/snapshots/cycyotw/) | Python, Shell, quantum SDK | `loomq.sh`; `starter_kit/loomq/agent.py` |
| 4 | `everest-an` | [archive/generated/snapshots/everest-an/](archive/generated/snapshots/everest-an/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 5 | `Muhongfan` | [archive/generated/snapshots/Muhongfan/](archive/generated/snapshots/Muhongfan/) | Python, quantum SDK | `starter_kit/l2_agent.py`; `starter_kit/runner.py` |
| 6 | `WilderNoTrack` | [archive/generated/snapshots/WilderNoTrack/](archive/generated/snapshots/WilderNoTrack/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/cli.py`; `starter_kit/loomq/web/server.py` |
| 7 | `AphrixZjr` | [archive/generated/snapshots/AphrixZjr/](archive/generated/snapshots/AphrixZjr/) | Python, HTML/JS, quantum SDK | `starter_kit/web/server.py`; `starter_kit/web/static/index.html` |
| 8 | `lyl2222` | [archive/generated/snapshots/lyl2222/](archive/generated/snapshots/lyl2222/) | Python, HTML/JS, quantum SDK | `starter_kit/web_app.py`; `starter_kit/loomq/agent.py` |
| 9 | `Jimmy658` | [archive/generated/snapshots/Jimmy658/](archive/generated/snapshots/Jimmy658/) | Python, quantum SDK | `starter_kit/l2_agent.py` |
| 10 | `tale03` | [archive/generated/snapshots/tale03/](archive/generated/snapshots/tale03/) | Python, Flask, HTML, quantum SDK | `starter_kit/app.py` |
| 11 | `AzureWynn` | [archive/generated/snapshots/AzureWynn/](archive/generated/snapshots/AzureWynn/) | Python, Shell, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 12 | `hongwei-2026` | [archive/generated/snapshots/hongwei-2026/](archive/generated/snapshots/hongwei-2026/) | Python, quantum SDK | `starter_kit/loomq_agent.py` |
| 13 | `zhangxinyang-z` | [archive/generated/snapshots/zhangxinyang-z/](archive/generated/snapshots/zhangxinyang-z/) | Python, quantum SDK | `starter_kit/chat.py` |
| 14 | `xinruliuresearch-maker` | [archive/generated/snapshots/xinruliuresearch-maker/](archive/generated/snapshots/xinruliuresearch-maker/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/ui/server.py`; `starter_kit/loomq/bonus/demo.py` |
| 15 | `EndlessTR` | [archive/generated/snapshots/EndlessTR/](archive/generated/snapshots/EndlessTR/) | Python, HTML/JS, quantum SDK | `starter_kit/quantumhelper_web/server.py` |
| 16 | `2IKK12` | [archive/generated/snapshots/2IKK12/](archive/generated/snapshots/2IKK12/) | Python, HTML/JS, quantum SDK | `starter_kit/web_app.py`; `starter_kit/loomq_agent.py` |
| 17 | `mayloveless` | [archive/generated/snapshots/mayloveless/](archive/generated/snapshots/mayloveless/) | Python, React/TypeScript, quantum SDK | `starter_kit/web/src/main.tsx`; `starter_kit/loomq/l2_agent.py` |
| 18 | `0Dionysus0` | [archive/generated/snapshots/0Dionysus0/](archive/generated/snapshots/0Dionysus0/) | Python, HTML/JS, quantum SDK | `starter_kit/web_chat.py`; `starter_kit/loomq_l2/cli.py` |
| 19 | `Huxingyu` | [archive/generated/snapshots/Huxingyu/](archive/generated/snapshots/Huxingyu/) | Python, quantum SDK | `starter_kit/loomq_cli.py` |
| 20 | `haiyun919` | [archive/generated/snapshots/haiyun919/](archive/generated/snapshots/haiyun919/) | Python, quantum SDK | `starter_kit/evaluator.py`; backends in `starter_kit/backends/` |
| 21 | `arw131072` | [archive/generated/snapshots/arw131072/](archive/generated/snapshots/arw131072/) | Python, Flask, quantum SDK | `starter_kit/l2_web_flask.py` |
| 22 | `yiyuanrvk77` | [archive/generated/snapshots/yiyuanrvk77/](archive/generated/snapshots/yiyuanrvk77/) | Python, HTML/CSS, quantum SDK | `starter_kit/agent.py`; `starter_kit/visualizations/index.html` |
| 23 | `UokyI` | [archive/generated/snapshots/UokyI/](archive/generated/snapshots/UokyI/) | Python, quantum SDK | `starter_kit/run_wukong.py` |
| 24 | `orange-city` | [archive/generated/snapshots/orange-city/](archive/generated/snapshots/orange-city/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 25 | `noh1204` | [archive/generated/snapshots/noh1204/](archive/generated/snapshots/noh1204/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 26 | `BEER7LN` | [archive/generated/snapshots/BEER7LN/](archive/generated/snapshots/BEER7LN/) | Python, HTML/JS, Node/Remotion/WebGL, quantum SDK | `start.ps1`; `starter_kit/web/index.html` |
| 27 | `zhangsiyue343-hub` | [archive/generated/snapshots/zhangsiyue343-hub/](archive/generated/snapshots/zhangsiyue343-hub/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/runner.py` |
| 28 | `elenawia` | [archive/generated/snapshots/elenawia/](archive/generated/snapshots/elenawia/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/web/server.py` |
| 29 | `talk2joan` | [archive/generated/snapshots/talk2joan/](archive/generated/snapshots/talk2joan/) | Python, HTML/JS, quantum SDK | `starter_kit/webapp.py` |
| 30 | `33ClayLesley` | [archive/generated/snapshots/33ClayLesley/](archive/generated/snapshots/33ClayLesley/) | Python, Streamlit, quantum SDK | `starter_kit/web/app.py` |
| 31 | `alicewangzm` | [archive/generated/snapshots/alicewangzm/](archive/generated/snapshots/alicewangzm/) | Python, HTML, quantum SDK | `starter_kit/loomq/webapp.py`; `starter_kit/loomq/agent.py` |
| 32 | `qianqiu0926` | [archive/generated/snapshots/qianqiu0926/](archive/generated/snapshots/qianqiu0926/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/cli.py`; `starter_kit/loomq/agent.py` |
| 33 | `Yolanlanlanda` | [archive/generated/snapshots/Yolanlanlanda/](archive/generated/snapshots/Yolanlanlanda/) | Python, quantum SDK | `starter_kit/interactive.py` |
| 34 | `Andante397` | [archive/generated/snapshots/Andante397/](archive/generated/snapshots/Andante397/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 35 | `iiixiscientia` | [archive/generated/snapshots/iiixiscientia/](archive/generated/snapshots/iiixiscientia/) | Python, quantum SDK | `starter_kit/web_app.py`; `starter_kit/src/agent/agent.py` |
| 36 | `LinXuan2576` | [archive/generated/snapshots/LinXuan2576/](archive/generated/snapshots/LinXuan2576/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/l2_agent.py` |
| 37 | `CloverLiu03` | [archive/generated/snapshots/CloverLiu03/](archive/generated/snapshots/CloverLiu03/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 38 | `arwenlinzhaoqing` | [archive/generated/snapshots/arwenlinzhaoqing/](archive/generated/snapshots/arwenlinzhaoqing/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 39 | `softeight` | [archive/generated/snapshots/softeight/](archive/generated/snapshots/softeight/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 40 | `zhaoqianyuan24` | [archive/generated/snapshots/zhaoqianyuan24/](archive/generated/snapshots/zhaoqianyuan24/) | Python, HTML/JS, quantum SDK | `starter_kit/l2/agent.py`; `starter_kit/frontend/index.html` |
| 41 | `jessicaruan6688-byte` | [archive/generated/snapshots/jessicaruan6688-byte/](archive/generated/snapshots/jessicaruan6688-byte/) | Python, HTML/JS, Shell, quantum SDK | `start_demo.sh`; `starter_kit/web/server.py` |
| 42 | `wronps` | [archive/generated/snapshots/wronps/](archive/generated/snapshots/wronps/) | Python, HTML, quantum SDK | `starter_kit/tools/run_hardware.py`; `starter_kit/tools/web/index.html` |
| 43 | `lil4notfound` | [archive/generated/snapshots/lil4notfound/](archive/generated/snapshots/lil4notfound/) | Python, HTML/JS, quantum SDK | `starter_kit/run_local.py`; `starter_kit/loomq_app/server.py` |
| 44 | `xueerlin20-stack` | [archive/generated/snapshots/xueerlin20-stack/](archive/generated/snapshots/xueerlin20-stack/) | Python, HTML/JS, quantum SDK | `starter_kit/run_l2.py`; `starter_kit/web_app.py` |
| 45 | `qwer-asdftg` | [archive/generated/snapshots/qwer-asdftg/](archive/generated/snapshots/qwer-asdftg/) | Python, PowerShell, quantum SDK | `starter_kit/l2_cli.py` |
| 46 | `LouisYye` | [archive/generated/snapshots/LouisYye/](archive/generated/snapshots/LouisYye/) | Python, quantum SDK | `starter_kit/l2_cli.py`; `starter_kit/l2_agent.py` |
| 47 | `betsywbx` | [archive/generated/snapshots/betsywbx/](archive/generated/snapshots/betsywbx/) | Python, Flask, HTML, quantum SDK | `starter_kit/app.py` |
| 48 | `zmath01` | [archive/generated/snapshots/zmath01/](archive/generated/snapshots/zmath01/) | Python, HTML, Shell, quantum SDK | `run.sh`; `starter_kit/webui/index.html` |
| 49 | `BH2-4` | [archive/generated/snapshots/BH2-4/](archive/generated/snapshots/BH2-4/) | Python, quantum SDK | `starter_kit/chat.py` |
| 50 | `Duanice` | [archive/generated/snapshots/Duanice/](archive/generated/snapshots/Duanice/) | Python, HTML, Shell, quantum SDK | `starter_kit/run_demo.sh`; `starter_kit/agent/server.py` |
| 51 | `danjituya` | [archive/generated/snapshots/danjituya/](archive/generated/snapshots/danjituya/) | Python, Flask, quantum SDK | `starter_kit/cli.py`; `starter_kit/webapp.py` |
| 52 | `WayneYu1212` | [archive/generated/snapshots/WayneYu1212/](archive/generated/snapshots/WayneYu1212/) | Python, HTML/JS, Shell/PowerShell, quantum SDK | `starter_kit/loomq/web/server.py` |
| 53 | `HpIahtcthocw` | [archive/generated/snapshots/HpIahtcthocw/](archive/generated/snapshots/HpIahtcthocw/) | Python, Flask/FastAPI, HTML/JS, quantum SDK | `start.sh`; `starter_kit/loomq/cli.py` |
| 54 | `casccjy67` | [archive/generated/snapshots/casccjy67/](archive/generated/snapshots/casccjy67/) | Python, setuptools, quantum SDK | `starter_kit/agent/chat.py`; baseline `starter_kit/evaluator.py` |
| 55 | `Pennie514` | [archive/generated/snapshots/Pennie514/](archive/generated/snapshots/Pennie514/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq_web.py`; `starter_kit/loomq_cli.py` |
| 56 | `JunkaiWang-TheoPhy` | [archive/generated/snapshots/JunkaiWang-TheoPhy/](archive/generated/snapshots/JunkaiWang-TheoPhy/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/agent.py`; `starter_kit/web/index.html` |
| 57 | `PHTPSN` | [archive/generated/snapshots/PHTPSN/](archive/generated/snapshots/PHTPSN/) | Python, HTML/JS, PowerShell, quantum SDK | `starter_kit/loomq_l2/agent.py`; `starter_kit/loomq_l2/ui/index.html` |
| 58 | `3dmove` | [archive/generated/snapshots/3dmove/](archive/generated/snapshots/3dmove/) | Python, quantum SDK | `starter_kit/evaluator.py` |
