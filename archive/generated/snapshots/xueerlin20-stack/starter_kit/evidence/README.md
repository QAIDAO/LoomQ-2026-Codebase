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
平台名称：本源量子 本源悟空180-2
平台 job ID：9AF78C69756E262144E19CC897A4D328
运行时间：2026-08-09T13:06:32.512572+00:00
shots：1000
实际执行的 QASM：starter_kit/circuits/bell.qasm
平台返回的原始结果：starter_kit/evidence/files/L1-真机/originq-raw-result.json
统一结果：starter_kit/evidence/files/L1-真机/originq-result.json
任务页截图：
    - starter_kit/evidence/files/L1-真机/originq_1.png
    - starter_kit/evidence/files/L1-真机/originq_2.png
    - starter_kit/evidence/files/L1-真机/originq_3.png
```
```text
平台名称：量旋云 2比特核磁量子计算机
平台 job ID：G-260809-0019
运行时间：2026-08-09T10:36:14.465306+00:00
shots：100
实际执行的 QASM：starter_kit/circuits/bell.qasm
平台返回的原始结果：starter_kit/evidence/files/L1-真机/spinq-raw-result.json
统一结果：starter_kit/evidence/files/L1-真机/spinq-result.json
任务页截图：
    - starter_kit/evidence/files/L1-真机/spinq_1.png
    - starter_kit/evidence/files/L1-真机/spinq_2.png
```

## L2 交互体验

请填写：

```text
启动web界面的命令：python3 starter_kit/web_app.py
测试入口或页面地址：http://127.0.0.1:8765

适合现场体验的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并进行全测量
2. 我想制备贝尔态，请修复这段代码：H q[0]; CX q[0] q[1]
3. 我要运行一个 26 比特电路，必须免费并且不能排队

额外支持features:
- 可通过网页直接配置模型（模型平台选择，API Key, 最大运行时间）
- 可根据量子知识水平选择不同的新手导入
- chatbot 对话支持上下文，可连续追问
- chatbot 支持电路解释功能
- chatbot 回答支持md格式渲染


截图文件夹:
starter_kit/evidence/files/L2-web-chatbot
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：starter_kit/docs/干净环境构建与启动.md

架构说明：starter_kit/docs/ARCHITECTURE.md

目标用户和使用场景：
- 量子计算初学者：通过交互式网页，用自然语言生成、修改和理解量子电路。
- 教师及教学人员：演示量子门、电路运行、测量结果和 Fidelity，辅助量子计算教学。
- 量子开发者：通过程序接口将 QASM 转换并运行到 SpinQ、OriginQ、Braket 等后端，或编译和验证混合量子—经典程序。

完整使用流程：starter_kit/docs/完整使用流程.md
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

### 必答题：你的工具让哪一类原本进不来的人，第一次能用上量子计算？（提供Web 界面、无代码引导等佐证最佳）
```text
我们的工具把量子计算的适用人群从专业研究者和程序员，拓展到没有物理、数学或编程背景的普通用户，包括学生、教师、其他行业从业者以及所有对新技术感兴趣的公众。
LoomQ L2 提供完整的 Web 无代码入口。首次进入时，用户可以根据自己的熟悉程度选择讲解深度；新手引导会依次介绍量子比特、量子门、电路和测量，并通过可点击的 H、CX 和测量操作，带领用户亲手完成第一个 Bell 纠缠实验。
web新手引导界面：starter_kit/evidence/files/L2-web-新手引导
chatbot运行环境无代码引导：starter_kit/evidence/files/L2-web-新手引导/运行环境设置.png

Appendix：量子知识科普文档 - starter_kit/docs/量子计算基础与LoomQ分层说明.md
```

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：`starter_kit/bonus_quantum_riscv/SPEC.md`
模拟器扩展实现：`starter_kit/bonus_quantum_riscv/emulator.py`（编码器位于同目录 `encoding.py` 和 `compiler.py`）
端到端测试命令：`python -B -m unittest discover -s starter_kit/bonus_quantum_riscv/tests -v`
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：
    - 一键启动，可不配置： starter_kit/docs/干净环境构建与启动.md
    - 网页配置模型： starter_kit/evidence/files/L2-web-新手引导/运行环境设置.png
量子概念解释：starter_kit/evidence/files/L2-web-新手引导
结果可视化：starter_kit/evidence/files/L2-web-chatbot/L2-生成电路.png
错误恢复或无障碍引导：starter_kit/evidence/files/L2-web-chatbot/L2-修改代码.png
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
