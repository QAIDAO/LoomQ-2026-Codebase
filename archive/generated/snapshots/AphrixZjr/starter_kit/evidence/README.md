# LoomQ 人工评分证据

本文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目；截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。所有结论以当前项目代码为准；开发计划、设计稿和早于对应阶段末次代码提交生成的材料不作为证据。文档分区规则见 [`docs/README.md`](../docs/README.md)。

## 得分项—实现—证据索引

| 得分项 | 当前实现 | 可复现证据与口径 |
| --- | --- | --- |
| L1 三平台软件契约 | [`loomq_l1.py`](../loomq_l1.py) 的统一 parser/IR，三个 `l1_*` SDK 适配器 | 2026-08-11 accepted 归档中的 Docker 三平台扩展回归 93/93：[`l1-regression-current.txt`](files/l1-regression-current.txt)；公开 evaluator 6/6：[`evaluator-l1-current.txt`](files/evaluator-l1-current.txt)。当前源码的完整三平台结果由 cold-build CI 复核 |
| L1 真机 | `l1_originq_hardware.py` 与 `l1_spinq_hardware.py` 的确认、凭证隔离、恢复、位序规范化和脱敏路径 | 申报 OriginQ 与 SpinQ 两个真机平台；各四个可追溯 job 的实际程序、结果与摘要见下文，不把任何本地模拟器计作真机 |
| L2 客观 Agent | [`loomq_l2.py`](../loomq_l2.py) 的有限 schema、本地证据约束、完整测量与目标校验，以及累计 attempt/retry/repair/token 预算；[`llm_client.py`](../llm_client.py) 只负责 transport、timeout、response bytes 和单次 output cap | 当前源码离线全量 268/268；2026-08-16 CST 真实模型三轮 [312/312](files/l2-raw-prompt-stress-remediation-20260815.json)，公开 evaluator [1/1](files/evaluator-l2-remediation-20260815.json)。2026-08-11 accepted 结果作为历史基线单独保留 |
| L3 混合编译 | [`loomq_l3.py`](../loomq_l3.py) 的 AST→线性表达式 lowering→标签汇编→官方模拟器路径 | 固定种子差分、嵌套分支、负常量、重复项、全寄存器终态测试：[`test_l3_differential.py`](../tests/test_l3_differential.py)；当前源码公开 evaluator 1/1。链接的 [`evaluator-l3-current.txt`](files/evaluator-l3-current.txt) 是 2026-08-11 历史 artifact |
| 工程与产品化 | 同一 [`Dockerfile`](../Dockerfile) 构建 L1/L2/L3/Bonus；[`compose.yaml`](../compose.yaml) 默认启动 Web；测试全部位于正式归档 | 当前源码本地回归 268/268、仓库级 294/294；可复现记录见 [当前验证清单](files/remediation-20260816/verification-manifest.json)。2026-08-11 旧镜像与 artifact 哈希见 [`verification-manifest.json`](files/verification-manifest.json)，cold-build workflow 的远端记录由 CI 补充 |
| 自定义量子 RISC-V Bonus | 官方 [`riscv_emulator.py`](../riscv_emulator.py) 直接公开 custom opcode 汇编、解码与执行；[`quantum_riscv.py`](../quantum_riscv.py) 仅为兼容导入 | 编码规格 [`loomq_qisa_v1.md`](../docs/loomq_qisa_v1.md)；官方入口 E2E [`test_quantum_riscv_e2e.py`](../tests/test_quantum_riscv_e2e.py)，结果包含在全量日志中 |
| L2 交互与新手 Bonus | [`web/`](../web/) 的 Agent-first Bell 八阶段、显式预置离线回退、提案确认、结构安全 gate、目标语义边界、真机证据只读复盘和可访问结果视图 | Web/审计回归、完整八阶段脚本 [`browser_agent_flow_check.mjs`](../browser_agent_flow_check.mjs) 与四视口脚本 [`browser_responsive_check.mjs`](../browser_responsive_check.mjs)；当前源码以 Edge 151/CDP 验证 22/22 与 4/4，2026-08-11 结构化 JSON 作为历史记录保留 |

本表是证据导航，不是保证得分。主观项仍以评委现场运行和赛事规则为准。

