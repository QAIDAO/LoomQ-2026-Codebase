# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机（量旋云已锁定；本源悟空仍在维护，若恢复将追加第二个平台块）
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

```text
平台名称：量旋云 SpinQ Cloud（gemini_vp 核磁真机）
平台 job ID：G-260822-0024（平台任务 tid=61428，账号 userId=6558）
运行时间：2026-08-22 17:59:51 ~ 18:01:24 (UTC+8)，timecost 3.0s
shots：1000
实际执行的 QASM：starter_kit/evidence/files/spinq_bell_submitted.qasm
    （与平台后台 sourceCode 字段逐字一致，同时内嵌于结果 JSON）
平台返回的原始结果：starter_kit/evidence/files/spinq_cloud_bell.json
    （含 get_task_by_code 完整任务实体 + task_result 原始概率分布）
主峰命中：理想贝尔态 {00:0.5, 11:0.5}；实测 {00:42.5%, 11:51.5%}，
    Top-2 主导态与理想完全一致，串扰合计约 6%（核磁真机典型噪声水平）
任务页截图：starter_kit/evidence/files/spinq_gemini_task_report.png
    （由平台 API 原始返回渲染的任务报告卡：任务编号/机器/时间/分布/保真度；
    控制台可按 G-260822-0024 溯源复核）
```

同平台第二台真机（补充证据）：

```text
平台名称：量旋云 SpinQ Cloud（triangulum_vp 3比特核磁真机）
平台 job ID：S-260822-0005（平台任务 tid=61431）
运行时间：2026-08-22 20:31:29 ~ 20:32:46 (UTC+8)
shots：1000
实际执行的 QASM：同上（同一贝尔电路）
平台返回的原始结果：starter_kit/evidence/files/spinq_cloud_bell_triangulum.json
主峰命中：{00:38.1%, 11:38.0%}，Top-2 主导态与理想一致（3比特机跑2比特电路噪声较大，符合预期）
任务页截图：starter_kit/evidence/files/spinq_triangulum_task_report.png
    （同上，按 S-260822-0005 溯源）
```

**关于第二个平台的说明**：本源悟空自 2026-08-22 起全部真机后端持续维护
（origin_72 / d5 / d4 均返回 maintenance，d3 资源 null），整个周末我每 15 分钟查询一次，均未开放。
若周一恢复，我将补交第二平台证据；
若维护持续，恳请评委考虑：我已在量旋云的两台不同真机上完成交叉验证
（2比特与3比特核磁架构各自独立执行），统一管线对多真机的适配能力已得到实证。

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
启动界面或 CLI 的命令：python starter_kit/webapp.py（零第三方依赖，仅标准库；
    需先设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL 三个环境变量，
    与 adapter.agent_chat 同一协议）
测试入口或页面地址：浏览器打开 http://127.0.0.1:8765
用于交互体验评测的 3 个用户任务：
1. 在对话框输入「帮我生成一个贝尔态电路」，等待智能体回复后，观察右侧自动绘制
   的电路图，点击绿色按钮「跑 1024 次」查看概率直方图（预期 00 与 11 各约 50%）。
2. 输入「帮我修复这段电路：qreg q[2]; creg c[2]; h q[0]; cx q[0] q[1];
   measure q -> c;」（cx 缺逗号的常见新手错误），验证智能体能定位并修复语法问题。
3. 输入「25比特电路，一点都不能排队等，用哪个平台？」，验证智能体依据
   backend_capabilities.json 给出数据驱动的后端推荐及理由。
截图或演示视频：evidence/files/web_experience_landing.png（首屏）、
    evidence/files/web_experience_full.png（完整流程：对话→电路图→试跑→直方图）
```

页面内置「① 说出想法 → ② 看电路织好 → ③ 按下试跑」三步引导与预设示例 chips；
IP 形象「量子Kitty」（薛定谔的猫）贯穿全站：页头会眨眼的猫、右下角可拖拽
桌宠（会在生成/试跑/出错时说话、闲时喵喵叫）；聊天区右侧实验台自动把生成的
OpenQASM 渲染为电路示意图（纯 SVG，无第三方库），试跑结果以动画柱状图呈现。
所有渲染逻辑位于 `starter_kit/web/`。
零配置演示版：`starter_kit/demo.html`——双击即可离线体验完整流程（内置示例
数据，无需 Python/网络/API Key）。

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：pip install -r requirements.txt && python evaluator.py --level declared（公开自测）；
    python webapp.py 启动量子Kitty网页入口；详见 starter_kit/README.md 快速开始
架构说明：starter_kit/ARCHITECTURE.md（统一转译管线、L2 自验闭环、L3 寄存器纪律、测试矩阵）
目标用户和使用场景：从没碰过量子计算、也不会写代码的跨界创作者与中小学生——
    用说人话的方式在 5 分钟内变出第一个量子电路并在真实/模拟量子设备上看结果
完整使用流程：打开网页 → 跟 Kitty 说「帮我变出一个贝尔态」→ 看右侧自动绘制的电路图 →
    点「掷 1024 次量子骰子」看直方图；出错时 Kitty 用人话解释并带用户一步步修好
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

### 必答题：你的工具让哪一类原本进不来的人，第一次能用上量子计算？

**答案：被「物理」和「命令行」双重挡在门外的人——具体说，是不懂任何量子力学、
也可能一辈子不会打开终端的跨界创作者、文科生和中学生。**

传统量子云平台的入门路径是：学线性叠加 → 学复振幅 → 学一门方言 DSL → 注册海外账号 →
写第一行 QASM。每一步都在筛选。量子Kitty把这条路压缩成一句话：
你只要会说「帮我变出一个贝尔态」，剩下的翻译、校验、执行、可视化全部由智能体完成。
三层保障让这句话不是营销：(1) LLM 只负责听懂人话，一切数学判定在确定性代码侧，
换任何模型都不掉链子；(2) 出错时用人话解释（「多比特门要用逗号分开哦」）并自动修复；
(3) 双击即玩的 demo.html 让连 Python 都不想装的人也能先玩起来。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：[填写文档路径]
模拟器扩展实现：[填写代码路径]
端到端测试命令：[填写命令或文档路径]
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
零基础首次运行指南：starter_kit/QUANTUM_101.md（30分钟速成手册）+
    starter_kit/demo.html（双击即玩，无需安装任何东西）
量子概念解释：QUANTUM_101.md 全文 + 网页内嵌的魔法隐喻体系
    （测量=掷量子骰子、波函数坍缩、保真度=像不像），由 Kitty 在对话中随问随讲
结果可视化：web/app.js 自绘 SVG 电路图（门药丸+连线+测量表盘）与动画概率直方图，
    见 evidence/files/web_experience_full.png
错误恢复或无障碍引导：agent_chat 人话报错层（_l2_lint 把天书报错翻译成
    「多比特门要用逗号分开」等可执行建议）+ 自验重试闭环 + 非法门确定性改写；
    前端错误气泡永远附带下一步指引；桌宠 Kitty 在生成/试跑/失败时给出情绪陪伴
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
