# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [ ] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：量旋 SpinQ 真机（两比特核磁共振 NMR）
平台 job ID：G-260819-0002
运行时间：2026-08-19 15:29:37 – 15:31:10（UTC+8）
shots：N/A（NMR 系综测量直接返回概率，无离散 shots 字段）
实际执行的 QASM：starter_kit/evidence/files/spinq-circuit.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-result.msgpack（JSON 可读版：spinq-result.json）
任务页截图：starter_kit/evidence/files/spinq-screenshot.png
```

> 说明：本平台为两比特 NMR 真机，系综读出结果为概率（非离散 counts），原始结果中主峰 `00`≈0.477、`11`≈0.398，与贝尔态理想分布（`00`/`11` 各 50%）主峰一致。

```text
平台名称：本源量子 悟空超导真机（originq_wukong，悟空芯 72 比特机型，控制台标注「本源悟空 180」）
平台 job ID：E782EA6B30439B7EE5199CC750DD0382
运行时间：2026-08-20 17:47:25.793 – 17:47:34.735（UTC+8，创建→结束）；其中芯片实际执行 0.319 秒
shots：1000（控制台「重复试验次数」）
量子比特数：2（贝尔态逻辑电路 q0/q1；平台自动线路优化 + 映射后落在物理比特 q[19]、q[29]）
实际执行的 QASM：starter_kit/evidence/files/originq-circuit.qasm
平台返回的原始结果：starter_kit/evidence/files/originq-result.json（控制台导出的概率分布：00≈0.49 / 11≈0.44 / 01≈0.034 / 10≈0.036）
任务页截图：starter_kit/evidence/files/originq-screenshot.png
```

> 说明：本平台为超导真机，任务流程「提交任务 → 线路优化 → 量控编译 → 芯片计算 → 计算完成」全部成功，job ID 可在本源量子云控制台溯源。电路以图形化方式编写、经平台自动线路优化与比特映射后在真机执行。原始概率分布主峰为 `00`≈0.49、`11`≈0.44，噪声态 `01`/`10` 各约 0.03——**Top-2 主峰与贝尔态 |00⟩+|11⟩ 理想分布（`00`/`11` 各 0.5）一致**，符合真机允许噪声、只查主峰命中的核验标准。

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

```text
启动界面或 CLI 的命令：
  cd starter_kit && python interactive.py
  · 零第三方依赖：只用到 Python 标准库 http.server / socketserver / json，无需 pip install。
  · 启动前按 submission.yaml 的 required_environment 注入三个环境变量：
        LOOMQ_LLM_BASE_URL   （LLM 服务地址）
        LOOMQ_LLM_API_KEY    （调用密钥，由组委会运行环境注入，绝不写入本仓库）
        LOOMQ_LLM_MODEL      （模型名）
    Key 仅以环境变量形式存在，提交包内不含任何密钥。

测试入口或页面地址：http://localhost:8000   （端口可用 LOOMQ_PORT 修改，默认 8000）

用于交互体验评测的 3 个用户任务：
  1. 生成电路：输入「帮我做一个 2 个比特的贝尔态电路」（或点首页示例卡片「生成电路」）
     ——期望得到可运行的 OpenQASM 2.0，并用大白话解释「什么是贝尔态、这几条门在干什么」。
  2. 选后端：输入「这个电路该用哪个后端跑最好？」（或点示例卡片「选后端」）
     ——期望按电路比特数/门类型，从 backend_capabilities.json 里挑出合适平台
       （本例两比特即量旋 SpinQ NMR 或本源悟空超导），并讲清选择理由。
  3. 纠错修复：输入「帮我看看这段 QASM 哪里错了：H q[0]; CNOT q[0],q[1]」
     （或点示例卡片「纠错修复」）——期望指出缺 qubit 声明/缺测量等问题并给出修复后可用版本。
  补充（复合意图）：输入「帮我做一个 3 个比特的 GHZ 态，选哪个后端跑？」
     ——期望同时给出电路 + 选后端两段回答。

截图或演示视频：
  - starter_kit/evidence/files/l2-chat-screenshot_1.png —— 首页引导：品牌「量语·QUANTALK」+ 平权文案「不用懂量子黑话」+ 3 张示例卡片 + 复合意图示例输入。
  - starter_kit/evidence/files/l2-chat-screenshot_2.png —— 多轮对话：复合意图「做一个三比特 GHZ 态，选哪个后端跑？」→ 同时输出可运行 OpenQASM 2.0 + 后端选型和理由。
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

