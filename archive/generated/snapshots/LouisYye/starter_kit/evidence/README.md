# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

-   [x] L1 真机
-   [x] L2 交互体验
-   [x] 工程与产品化
-   [x] 自定义量子 RISC-V Bonus
-   [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。

### SpinQ Cloud 2 Qubits NMR

``` text
平台名称：SpinQ Cloud - 2 Qubits NMR
平台 job ID：G-260821-0001
运行时间：2026-08-21 15:02:41 至 15:04:14（UTC+8）
shots：N/A（该 NMR 任务返回连续投影概率，SpinQ Cloud 未显示 shots）
实际执行的 QASM：starter_kit/evidence/files/spinq/spinq-bell.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq/spinq-bell-raw-result.msgpack
可读结果：starter_kit/evidence/files/spinq/spinq-bell-result.json
任务页截图：starter_kit/evidence/files/spinq/spinq-screenshot.png
```

任务状态为 `Success`，来源为 `SpinQ Cloud`。原始结果中的投影概率为: - 00: 0.44239204 - 01: 0.06120968 - 10: 0.03296570 - 11: 0.46343258 符合bell态的预期结果，主导测量结果为 00 和 11。

### OriginQ 本源悟空 180

``` text
平台名称：本源量子云 - 本源悟空 180
平台 job ID：FFA39889E42949045D8C2192EF616D50
运行时间：2026-08-25 01:11:44.422 至 01:13:30.703（UTC+8；平台任务详情页时间）
shots：1024
实际执行的 QASM：starter_kit/evidence/files/originq-bell.qasm
平台返回的原始结果：starter_kit/evidence/files/originq-bell-raw.json
可读结果：starter_kit/evidence/files/originq-bell-result.json
任务提交元数据：starter_kit/evidence/files/originq-bell-task.json
实际执行的 OriginIR：starter_kit/evidence/files/originq-bell-originir.txt
任务成功截图：starter_kit/evidence/files/originq-bell-task-success.png
结果与映射线路截图：starter_kit/evidence/files/originq-bell-result-circuit.png
```

任务状态为 `FINISHED`，设备记录为 `origin_180`。真机返回概率为 00：
0.5189357、01：0.0000209、10：0.0007325、11：0.4803105；按 1024 shots
换算为 531、0、1、492。Bell 态目标结果 00 与 11 合计占 1023/1024，且标准化证据
明确标记 `is_mock: false`。

其他真机平台如需申报，可复制并填写下面的信息：

``` text
平台名称：[填写]
平台 job ID：[填写]
运行时间：[填写，带时区]
shots：[填写]
实际执行的 QASM：[填写仓库内路径]
平台返回的原始结果：[填写仓库内路径]
任务页截图：[选填，填写仓库内路径]
```

建议把文件放进 `evidence/files/`，比如：

``` text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

请填写：

``` text
启动界面或 CLI 的命令：python3 -m starter_kit.l2_cli
测试入口或页面地址：无（终端交互入口）
用于交互体验评测的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并测量全部比特
2. 帮我修复这段电路并保持 Bell 态目标：OPENQASM 2.0; qreg q[2]; h q[0]; cx q[0], q[2];
3. 我没有账号、只接受免费且无需排队的后端，请推荐一个至少支持 3 比特的选项
欢迎菜单截图：starter_kit/evidence/files/l2-cli-welcome.png
GHZ 生成、本地验证与直方图截图：starter_kit/evidence/files/l2-cli-ghz-histogram.png
Key 缺失时的中文恢复提示截图：starter_kit/evidence/files/l2-cli-error-recovery.png
```

CLI 提供欢迎语、连续多轮输入、可直接选择的示例任务和 `q` 退出方式。生成或
修复电路后，会显示经本地模拟得到的 counts 换算值、百分比和文本直方图；模型
配置缺失或结果图生成失败时，会保留已有结果并给出可执行的中文恢复建议。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

``` text
干净环境中的一键构建并运行命令：cd starter_kit && docker build -t loomq-submission . && docker run --rm loomq-submission
容器公开自测命令：docker run --rm loomq-submission
本地 CLI 启动命令：python3 -m starter_kit.l2_cli
架构说明：starter_kit/ARCHITECTURE.md
目标用户和使用场景：会描述实验目标、但不会 QASM、不了解厂商 SDK 与后端限制的
学生、教师和应用开发者；用于自然语言生成/修复电路、理解测量结果和选择可用后端。
完整使用流程：starter_kit/README.md 的 L2 统一模型与环境变量一节，以及
starter_kit/ARCHITECTURE.md 的“一次请求如何流动”一节。
```

必须使用上述 Docker 构建流程：SpinQ SDK 位于隔离虚拟环境中，并由 Dockerfile 设置
`LOOMQ_SPINQ_PYTHON`，从而避免其依赖版本与 Qiskit、Braket 冲突。仅在同一环境执行
`pip install -r requirements.txt` 不能复现 SpinQ 后端。

必答题：LoomQ 让被量子汇编语法、厂商 SDK、平台账号与排队规则挡在门外的学习者
和应用开发者，第一次可以只描述目标，就获得经过本地验证的量子电路、看得懂的测量
分布，以及符合自身限制的运行后端。运行时模型负责理解人话，确定性代码负责守住
正确性边界。

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

``` text
指令编码规格：starter_kit/QUANTUM_RISCV.md
模拟器扩展实现：starter_kit/riscv_emulator.py（qgate、qmeasure 与 quantum_trace）
端到端测试命令：python3 -m pytest tests/test_quantum_riscv.py -q
量子操作编码器：starter_kit/l3_compiler.py 的 emit_quantum_riscv()
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

``` text
零基础首次运行指南：starter_kit/README.md（L2 环境配置、CLI 命令与三个内置示例）；截图 starter_kit/evidence/files/l2-cli-welcome.png
量子概念解释：starter_kit/QUANTUM_101.md
结果可视化：starter_kit/l2_cli.py（counts、概率和终端文本直方图）；截图 starter_kit/evidence/files/l2-cli-ghz-histogram.png
错误恢复或无障碍引导：starter_kit/l2_cli.py（中文配置提示、空输入提示、模拟失败降级）；截图 starter_kit/evidence/files/l2-cli-error-recovery.png
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

-   所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
-   外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
-   整个 fork commit 的归档包不得超过 100 MiB。
-   不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
-   如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
