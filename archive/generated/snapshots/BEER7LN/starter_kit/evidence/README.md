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

### SpinQ Cloud

```text
平台名称：SpinQ Cloud（gemini_vp，2Qubit 核磁量子计算机）
平台 job ID：G-260807-0011
运行时间：2026-08-07T09:37:30.832+0000
shots：1024
实际执行的 QASM：evidence/files/spinq-bell-executed.qasm
平台返回的原始结果：evidence/files/spinq-bell-raw-result.json
标准化结果与 Top-K 校验：evidence/files/spinq-bell-result.json
任务页截图：未提交（选填；以可追溯 job ID、原始响应和标准化结果为核验依据）
```

原始 SpinQ 结果提供 `module` 概率而不是 `count`；标准化文件按照 SpinQit SDK 的规则使用 `round(probability * shots)` 生成 `counts`。Top-2 为 `11`、`00`，命中 Bell 理想主导态。原始 task 元数据包含平台用户名和 userId，仅本地留存，不进入公开证据。

### Origin Quantum Cloud

```text
平台名称：Origin Quantum Cloud（WK_C180_2，本源悟空 180 超导真机）
平台 job ID：E03FE919C438D14649B3C227CB6979D8
运行时间：2026-08-07T12:13:30.819000Z
shots：1024
实际执行的 OriginIR：evidence/files/originq-bell-executed.originir
平台返回的原始结果：evidence/files/originq-bell-raw-result.json
标准化结果与 Top-K 校验：evidence/files/originq-bell-result.json
物理比特：38、47（2比特）
任务页截图：未提交（选填；以可追溯 job ID、原始响应和标准化结果为核验依据）
```

该任务通过 `pyqpanda3 0.4.0` 提交到账号可见且在线的 `WK_C180_2` 真实 QPU。执行链路为同一份 `adapter.transpile(qasm, "originq")` 输出 OriginIR，再由 QPanda3 解析为 QProg；没有使用手写平台答案。原始 counts 为 `00=509, 01=87, 10=43, 11=385`，Top-2 为 `00`、`11`，命中 Bell 理想主导态。公开原始响应不包含 API Token、用户名、userId、邮箱或手机号字段。

## L2 交互体验

```text
启动界面或 CLI 的命令：python l2_app.py --host 127.0.0.1 --port 8765
测试入口或页面地址：http://127.0.0.1:8765
适合现场体验的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并进行全测量；查看生成的 QASM 和 1024-shot 直方图。
2. 修复 `H q[0]; CX q[0] q[1]`，保持“制备 Bell 态”的原始意图，并观察自动校验与重试。
3. 为“15 比特、免费、零排队、无需账号”的任务选择后端，并核对规范后端 ID 与理由。
演示视频：仓库根目录 video.mp4（完整前台流程，约 34 MiB）
```

前台演示视频：[点击播放 `video.mp4`](../../video.mp4)。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

实现说明与可复现测试见 `docs/L2_IMPLEMENTATION.md`。Web 入口和官方评测入口共享 `adapter.agent_chat()`；界面不会绕过模型调用、L1 QASM 校验或官方后端能力表。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：根 README.md 第 2 节；Docker 使用 `docker build -t loomq-submission ./starter_kit` 后运行 `docker run --rm loomq-submission python scripts/verify_all.py`
架构说明：docs/architecture.md、docs/HARDENING_DESIGN.md、docs/L1_IMPLEMENTATION.md、docs/L2_IMPLEMENTATION.md、docs/L3_IMPLEMENTATION.md
目标用户和使用场景：没有量子物理、线性代数、OpenQASM 或厂商 SDK 背景的第一次学习者；通过六节微课程、本地实验、自然语言生成/修复和知情确认的可选真机路径完成第一次可验证量子计算
完整使用流程：evidence/files/engineering-container-verification.md（Docker 实际构建、L1/L3/原生 SDK 验证及 L2 服务健康检查）
```

2026-08-14 已在 Docker Desktop 29.7.2 / WSL 2 上从本仓库 `Dockerfile` 成功构建 `loomq-submission:validation`。L1 三后端公开评测 6/6、L3 公开评测 1/1、强制原生 SDK L1 测试 6 项以及 L3/Bonus 19 项均在 Linux 容器中通过；容器化 L2 服务 `/api/health` 返回 HTTP 200。完整命令、镜像标识和 L2 注入配置边界见上述记录。

2026-08-24 又在隔离 Python 3.10 原生 SDK 环境中对代码父提交 `6dd7f4ea04e22a91d2b6833c941005c07f47aeed` 执行 `python scripts/verify_all.py --release`：公开 L1 6/6、公开 L3 1/1、137 项本地测试和 72 项 official-family pipeline 验证全部通过，0 failed、0 skipped。此后仅更新本人工证据文档，不改变受测实现。

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：docs/L3_RISCV_EXTENSION.md（custom-0 / opcode 0x0b，字段布局、合法性约束与运行模型）
模拟器扩展实现：loomq/riscv_quantum_extension.py（ExtendedTinyRISCVEmulator；独立兼容 fork，保留官方经典指令语义，并用 statevector 执行 12 个量子门、测量坍缩及 `x(10+cbit)` 写回）
端到端测试命令：cd starter_kit && python -m unittest tests.test_l3_bonus_contract
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：根 README.md 第 2、7、10 节；QUANTUM_101.md；l2_app.py 首页从经典 bit 开始，不要求预先理解 ket、矩阵或 QASM
量子概念解释：curriculum/lessons.json；learning.py；motion/remotion/；motion/hyperframes/；六节内容覆盖路径、shots、Bell 相关、相位、GHZ 与真机噪声
结果可视化：web/index.html、web/app.js、web/styles.css；状态概率、1024-shot counts、直方图、预测对比、两平台只读真机 Bell 证据；根目录 video.mp4
错误恢复或无障碍引导：docs/L2_IMPLEMENTATION.md；模型错误反馈与重试、输入保留、诚实无解、skip link、ARIA、直方图朗读、reduced-motion、深浅主题和移动端 compact 模式
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

本项目对必答题的回答是：**让没有量子学术背景、不会 QASM、也不了解厂商 SDK 的学生、教师、产品经理、设计师、文科创作者和普通软件开发者，第一次能够提出自己的量子问题、运行可验证实验、看懂结果，并在明确同意与凭据安全边界下接触真实量子硬件。** 这里的“第一次使用”不是观看介绍，而是完成“预测 → 运行 → 解释 → 创造”的闭环。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
