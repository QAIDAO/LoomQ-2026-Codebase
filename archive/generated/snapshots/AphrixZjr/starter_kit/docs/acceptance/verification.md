# 当前验收记录

> 本页分列 2026-08-16 当前源码验证与 2026-08-11 accepted 历史记录；旧 manifest、live benchmark、Docker image 和浏览器 JSON 只对应历史源码。

## 2026-08-16 当前源码验证

- 完整离线回归：在 `starter_kit/` 运行 `python -m unittest discover -s tests -v` 为 268/268；在仓库根运行同名命令为 294/294。L2 的 Agent、契约、Web、审计、预算与 benchmark 六模块专项入口为 115/115。
- SpinQ：四个既有 task 各有 `source/submitted/request/raw/summary` 五件套；公共结果 Schema、provider 时间戳、哈希、测量映射和请求/provider shots 绑定均进入回归。旧 `.json`/`.qasm` 原路径保持兼容。真正方向非对称的 [`bit_order_direction.qasm`](../../circuits/bit_order_direction.qasm) 仅为 opt-in 输入，当前没有真机 job 或结果。
- L2：累计上限为 3 次 transport attempt、一次瞬态 retry、8,000 输入和 2,000 输出 Token，单次默认 900/上限 1,000；每次 `max_tokens` 会在 transport 前收缩到累计输出剩余额度，余额为零不再发请求。无 usage 时输入按 UTF-8 字节上界、输出按实际请求 cap 预留。凭证通过进程环境注入后，12-case live smoke 12/12；固定 12 + 压力 72 + adversarial 20 的三轮 [312/312](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.json)，每轮 104/104；[raw stdout](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.stdout.txt) SHA-256 绑定有效，公开 L2 evaluator [1/1](../../evidence/files/evaluator-l2-remediation-20260815.json)，artifact 未记录环境值。
- L3：`classical_width <= 21` 使用单份共享 CFG；width 22 在入口按 `c[21]` 特化为两条共享 CFG 路径并在退出前恢复 `x31`；width > 22 因无法映射到 `x10..x31` 而在生成汇编前硬拒绝。20 个顺序 `if` 的 width-22 压力结果为 1,021 行、16,494 字节；深度 4 为 700 行、10,819 字节，均通过全测量组合差分和执行步数门禁。
- Web：服务端重新验证结构安全后才允许 run/apply，测量 collision 硬拒绝，目标不一致只允许带明确边界的探索运行。真机复盘只读取四份正式摘要的精确白名单，公共 Schema 与任务身份校验失败会显示不完整。Edge 151/CDP 本地验证响应式 4/4、完整流程 22/22，覆盖八阶段、真机复盘完整性、验证、运行、结果边界、删除 CX、撤销及零运行时错误。
- 工程检查：Python `py_compile`、三个 JavaScript `node --check`、`docker compose config --quiet`、`actionlint` 和 `git diff --check` 均通过。[Linux cold-build workflow](../../../.github/workflows/starter-kit-cold-build.yml) 在镜像构建期限制仅四份非敏感 formal summary；一次性容器测试进程把 checkout 的完整 `evidence/` 只读挂载为测试 fixture，以运行 268 项完整套件，随后不带挂载启动最终镜像并断言 Bell/GHZ 都含 Ideal、SpinQ、OriginQ。raw/request/QASM 不进入镜像。本机没有可用 Docker daemon，远端 cold-build 结果由 Actions 提供。
- 可复现清单：[当前验证清单](../../evidence/files/remediation-20260816/verification-manifest.json)；该清单记录源码提交、运行前干净状态、命令返回码、原始日志与 live/SpinQ artifact 哈希。2026-08-11 accepted 清单继续单独保留。
- 环境限定复现：L3 public evaluator 1/1 通过。L1 public evaluator 在本机仅 SpinQ 2/2 通过，OriginQ 与 Braket 4 项因缺少锁定的 pyQPanda/Braket SDK 明确失败；同理，三平台 L1 regression 仅 SpinQ 与 reference 31/93 通过，另外 62 项按缺失 SDK 失败。完整 evaluator 6/6 与 regression 93/93 必须由新容器 CI 证明，不能引用旧镜像替代。
- 外部待办：组委会书面确认 `triangulum_vp` 核磁真机的 +5 口径；有 SpinQ 凭证时只读补 platform snapshot 并执行或恢复一次方向探针；取得 cold-build CI 记录；运行 `prepare_submission.py` 并等待新 Issue accepted。

## 2026-08-11 accepted 归档（历史记录）

