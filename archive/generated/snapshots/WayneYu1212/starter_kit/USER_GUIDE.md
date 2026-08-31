# 第一次 LoomQ 实验

这份指南不要求任何量子计算背景。先看懂页面要带你做什么，再在五分钟内跑出一份结果，最后把自己的问题交给 Agent。

## 5 分钟跑完第一次实验

1. 按 `README.md` 的命令完成安装并启动 Web 服务。
2. 打开 `http://127.0.0.1:8765/`，先看页面承诺：**不懂量子也可以。先跑一次，再看发生了什么。**
3. 先看 `00` 与 `11` 为什么会占大多数，再读 **开始前，先认四件事**，认识量子计算、量子比特、Bell 实验和 `|0⟩` / `H` / `CNOT` / `M`。
4. 通过 H、CNOT 和整条电路检查器，先理解一个量子比特，再理解控制位与目标位。
5. 点击 **重做刚才的 Bell 实验**，载入已经讲过的 Bell 电路；第一次体验不需要模型 Key。
6. 选择任意一个可用的本地后端，点击 **执行这个实验**，再查看 counts、解释、电路和 OpenQASM。
7. 经过归档硬件桥接后，再到 **现在，把你的问题说成人话就行。**；这里的 Agent 是产品入口，但连接模型仍是可选进阶功能。

不要把 `loomq/web/static/index.html` 当作 `file://` 页面打开；静态页面无法连接 Python SDK 服务。若误开，LoomQ 会给出正确的启动地址，不会把它误报为模型 Key 问题。

这条 Bell 路径不需要模型 Key。自由输入的 Agent 任务才使用服务端提供的 `LOOMQ_LLM_*`；浏览器不要求初学者粘贴 Key，也不会把密钥写入 LocalStorage。

## Windows 本地服务

从当前仓库启动 Web 的唯一必要命令是：

```powershell
.\starter_kit\scripts\run_web.ps1 -Port 8765
```

启动器会确认仓库 `.venv`、Python 3.10 与 `spinqit==0.2.4`，然后打印精确访问地址并启动服务。若缺少环境，按它给出的命令运行 `.\starter_kit\scripts\setup.ps1` 后重试。然后从浏览器打开 `http://127.0.0.1:8765/`。不要双击静态 HTML；静态页面只能展示故事，无法连接本地实验接口。

Bell 的正确本地结果通常由 `00` 和 `11` 主导，各自接近 50%。49%/51% 与恰好 50%/50% 都可能是健康的采样涨落。但这份计算基相关性只是重要线索：经典混合也能产生相同的 `00/11` 统计，因此不能只凭这张图认证纠缠。页面的证据段会继续指向换基测量、纠缠见证和量子态层析。

## 先记住三个概念

- **qubit（量子比特）**是电路操作的基本单位。
- **gate（量子门）**是程序中的一次操作。
- **shots** 表示重复执行同一个实验；counts 记录每种经典结果出现了多少次。

使用 Web 入口不需要手算矩阵，也不需要自己写 QASM。

After configuring `LOOMQ_LLM_*`, try `生成 3 比特 GHZ 态`. A correct GHZ result is dominated by `000` and `111`.

## Agent tasks

After configuring `LOOMQ_LLM_*`, try:

1. `生成一个 5 比特 GHZ 态并测量全部量子比特。`
2. `我想制备 Bell 态，但这段代码有错：H q[0]; CX q[0] q[1]。保持原意并修好。`
3. `我要运行一个 15 比特电路，不想排队、不想付费也不想注册，应该选哪个后端？`

The first two responses must contain complete verified OpenQASM. The third must contain canonical IDs from the organizer's capability table. If the model returns an invalid candidate, LoomQ gives it one correction attempt; it never silently claims the invalid program passed.

## Reading the workbench

- **CIRCUIT** shows the shared IR as circuit rails. A small circle marks a control; a labeled box is the target gate; `M` marks measurement.
- **VERIFICATION** lists checks actually returned by the program. No check begins green.
- **RESULT** shows raw SDK counts as bars and an accessible table.
- **这些结果能说明什么？** gives a beginner explanation. OpenQASM is visible by default and can still be collapsed when you want to focus on the result.

## Scientific boundary

An ideal local simulator can show that the program implements the intended mathematical distribution. It does not prove quantum advantage, hardware fidelity, or resistance to real QPU noise. A true hardware claim needs a traceable platform job ID and raw result captured inside the contest window.

## Recovery

- **Agent 模型尚未配置**: 不影响第一次 Bell 体验；不要为了运行现成 Bell 实验粘贴 API Key。只有要处理自己的自然语言问题时，才需要由服务端提供 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL`。
- **Unsupported gate**: the contest accepts only the 12 gates listed in the README.
- **SDK unavailable**: run the setup script and `python -m pip check` inside `.venv`.
- **Counts look slightly uneven**: sampling fluctuation is expected. Use 8192 shots for scoring comparisons.
- **Port 8765 is busy**: start with `--port 8766` and open that address.

## 页面路线

页面顺序是：承诺与入口 → 先看理想 Bell 结果 → 概念地基 → 单 qubit / H → CNOT 与整条电路 → 本地 Bell 实验 → 结果与 OpenQASM → 归档硬件桥接 → Agent 问题入口 → X/Y/Z 与 tomography。第一次出现的概念总是先讲刚刚发生的现象，再给名称和公式；科学边界随后单独展开。

- Hero 同时提供 **带我完成第一次实验** 与 **我有自己的问题** 两条入口；前者进入 Bell 路径，后者跳到 Agent 示例问题。
- Agent 示例保持为三个自然语言提示：`帮我生成一个 GHZ 态并测量`、`这段 Bell 电路写错了，帮我修好`、`我有一个 15 比特任务，不想排队，应该选哪个后端？`。卡片只填入问题，不预设模型回答。

- X/Y/Z 面板是三个独立归档作业的交互回放：`Czz = 0.99955`、`Cxx = 0.99956`、`Cyy = -0.99865`。
- tomography 卡片展示 provider 重建点估计：Fidelity `0.952449` 与 PPT `λmin -0.4561`，并说明这不是统计置信区间或量子优势声明。
- 证据说明先指向已归档的 SpinQ + OriginQ canonical hardware，再指向 Wukong X/Y/Z、tomography 与 Agent / L3 / Custom RISC-V 的补充与工程材料；页面只回放已有证据。
- 英文界面与中文界面共用同一条实验路径；移动端优先保留原生按钮、可见 shots/backend 帮助和可展开 OpenQASM。
- 归档证据的英文边界句是：`This page is replaying evidence; it is not submitting a new hardware job.`