## 申报项目

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## 证据来源与时间

- 2026-08-11 accepted 周期的 SpinQ 源码冻结提交 S 为 `60af4a954e0058331a41e085bf252f93c39c0eac`。真机、live benchmark 与说明先形成仅文档/证据的干净基线 P，再在 P 上运行生成器并以仅证据提交 E 归档；manifest 的 `repository.head` 是证据写入前的 P，P 的可执行源码与 S 相同。最终以 manifest 的 `dirty == false`、`success == true` 为准，并用 `git diff --name-only S..E` 确认没有可执行源码变化。
- OriginQ 真机证据归档于 `3457ec3`（2026-08-03 14:19:16 +08:00），晚于对应 OriginQ 真机实现末次提交 `24980d3`（2026-08-03 14:09:00 +08:00）；平台任务时间来自原始响应。
- SpinQ 真机任务于 2026-08-11 在当前实现完成专项回归后执行；标准摘要的 `timestamp` 来自只读 task 查询的 provider `createdTime`，原始脱敏 JSON 继续保留客户端提交/完成或只读恢复时间。`S-260811-0003` 在首次本地规范化失败后只读恢复归档，没有重复提交。
- 三张 L2 截图由提交人在 2026-08-11 基于当时冻结代码人工截取，分别展示自由工作台、已配置模型连接下的 Agent-first Bell 引导和 Bell 完成结果。截图只证明当时视觉流程，不替代当前自动测试、新 live benchmark、结构化浏览器记录或评委现场运行；其中 Agent 自由文本由外部模型即时生成，不作为项目的确定性科学结论，单一 Z 基测量不能认证纠缠等正式边界以验收说明和本地确定性证据为准。
- 历史 live benchmark 使用提交人自行配置的模型连接在源码 S 上执行；仓库只记录模型名、用例、通过情况和计时，不记录 API Key、服务地址、Token 或账户信息。该旧源码上 12-case 通过 12/12、72-case 并发压力通过 72/72；不能把它们归因于 2026-08-15 的 L2 改动。
- 当前源码先完成 12-case smoke 12/12，再于 2026-08-16 CST（机器记录 `2026-08-15T16:12:26.094379+00:00`）完成三轮 312/312，随后公开 L2 evaluator 1/1。三轮 [JSON](files/l2-raw-prompt-stress-remediation-20260815.json) SHA-256 为 `898f7aaeb3597f528bc52c71794247ea9753275a04e6a7d0f40a653814d8e5de`，并绑定 [raw stdout](files/l2-raw-prompt-stress-remediation-20260815.stdout.txt) 的 34,979 bytes 与 SHA-256 `86425ed86c0b290d2ab0eaf639430e89a842746c1e14294012f3f698d69fe494`；[evaluator JSON](files/evaluator-l2-remediation-20260815.json) SHA-256 为 `2319e0de465ea473b9127626d98f12772546564c078fdaeacc32dd56071a3b37`。模型凭证仅通过进程环境注入，三份 artifact 未记录环境值，逐值扫描为 0 命中。
- 当前代码的专用验收说明位于 `docs/acceptance/`；`docs/development/` 中的计划、设计、ADR 和阶段材料不在下文引用。
- 当前测试与浏览器验收结论：[`docs/acceptance/verification.md`](../docs/acceptance/verification.md)。

## L1 真机：SpinQ Cloud（triangulum_vp）

- 申报范围：SpinQ 三比特真机，作为 OriginQ 之外的第二个真机平台。
- 任务总量：2026-08-11 完成 Bell、测量映射探针和 GHZ-3 共 4 个任务，合计 16,584 shots。
- 时间口径：下表与四份标准摘要使用只读 task 查询的 `createdTime`（UTC）；客户端提交/完成和恢复时间只作为原始脱敏记录中的辅助时间。