- 记录日期：2026-08-11；机器生成的精确 UTC 时间以 [`verification-manifest.json`](../../evidence/files/verification-manifest.json) 为准。
- Git 身份采用可实现的两阶段口径：SpinQ 可执行源码冻结提交 S 为 `60af4a954e0058331a41e085bf252f93c39c0eac`；真机、live benchmark 与说明形成仅文档/证据的干净基线 P，在 P 上生成机器日志，再以仅证据提交 E 归档。manifest 的 `repository.head` 是证据写入前的 P，P 的可执行源码与 S 相同；最终应满足运行前 `dirty == false`、`success == true`，并用 `git diff --name-only S..E` 确认没有可执行源码变化。
- 正式归档内全量回归：在 `starter_kit/` 运行 `python -m unittest discover -s tests -v`，233/233 通过；其中归档隔离测试会把单独的 `starter_kit/` 复制到临时目录并在副本内重跑同一套测试。原始合并输出见 [`unittest-current.txt`](../../evidence/files/unittest-current.txt)。
- 仓库级回归：在仓库根运行 `python -m unittest discover -s tests -v`，通过归档测试 wrapper、官方包导入契约与 organizer intake 测试共 259/259，原始输出见 [`repository-unittest-current.txt`](../../evidence/files/repository-unittest-current.txt)。
- 三平台 L1 扩展回归：统一 Docker 镜像中 93/93 通过，见 [`l1-regression-current.txt`](../../evidence/files/l1-regression-current.txt)。
- 公开 evaluator：统一镜像内 L1 三平台 6/6、L3 1/1，分别见 [`evaluator-l1-current.txt`](../../evidence/files/evaluator-l1-current.txt) 与 [`evaluator-l3-current.txt`](../../evidence/files/evaluator-l3-current.txt)。
- Python/JavaScript/Compose/Git：`python -m compileall -q competition starter_kit`、`node --check` 三个当前脚本、`docker compose config --quiet` 和 `git diff --check` 均通过；各命令的当前日志与哈希均进入 manifest。
- Docker：`docker compose build` 成功；精确镜像 ID 以机器生成的 [`docker-image-current.txt`](../../evidence/files/docker-image-current.txt) 与 manifest 为准，避免把镜像自身的可变 ID 硬编码进构建上下文。Dockerfile 默认 Web CMD、Compose 与 healthcheck 一致；实际启动后 `/api/health` 为 `ok`，三个本地 SDK 均为 connected。
- 浏览器响应式验收：Edge headless/CDP 在 1366×768、1280×720、1024 CSS px 与 200% 缩放等价视口下检查页面级横向溢出、纵向滚动、运行时异常与错误覆盖层；检查脚本是 [`browser_responsive_check.mjs`](../../browser_responsive_check.mjs)，结构化结果见 [`browser-responsive-current.json`](../../evidence/files/browser-responsive-current.json)。
- Agent-first 交互验收：无 `LOOMQ_LLM_*` 的最终镜像中，[`browser_agent_flow_check.mjs`](../../browser_agent_flow_check.mjs) 验证开始引导不自动预填、按钮只填入并聚焦且不改阶段/QASM/revision、发送后恰好推进一阶段、状态和回复显式标注未调用模型，共 16/16 通过；结构化结果见 [`browser-agent-flow-current.json`](../../evidence/files/browser-agent-flow-current.json)。两个浏览器脚本均要求预先在 `127.0.0.1:9333` 启动使用临时 profile 的 Chromium-family CDP 浏览器，命令见 [`web/README.md`](../../web/README.md)。专用 `agent-browser` CLI 在本机不可用，未联网安装替代依赖。
- 当前 UI 实拍：[`l2-ui-workbench.png`](../../evidence/files/l2-ui-workbench.png)、[`l2-ui-guide.png`](../../evidence/files/l2-ui-guide.png) 与 [`l2-ui-bell-results.png`](../../evidence/files/l2-ui-bell-results.png) 由提交人在 2026-08-11 基于冻结代码人工截取；引导与结果图使用提交人自行配置的模型连接。截图只证明视觉流程，最终 manifest 记录其 SHA-256，不把单次人工演示计作 live benchmark；图中外部模型即时生成的自由文本不作为项目确定性科学结论。
- 证据清单：[`verification-manifest.json`](../../evidence/files/verification-manifest.json) 记录 UTC、运行前完整 source HEAD/dirty 状态、Python/Node/Docker/OS/架构、每条命令、返回码、耗时、日志 SHA-256、关键 artifact SHA-256 和镜像 ID 日志。生成器是 [`generate_verification_manifest.py`](../../generate_verification_manifest.py)，默认不读取密钥环境、不调用真实模型/真机、不提交 Git，并把证据写入造成的工作树变化显式标为两阶段归档流程。
- L2 真实模型验证已在源码 S 上重跑：12-case 通过 12/12，中位延迟 6.110 秒、最大 6.906 秒；72-case 四并发压力通过 72/72，generate、repair、backend 各 24/24，墙钟 117.609 秒、中位延迟 5.961 秒、P95 6.859 秒。结构化结果见 [`l2-live-benchmark-current.json`](../../evidence/files/l2-live-benchmark-current.json) 与 [`l2-raw-prompt-stress-current.json`](../../evidence/files/l2-raw-prompt-stress-current.json)；密钥和服务地址未写入证据。
- SpinQ 真机支撑率保留未缓解原值；Wilson 区间、均匀基线、位序探针与“不补跑挑样”的解释见 [`spinq-hardware-analysis.json`](../../evidence/files/hardware/spinq/spinq-hardware-analysis.json)。该 Z 基证据只说明真机执行和与理想支撑的一致性，不认证纠缠或相干性。
- OriginQ 真机结果沿用已归档的四个原始 provider 响应与标准摘要；当前验证没有重新提交付费或外部硬件任务。

## 重现

在 `starter_kit/` 中运行离线默认验证并生成日志：

```bash
python generate_verification_manifest.py
```

本次包含 Docker 三平台的命令使用 `--command` 显式加入 `docker run ...`；运行
`python generate_verification_manifest.py --help` 可查看命名日志、自定义命令、额外
artifact、`--skip-heavy` 与两阶段归档说明。

若要把生成证据纳入 Git，使用可实现的两阶段流程：先形成干净的代码冻结提交 S；若需先归档真机/live 原始证据与说明，则形成不改可执行源码的干净基线 P。在 P 上运行生成器并确认 manifest 的 `repository.head == P`、运行前 `dirty == false`、
`success == true`；随后只提交生成的 `evidence/files/`，形成最终证据提交 E。提交前用
`git diff --name-only S..E` 确认没有可执行源码变化，再以 E 运行只读
`prepare_submission.py` 并提交 Issue。不要要求 manifest 预先等于包含它自身的 E；若
必须让 manifest HEAD 与最终源码 SHA 完全相同，应把 manifest 作为该 SHA 的外部 CI
artifact，而不是跟踪在同一提交中。
