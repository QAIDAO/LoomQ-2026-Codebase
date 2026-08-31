# LoomQ Pegasus · 开发状态

最后更新时间：2026-08-21（UTC+8）

这是项目状态的唯一事实入口。状态只由可复跑测试升级；公开 evaluator、离线模型桩和本地模拟器均不等于隐藏评测、正式模型或量子真机结果。

## 当前阶段

核心实现、标准 clone 迁移、完整复测、fork 发布和一次官方预检已经完成，当前处于最终 HEAD 核对与 Issue 回执阶段。

- Gate A（L1）：本地完成。OpenQASM 结构化前端、12 门、三目标 IR、参考态矢执行和结果准入均有测试。
- Gate B（L2）：实现与本地真实 HTTP stub 验证完成；尚未在组委会正式 DeepSeek 端点验证。
- Gate C（L3）：本地完成。Hybrid parser、参考解释器、寄存器分配和编译器均有公开与随机穷举验证。
- Gate D（工程/UI）：Python 本地工作台、文档和浏览器 QA 完成；Docker 因当前主机没有可用 Docker 可执行文件而未构建验证。
- Gate E（Bonus）：量子 RISC-V 与新手视觉路径本地完成。
- Gate F（真机）：仅完成安全运行器、runbook 与 dry-run 测试；没有账号、QPU job 或真实结果，未申报。

## 已完成实现

- `adapter.py` 保持四个官方接口的薄入口。
- `loomq/qasm/` 提供 lexer、不可变 AST、parser、语义验证、规范化与序列化，覆盖题面 12 门、多寄存器、参数表达式和测量映射。
- `loomq/targets/` 生成 SpinQ OpenQASM 2、OriginIR 和 Braket OpenQASM 3，并由独立子集解析器做 round-trip 准入。
- `loomq/runtime/` 提供标准库态矢参考模拟器、little-endian 结果归一化与严格 schema 检查。三个 target 的 `run()` 当前都明确报告 `loomq_reference_statevector`，不冒充厂商 SDK 或 QPU。
- `loomq/agent/` 实现一次主模型调用、仅在验证失败时最多一次修复调用的有界工作流；模型候选必须经过确定性 QASM/能力表验证。
- `loomq/hybrid/` 实现 Hybrid-QASM AST、参考解释器、寄存器分配与 Tiny RISC-V 编译。
- `loomq/ui/` 提供仅绑定本机的无 CDN 工作台、三种目标 IR、运行结果可视化、中英文、新手解释、结构化错误和请求级原子证据目录。
- `loomq/bonus/` 提供隔离的 RISC-V `custom-0` 量子指令编码、扩展模拟器与端到端演示，不修改官方 L3 模拟器。
- `loomq/hardware/` 与 `scripts/hardware/` 提供 SpinQ/OriginQ 的安全 dry-run、凭证边界和原子证据契约；只有 `--record` 的真实完整 QPU 响应才允许落证据。
- SCI-Pegasus 只作为架构思想参考，正式实现为 Python clean-room 重写；`.codex_reference/` 不进入依赖或提交。

## 已验证结果

验证解释器：Python **3.10.11 正式解释器**。

| 检查 | 结果 | 证据边界 |
|---|---:|---|
| Python 源文件语法检查 | 78/78 | 只证明所检查源文件可编译 |
| 全部 `unittest` | 119/119 | 本地 Windows / Python 3.10.11 |
| 公开 L1，Bell/GHZ-3 × 3 target | 6/6 | `evidence/files/l1-public-report.json`；公开自测，不是正式分数 |
| QASM 随机 target round-trip | 100 seeds × 3 target | 覆盖题面门集的本地差分 |
| 公开 L2 | 1/1 | 本地 OpenAI-compatible HTTP stub 确实收到了请求；不是正式 DeepSeek |
| 公开 L3 | 1/1 | `evidence/files/l3-public-report.json` |
| Hybrid 随机穷举差分 | 500 programs × 8 measurement assignments | 参考解释器对官方 TinyRISCV 路径，要求终态一致 |
| UI 单元/HTTP 集成 | 9/9 | 真实 loopback socket、证据、可视化与安全边界 |
| 浏览器 QA | 桌面 1440×900、移动 390×844；0 console errors | `evidence/files/ui/browser-qa.json` 与 3 张截图 |
| 量子 RISC-V Bonus | 17/17 | ISA、编码/解码、扩展模拟器、随机差分和 demo |
| 真机准备层 | 23/23 | 全部为 dry-run/证据契约测试；没有网络提交、job ID 或真机结果 |

`baseline-report.json` 保存的是修改前默认 evaluator 0/4 的历史事实，不能与上述当前结果混用。

## Git 与提交状态

- 已恢复标准 clone：`<standard-clone>/`。
- 实现已增量迁入 `<standard-clone>/starter_kit/`，排除参考材料、缓存、凭证和临时工作区；标准 clone 的完整复测为 119/119，公开 L1/L2/L3 与随机差分均通过。
- `main` 已 commit 并 push 到参赛 fork，远端仓库页面已核验更新；最终提交身份仍以实时 GitHub 记录为准，本文不写死会继续变化的提交 SHA。
- 官方 `prepare_submission.py` 已在一个已 push 的干净 HEAD 上完整通过；任何后续 commit 都会改变 HEAD，创建 Issue 前必须对届时的当前 HEAD 再运行。
- 上游 Final Submission Issue 尚未创建，也没有 `submission:accepted`、归档 SHA-256 或 Artifact ID 回执。

## 尚未完成与外部阻塞

1. 确保 Final Submission Issue 引用的完整 SHA 正是最近一次官方预检通过且已 push 的干净 HEAD；HEAD 变化后必须重跑。
2. 创建上游 Final Submission Issue，并等待 `submission:accepted` 标签、归档 SHA-256 与 Artifact ID；只有该回执出现才算最终提交成功。
3. 在有 Docker 的 Python 3.10/Linux 环境完成 `docker build --no-cache` 与默认 CMD 验证；当前主机没有 Docker。
4. 在正式 `deepseek-v4-flash` 注入环境验证 L2。当前只验证了真实本地 HTTP 传输、工作流、超时与错误路径。
5. 由账号持有人取得 SpinQ/OriginQ 真实 QPU 权限并运行 `--record`。当前没有任何可申报硬件证据。

## 当前不得宣称

- 不得从公开 6/6、1/1、1/1 推导隐藏评测通过、正式得分或最高奖。
- 不得把本地 HTTP stub 写成正式 DeepSeek 结果。
- 不得把 LoomQ 参考模拟器、硬件 dry-run 或厂商方言输出写成厂商 SDK、云任务或 QPU 运行。
- 不得宣称 Docker 已构建验证。
- 不得把已 push 或预检通过写成赛事已接收，也不得在 Final Submission Issue 获得自动回执前宣称赛事提交成功。
- 不得宣称 SCI-Pegasus 具有未获书面依据的开源许可证。

## 下一步

1. 从 fork 根目录对最终 HEAD 运行 `python starter_kit/prepare_submission.py --team-id xinruliuresearch-maker`，确认其完整 SHA 已 push 且预检通过。
2. 用该 SHA 创建最终 Issue，并核对自动回执。
3. 在可用环境补 Docker 冷构建；若截止前不可用，如实保留未验证状态。
4. 真机或正式模型证据只有真实完成后再更新。