| 阶段/电路 | 平台 job ID | 平台创建时间（UTC） | shots | 验证结果 |
| --- | --- | --- | ---: | --- |
| 冒烟 Bell | `S-260811-0002` | `2026-08-11T06:36:03.268Z` | 100 | `00/11` 预期支撑率 0.94 |
| 冒烟 `bit_order` | `S-260811-0003` | `2026-08-11T06:37:20.476Z` | 100 | 99/100 为 LoomQ bit order 下的 `011`；既有 job 只读恢复 |
| 正式 Bell | `S-260811-0004` | `2026-08-11T06:44:30.049Z` | 8192 | `00/11` 预期支撑率 0.808837890625 |
| 正式 GHZ-3 | `S-260811-0005` | `2026-08-11T06:45:47.257Z` | 8192 | `000/111` 预期支撑率 0.85498046875 |

- 冒烟 Bell：[source QASM](files/hardware/spinq/spinq-smoke-bell-S-260811-0002-source.qasm)、[submitted QASM](files/hardware/spinq/spinq-smoke-bell-S-260811-0002-submitted.qasm)、[request](files/hardware/spinq/spinq-smoke-bell-S-260811-0002-request.json)、[原始脱敏结果](files/hardware/spinq/spinq-smoke-bell-S-260811-0002-raw.json)、[标准摘要](files/hardware/spinq/spinq-smoke-bell-S-260811-0002-summary.json)。
- 冒烟 `bit_order`：[source QASM](files/hardware/spinq/spinq-resume-bit_order-S-260811-0003-source.qasm)、[submitted QASM](files/hardware/spinq/spinq-resume-bit_order-S-260811-0003-submitted.qasm)、[request](files/hardware/spinq/spinq-resume-bit_order-S-260811-0003-request.json)、[原始脱敏结果](files/hardware/spinq/spinq-resume-bit_order-S-260811-0003-raw.json)、[标准摘要](files/hardware/spinq/spinq-resume-bit_order-S-260811-0003-summary.json)。
- 正式 Bell：[source QASM](files/hardware/spinq/spinq-formal-bell-S-260811-0004-source.qasm)、[submitted QASM](files/hardware/spinq/spinq-formal-bell-S-260811-0004-submitted.qasm)、[request](files/hardware/spinq/spinq-formal-bell-S-260811-0004-request.json)、[原始脱敏结果](files/hardware/spinq/spinq-formal-bell-S-260811-0004-raw.json)、[标准摘要](files/hardware/spinq/spinq-formal-bell-S-260811-0004-summary.json)。
- 正式 GHZ-3：[source QASM](files/hardware/spinq/spinq-formal-ghz3-S-260811-0005-source.qasm)、[submitted QASM](files/hardware/spinq/spinq-formal-ghz3-S-260811-0005-submitted.qasm)、[request](files/hardware/spinq/spinq-formal-ghz3-S-260811-0005-request.json)、[原始脱敏结果](files/hardware/spinq/spinq-formal-ghz3-S-260811-0005-raw.json)、[标准摘要](files/hardware/spinq/spinq-formal-ghz3-S-260811-0005-summary.json)。
- 平台任务字段：[四项只读 task 元数据](files/hardware/spinq/spinq-task-metadata.json)。
- 数据说明：SpinQ Cloud 返回量子位顺序的概率分布；四份标准摘要均以确定性最大余数法还原到精确 shots，再按 request 中的 `measurement_map` 投影到 LoomQ classical bit order（包括旧 Smoke Bell 摘要）。原始概率与 SDK counts 未被改写，保留在 `-raw.json`；旧 `.json`/`.qasm` 路径作为既有 manifest 的逐字节兼容副本保留，新的 canonical 引用均指向 `-raw.json`/`-submitted.qasm`。证据不包含用户名、私钥路径或账户信息。source/submitted QASM、request、raw 与 summary 通过文件名和 SHA-256 互相绑定。
- 平台快照：仓库没有保存 `triangulum_vp` 的只读平台能力快照，因此不申报 `simu`、`max_bitnum`、在线机器数或支持门列表；这些字段须在有权访问平台时通过只读查询补录。
- 方向探针待补：[`bit_order_direction.qasm`](../circuits/bit_order_direction.qasm) 已作为 opt-in 单任务输入准备，预期 classical key `100`，但它不在上述四项任务中，当前没有对应真机 job、raw 结果或 summary。未来只能用 `run_spinq_hardware.py submit-one --circuit bit_order_direction --shots 100 --confirm-submit SPINQ_HARDWARE` 显式提交一次，并在已有 job ID 时改用 `resume`，不得把离线电路当作真机证据。
- 计分口径待确认：当前 `problem_statement.md` 将 SpinQ 路径写成“超导真机”，而 `backend_capabilities.json` 允许“超导 / 核磁”；`triangulum_vp` 的既有任务事实属于核磁真机。仓库没有组委会书面确认，因此 `submission:accepted` 不能被解释为该物理路线已确定获得平台真机 +5。提交人仍需向组委会确认：“`spinq_cloud_qpu` 的 `triangulum_vp` 核磁真机可否按每个平台真机 +5 计分？”
- 支撑率解释与机器可读统计见 [`spinq-hardware-analysis.json`](files/hardware/spinq/spinq-hardware-analysis.json)：正式 Bell 的 Wilson 95% 区间为 `[0.800179, 0.817208]`，高于二态理想支撑的均匀基线 0.5；正式 GHZ-3 为 `[0.847189, 0.862439]`，高于二态理想支撑的均匀基线 0.25。两者的理想态仍是主要峰值，GHZ-3 理想支撑内部 `000/111` 比例为 0.50257/0.49743。
- 优化与解释：现有 `bit_order` 任务达到 99/100，支持归档的 `q→c` permutation 与当前投影结果一致；但其制备物理态是回文 `101`，不能单独区分 provider raw key 的两种整体反转方向，因此不作为方向性位序证明。已安装 SDK 明示 `triangulum_vp` 不支持自定义物理布局，没有可依据公开能力实施的 qubit-pair 重映射。归档结果未采用事后读出缓解、后选择或补跑挑样；Bell/GHZ 泄漏可合理归入多比特门路径与硬件噪声，但仅凭这些 Z 基分布不能进一步认证纠缠或相干性。

