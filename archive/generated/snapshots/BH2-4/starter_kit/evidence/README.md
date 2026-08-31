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

### 平台 1：SpinQ 量旋云（核磁量子真机，属官方能力表 `spinq_cloud_qpu` 的 2–8 比特真机范围）

```text
平台名称：SpinQ 量旋云 · 核磁量子计算机（Bell 用 2 比特 Gemini，GHZ-3 用 3 比特 Triangulum）
平台 job ID：Bell = G-260815-0001；GHZ-3 = S-260815-0002
运行时间：2026-08-15 02:58 UTC（Bell）；2026-08-15 03:00 UTC（GHZ-3）
shots：各 1000
实际执行的 QASM：starter_kit/circuits/bell.qasm 与 starter_kit/circuits/ghz3.qasm（实际提交的是其中间层规范化输出，已原样保存在证据 JSON 的 qasm_contract_output 字段）
平台返回的原始结果：evidence/files/spinq/bell_G-260815-0001.json；evidence/files/spinq/ghz3_S-260815-0002.json
任务页截图：无（job ID 可在量旋云控制台任务记录中溯源复核）
```

主峰校验：Bell Top-2 = {11, 00}；GHZ-3 Top-2 = {111, 000}，与理想分布一致。

### 平台 2：本源量子云（超导真机 悟空 180 / WK_C180_2，官方 Q&A 认可的非强制真机后端）

```text
平台名称：本源量子云 · 悟空 180 真机（后端 WK_C180_2，经 pyqpanda3 动态后端发现接口提交）
平台 job ID：Bell = 2E213684ED8EB081361832057F1D12B3；GHZ-3 = B054B2797AD542992605601384F9DB4B
运行时间：2026-08-15 15:23 UTC（两个任务）
shots：各 1000
实际执行的 QASM：starter_kit/circuits/bell.qasm 与 starter_kit/circuits/ghz3.qasm（实际提交的规范化 QASM2 保存在证据 JSON 的 qasm_submitted 字段）
平台返回的原始结果：evidence/files/originq/bell_WK_C180_2_2E213684ED8EB081361832057F1D12B3.json；evidence/files/originq/ghz3_WK_C180_2_B054B2797AD542992605601384F9DB4B.json
任务页截图：无（task_id 可在本源量子云控制台任务查询中溯源复核）
```

主峰校验：Bell Top-2 = {11, 00}（52.5% / 46.8%）；GHZ-3 Top-2 = {111, 000}（37.6% / 34.1%），与理想分布一致。

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
启动界面或 CLI 的命令：python3 starter_kit/chat.py（交互模式）；单发 python3 starter_kit/chat.py --prompt "生成一个 3 比特 GHZ 态并测量"；离线演示 python3 starter_kit/chat.py --demo（无需模型）
测试入口或页面地址：无（CLI 入口）
用于交互体验评测的 3 个用户任务：
1. 零基础第一次使用：运行 --demo，30 秒内看到量子纠缠直方图与通俗解读（GETTING_STARTED.md 第 1 步）。
2. 自然语言生成：对话输入"生成一个 3 比特 GHZ 态并测量"，助手生成电路并自动本地运行 4096 次，给出直方图 + "总是给出相同答案的骰子"式解释；换措辞（如"来个五比特最大纠缠"）结果仍正确。
3. 容错与纠错：输入"我想跑贝尔态但代码报错了：H q[0]; CX q[0] q[1]"，助手修复并说明修复内容；未配置环境变量时给出明确自救指引（chat.py 的 WELCOME_NO_ENV 与错误自救表）。
截图或演示视频：无（CLI 可直接复跑；--demo 模式完全离线可验证）
```

多轮一致性说明：`agent_chat` 为确定性编排（意图分类 → 模板生成 → 本地验证），
同一问题重复提问答案一致；`--demo` 与模拟器路径零网络依赖。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：零依赖零构建——python3 starter_kit/chat.py --demo 即可运行（Python 3.10+，纯标准库）；契约自测 python3 starter_kit/evaluator.py
架构说明：starter_kit/README.md「架构」一节（loomq/loomq_l2/loomq_l3 三层模块图 + 各模块工作原理 + AI 辅助开发披露）
目标用户和使用场景：零量子背景的跨界创作者（设计师/文科研究者/产品经理/中学生）——说大白话即可生成、验证、解读量子电路；详见 README「目标用户与使用场景」
完整使用流程：starter_kit/GETTING_STARTED.md（5 分钟三步上手）→ README「完整使用流程」五步 → 质量验证命令
```

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/l3_bonus_spec.md
模拟器扩展实现：starter_kit/riscv_emulator_qext.py（官方 riscv_emulator.py 的扩展 fork，原文件未改动）
端到端测试命令：python3 starter_kit/l3_selftest.py --bonus（另有模拟器自测：python3 starter_kit/riscv_emulator_qext.py）
```

扩展指令集为 QH/QX/QCX/QMS（Hadamard、X、受控非、测量入寄存器），编码占用
RISC-V CUSTOM-0（opcode 0x0B）扩展空间；量子部分编译为量子指令、经典部分仍为
官方 7 指令，混合程序在扩展模拟器上一次执行完成"量子演化→测量读数→经典控制"
闭环。端到端测试对 200 个随机 Hybrid 用例与独立状态向量参考全对拍，0 失配。

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/GETTING_STARTED.md（5 分钟三步上手，无需任何量子基础或第三方依赖）
量子概念解释：starter_kit/GETTING_STARTED.md「三句话理解刚才发生了什么」+ 官方 QUANTUM_101.md；对话回复内嵌每个电路的通俗原理说明
结果可视化：starter_kit/chat.py —— ASCII 直方图（按频次排序、含百分比）+ 自动通俗解读（chat.py 的 bar_chart/explain_result，生成电路后自动运行 4096 次展示）
错误恢复或无障碍引导：starter_kit/GETTING_STARTED.md「错误自救表」+ chat.py --doctor 环境自检 + 未配置/模型故障时的分步自救提示（不泄露任何密钥）
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