```text
干净环境中的构建和启动命令：
  git clone <你的 fork 地址> && cd LoomQ-2026-main
  # 1) 安装依赖：只装两个可共存的 SDK（详见 requirements.txt 注释，无 antlr4 冲突）
  pip install -r starter_kit/requirements.txt          # spinqit==0.2.4  pyqpanda==3.8.5
  # 2) 注入模型服务环境变量（L2 需要；Key 由组委会统一注入，绝不写入仓库）
  export LOOMQ_LLM_BASE_URL="..."                       # OpenAI-compatible 服务地址
  export LOOMQ_LLM_API_KEY="..."                        # 由运行环境注入，勿提交
  export LOOMQ_LLM_MODEL="..."
  # 3) 自动评测（L1 4/4、L3 1/1 预期全过；L2 需上面的 env）
  python3 starter_kit/evaluator.py --level l1
  python3 starter_kit/evaluator.py --level l3
  # 4) 启动零依赖网页（纯标准库，无需额外 pip）
  python3 starter_kit/interactive.py                   # → http://localhost:8000
  说明：braket 的转译/执行代码在 adapter.py 中，但它与 spinq 的 antlr4 版本互斥，
       只能装在独立环境；本仓库以内置的 spinq + originq 作为默认双后端（也是评委默认 --target）。

架构说明：（分层图见 starter_kit/evidence/files/architecture.svg）
  ┌────────────────────────────────────────────────────────────────┐
  │  入口层  interactive.py       零依赖网页（浏览器 ⇄ 内置 http.server）│
  │          · 首页：品牌 / 示例卡片 / 平权引导 / 自然语言输入框          │
  │          · /chat：多轮 = 服务端把上文拼进本轮后调 agent_chat         │
  └──────────────────────────────┬─────────────────────────────────┘
                                 ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  智能层  agent_chat()  +  llm_client.py                        │
  │          · LLM 意图分类 generate / fix / backend（可任意组合）      │
  │          · 后端选型：LLM 只抽结构化约束 JSON，代码遍历              │
  │            backend_capabilities.json / l2_policy.json 精确匹配     │
  └──────────────────────────────┬─────────────────────────────────┘
                                 ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  中间层（核心） transpile(qasm, target) + run(qasm, target, shots)│
  │          · OpenQASM 2.0 → spinq / originq / braket 三方言         │
  │          · run：本地模拟器或真机；统一 counts 位序归一化            │
  └──────────────────────────────┬─────────────────────────────────┘
                                 ▼
  ┌────────────────────────────────────────────────────────────────┐
  │  L3 编译层  compile_hybrid(hybrid_qasm) → (quantum_ops, RISC-V)│
  │          · hybrid_compiler.py：经典块 → RISC-V 汇编 + 量子操作序列│
  │          · riscv_emulator.py：穷举注入测量值验证寄存器终态         │
  └────────────────────────────────────────────────────────────────┘

目标用户和使用场景：
  面向「不会写量子程序 / 没有量子硬件账号」的人——物理系学生、量子爱好者、AI 背景
  转量子的开发者、想给课上的老师。产品要消灭三道门槛：
    · 语言门槛：只讲自然语言，不必懂 OpenQASM / OriginIR（L2 agent_chat）
    · 平台门槛：同一份电路可翻译到多家云端方言，不必学各家语法（L1 transpile）
    · 上手门槛：从一句中文到「真机上的电路 + 选对后端」一气呵成，网页直达
  场景：用户输入「帮我在量旋上做一个 3 比特 GHZ 态并测量」，得到可直接交给
  LoomQ 转译层执行的 OpenQASM 2.0，同时被推荐到满足约束的后端，本地即可跑出结果。

完整使用流程（对应下方截图）：
  ① 打开 http://localhost:8000 —— 见品牌「量语·QUANTALK」+ 3 张示例卡片 + 平权文案
     （evidence/files/l2-chat-screenshot_1.png）
  ② 点「生成电路」卡片或直接输入任务 → 得到可运行 OpenQASM 2.0 与大白话解释
  ③ 继续追问「这个电路该用哪个后端跑最好？」→ 依比特数/门类型从能力表选后端并说明理由
  ④ 复合意图「做一个三比特 GHZ 态，选哪个后端跑？」→ 一段输入同时给出电路 + 选型
     （evidence/files/l2-chat-screenshot_2.png）
  ⑤ 支持连续多轮：本页内任意次追问（输入框不消失），上下文由服务端拼接历史维持
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：[填写文档路径]
模拟器扩展实现：[填写代码路径]
端到端测试命令：[填写命令或文档路径]
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：[填写]
量子概念解释：[填写]
结果可视化：[填写]
错误恢复或无障碍引导：[填写]
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