## L1 真机：OriginQ QCloud（WK_C180）

- 申报范围：OriginQ 悟空真机；与上方 SpinQ 一并申报两个真机平台，AWS Braket 未运行真机。
- 任务总量：2026-08-03 完成 Bell、非对称位序探针和 GHZ-3 共 4 个任务，合计 16,584 shots。
- 时间口径：下表时间来自平台原始响应 `sdk_response.origin_data.obj.startTime`；`qpuRunTime` 保留平台原值。

| 阶段/电路 | 平台 job ID | 平台开始时间（UTC） | shots | `qpuRunTime` | 验证结果 |
| --- | --- | --- | ---: | ---: | --- |
| 冒烟 Bell | `9F1D641D6D92B2B8FACD91AD3F760FFD` | `2026-08-03T05:54:04.697Z` | 100 | 39 | `00/11` 预期支撑率 1.0 |
| 冒烟 `bit_order` | `C5EFF0A8FD0C1CC603C0AEDA3DB3AF5F` | `2026-08-03T06:11:33.454Z` | 100 | 39 | 100/100 为 LoomQ bit order 下的 `011` |
| 正式 Bell | `21E79A08CED67A08B9FFB8DC109DABD8` | `2026-08-03T06:13:12.360Z` | 8192 | 1705 | `00/11` 预期支撑率 1.0 |
| 正式 GHZ-3 | `5F5EB24ADDB266E77E8A52A478D8AAF2` | `2026-08-03T06:13:28.939Z` | 8192 | 1662 | `000/111` 预期支撑率 0.9974365234375 |

