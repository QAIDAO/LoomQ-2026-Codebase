# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也引用 `starter_kit/` 中已有的代码和文档。

## 提交前填写

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

未申报（仅在模拟器上验证：SpinQ、OriginQ）。

## L2 交互体验

```text
启动界面或 CLI 的命令：
  # 网页版（推荐现场体验）
  .venv/Scripts/python starter_kit/loomq/webapp.py
  # 命令行冒烟测试（依次跑三种任务）
  .venv/Scripts/python starter_kit/loomq/agent.py
  需先设置 LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL

测试入口或页面地址：http://localhost:8000

适合现场体验的 3 个用户任务：
1. 生成（GENERATE）：Make a 3-qubit GHZ (maximally entangled) state and measure everything.
   → 代理返回完整合法的 OpenQASM，网页画出电路并逐门讲解。
2. 修复（FIX）：I want a Bell state but this errors, please fix it: H q[0]; CX q[0] q[1]
   → 代理指出缺少分号/寄存器声明并返回可运行版本；自校验环回验证后才回复。
3. 推荐（RECOMMEND）：I need to run a 15-qubit circuit with zero queue wait. Which backend?
   → 代理用大白话给出建议，并给出确切的规范后端 id（取自 backend_capabilities.json）。

截图或演示视频：无（评测在组委会统一模型环境中现场运行以上任务即可复现）
```

代理实现见 `starter_kit/loomq/agent.py`：单一系统提示覆盖三类任务，并带有
**自校验环路**——用 L1 的 `parse_qasm` 解析自己的输出、越界检查，失败则把错误
回喂给模型重试（`max_retries`）。温度固定为 0，符合 L2 一致性要求。

## 工程与产品化

```text
干净环境中的构建和启动命令：见 starter_kit/loomq/README.md 的 “Run it (clean environment)”
  python -m venv .venv
  .venv/Scripts/python -m pip install -r starter_kit/requirements.txt
  .venv/Scripts/python starter_kit/evaluator.py --level l1 --target spinq,originq
  .venv/Scripts/python starter_kit/loomq/run_tests.py   # 快速自测，无需 API Key

架构说明：starter_kit/loomq/README.md（模块表 + 数据流图）。
  核心是“窄腰” IR：所有后端与代理自校验都经过同一个 parse_qasm → IR。

目标用户和使用场景：零量子基础的学生 / 跨领域研究者 / 产品同学。
  用自然语言描述想做的实验 → 得到可运行的电路 → 看图看讲解 → 运行 → 读懂结果。

完整使用流程：starter_kit/loomq/README.md 的 “Who this is for” 一节，
  以及网页版从输入到“逐步讲解 + 结果解读”的端到端体验。
```

## 自定义量子 RISC-V Bonus

未申报（`submission.yaml` 中 `l3: false`）。

## 新手引导与视觉叙事 Bonus

以下四项均由自建的零依赖网页 UI 提供（`starter_kit/loomq/webapp.py` +
`starter_kit/loomq/index.html`，纯标准库 + 原生 JS，无 CDN、无外部依赖）：

```text
零基础首次运行指南：starter_kit/loomq/README.md（一条命令装好、一条命令启动；
  网页打开即用，输入框有示例提示，无需先懂 QASM）。
量子概念解释：网页的“图例（legend）”与逐步讲解用大白话解释每个门，
  例如 Hadamard → “creates superposition (both 0 and 1 at once)”
  （见 index.html 的 legend / stepCaption / 单量子比特状态盘 state dial）。
结果可视化：SVG 电路图 + 动画结果条 + 单量子比特“状态盘”坍缩动画
  （0 → 叠加 → 测量），把测量分布转成一眼看懂的图形。
错误恢复或无障碍引导：代理自校验环路在出错时自动修复并重试；网页对错误给出
  可读提示（而非堆栈）；SVG 带 role/aria-label，图例逐条对应电路概念，
  提供自定进度的“▶ Walk me through it, step by step”分步引导。
```

以上四项各 1 分，均指向已实现且随最终 commit 归档的功能，未为评分另写文档。

## 提交规则

- 所有材料都在截止前进入最终提交的 commit。
- 未提交 API Key、Token、Cookie 或个人隐私。
- 未申报 L1 真机，无需在提交 Issue 的 `Hardware evidence` 中填写本文件；
  如需人工复核 L2/工程/新手引导，请指向 `starter_kit/evidence/README.md`。
