# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

### 平台 1：量旋 SpinQ Cloud（`spinq_cloud_qpu`） — 已申报

```text
平台名称：量旋云 · SpinQ Cloud（gemini_vp / triangulum_vp）
平台 job ID：G-260817-0005（Bell，gemini_vp，2 比特核磁真机）
运行时间：2026-08-17T08:13:27Z（UTC）
shots：1024
实际执行的 QASM：evidence/files/spinq-cloud-bell.qasm
平台返回的原始结果：evidence/files/spinq-cloud-bell-result.json
任务页截图：无（job_id 可在 cloud.spinq.cn 控制台溯源）
```

第二个任务（同平台，增强可信度）：

```text
平台名称：量旋云 · SpinQ Cloud（triangulum_vp，3 比特核磁真机）
平台 job ID：S-260817-0002（GHZ-3）
运行时间：2026-08-17T08:16:09Z（UTC）
shots：1024
实际执行的 QASM：evidence/files/spinq-cloud-ghz3.qasm
平台返回的原始结果：evidence/files/spinq-cloud-ghz3-result.json
任务页截图：无
```

主峰命中验证：Bell → `00`/`11` 合计约 88%；GHZ-3 → `000`/`111` 合计约 87%，均与理想分布一致（真机含噪声，仅查主峰）。

建议把文件放进 `evidence/files/`，比如：

```text
evidence/files/spinq-circuit.qasm
evidence/files/spinq-result.json
evidence/files/spinq-screenshot.png
```

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

启动界面或 CLI 的命令：`python3 starter_kit/cli.py`（交互模式）或 `python3 starter_kit/cli.py "你的需求"`（单次模式）
测试入口或页面地址：无（CLI，无 Web 页面）
用于交互体验评测的 3 个用户任务：
1. 生成：输入"生成一个 3 比特 GHZ 态并全测量" → Agent 生成 OpenQASM 2.0，本地模拟器自验通过后展示程序并运行，输出 000/111 各约 50% 的直方图
2. 修复：输入"帮我修复贝尔态代码：H q[0]; CX q[0] q[1]" → 自动补全 qreg/creg 声明并修正门名大小写，输出正确的 2 比特贝尔态并运行验证
3. 选后端：输入"15 比特电路且零排队，选哪个后端？" → 依据官方 backend_capabilities.json 约束过滤，列出候选并给出推荐后端 id
截图或演示视频：无（可运行代码本身即测试入口，欢迎工作人员直接运行）

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

干净环境中的构建和启动命令：见 [`ARCHITECTURE.md`](../ARCHITECTURE.md) 第 3 节；两条路径均一条命令可跑通：
- Docker：`docker build -t loomq-submission starter_kit && docker run --rm loomq-submission`
- 本地：`bash setup_local.sh && source .venv/bin/activate && python3 starter_kit/evaluator.py --level all --target spinq,originq,braket`
架构说明：[`ARCHITECTURE.md`](../ARCHITECTURE.md)（L1 策略+工厂、L2 管道+装饰器、L3 递归下降+RISC-V 代码生成、adapter 契约薄层）
目标用户和使用场景：见 ARCHITECTURE.md 第 1、4 节 —— 面向会说母语但看不懂量子术语的跨界创造者；说需求 → 生成/修复程序 → 本地运行 → 看懂结果
完整使用流程：见 ARCHITECTURE.md 第 4 节（新手 5 分钟流程示例）

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/riscv_quantum_spec.md
模拟器扩展实现：starter_kit/riscv_quantum_emulator.py（对官方 riscv_emulator.py 的 fork）
端到端测试命令：python3 starter_kit/test_quantum_riscv.py
```

设计要点：基于 RISC-V custom-0(0x0B)/custom-1(0x7B) 指令空间编码量子门与量子控制指令；
**编码已真正进入执行链路**——每个量子助记符先经 `encode_instruction` 编码为 32 位指令字、
再经 `decode_instruction` 解码后执行（opcode/funct3/funct7 实际参与运行，非仅规格文档）；
经典子集（li/add/sub/addi/beq/bne/j）行为与官方一致；内置 statevector 量子引擎。
测试覆盖：编码往返 + opcode 空间断言、Bell/GHZ 相关性、qcount 概率（P(00)≈0.5、RZ(π/4)≈0.8536）、
参数门 RY(π/2)→|1>、Toffoli、以及与 L1 braket 参考的 Hellinger 交叉验证（≥0.97）。8/8 通过。

## 新手引导与视觉叙事 Bonus

四项材料对应实现位置（均可运行验证）：

```text
零基础首次运行指南：README.md「本项目做了什么」+ cli.py 顶部 banner（三条可试例句）
量子概念解释：QUANTUM_101.md（官方手册，CLI 直方图直观呈现 000/111 各 50% 的纠缠）
结果可视化：cli.py 的 ASCII 直方图（运行后自动绘制各测量态占比 + 最可能结果）
错误恢复或无障碍引导：cli.py 对无法解析的输入给出友好提示（"没听懂，换个说法试试"）
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
