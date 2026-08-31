# LoomQ 人工评分证据

这是 Huxingyu 参赛实现的人工评分统一入口。`files/...` 证据路径相对于 `starter_kit/`，命令则显式标明工作目录；原始返回、实际电路和附件均已进入最终 commit，不依赖可变的外部链接。

## 申报项目

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

两份主证据分别来自 SpinQ 与 Origin Quantum 的真机，不是模拟器或 mock。两份 `*-result.json` 均保留平台原始返回，并在顶层归一化为官方 Schema：`backend`、`job_id`、`shots`、`counts`、`bit_order="little"`、`timestamp`。`counts` 为非负整数且总和严格等于 `shots=1024`。

可复现的自检：

```bash
python3 -m unittest discover -s tests -p 'test_evidence.py' -v
```

### 平台 1：SpinQ Cloud

```text
平台名称：SpinQ Cloud 2Qubit核磁量子计算机（Gemini-pro-1）
平台 job ID：G-260822-0014
运行时间：2026-08-21T21:37:37.553Z ~ 2026-08-21T21:39:11.237Z
shots：1024
实际执行的 QASM：files/spinq-gemini-bell.qasm
平台返回的原始结果：files/spinq-gemini-bell-result.json
任务页截图：未提交（题面选填；评分所需 job ID、时间、QASM 和平台原始返回已提交）
```

同一台真机还额外完成了 8 组语义验证（X、H、CNOT、SWAP、Ry、Rz、CU1 分解），原始结果与理论分布汇总在 `files/spinq-gemini-validation-results.json`。

3 比特核磁真机（Triangulum）另完成 3 组验证（GHZ-3、X+CNOT 链、H），原始结果与理论分布汇总在 `files/spinq-triangulum-validation-results.json`。

`spinq-gemini-bell-result.json` 的 `raw_result_api` 保留查询接口原始结构，`raw_result_file_msgpack_base64` 保留结果文件原始负载，`task_id=61397`、`source_addr` 和机器标识可辅助复核。

SpinQ Cloud 该任务格式会对声明的量子比特做隐式全测量，因此平台实际接收的 `spinq-gemini-bell.qasm` 只包含 Bell 态制备指令，不应为了形式统一而事后改写。原始结果中的 `bit_num=2`、`shots=1024` 和四个二比特 counts 是实际测量记录。

### 平台 2：Origin Quantum Cloud

```text
平台名称：本源量子云 WK_C180 超导量子计算机（悟空系 180 比特）
平台 job ID：DD891ACC37461FFCC199AC4FE14224D4
运行时间：2026-08-21T23:00:53Z ~ 2026-08-21T23:00:59Z
shots：1024
实际执行的 QASM：files/originq-wukong-bell.qasm
云平台转译后的 OriginIR：files/originq-wukong-bell.originir
平台返回的原始结果：files/originq-wukong-bell-result.json
任务页截图：未提交（题面选填；评分所需 job ID、时间、QASM、OriginIR 和平台原始返回已提交）
```

本源云的 `raw_origin_data` 保留原始返回，其中包含 `taskId`（与 job ID 一致）、`chipId=WK_C180`、`pilotTaskId=4DBDAFA8B66B4E2FB01F4E42CBC875CB`、`qpuRunTime=338`（毫秒）和概率分布；主峰为 00/11。

同一本源真机另完成 GHZ-3 验证（job `27D603013382A1B0DD184B951A87C545`，物理比特块 `[157,166,176]`，qpuRunTime=323 毫秒，主峰 000/111），证据见 `files/originq-wukong-ghz3-*`。3 比特任务需要显式指定最优物理比特块，否则本源云编译器会报错，这也成为我们接入层的一个兼容性结论。

## L2 交互体验

```text
工作目录：fork 根目录
无配置首次体验：python3 starter_kit/loomq_cli.py --demo bell
自然语言 Agent 入口：python3 starter_kit/loomq_cli.py
单次可重复入口：python3 starter_kit/loomq_cli.py --prompt "<用户请求>"
组委会解包后的评测根：上述命令去掉 starter_kit/ 前缀，即 python3 loomq_cli.py ...
完整用户流程与配置：starter_kit/SOLUTION.md
用于交互体验评测的 3 个用户任务：
1. 生成一个 4 比特 GHZ 态并进行全测量。
2. 我想制备 Bell 态，请修复：H q[0]; CX q[0] q[1]
3. 我要运行 25 qubit 电路，要求本地、免费、无需账号且不排队，推荐后端。
截图或演示视频：未提交；可按上述命令直接运行完整产品
```

入口首屏中英双语说明“无需量子物理背景”，提供 3 个可直接复制的任务和 `/help`、`/demo bell`、`/clear`、`/quit` 命令。“改成 5 比特”类跟进请求会透明引用上一轮，`/clear` 可显式重置。生成／修复的 QASM 会被本地解析、语义验证、运行，然后展示 counts、精确百分比、ASCII 直方图和人话解释；缺少模型配置时会指出具体环境变量并引导回离线 demo，不会打印凭据。

## 工程与产品化

```text
干净环境一键启动：python3 starter_kit/loomq_cli.py --demo bell
组委会解包后的评测根：python3 loomq_cli.py --demo bell
容器复现：docker build -t loomq-submission starter_kit && docker run --rm loomq-submission
评测根容器复现：docker build -t loomq-submission . && docker run --rm loomq-submission
架构与失败恢复：starter_kit/SOLUTION.md
零基础概念手册：starter_kit/QUANTUM_101.md
主要模块：qasm_core.py、agent_engine.py、hybrid_compiler.py、riscv_emulator.py、loomq_cli.py
依赖：首次体验和公开自测均仅用 Python 标准库；requirements.txt 无未锁定依赖
```

**必答题——谁第一次能用上量子计算？** 从未学过量子物理、从未写过 QASM，且不愿意在首次体验前安装 SDK、注册云账号或申请 Key 的开发者、学生和产品设计者。他们只需一条命令就能运行第一个可验证的量子电路；接着可用自然语言生成、修复并选择后端，同时保留 QASM 与标准 Schema 作为可追溯的技术出口。

2026-08-24 已在新建 Docker 镜像的 Python 3.10.21 中实测：默认 CLI 容器启动成功，L1 公开评测 6/6，L3 公开评测 1/1。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：quantum_riscv_extension.md
模拟器扩展实现：riscv_emulator.py
端到端测试命令：在 starter_kit 目录运行 python3 -m unittest test_quantum_riscv_extension -v
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行：SOLUTION.md 的 Five-minute first run；python3 starter_kit/loomq_cli.py --demo bell
量子概念解释：QUANTUM_101.md 的 Bell/GHZ、shots、counts、位序和保真度人话解释；CLI 在结果就地解释“随机但关联”
结果可视化：loomq_cli.py 同时显示 counts、百分比和 ASCII 概率直方图，不依赖颜色
错误恢复：SOLUTION.md 的 Error recovery；CLI 精确提示缺失的 LOOMQ_LLM_* 配置并提供 /demo bell 离线路径
无障碍与包容性：全键盘操作、中英双语首屏、纯 ASCII 图表、精确数值冗余表达，可在基础终端与复制日志中使用
```

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
