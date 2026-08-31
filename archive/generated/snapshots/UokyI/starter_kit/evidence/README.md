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
平台名称：本源量子「悟空」超导真机（180 比特，chip origin_180）
平台 job ID：A7C58462C717A6873FF1AEF6B8728213
运行时间：2026-08-24T08:46:04Z
shots：8192
实际执行的 QASM：evidence/files/wukong-circuit.qasm
平台返回的原始结果：evidence/files/wukong-result.json
任务页截图：（选填，无）
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
启动界面或 CLI 的命令：python3 starter_kit/chat_cli.py
测试入口或页面地址：无（CLI 交互式入口，也支持单次提问：python3 starter_kit/chat_cli.py "生成一个3比特纠缠态"）
用于交互体验评测的 3 个用户任务：
1. 「我想做一个能让 3 个量子比特像串联灯泡一样同时亮或同时灭的实验，帮我生成电路并运行。」（考察自然语言生成 + 结果可视化）
2. 「我想得到一个贝尔态，但下面这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]」（考察代码纠错与容错提示）
3. 「我需要运行一个 15 比特的电路，而且不想排队，帮我选一个平台。」（考察智能选后端）
截图或演示视频：无
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：python3 starter_kit/evaluator.py --level l1 --target spinq,originq,braket --json-out report.json（零第三方依赖，无需安装）
架构说明：starter_kit/ARCHITECTURE.md
目标用户和使用场景：无量子背景的跨界创作者（产品/设计/内容/教育），用自然语言驱动量子电路；详见 ARCHITECTURE.md「必答题」与「目标用户」
完整使用流程：python3 starter_kit/chat_cli.py "生成一个3比特纠缠态"；详见 ARCHITECTURE.md「完整使用流程」
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/QISA_SPEC.md
模拟器扩展实现：starter_kit/qriscv_emulator.py
端到端测试命令：python3 starter_kit/qisa_test.py
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/ARCHITECTURE.md「完整使用流程」与「一键复现」
量子概念解释：starter_kit/ARCHITECTURE.md「必答题」与「目标用户」（用生活化隐喻说明量子态）
结果可视化：starter_kit/chat_cli.py 的 ASCII 直方图（自动运行并可视化测量结果）
错误恢复或无障碍引导：starter_kit/chat_cli.py 的缺配置/报错友好提示（中文，无 traceback）
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
