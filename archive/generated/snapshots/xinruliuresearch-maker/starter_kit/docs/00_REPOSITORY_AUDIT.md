# 00 · 仓库与材料审计

最后审计：2026-08-21 07:23:38 UTC+8

本文只记录可复核事实。公开 evaluator 的结果是合同自测，不是正式分数；浏览器页面上的短 SHA 也不等同于已经在本地验证的完整提交身份。

## 1. 权威顺序与正式边界

发生冲突时采用以下顺序：

1. 当前 LoomQ 仓库中的正式题面、Starter Kit、接口合同、公开 evaluator、测试和提交流程；
2. 上游仓库当前版本；
3. 项目开发总控要求；
4. SCI-Pegasus 参考实现；
5. 工程经验或外部资料。

正式构建与评测根目录是 starter_kit/。仓库其他目录可用于理解规则，但不能成为评分路径的运行依赖。固定合同版本为 1.0，当前 Starter Kit 版本为 1.1.0，基准运行时为 Python 3.10。

已审阅的官方事实源包括：

- README.md、NEXT.md、problem_statement.md；
- starter_kit/README.md、QUANTUM_101.md、gate_identities.md；
- starter_kit/target_ir_contract.md、backend_capabilities.md/json、l2_policy.json；
- starter_kit/adapter.py、evaluator.py、llm_client.py、riscv_emulator.py；
- starter_kit/submission.yaml、requirements.txt、Dockerfile、evidence/README.md；
- starter_kit/circuits/、根 tests/、competition/。

competition/config.json 是截止时间与提交边界的官方机读事实源：截止为 2026-08-25 12:00 UTC+8（2026-08-25T04:00:00Z），归档上限 104857600 字节，正式提取目录为 starter_kit。

## 2. LoomQ 来源与本地 Git 状态

| 项目 | 审计结果 |
|---|---|
| 上游仓库 | https://github.com/QAIDAO/LoomQ-2026 |
| 参赛 fork | https://github.com/xinruliuresearch-maker/LoomQ-2026 |
| 开发来源 | 先审计参赛 fork 的 GitHub codeload 归档，后已迁移到独立标准 clone |
| 标准 clone | 已建立；origin 为参赛 fork，迁移前基线分支为 main |
| 下载归档大小 | 7137939 字节 |
| 下载归档 SHA-256 | BA43083CD2C1A9B99A8641600933EC36D7F406A0CC071BCEC19FC1A0951F5118 |
| 迁移前完整 HEAD | 1071f713e9026e8063b3ba7b6f09985c0ff99e02 |
| 页面观察 | 官方 GitHub HEAD 页面曾显示相符的短 SHA 1071f71 |

最初的 codeload 归档不含 `.git`，因此它只用于受控开发和基线审计。随后已从参赛 fork 建立独立标准 clone，并核对 origin、main 分支和完整 40 位基线 SHA。功能差异已经迁入该 clone、完整复测、commit 并 push，远端仓库页面也已核验更新；这些事实仍不等于赛事已接收。

发布步骤当前状态：

1. 已将受控开发差异迁移到标准 clone，并排除参考材料、缓存、凭证和临时产物；
2. 已核对 origin、main、提交历史与远端仓库页面；
3. 已在标准 clone 中完成 119/119 与公开/随机验证；
4. 已 commit 并 push `main`，本文不写死会继续变化的最终 SHA；
5. `prepare_submission.py` 已在一个已 push 的干净 HEAD 上完整通过；任何后续 commit 都必须在创建 Issue 前重跑。Final Submission Issue 与自动回执仍待完成。

## 3. SCI-Pegasus 参考材料

| 项目 | 审计结果 |
|---|---|
| 原始压缩包 | 用户提供的 `sci-pegasus-main(2).zip`（本地只读审计，不入库） |
| 大小 | 1179936 字节 |
| 修改时间 | 2026-08-19T00:29:24+08:00（文件系统包含更高精度小数，本表按秒记录） |
| SHA-256 | 7306ACF30D33BA1A393660AFA23D3CAA05BDE2C28041641AC3BCA8090FF02CEE |
| 只读参考位置 | .codex_reference/sci-pegasus/ |
| 正式运行依赖 | 禁止 |
| LICENSE | 压缩包根目录未发现权威 LICENSE 文件 |

解压时未提取任何 .env、.env.* 或同类环境文件；没有把密钥、Cookie、数据库数据、用户数据、日志或账号配置复制到 starter_kit。根 .gitignore 已排除 .codex_reference/，标准 clone 的 Git 索引审计也确认它未进入提交内容。