- 冒烟 Bell：[QASM](files/hardware/originq/originq-bell-9F1D641D6D92B2B8FACD91AD3F760FFD.qasm)、[OriginIR](files/hardware/originq/originq-bell-9F1D641D6D92B2B8FACD91AD3F760FFD.originir)、[平台原始结果](files/hardware/originq/originq-bell-9F1D641D6D92B2B8FACD91AD3F760FFD-raw.json)、[标准摘要](files/hardware/originq/originq-bell-9F1D641D6D92B2B8FACD91AD3F760FFD-summary.json)。
- 冒烟 `bit_order`：[QASM](files/hardware/originq/originq-bit_order-C5EFF0A8FD0C1CC603C0AEDA3DB3AF5F.qasm)、[OriginIR](files/hardware/originq/originq-bit_order-C5EFF0A8FD0C1CC603C0AEDA3DB3AF5F.originir)、[平台原始结果](files/hardware/originq/originq-bit_order-C5EFF0A8FD0C1CC603C0AEDA3DB3AF5F-raw.json)、[标准摘要](files/hardware/originq/originq-bit_order-C5EFF0A8FD0C1CC603C0AEDA3DB3AF5F-summary.json)。
- 正式 Bell：[QASM](files/hardware/originq/originq-bell-21E79A08CED67A08B9FFB8DC109DABD8.qasm)、[OriginIR](files/hardware/originq/originq-bell-21E79A08CED67A08B9FFB8DC109DABD8.originir)、[平台原始结果](files/hardware/originq/originq-bell-21E79A08CED67A08B9FFB8DC109DABD8-raw.json)、[标准摘要](files/hardware/originq/originq-bell-21E79A08CED67A08B9FFB8DC109DABD8-summary.json)。
- 正式 GHZ-3：[QASM](files/hardware/originq/originq-ghz3-5F5EB24ADDB266E77E8A52A478D8AAF2.qasm)、[OriginIR](files/hardware/originq/originq-ghz3-5F5EB24ADDB266E77E8A52A478D8AAF2.originir)、[平台原始结果](files/hardware/originq/originq-ghz3-5F5EB24ADDB266E77E8A52A478D8AAF2-raw.json)、[标准摘要](files/hardware/originq/originq-ghz3-5F5EB24ADDB266E77E8A52A478D8AAF2-summary.json)。
- 数据说明：平台返回概率分布，原始 JSON 明示 `result_kind: probabilities`；摘要 counts 由概率与 shots 用确定性最大余数法换算，并非逐 shot 原始数据。证据不包含 token、账户信息或本地凭证。

## L2 交互体验

- 启动命令：在 `starter_kit/` 运行 `docker compose up --build`；已安装依赖时也可运行 `python web/server.py`。
- 页面入口：`http://127.0.0.1:8765`；健康检查：`http://127.0.0.1:8765/api/health`。
- 现场任务与观察点：[`docs/acceptance/l2-experience.md`](../docs/acceptance/l2-experience.md)。
- 当前实拍：[自由工作台](files/l2-ui-workbench.png)、[Agent-first Bell 引导](files/l2-ui-guide.png)、[Bell 运行结果](files/l2-ui-bell-results.png)。截图的采集边界见上文，只用于说明产品流程。
- 自动验证：`python -m unittest tests.test_l2_agent tests.test_l2_contract tests.test_l2_web tests.test_l2_audit_regressions tests.test_l2_budget tests.test_l2_benchmark -v` 为 115/115；该入口同时覆盖累计预算与 benchmark runner。旧归档全量输出见 [`unittest-current.txt`](files/unittest-current.txt)，当前完整计数见 [`verification.md`](../docs/acceptance/verification.md)。
- 真实模型结果：2026-08-11 冻结源码上的 12/12 与旧版 72/72 分别见 [`l2-live-benchmark-current.json`](files/l2-live-benchmark-current.json) 和 [`l2-raw-prompt-stress-current.json`](files/l2-raw-prompt-stress-current.json)。当前 runner 的复现入口为 `python experiments/l2_raw_prompt_stress.py --rounds 3 --workers 4 --json-out <JSON> --stdout-out <RAW>`；实测 312/312，三轮各 104/104，fixed/generate/repair/backend/backend-adversarial 分别为 36/72/72/72/60 全通过，见 [结构化报告](files/l2-raw-prompt-stress-remediation-20260815.json) 与 [原始 stdout](files/l2-raw-prompt-stress-remediation-20260815.stdout.txt)。共 329 次成功且有效的模型响应，0 HTTP retry、0 canonical recovery，单 case 最大输入/输出为 886/230；公开 evaluator [1/1](files/evaluator-l2-remediation-20260815.json)。
- 浏览器验证：当前源码以 Edge 151/CDP 实跑 [`browser_responsive_check.mjs`](../browser_responsive_check.mjs) 4/4 视口和 [`browser_agent_flow_check.mjs`](../browser_agent_flow_check.mjs) 22/22 检查，覆盖真机复盘完整性、八阶段、验证、运行、结果边界、删除 CX 与撤销，且无运行时错误；仓库中的 `*-current.json` 是 2026-08-11 历史记录。

