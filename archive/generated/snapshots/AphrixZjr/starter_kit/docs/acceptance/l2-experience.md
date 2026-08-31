# L2 交互体验验收说明

本文专门说明评委可现场执行的 L2 交互任务；截图仅说明流程，现场运行的最终代码才是判定依据。

## 启动与入口

- 推荐命令：在 `starter_kit/` 运行 `docker compose up --build`。
- 快速本地命令：在依赖已安装时运行 `python web/server.py`。
- 页面地址：`http://127.0.0.1:8765`。
- 健康检查：`http://127.0.0.1:8765/api/health`。

## 三项现场任务

- Bell 新手路径：在评测环境注入模型配置后点击“开始 Bell 引导”；每阶段点击“填入本阶段指令”，确认 Agent 输入框获得焦点且实验尚未改变，再发送并按八阶段完成目标、H、CX、测量、预测、验证、本地 1024 条教学计数和结果解释。核对主要结果为 `00/11`，并指出界面没有把单一 Z 基测量说成纠缠认证。
- QASM 恢复：在编辑器制造缺少分号的错误，依次执行检查、修复预览、应用修复和撤销；确认错误不会破坏最后有效电路，修改前可看到 diff。
- 后端比较：打开“运行位置”，比较内置执行器与 SpinQit、pyQPanda、AWS Braket 本地模拟器；确认缺 SDK 或云端条件不会阻断内置本地流程，且界面没有把本地模拟器称作真机。
- 真机复盘：打开“真机复盘”，同时比较 Bell 与 GHZ-3 的 Ideal、SpinQ、OriginQ 三组计数、主峰、泄漏、job ID 和时间；确认页面明确标注“已归档”且不会连接云平台或新建任务。

## 评委应观察的产品行为

- Agent 从首次加载即可输入，并显示已配置、未配置、本地预置回退或失败；未配置时不伪造模型回复。
- 顶部阶段按钮只填入当前预设并把焦点移到 Agent，不直接调用 `/advance`、修改 revision 或推进电路。
- Bell 当前阶段的精确预设在模型缺失或调用失败时仍由同一本地确定性工具推进；未配置时标注“本地预置回复｜未调用模型”，已经尝试连接或生成但失败时标注“本地预置回复｜非模型生成”。自由问答、改写指令和未来阶段指令不会使用该回退。
- 每次 Agent 阶段请求绑定发送时的阶段与只增 `workbench_revision`；等待模型期间工作台被修改或两个相同阶段请求并发时，旧请求以 stale conflict 结束。确定性阶段工具自身失败时不重试，也不冒充预置回退。
- 一般问答携带当前工作区和最近对话上下文；写操作经工具或结构化提案，本地验证后才应用。
- 结构验证是运行和 QASM 提案的硬安全门：经典位写入覆盖等测量冲突会令 `runnable=false`、`safe_to_apply=false`，服务端也会拒绝绕过界面的运行或应用。仅目标语义不一致时允许探索电路，但运行快照和结论边界必须显示“本次运行不支持当前目标”。
- 运行结果是不可变快照；后续编辑不会改写既有结果。
- 页面提供可见焦点、读屏等价文本、图表等价表格、减少动态和色觉辅助开关。
- 在 1366×768、1280×720、1024 宽与 200% 缩放下页面可滚动且主要控件不被裁切；同时复核键盘全流程和系统 reduced motion。

## Agent-first 与预置回退的权衡

正常评测路径以组委会注入的模型为准：用户从同一个 Agent 对话框发送阶段指令，模型只能调用当前阶段工具一次，并根据工具的真实结果解释。回退不是第二套用户流程；它只在当前精确预设已经从同一对话框发送、但模型未配置、连接失败或响应无效时生效。服务端执行相同工具并选择随代码发布的阶段回复；若工具已经执行而模型只在解释阶段断线，则只补本地回复，不会重复推进。响应同时公开 `model_attempted` 与 `model_generated`，避免把“模型调用失败”误写为“从未调用模型”。

设计目的，是避免一个“直接执行”按钮与 Agent 争夺视觉焦点和操作心智，同时不让外部模型故障使现场演示完全中断。权衡也明确：回退回复不是实时生成，不能适应自由问题，不代表 Agent 已连接。界面以独立 fallback 状态和回复正文双重标注这一边界。

## 支撑材料

- 历史流程截图：`evidence/files/l2-ui-workbench.png`、`evidence/files/l2-ui-guide.png`、`evidence/files/l2-ui-bell-results.png`。它们由提交人在 2026-08-11 基于当时冻结代码人工截取，分别展示自由工作台、已配置模型连接下的 Agent-first Bell 引导和 Bell 完成结果；截图只证明当时视觉流程，不替代当前 benchmark 或评委现场运行。当时源码的真实模型结果归档为 [`l2-live-benchmark-current.json`](../../evidence/files/l2-live-benchmark-current.json)（12/12）与 [`l2-raw-prompt-stress-current.json`](../../evidence/files/l2-raw-prompt-stress-current.json)（72/72），不得归因于 2026-08-15 的预算/语义修复。图中的 Agent 自由文本由外部模型即时生成，不作为项目科学结论；单一 Z 基结果只能说明与理想预测一致、不能认证纠缠等边界以本页验收口径为准。
- 当前源码真实模型验证：12-case smoke 12/12，三轮 runner [312/312](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.json)，公开 evaluator [1/1](../../evidence/files/evaluator-l2-remediation-20260815.json)；[raw stdout](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.stdout.txt) 与 JSON 的哈希绑定已复核，artifact 未记录模型环境值。
- 响应式检查脚本 [`browser_responsive_check.mjs`](../../browser_responsive_check.mjs) 覆盖四种视口；[`browser-responsive-current.json`](../../evidence/files/browser-responsive-current.json) 是 2026-08-11 历史记录，当前源码本地 4/4 结果见 [`verification.md`](verification.md)。
- Agent-first 无模型交互检查：[`browser_agent_flow_check.mjs`](../../browser_agent_flow_check.mjs) 覆盖八次发送、验证、运行、结果表、结论边界、删除 CX 和撤销；已归档结果文件对应旧源码时只作历史记录，当前提交应在 CI 或验收机重跑脚本。
- 自动测试：`python -m unittest tests.test_l2_web tests.test_l2_audit_regressions -v`；L2 客观契约另见 `tests.test_l2_agent` 和 `tests.test_l2_contract`。