参考材料显示 SCI-Pegasus 是 Next.js/TypeScript、React、MongoDB、认证、持久 Agent Runtime 与 Workspace 组成的研究工作台。它只提供设计参考；许可不明时，不复制源代码到正式项目。详细边界见 02_SCI_PEGASUS_REUSE_MATRIX.md 与 07_ORIGIN_AND_LICENSE.md。

## 4. 修改前基线

以下是大规模实现前保存的历史基线，不代表当前并行开发中的代码状态。

| 检查 | 环境/命令意图 | 结果 |
|---|---|---|
| Python | Python 3.10.11 | 已确认基准解释器 |
| 默认公开 evaluator | python evaluator.py --json-out baseline-report.json | 0/4；Bell、GHZ-3 × spinq、originq 均因官方入口未实现而失败 |
| L1 三目标 | python evaluator.py --level l1 --target spinq,originq,braket | 0/6；Bell、GHZ-3 × 三目标均失败 |
| L3 | python evaluator.py --level l3 | 0/1；compile_hybrid 未实现 |
| compileall | python -m compileall . | 通过 |
| L2 | 需要 LOOMQ_LLM_* 模型服务 | 环境阻塞，未取得可评分结果 |

baseline-report.json 保存了默认 0/4 的逐 case 原因及生成时间。该表是修改前历史基线，不是当前实现结果。正式 L2 服务仍是外部环境边界；当前本地验证使用真实 HTTP stub，只证明协议和有界工作流，不等同正式 DeepSeek 结果。

后续实现结果保存在独立报告和测试记录中，不改写上述历史基线。当前可复跑结果见 `DEVELOPMENT_STATUS.md`、`docs/04_TEST_STRATEGY.md` 和 `evidence/files/`。

## 5. 官方合同摘要

- L1 必须保留 transpile(qasm_str, target) 和 run(qasm_str, target, shots)。
- L2 必须保留 agent_chat(prompt)，从 LOOMQ_LLM_* 读取 OpenAI-compatible 配置；正式模型为 deepseek-v4-flash，每 case 120 秒，正式共 12 case，至少一次有效模型调用。
- L3 必须保留 compile_hybrid(hybrid_qasm_str)，返回量子操作 list 与可由官方 TinyRISCVEmulator 执行的汇编。
- L1/L3 不依赖外网；L2 只依赖组委会注入的模型服务。
- run 结果的 counts 总数必须严格等于 shots，bit_order 必须为 little，最右字符对应 c[0]；任何 meta.is_mock=true 均失败。
- 依赖必须精确锁定；不得在 import 时联网或执行重任务。
- 最终只有 fork 所有者、Team ID 和 Issue 作者为同一 GitHub 账号时才有效。
- 预检必须在干净 Git 工作树、已 push 的完整 40 位 HEAD 上运行。
- 截止以 GitHub Issue created_at 为准；只有 submission:accepted 标签及归档 SHA-256/Artifact ID 回执构成有效提交。

## 6. 当前官方盲区

公开材料不能证明以下事项，必须通过自建测试、正式环境或人工证据补足：

- 隐藏的 GHZ-5、QFT-4、Grover-3 和三个随机电路内容及私有种子；
- 官方目标 IR 解析器的全部容错边界；
- 隐藏 QASM 的寄存器命名、空白、注释、参数表达式、测量排列和深度组合；
- 三家真实 SDK/硬件的版本差异、排队、噪声、账号权限与返回格式；
- L2 未公开 prompt 改写与模型响应波动；
- L3 随机文法组合、嵌套深度与临时寄存器压力；
- 固定 Linux 容器中的构建、系统库和资源限制；
- 人工 UX、工程叙事与 Bonus 的最终主观判定。
- 工程与产品化的细分口径存在官方文本歧义：problem_statement.md 给出模块总计 10 分，而根 README.md 的人工证据表称“人工部分最高 5 分”；当前材料没有公布其余 5 分的独立细则。

因此，公开 evaluator 通过只能作为必要条件，不能称为正式得分或隐藏评测通过。

## 7. 提交检查结论

L1/L2/L3、本地 UI、随机差分与 Bonus 已形成 Python 3.10 可复跑证据；标准 clone 已迁移、复测、commit/push，远端页面已核验，官方预检也已在一个已 push 的干净 HEAD 上完整通过。最终状态仍不能称为“赛事已接收”：任何后续 commit 都必须重跑预检，Final Submission Issue 尚未创建，也没有 `submission:accepted` 回执。Docker 在当前主机不可用，正式 DeepSeek 与 SpinQ/OriginQ 真机证据也未取得；这些限制必须继续如实披露。公开自测通过不代表隐藏评测得分。
