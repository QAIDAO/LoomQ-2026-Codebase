# LoomQ 人工评分证据

这是人工评分材料的统一入口。勾选只表示仓库内已有可运行实现与复核材料，不表示评委已授分。公开 evaluator、本地 HTTP stub、参考模拟器和 dry-run 均按其真实边界标注。

## 申报项目

- [ ] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机：未申报

当前没有 SpinQ 或 OriginQ 的真实 QPU job ID、厂商原始结果、赛程内时间戳或任务截图。`loomq/hardware/`、`scripts/hardware/` 与 `docs/hardware/` 只提供安全 runner、runbook、dry-run 和证据契约；23/23 hardware tests 没有联网、没有读取真实凭证，也没有生成 job。

模拟器、目标 IR、dry-run 和占位 ID 都不计真机证据，因此本项保持未勾选。

## L2 交互体验

```text
启动命令：在 starter_kit/ 运行 python -m loomq.ui.server
页面地址：http://127.0.0.1:8765
Agent 正式配置：LOOMQ_LLM_BASE_URL / LOOMQ_LLM_API_KEY / LOOMQ_LLM_MODEL

用于交互体验复核的 3 个用户任务：
1. “生成一个 5 比特 GHZ 电路，进行全测量，输出 OriginIR 后用 LoomQ 本地参考模拟器运行。”
2. “我想制备 Bell 态，请修复 H q[0]; CX q[0] q[1]。”
3. “15 比特、免费、无需排队，推荐后端。”
```

实现入口：

- `loomq/ui/`：本地工作台、结构化错误、IR/电路/counts 可视化、请求级证据；
- `loomq/agent/workflow.py`：生成/修复/推荐、有界一至两次模型调用、确定性准入；
- `backend_capabilities.json`：推荐事实源；
- `scripts/run_l2_stub_evaluator.py`：真实本地 HTTP 传输复现。

本地公开 L2 为 1/1，HTTP stub 确实收到模型协议请求；这不是正式 DeepSeek 准确率证据。浏览器 QA 已实际加载 Bell starter 并执行验证流水线，未在截图中伪装正式模型或 QPU。

截图与机器可读记录：

- `evidence/files/ui/workbench-1440x900.png`
- `evidence/files/ui/workbench-run-1440x900.png`
- `evidence/files/ui/workbench-390x844.png`
- `evidence/files/ui/browser-qa.json`

## 工程与产品化

```text
Python 要求：3.10
完整检查：python scripts/run_all_checks.py
快速检查：python scripts/run_all_checks.py --quick
UI 启动：python -m loomq.ui.server
架构说明：docs/03_SYSTEM_ARCHITECTURE.md
测试策略：docs/04_TEST_STRATEGY.md
目标用户与完整流程：README.md
当前状态：DEVELOPMENT_STATUS.md
```

目标用户是会描述科研/计算问题、但不会 OpenQASM 或平台方言的研究者、学生和工程实践者。完整路径为“自然语言/QASM → 结构化准入 → 生成/修复 → 三目标转译 → 独立回读 → LoomQ 本地参考执行 → schema/位序验证 → 可视化与请求级证据”。

当前本地验证：Python 3.10.11；source syntax 78/78；unittest 119/119；公开 L1 6/6、L2 stub 1/1、L3 1/1；QASM 100 seeds × 3；Hybrid 500 × 8；UI 9/9；浏览器桌面/移动无 console error；Bonus 17/17；hardware preparation 23/23 dry-run only。

Dockerfile 已提供，但当前主机没有 Docker，尚未完成实际 build/run；因此不把容器写成已验证。实现已迁入标准 clone 并用 Python 3.10.11 完整复测，`main` 已 commit/push 且远端页面已核验更新；官方预检已在一个已 push 的干净 HEAD 上完整通过。任何后续 commit 必须重跑预检；Final Submission Issue 尚未创建，也没有接收回执。

## 自定义量子 RISC-V Bonus

```text
指令编码规格：loomq/bonus/quantum_riscv_spec.md
评审指南：docs/bonus/QUANTUM_RISCV_ISA.md
模拟器扩展：loomq/bonus/emulator.py
编码/解码：loomq/bonus/isa.py
态矢实现：loomq/bonus/statevector.py
端到端演示：python -m loomq.bonus.demo
测试命令：python -m unittest discover -s tests -p "test_bonus_*.py" -v
```

17/17 Bonus tests 通过。扩展覆盖 QINIT/QH/QX/QRY/QRZ/QCX/QSWAP/QCCX/QMEASURE（另有 QS/QT），使用 RISC-V `custom-0` 32 位编码与 GPR Q16.16 角度。它继承官方 TinyRISCV 接口但不修改正式 L3 文件，报告始终标记 `hardware_execution=false`。

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：README.md 的“30 秒启动”“三个首屏任务”
量子概念解释：loomq/ui/static/index.html 与 app.js 的 newcomer/glossary 区域
结果可视化：SVG 电路线、门序列、counts 柱状图、Top states、三目标 IR tabs
错误恢复：行列定位、结构化诊断、保守 repair、明确重试建议
无障碍：skip link、语义标签、键盘焦点、中英文、390px 响应式布局
视觉证据：evidence/files/ui/*.png 与 browser-qa.json
```

UI tests 9/9。浏览器记录使用 Chrome 151 / Playwright 1.62.1：1440×900 运行状态 completed、verification PASSED、10 个 artifact；390×844 页面无横向溢出；两种视口 console errors 均为 0。界面明确标识“LoomQ local reference”，目标 tabs 是方言产物而不是 vendor jobs。

## 复核声明

- 所有 `l1/l2/l3-public-report.json` 只是公开自测，不是正式分数或隐藏评测证明。
- 本地 L2 stub 不等于正式 `deepseek-v4-flash`。
- LoomQ reference statevector、target emitter 和 hardware dry-run 不等于厂商 SDK、云任务或 QPU。
- L1 真机没有材料，因此未勾选。
- Docker、正式 DeepSeek 与真实 QPU 尚未验证；fork 已 push 且官方 preflight 曾完整通过，但任何新 HEAD 都必须重跑，Final Submission Issue 与 `submission:accepted` 回执尚未完成。
- 所有提交材料必须进入最终 commit，且不得含 API Key、Token、Cookie、个人账户信息、`.codex_reference/` 或缓存。
