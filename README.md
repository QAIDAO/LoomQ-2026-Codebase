# LoomQ 2026 submission archive

This repository archives all 58 formal LoomQ 2026 submissions. Each entry records the organizer-supplied GitHub HTTPS URL and an exact 40-character commit SHA in `archive/submissions.json`.

# 优秀选手索引

- **选手：** lil4notfound
- **链接：** [archive/generated/snapshots/lil4notfound/starter_kit](archive/generated/snapshots/lil4notfound/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 以强类型 Circuit 统一解析、三平台目标生成和自建模拟执行，Agent、Hybrid 编译与量子 RISC-V 复用同一语义基础。
  - **亮点 1：** 目标程序生成后重新解析并比较门、参数和操作数，避免控制位与目标位交换后仍被当作正确转换
  - **亮点 2：** Agent 候选会被实际模拟并与目标分布比较，避免“语法正确但任务做错”的电路进入结果。

---

- **选手：** AphrixZjr
- **链接：** [archive/generated/snapshots/AphrixZjr/starter_kit](archive/generated/snapshots/AphrixZjr/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 以共享语义基座连接多平台转换、结构化 Agent 提案、Hybrid 编译和量子指令执行。
  - **亮点 1：** Agent 修改先形成提案，用户确认后才写入当前实验，避免模型输出直接覆盖有效电路
  - **亮点 2：** 前端用 circuit revision 绑定异步请求，避免旧响应晚到后覆盖用户刚完成的新编辑。

---

- **选手：** Duanice
- **链接：** [archive/generated/snapshots/Duanice/starter_kit](archive/generated/snapshots/Duanice/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 通过独立 worker 隔离不同厂商 SDK，并把真机提交、轮询、终态和结果提取建模为完整任务生命周期。
  - **亮点 1：** 主进程与 SDK 只通过窄 JSON 接口通信，并设置超时，避免依赖冲突或子进程卡死拖垮整个应用
  - **亮点 2：** 对错误、日志和任务证据做脱敏，避免真机凭据因调试信息外泄。

---

- **选手：** qianqiu0926
- **链接：** [archive/generated/snapshots/qianqiu0926/starter_kit](archive/generated/snapshots/qianqiu0926/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 模型只输出结构化计划，常见电路构造、精确概率计算、目标回读和设备筛选由本地工具完成。
  - **亮点 1：** 用本地构造器和概率验证裁决候选，避免 Agent 返回能够解析但不符合用户目标的电路
  - **亮点 2：** 用设备能力表做约束交集，避免模型凭记忆虚构后端或推荐不满足门集要求的设备。

---

- **选手：** BEER7LN
- **链接：** [archive/generated/snapshots/BEER7LN/starter_kit](archive/generated/snapshots/BEER7LN/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 课程讲解、理论态和有限 shots 采样共用同一份 QASM；Hybrid 另用独立 oracle 与 stress 用例验证。
  - **亮点 1：** 理论概率与实际采样来自同一电路，避免教材展示的电路和按钮实际运行的程序不一致
  - **亮点 2：** oracle 不复用编译器生成的 RISC-V，避免编译器和验证器复制同一错误后互相证明正确。

---

- **选手：** 2IKK12
- **链接：** [archive/generated/snapshots/2IKK12/starter_kit](archive/generated/snapshots/2IKK12/starter_kit)
- **优秀层级：** L1、L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 三种目标程序统一交给自建 statevector 执行，多轮对话则从历史中恢复最近一份可解析 QASM。
  - **亮点 1：** 倒序寻找“最近有效电路”而不是最近代码块，避免解析失败的模型候选污染下一轮修改
  - **亮点 2：** 对 GHZ 扩展等明确任务采用确定性结构变换，避免重新生成后得到主题相近但并非同一实验的电路。

## 分层亮点

- **选手：** PHTPSN
- **链接：** [archive/generated/snapshots/PHTPSN/starter_kit](archive/generated/snapshots/PHTPSN/starter_kit)
- **优秀层级：** L1、L2
- **技术方案与亮点：**
  - **技术方案：** 用共享 IR、SDK worker 和真机前置检查连接多平台目标生成与执行。
  - **亮点 1：** 提交前检查活动量子位、门集和有向耦合，避免本地可表示的电路在真实设备上无法路由或执行
  - **亮点 2：** 将本地模拟与真机任务分开处理，避免把排队中的硬件任务误当作同步调用。

---

- **选手：** WilderNoTrack
- **链接：** [archive/generated/snapshots/WilderNoTrack/starter_kit](archive/generated/snapshots/WilderNoTrack/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 采用 parser→IR→pass→emitter→runtime→result 的分层管线，并为 Hybrid 配置 AST、源解释器和量子指令模拟器。
  - **亮点 1：** 按后端处理键类型、位序和宽度，避免不同 SDK 的 counts 被错误解释为同一经典位顺序
  - **亮点 2：** 记录执行来源和回退原因，避免用户把参考模拟结果误认为厂商后端的真实返回。

---

- **选手：** xinruliuresearch-maker
- **链接：** [archive/generated/snapshots/xinruliuresearch-maker/starter_kit](archive/generated/snapshots/xinruliuresearch-maker/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** L1 使用 lexer/parser/normalize/serialize 分层；Hybrid 使用 AST、寄存器分配器、compiler 和独立解释器。
  - **亮点 1：** 显式保留测量寄存器并隔离临时寄存器，避免用户变量覆盖量子测量结果
  - **亮点 2：** 用唯一标签和源程序/目标程序差分，避免嵌套分支跳错位置却只因汇编文本合理而漏检。

---

- **选手：** jessicaruan6688-byte
- **链接：** [archive/generated/snapshots/jessicaruan6688-byte/starter_kit](archive/generated/snapshots/jessicaruan6688-byte/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 在当前进程调用三套厂商 SDK，并按测量映射把各 SDK 的原始结果投影到统一经典位。
  - **亮点 1：** 为不同后端分别处理 bitstring 契约，避免统一反转字符串造成 counts 含义静默错位
  - **亮点 2：** 将 parser、Circuit、backend 和 result 分层，避免目标语法差异渗入公共电路语义。

---

- **选手：** mayloveless
- **链接：** [archive/generated/snapshots/mayloveless/starter_kit](archive/generated/snapshots/mayloveless/starter_kit)
- **优秀层级：** L1、L3
- **技术方案与亮点：**
  - **技术方案：** 分别建模解析、测量映射和结果协议，并以独立 oracle 对照 Hybrid 源语义与目标终态。
  - **亮点 1：** 验证路径不复用候选实现，避免编译器和验证器带着同一错误互相证明正确
  - **亮点 2：** Bonus 虽有机器字、写回和经典分支，但测量由外部预置位注入；明确标为接口/控制闭环，避免误称完整量子态闭环。

---

- **选手：** 0Dionysus0
- **链接：** [archive/generated/snapshots/0Dionysus0/starter_kit](archive/generated/snapshots/0Dionysus0/starter_kit)
- **优秀层级：** L1
- **技术方案与亮点：**
  - **技术方案：** 用共享 QASM/IR 统一三种目标转换，并在教学演示中让隐藏 oracle 查询经过实际执行。
  - **亮点 1：** 黑盒内容不会随前端资源直接暴露，避免挑战退化为读取常量答案
  - **亮点 2：** 执行异常会明确呈现为失败，避免用预设结果或静默回退制造成功假象。

---

- **选手：** JunkaiWang-TheoPhy
- **链接：** [archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit](archive/generated/snapshots/JunkaiWang-TheoPhy/starter_kit)
- **优秀层级：** L1、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 对生成的目标程序做整电路回读，并为转换生成可重算证书和执行轨迹。
  - **亮点 1：** 回读后比较门、参数和操作数，避免目标文本能够生成却已经改变源电路语义
  - **亮点 2：** 证书同时记录依据和证明边界，避免只有结论而无法判断证据究竟证明了什么。

---

- **选手：** talk2joan
- **链接：** [archive/generated/snapshots/talk2joan/starter_kit](archive/generated/snapshots/talk2joan/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：** 用本地 lint、参考模拟和候选自检约束 Agent，再以浏览器模拟器按目标概率判定关卡。
  - **亮点 1：** 通关由用户门序产生的概率分布决定，避免游戏化退化为点击次数或预设奖励
  - **亮点 2：** 失败后保留当前门序和计算分布，避免用户被重置后看不到目标与结果的差距。

---

- **选手：** zmath01
- **链接：** [archive/generated/snapshots/zmath01/starter_kit](archive/generated/snapshots/zmath01/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：** 后端每次直接读取当前编辑器的 QASM，同时把旧 counts、目标表示和解释保留为历史证据。
  - **亮点 1：** 当前请求文本直接决定下一次运行，避免编辑器已经改变却仍执行缓存电路
  - **亮点 2：** 历史记录绑定结果、目标表示和解释，避免下一次运行覆盖此前的结果来源；但未保存 QASM，不视为完整实验快照。

---

- **选手：** Pennie514
- **链接：** [archive/generated/snapshots/Pennie514/starter_kit](archive/generated/snapshots/Pennie514/starter_kit)
- **优秀层级：** L2、L3（含 Bonus）
- **技术方案与亮点：**
  - **技术方案：** 教学采用“先预测、再观察、后解释”，Hybrid 则用随机用例比较源程序与目标程序终态。
  - **亮点 1：** 先固定用户预测再展示实验结果，避免事后产生“本来就知道”的认知错觉
  - **亮点 2：** 随机生成嵌套分支、负数和连续赋值，避免固定样例漏掉标签或寄存器错误。

---

- **选手：** WayneYu1212
- **链接：** [archive/generated/snapshots/WayneYu1212/starter_kit](archive/generated/snapshots/WayneYu1212/starter_kit)
- **优秀层级：** L2
- **技术方案与亮点：**
  - **技术方案：** 用结构化 AgentPlan 和本地 verifier 约束模型输出，界面按“现象—解释—代码证据”渐进展示。
  - **亮点 1：** 本地 verifier 在结果展示前检查 QASM 和后端约束，避免模型生成的设备名或不可执行代码直接进入实验
  - **亮点 2：** 通过键盘导航、读屏播报和减少动画支持，避免新手因信息过载或访问障碍无法理解运行状态。

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
