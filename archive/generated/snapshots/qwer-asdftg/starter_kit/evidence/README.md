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

```text
平台名称：OriginQ WK_C180
平台 job ID：8FEAB29CDEF92F47DD115E023FAF329B
运行时间：2026-08-24 11:03:19.590 UTC+8
shots：8192
实际执行的 QASM：starter_kit/evidence/files/originq-8FEAB29CDEF92F47DD115E023FAF329B-submission.qasm
平台返回的原始结果：starter_kit/evidence/files/originq-8FEAB29CDEF92F47DD115E023FAF329B-provider-raw.json
标准化结果：starter_kit/evidence/files/originq-8FEAB29CDEF92F47DD115E023FAF329B.normalized-result.json
执行元数据：starter_kit/evidence/files/originq-8FEAB29CDEF92F47DD115E023FAF329B-execution-metadata.json
物理比特映射：[157, 166]
任务页截图：无（通过 pyqpanda3 QCloudService 提交并保留平台原始 JSON）
```

```text
平台名称：SpinQ gemini_vp（Gemini-pro-1，2 比特核磁真机）
平台 job ID：61461
平台 task code：G-260824-0003
运行时间：2026-08-24 11:35:39.885 至 11:37:12.132 UTC+8
shots：8192
实际执行的 QASM：starter_kit/evidence/files/spinq-61461-cloud-submission.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-61461-provider-raw.json
标准化结果：starter_kit/evidence/files/spinq-61461.normalized-result.json
执行元数据：starter_kit/evidence/files/spinq-61461-execution-metadata.json
任务状态：S（成功），simulator=false
任务页截图：无（通过 SpinQ 官方 spinqit_mcp_tools 0.0.1 提交并保留平台原始 JSON）
结果说明：Gemini 核磁真机返回归一化概率；原始概率完整保留在 provider-raw 和 execution-metadata 中，统一 counts 由 8192 shots 按最大余数法确定性换算。
```

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

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：python -m starter_kit.l2_cli "生成一个 3 比特 GHZ 态并进行全测量"
本地多模型探测：python -m starter_kit.l2_cli --provider dashscope --probe --all --model qwen-plus --model qwen-max --json（默认 dry-run；确认调用成本后才加 --execute）
测试入口或页面地址：无（CLI；自动测试入口为 python -m unittest tests.test_l2_contract starter_kit.tests.l2 -v）
用于交互体验评测的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并全测量，查看可复制的完整 OpenQASM 2.0。
2. 粘贴有语法错误的 Bell QASM，要求助手返回可解析的修复程序。
3. 描述比特数、预算和是否需要真机，让助手从能力表返回 canonical backend id。
错误恢复：CLI 会分别说明缺少的环境变量、连接主机/超时、HTTP 状态/request ID 或 QASM/后端校验原因；不会输出 Key、Authorization 或响应正文。
截图或演示视频：无；最终调用由组委会注入的 L2 环境完成，本地探测仅使用显式 provider 和用户提供的候选模型 ID，不保存凭据或对话。
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：cd starter_kit && docker build -t loomq-l1 . && docker run --rm -w /workspace loomq-l1 python -m starter_kit.evaluator --level l1 --target spinq,originq,braket --shots 8192
架构说明：starter_kit/README.md（OpenQASM 2.0 → 统一 IR → 三平台发射/执行/结果归一化；L2 为模型调用加本地校验；L3 为 Hybrid-QASM → RISC-V）
目标用户和使用场景：没有量子 SDK 使用经验、但需要把量子线路接入现有 Python 工程的跨学科开发者；可先用 CLI 将自然语言需求变成 QASM，再在 SpinQ、OriginQ 或 Braket 中以同一接口执行。
完整使用流程：starter_kit/README.md 的 L2 assistant、L3 Hybrid-QASM、Public L1 evaluator 三节；用户先运行 python -m starter_kit.l2_cli 提出需求，再将返回 QASM 传给 adapter.transpile 或 adapter.run，最后读取统一 JSON counts。
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/quantum_riscv_extension.md
模拟器扩展实现：starter_kit/riscv_emulator.py（直接扩展 starter kit 的 TinyRISCVEmulator）
端到端测试路径：starter_kit/tests/l3/test_quantum_riscv_extension.py
端到端测试命令：python -m unittest discover -s starter_kit/tests/l3 -p 'test_*.py' -v
```

规格文档列出 Custom-0 的完整 32 位字段、保留位规则、`qh`/`qcx`/`qmeas` 操作数语义、8 量子位状态模型和原始指令字 Bell 示例。评审可按上述命令复现；最终是否计入 Bonus 以组委会实际构建和测试结果为准。

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/newcomer_guide.md；离线入口为 python -m starter_kit.l2_cli --guide
量子概念解释：starter_kit/newcomer_guide.md 的“认识五个词”（QASM、后端、模拟器、shots、真机 QPU 的比喻与下一步）
结果可视化：python -m starter_kit.l2_cli --explain-counts '{"00":4102,"11":4090}'（确定性 ASCII counts 柱状图；不声称结果来自真机或证明硬件纠缠质量）
错误恢复或无障碍引导：starter_kit/newcomer_guide.md 的“第 5 分钟”与 l2_cli 的安全错误类别说明
自动测试：python -m unittest starter_kit.tests.l2.test_cli -v（其中包含 --guide 无 Key/无模型调用，以及 Bell counts 关联说明测试）
```

这项申报只覆盖上述本地 CLI 和文档可验证的引导、术语解释、ASCII 结果呈现与下一步提示；
不以截图、LLM 成功调用或真机运行作为证据。

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。

## L1 真机账户开通后的安全取证流程

在账户、设备权限和平台最新 API 合同均已确认之前，`run_qpu.py` 不会提交、排队或执行任何 QPU 任务。先在本地确认同一份电路可以被解析和发射：

```bash
python -m starter_kit.hardware.run_qpu --provider spinq --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
python -m starter_kit.hardware.run_qpu --provider originq --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
python -m starter_kit.hardware.run_qpu --provider braket --qasm starter_kit/circuits/bell.qasm --shots 8192 --dry-run
```

竞赛窗口内获得真实平台结果后，优先准备 SpinQ 和 OriginQ 的证据；AWS Braket 的 QPU 可能产生费用。SpinQ 官方客户端使用 `PRIVATEKEYPATH`、`SPINQCLOUDUSERNAME` 和 `SPINQCLOUDHOST`，私钥对应的公钥需预先登记在 SpinQ Cloud；OriginQ 使用 API Token；Braket 使用标准 AWS credential chain，并额外需要 `AWS_BRAKET_DEVICE_ARN`。不要把密钥、Token、Cookie、配置文件或环境导出内容放入仓库。

把平台返回的数据保存为 UTF-8 JSON，再导入为可追溯的四个文件：

```bash
python -m starter_kit.hardware.run_qpu --provider originq --qasm starter_kit/circuits/bell.qasm --import-result provider-result.json --output-dir starter_kit/evidence/files
```

`provider-result.json` 必须包含以下原始字段：`provider`（`spinq`、`originq` 或 `braket`）、非空且安全的 `job_id`、带 UTC 时区的 `timestamp`、正整数 `shots`，以及总和严格等于 `shots` 的非空 `counts` 位串计数对象。`job_id` 必须是竞赛窗口内平台返回、可以复核的真实任务 ID；截图不能代替它。导入后会以 `<provider>-<job_id>` 为统一基名写入 `-submission.qasm`、`.native.ir`、`.raw-result.json` 和 `.normalized-result.json`，且拒绝覆盖已有证据。
