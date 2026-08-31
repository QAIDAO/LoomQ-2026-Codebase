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

### 平台 1：SpinQ Cloud

```text
平台名称：SpinQ Cloud (Gemini NMR 2-qubit)
平台 job ID：G-260818-0009
运行时间：2026-08-18T08:49:28Z (UTC)
shots：8192
实际执行的 QASM：evidence/files/spinq-circuit.qasm
平台返回的原始结果：evidence/files/spinq_cloud_result.json
任务页截图：无
```

备注：SpinQ Cloud 不支持显式 measure 指令，平台自动在电路末尾执行全量测量。提交代码中已做适配。

### 平台 2：OriginQ 悟空 180

```text
平台名称：本源悟空 180 超导真机
平台 job ID：EC100A9E1CCE2596F25F7293995FF104
运行时间：2026-08-18T21:53:25.376+08:00
shots：8192
实际执行的 QASM：evidence/files/originq-circuit.qasm
平台返回的原始结果：evidence/files/originq_wukong_result.json
任务页截图：无
```

## L2 交互体验

```text
启动界面或 CLI 的命令：pip install -r starter_kit/requirements.txt && cd starter_kit && python app.py（L2 环境变量由组委会统一注入）
测试入口或页面地址：http://localhost:5000
用于交互体验评测的 3 个用户任务：
1. 点击欢迎卡中的「抛一枚量子硬币」按钮，查看生成的代码，点击代码下方的「运行」按钮，观察薛定谔盒子动画和结果直方图
2. 在输入框输入「帮我生成一个3比特的GHZ态」，运行代码并观察结果
3. 在输入框输入「我需要跑一个15比特电路，不想排队，推荐哪个平台？」，观察后端推荐
截图或演示视频：无
```

## 工程与产品化

```text
干净环境中的构建和启动命令：pip install -r starter_kit/requirements.txt && cd starter_kit && python app.py
架构说明：
  adapter.py — 核心模块：transpile()（L1 转译器，支持 spinq/originq/braket 三后端）、run()（多后端执行）、agent_chat()（L2 智能体）、compile_hybrid()（L3 混合编译）
  llm_client.py — LLM API 调用封装，读取 LOOMQ_LLM_* 环境变量
  app.py — Flask 服务器，提供 /chat（智能体对话）和 /run（电路执行）接口
  templates/index.html — 前端界面（Qat/喵子），包含欢迎引导、双语聊天、薛定谔盒子可视化、侧边栏概念解释
  riscv_emulator.py — 量子扩展 RISC-V 模拟器（含自定义量子指令集 + 二进制编码/解码）
  quantum_riscv_spec.md — 量子 RISC-V 扩展指令编码规格文档
目标用户和使用场景：零量子背景的用户（学生、跨界创作者、非技术人员），希望第一次体验量子计算但不会写 QASM 代码。用户用中文或英文描述实验，喵子自动生成代码、翻译到不同量子计算机、运行并可视化结果。
完整使用流程：启动 Flask → 打开浏览器访问 localhost:5000 → 点击波纹首页进入聊天 → 阅读欢迎卡了解量子计算 → 点击试试看按钮或输入实验描述 → 喵子生成 QASM 代码 → 点击「运行」按钮 → 薛定谔盒子动画揭晓结果 → 直方图 + 文字解释
```

## 自定义量子 RISC-V Bonus

```text
指令编码规格：starter_kit/quantum_riscv_spec.md
模拟器扩展实现：starter_kit/riscv_emulator.py
端到端测试命令：python starter_kit/riscv_emulator.py
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/templates/index.html — 欢迎卡从「比特」概念讲起，逐步介绍量子比特、叠加、QASM，最后引导用户通过三大功能（生成代码、修复代码、选择平台）开始使用，每个功能配有可点击的试试看按钮
量子概念解释：starter_kit/templates/index.html — 左侧边栏「了解概念」包含7个按钮（量子比特、叠加态、测量与坍缩、量子纠缠、概率与确定性、量子优势、薛定谔的猫），点击后由智能体用通俗语言解释
结果可视化：starter_kit/templates/index.html — 首页：波纹在鼠标移动时「坍缩」出猫头轮廓，隐喻量子测量导致波函数坍缩——未观测时是均匀波纹（叠加态），观测后坍缩为确定形态（猫），点击任意位置进入聊天界面（"观测"）。运行结果：薛定谔盒子动画（摇晃音效 → 开盖 → 猫醒着或睡着）+ 结果直方图 + 概率百分比 + 通俗文字解释（如「2个量子比特发生了纠缠」）
错误恢复或无障碍引导：starter_kit/templates/index.html — 网络或运行错误时显示温馨提示「喵...出了点问题」+ 重试按钮；输入框占位提示引导用户尝试；右上角提供语言切换（中/英）、主题切换（亮/暗）、音效开关；猫爪按钮显示项目信息
```
