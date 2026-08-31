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
平台名称：量旋云 gemini_vp（2比特核磁量子计算机）
平台 job ID：G-260820-0002
运行时间：2026-08-20T02:13:18.927460+00:00
shots：1024
实际执行的 QASM：evidence/files/spinq-circuit.qasm
平台返回的原始结果：evidence/files/spinq-result.json
任务页截图：未提供（可选）
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
启动界面或 CLI 的命令：配置 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL` 后运行 `python -m starter_kit.chat "<自然语言问题>"`
测试入口或页面地址：无（本地 CLI）
适合现场体验的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并进行全测量，查看 QASM 和结果解释。
2. 修复缺少寄存器声明、门名大小写错误的贝尔态代码，并查看修复说明。
3. 为“15 比特且零排队”的需求选择后端，比较比特上限、排队和费用。
截图或演示材料：`evidence/files/l2-ghz-output.txt`、`evidence/files/l2-repair-output.txt`、`evidence/files/l2-backend-output.txt`
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：`docker build -t loomq-submission starter_kit`；运行全部已声明 Level 时使用 `docker run --rm -e LOOMQ_LLM_BASE_URL -e LOOMQ_LLM_API_KEY -e LOOMQ_LLM_MODEL loomq-submission`；L2 CLI 见上方命令。
架构说明：`starter_kit/adapter.py` 提供 L1/L2/L3 固定接口；`llm_client.py` 负责 OpenAI-compatible 调用；`evaluator.py` 做公开契约自测；`riscv_emulator.py` 执行 L3 经典控制流；`chat.py` 提供零基础 CLI。
目标用户和使用场景：没有量子计算背景、希望用自然语言生成/修复 QASM 并选择本地后端的初学者和教学演示者。
完整使用流程：先运行公开自测，再配置 L2 环境变量运行 `python -m starter_kit.chat`；代码结构和启动方式见 `starter_kit/README.md`。
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：`starter_kit/RISCV_QUANTUM_EXTENSION.md`
模拟器扩展实现：`starter_kit/riscv_emulator.py`
端到端测试命令：`python -m unittest discover -s starter_kit/tests -p "test_*.py"`
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：`starter_kit/BEGINNER_GUIDE.md`
量子概念解释：`starter_kit/BEGINNER_GUIDE.md`、`starter_kit/QUANTUM_101.md`
结果可视化：`starter_kit/chat.py`（对回复中的 QASM 输出本地理想测量结果柱状图）
错误恢复或无障碍引导：`starter_kit/chat.py`、`starter_kit/BEGINNER_GUIDE.md`
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