## 工程与产品化

- 干净环境的一键构建与启动：在 `starter_kit/` 运行 `docker compose up --build`。
- 架构说明：[`docs/acceptance/architecture.md`](../docs/acceptance/architecture.md)，专门描述当前代码边界与数据流。
- 目标用户、门槛降低方式与完整流程：[`docs/acceptance/productization.md`](../docs/acceptance/productization.md)。
- 主操作手册：[`README.md`](../README.md) 与 [`web/README.md`](../web/README.md)。
- 历史全量回归：2026-08-11 归档内为 233/233，仓库根为 259/259。隔离用例会只复制 `starter_kit/` 并在副本中重跑；当前源码精确计数见 [`verification.md`](../docs/acceptance/verification.md)。
- 可复现清单：[`generate_verification_manifest.py`](../generate_verification_manifest.py) 记录 Git、环境、命令、返回码、日志 SHA-256 和关键 artifact SHA-256；[当前验证清单](files/remediation-20260816/verification-manifest.json)与 [2026-08-11 accepted 清单](files/verification-manifest.json)分别保存。

## 自定义量子 RISC-V Bonus

- 实现理由与各字段简述：[`docs/acceptance/bonus-rationale.md`](../docs/acceptance/bonus-rationale.md)。
- 指令编码规格：[`docs/loomq_qisa_v1.md`](../docs/loomq_qisa_v1.md)，定义 32 位 custom opcode、12 种门、量子提交/读取与 Q16.16。
- 模拟器扩展实现：官方 [`riscv_emulator.py`](../riscv_emulator.py) 直接承载 `assemble()`、`decode()` 和 `QuantumRISCVEmulator`；[`quantum_riscv.py`](../quantum_riscv.py) 仅保留旧 API 的兼容导入。
- 端到端测试：归档内的 [`tests/test_quantum_riscv_e2e.py`](../tests/test_quantum_riscv_e2e.py)；在 `starter_kit/` 内运行 `python tests/test_quantum_riscv_e2e.py -v`。

## 新手引导与视觉叙事 Bonus

- 实现理由与各字段简述：[`docs/acceptance/bonus-rationale.md`](../docs/acceptance/bonus-rationale.md)。
- 零基础首次运行指南：[`web/README.md`](../web/README.md) 与 [`web/static/index.html`](../web/static/index.html) 的可选八阶段 Bell 引导。
- 量子概念解释：[`web/app.py`](../web/app.py) 的指导文案及 [`web/static/index.html`](../web/static/index.html) 的解释视图。
- 结果可视化：[`web/static/app.js`](../web/static/app.js) 的计数柱状图、等价数据表、shots 摘要和结论边界；当前流程实拍见 [Bell 结果](files/l2-ui-bell-results.png)。
- 错误恢复与无障碍：[`web/app.py`](../web/app.py)、[`web/server.py`](../web/server.py)、[`web/static/styles.css`](../web/static/styles.css) 及归档内的 [`tests/test_l2_web.py`](../tests/test_l2_web.py)、[`tests/test_l2_audit_regressions.py`](../tests/test_l2_audit_regressions.py)。

## 提交规则

- 所有材料必须进入截止前的最终提交；任何代码变更后，应重新生成受影响的验收记录和截图。
- 外部视频可使用稳定只读链接；源码、原始结果和复现命令保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，最终提交 Issue 的 `Hardware evidence` 字段填写 `starter_kit/evidence/README.md`。
- 当前源码已完成真实模型三轮 312/312、公开 L2 evaluator 1/1 和本地全量回归。外部待办包括：取得核磁计分书面确认；有凭证时只读补平台快照并执行或恢复一次方向探针；取得 Linux cold-build CI 记录；以实际 GitHub 用户名运行 `prepare_submission.py --team-id <GITHUB_USERNAME>`、创建新 Issue 并等待 accepted 归档回执。完整口径见 [`verification.md`](../docs/acceptance/verification.md)。
