# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
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

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：
streamlit run starter_kit/web/app.py

测试入口或页面地址：
http://localhost:8501（本地运行）

适合现场体验的 3 个用户任务：
1. 点击左侧「生成一个贝尔态」示例按钮 → 自动生成 QASM + 原理讲解 + 直方图
2. 在输入框输入「什么是量子门？」→ Agent 用旋转硬币类比解释
3. 输入「生成一个 4 比特的随机数生成器」→ Agent 生成代码并运行

截图或演示视频：
evidence/files/ux_screenshot1.png（界面截图）
evidence/files/ux_screenshot2.png（界面截图）
evidence/files/ux_screenshot3.png（界面截图）
evidence/files/ux_screenshot4.png（界面截图）
evidence/files/ux_screenshot5.png（界面截图）
evidence/files/ux_screenshot6.png（界面截图）
evidence/files/ux_screenshot7.png（界面截图）
evidence/files/ux_screenshot8.png（界面截图）
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
cd LoomQ-2026
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r starter_kit/requirements.txt
pip install streamlit matplotlib qiskit qiskit-aer python-dotenv openai
streamlit run starter_kit/web/app.py

目核心亮点：
- L1 通用中间层：内置 fallback 解析器，支持 swap / ccx / cu1 等白名单门，确保 QFT、Grover 等隐藏电路语义等价。
- L2 智能体：同时支持自然语言生成电路与后端推荐，并包含代码自愈闭环。
- L3 混合编译：完整支持 Hybrid-QASM 中 `classical {}` 块的解析与 RISC-V 汇编生成。
- UI 界面：提供“量子游乐场”拖拽式搭建 + “自然语言实验室”双模式，降低学习门槛。

一键验证（评委可快速复现核心功能）：
python starter_kit/evaluator.py --level l1,l2,l3

架构说明：
starter_kit/README.md 或见以下简述：
- adapter.py：L1 模拟执行 + L2 Agent 入口 + L3 混合编译
- web/app.py：Streamlit 双模式交互界面
- evidence/：人工评分材料与演示截图

目标用户和使用场景：
完全不懂量子编程的跨界创作者（设计师、产品经理、学生）。
场景：打开网页 → 点击示例或输入想法 → 5 分钟内获得可运行的量子程序 + 原理解释。

完整使用流程：
1. 访问 Web 界面
2. 左侧点击预设示例（如 GHZ 态）
3. 查看生成的 QASM 代码、原理讲解和直方图
4. 自由输入任何量子实验想法
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

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
零基础首次运行指南：
Web 界面左侧预设了 5 个示例按钮，点击即可自动运行，无需任何量子知识。

量子概念解释：
Agent 在每次生成代码后，自动用「旋转硬币」「心灵感应骰子」等生活类比解释原理。

结果可视化：
运行后自动显示 QASM 代码 + 原理讲解 + 测量结果直方图（使用 Qiskit plot_histogram）。

错误恢复或无障碍引导：
Agent 内置自愈闭环：当生成的代码无法运行时，会自动捕获错误并重新生成，最多重试 2 次。用户无需手动调试。
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
