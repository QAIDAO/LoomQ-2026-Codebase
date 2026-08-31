# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 贡献说明

不改变 Team ID，正式提交账号仍为 `0Dionysus0`。分工如下：

- **HeliosLL**：L1 统一中间层（`starter_kit/loomq/` 转译与执行）、L3 混合编译（`hybrid.py`）、自定义量子 RISC-V Bonus（`quantum_riscv_spec.md` / `riscv_quantum_emulator.py`）
- **0Dionysus0**：L2 智能体与网页（`loomq_l2/`、`web/`）、真机证据整理、交卷与工程说明

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
平台名称：本源量子云 / 本源悟空 180
平台 job ID：3C524A614AEFAA3130F2F3C139E9C8D8
运行时间：2026-08-14 14:51:57.173 +08:00（结束 14:52:03.874 +08:00，芯片运行 0.359 秒）
shots：1000
实际执行的 QASM：starter_kit/evidence/files/originq-bell.originir
平台返回的原始结果：starter_kit/evidence/files/originq-probability.csv
任务页截图：starter_kit/evidence/files/originq-screenshot-histogram.png
```

配套文件：`originq-result.json`（job 元数据 + counts）、`originq-screenshot-status.png`、`originq-screenshot-circuit.png`。官方 CSV 为 1000 shots：`00=0.494`、`11=0.455`、`01=0.028`、`10=0.023`。

```text
平台名称：量旋云 / 2 比特核磁量子计算机（gemini）
平台 job ID：61302（任务编号 G-260814-0001）
运行时间：2026-08-14 09:12:17 +08:00（结束 09:13:51 +08:00）
shots：原始结果未给出整数采样次数。平台官方 msgpack 只含四态投影概率（00=0.4243644，01=0.02228071，10=0.05090786，11=0.50244704，四者之和为 1）。任务页截图亦未标 shots。该后端为 2 比特核磁（gemini）系综读出，与超导按次数计数的 shots 不是同一套字段。
实际执行的 QASM：starter_kit/evidence/files/spinq-bell.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-task_result_G-260814-0001.msgpack
任务页截图：starter_kit/evidence/files/spinq-screenshot.png
```

配套文件：`starter_kit/evidence/files/spinq-result.json`（任务元数据与概率）。原始结果以平台返回的 msgpack 为准。

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

```text
启动界面或 CLI 的命令：cd starter_kit && python web_chat.py
（需已设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL）
备用 CLI：python chat.py
测试入口或页面地址：http://127.0.0.1:8877/ （启动 web_chat.py 后自动打开）
适合现场体验的 3 个用户任务：
1. 【看懂】跟着页面：拨空盒 → 看 F1–F4 两组 → 拨秘密盒子两次分出一样/不一样组
   → 搭激光笔和斜玻璃 → 只问一次看灯 → 读「灯亮和灯不亮到底在说什么」
   （Deutsch 算法）。全程不需要量子背景，大约 5 分钟。从搭机器起右下角可问助手。
2. 【问倒它】从搭机器起点右下角「我不懂，问一下」，用预置按钮：
   a) 「帮我生成一个 3 比特 W 态并全部测量」——自验不通过时会在回答最前面
      写明「这道题我没做对」；
   b) 「修好这段电路：h q[0]; cx q[0] q[1]; measure q -> c;」——修好后展示
      实际跑出来的分布和吻合度。
3. 【选后端】在助手里问「我想在真正的量子计算机上跑这个 2 比特的电路，
   不想花钱，应该选哪个平台」，确认助手给出规范后端标识并用白话解释理由。
截图或演示视频：选填；现场以最终 commit 实际运行 python web_chat.py 为准
```

每条结果都带来源标记，四种状态互不混淆：模型生成且已通过本地验证（附吻合度）、模型生成但未通过验证（助手明说没做对）、模型未连上而由本地规则算出、真机结果（可溯源到 job ID）。助手写的电路验证不通过时，页面提供「用内置标准电路继续」的降级路径，并明确标注该步不再由助手生成。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
1. 使用 Python 3.10。在 starter_kit/ 执行：pip install -r requirements.txt
2. 公开自测（不需要模型 Key）：python evaluator.py --level l1 --target spinq,originq,braket
   L3：python evaluator.py --level l3
3. 零基础界面：先在终端设置 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY、LOOMQ_LLM_MODEL（不要写进仓库），
   再执行 python web_chat.py
   浏览器打开 http://127.0.0.1:8877/
   无界面备用：python chat.py
4. 也可用官方容器：在 starter_kit/ 执行 docker build -t loomq-submission . && docker run --rm loomq-submission
   （容器默认跑公开 evaluator，不启动网页）

架构说明：
- 评测入口：starter_kit/adapter.py（transpile / run / agent_chat / compile_hybrid）
- L1 统一中间层：starter_kit/loomq/（QASM 解析 → IR → 按 spinq/originq/braket 分别 emit；run 走参考模拟器）
- L2 智能体与网页：starter_kit/loomq_l2/ + starter_kit/web/；agent_chat 生成电路后调用 adapter.run 自验
- L3：starter_kit/loomq/hybrid.py
- 自定义量子 RISC-V Bonus：starter_kit/loomq/riscv_quantum_emulator.py，规格见同目录 quantum_riscv_spec.md

目标用户和使用场景：
不懂量子力学、没有线性代数基础、想第一次尝试量子计算的中学生。
场景：让初学者初步理解量子计算的教学场景，或用助手生成/修复小电路并看到测量条形图，
而不必先学会三家云的 SDK。

完整使用流程：
见 starter_kit/web_chat.py 与 starter_kit/web/index.html；评委任务与本文件「L2 交互体验」三个用户任务相同：
看懂量子算法 → 询问助手 → 按约束选后端。CLI 流程见 starter_kit/chat.py。
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：starter_kit/loomq/quantum_riscv_spec.md
模拟器扩展实现：starter_kit/loomq/riscv_quantum_emulator.py
端到端测试命令：在 starter_kit/ 目录执行 python -m loomq.riscv_quantum_emulator
```

说明见规格第五节。模拟器与 L1 共用 `loomq/gates.py`、`loomq/simulate.py`，不要用 `python loomq/riscv_quantum_emulator.py` 直接跑（相对导入会失败）。

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/web_chat.py + starter_kit/web/index.html
  约 5 分钟线性引导（空盒 → 分组 → 拨两次 → 搭机器 → 看灯 → 真机对照）；
  术语等用户亲手做过之后才出现；从搭机器起可问助手；纯 CSS 无第三方前端依赖
量子概念解释：黑盒谜题（一样组 / 不一样组 / Deutsch），灯的一页写明量子并非
  「一次看到两个输出」、也不是更快的普通电脑，只拿到「一不一样」这一条信息；
  助手讲解通道 starter_kit/loomq_l2/agent.py::explain 附同样的诚实约束；另见 starter_kit/QUANTUM_101.md
结果可视化：灯亮/灯不亮 + 黑盒只用 1 次对照普通办法 2 次
  （starter_kit/web/main.js + starter_kit/loomq_l2/deutsch.py）；助手电路条形图；CLI 文本图 starter_kit/loomq_l2/viz.py
错误恢复或无障碍引导：缺 LOOMQ_LLM_* 时助手面板顶部健康检查给出具体缺哪个变量；
  助手电路自验不通过时明说「这道题我没做对」并给降级路径（starter_kit/loomq_l2/agent.py::
  _honest_failure_notice）；会话过期返回 410 并提示重开一局；
  灯的结果同时用「亮/不亮」文字，不单靠颜色传达信息
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
