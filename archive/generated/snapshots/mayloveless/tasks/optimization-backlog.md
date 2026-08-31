# LoomQ Remaining Optimization Plan

> 当前阶段不再扩产品范围。`05 Backend` 完成后，先集中提高客观评分稳定性，再做主观体验 / evidence，最后进入提交冻结。
>
> 正式评分里最值得保护的是：L1 45（其中语义 35 + 真机 10）、L2 客观 20、L3 15。任何优化都必须能对应评分风险或最终提交风险；已经完成、重复、或短期收益明显不足的候选不再保留。

## 执行原则

- 优先补**测试盲区**，不要为了“更鲁棒”先重构已经稳定的核心实现。
- 新增 robustness 规则必须有 hidden-like / adversarial case 支撑；没有失败证据时，不主动扩大协议或模型调用次数。
- 客观题改动后要重跑受影响级别的完整回归；改变 Parser / IR / serializer / measurement normalization 后，旧 target-native 证据自动失效。
- 真实 L2 benchmark 必须绑定 exact source SHA；源码改变后旧结果只算历史记录。
- 最终冻结后不再做体验型重构，只修阻塞提交或明确丢分的问题。

---

## P0：客观评分加固

### 1. L1｜35 分语义等价性

当前已有：三平台 Adapter / Runner / Serializer、12 门支持、公开三平台 PASS、SpinQ + Braket hidden-like 组合电路回归。

剩余高价值项：

- [ ] **把 hidden-like 8 电路风格扩到 OriginQ**：GHZ-5、QFT-4、Grover-3、Random × 3 以及多寄存器 / 测量映射，都通过 `adapter.run(..., "originq", ...)` 验证；不要只让 OriginQ 停留在公开 Bell/GHZ-3。
- [ ] **把 hidden-like 验证从 `run()` 扩到 `transpile()`**：正式 L1 会解析并模拟 `transpile()` 的目标 IR。对 SpinQ QASM2、OriginIR、Braket OQ3 的公开输出做 target-native 语义验证，不能只证明 runner 的私有 execution mode 正确。
- [ ] **目标 IR 使用独立 / 厂商 parser 或 SDK 再验一次**：SpinQit、pyQPanda、Braket 能解析的产物实际交给对应工具链；至少用非对称、相位敏感、`cu1/swap/ccx`、交叉 measurement case 防止内部 serializer 与自测共享同一错误。
- [ ] **补一组解析答案明确的独立 Oracle case**：重点攻击 bit order、control/target 顺序、相位符号和多经典寄存器映射；不要只依赖 Bell/GHZ 或 `U + U^-1` 这类可能掩盖共同错误的测试。
- [ ] **当前 SHA 做一次三平台 8192-shots hidden-like 总回归**：最终报告记录 source SHA、case ID、target、fidelity、耗时与环境版本。

### 2. L2｜20 分黑盒客观题

当前已有：真实模型调用、独立 target judge、statevector Fidelity、自验失败最多一次 repair、确定性 backend capability selector、pure-state downgrade guard。

剩余高价值项：

- [ ] **重跑正式形态 12-case real-model benchmark，并扩大改写**：生成 / 修复 / backend 三类都要覆盖同义改写；报告绑定 exact source SHA、模型、case-set version、调用次数、总耗时、结果。
- [ ] **backend 专门做否定 / 排除 / no-match adversarial**：至少覆盖“不需要真机 / 不要付费 / 不要账号 / 零排队 / 必须真机 + 零排队”等官方字段组合。平台名排除只在官方约束协议确实支持时测试，不为了额外语义擅改正式 schema。
- [ ] **120 秒总 deadline 做成真实硬边界**：当前单次 transport timeout 不能等价于整 case 预算。保证 1/2/3 次调用路径都在总预算内留出本地验证和最终返回时间，且不增加第 4 次模型调用。
- [ ] **结构化模型输出做有限容错**：保留“严格执行”，只允许安全、无歧义的 JSON 围栏 / 单一 JSON 对象提取等表示层容错；字段别名、数字字符串等更宽 normalize 仅在真实 benchmark 暴露失败时再吸收。
- [ ] **明确 unsupported 的评分边界继续回归**：Bell/GHZ/ket/relative-phase 等明确纯态不得静默降级；非唯一目标可 Parser-only，但最终文本不能夸大为已完成语义验证。
- [ ] **最终 DeepSeek benchmark 只在客观代码稳定后跑**：避免频繁烧额度；源码再变更则相关 benchmark 失效。

### 3. L3｜15 分确定性编译

当前实现已经有独立 Lexer / Parser / AST / RISC-V codegen、大量 adversarial case、随机 differential 与高 classical-bit / scratch 测试；不再重写编译器。

剩余只做收口验证：

- [ ] **在当前 SHA 重跑独立随机 differential**：随机生成完整 mini grammar，穷举 measurement 组合，与独立 reference interpreter 比较最终 `r1..r9`；记录 seed / case 数 / measurement 组合数。
- [ ] **再次确认 `quantum_ops` 语义等价**：参数、注释、classical block 前后操作、measurement 顺序和多位索引至少保留一组独立测试；只有发现失败才改 production。
- [ ] **官方 public L3 + 全量单测 + 冷启动环境复跑**：L3 已开启，任何失败都按阻塞提交处理。

### 4. L1 真机｜10 分证据风险

- [ ] **OriginQ 证据做最终 Schema / 可复算检查**：原始 CSV 保留不改，1000 shots → counts 的转换提供机械复算；确认 `job_id`、时间、counts 主峰与赛程窗口一致。
- [ ] **SpinQ 证据单独处理 shots/counts 风险**：当前平台导出只有 probabilities，没有离散 shots。禁止为了满足 Schema 推测或伪造 counts；优先确认平台任务元数据能否补到真实 shots，或在可行时补跑一条能导出 counts/shots 的真机任务。若平台客观上不给，则在提交前明确评估这 +5 分是否可申报。
- [ ] **两平台 job ID 可追溯性人工复核一次**：最终 evidence 中平台名、job ID、时间、电路、原始文件路径必须互相一致。

---

## P1：主观体验与 Bonus 收口

客观题稳定后再做，避免 UI 继续影响生产路径。

- [ ] **L2 交互体验 evidence 补齐**：启动命令、测试入口、3 个用户任务，目标用户改成“有编程基础、没有量子背景的开发者”。
- [ ] **做一次无作者讲解的首次使用验收**：重点看 Learn → Experiments → Explorer、Repair、Backend 是否知道下一步点哪里；只修真实卡点。
- [ ] **多轮一致性做轻量验收**：工作人员会看多轮回答是否一致。先测试现有产品路径；只有确实出现上下文断裂，再决定是否加最小 session，不为了聊天形态重做 Explorer。
- [ ] **结论边界与无障碍最后扫一遍**：关键状态不只靠颜色；`prefers-reduced-motion`、键盘焦点、缩放和小屏不阻塞主流程；量子测量展示不把“相关性”写成“已证明纠缠”。
- [ ] **新手引导与视觉叙事 Bonus evidence 填写**：Learn、概念解释、结果可视化、错误恢复 / 引导分别给出仓库路径。
- [ ] **Repair 可选增加最小 diff**：仅当现有“原始 QASM / 修复提案”人工比较明显困难时做；不再扩执行轨迹或新 Agent 功能。

---

## P2：最终提交阶段

只在功能和客观优化结束后执行。

- [ ] **官方契约漂移检查**：重新对照最新 upstream 的 `problem_statement.md`、`submission.yaml`、Starter Kit 版本、提交路径、网络规则和 precheck。
- [ ] **最终 Docker / SDK 冷启动**：从干净环境安装 Braket、SpinQit、pyQPanda，运行 declared levels、全量单测、Web 启动与 Bonus E2E。
- [ ] **正式归档隔离**：把最终 `starter_kit/` 单独放到临时目录 / 镜像，只依赖归档内文件完成 evaluator、测试和 Web 启动。
- [ ] **冻结 source SHA 后生成最终证据**：L1 hidden-like / native validation、L2 real-model benchmark、L3 differential、硬件 evidence、Web 三条体验任务都绑定冻结 SHA。
- [ ] **更新 evidence/README 与主 README**：目标用户、启动方式、三条体验任务、真机、Bonus、产品定位与当前实现一致。
- [ ] **官方 public evaluator / precheck 最终全过**，再同步公开 fork / 提交入口。
- [ ] **冻结后任何可执行代码改动都触发受影响证据重跑**；8 月 24 日只保留为 blocker buffer，不安排新功能。

---

## 明确不再做

以下候选已完成、被现有架构取代，或在当前赛程收益不足，因此从优化任务中删除：

- 重新实现 L2 “生成后语义自验 / target judge 解耦 / deterministic backend selector / parser feedback repair”；
- 多轮 repair 与“保留历史最优候选”（正式路径只有一次 bounded repair）；
- 新写一套轻量 statevector 模拟器来替换当前已工作的验证链；
- 大规模 Quick Actions / 菜单重构 / target-native Viewer；
- 产品内实时真机提交、长轮询、recover/resume、模拟器 fallback 等完整云任务系统；
- 为自定义量子 RISC-V 再扩 opcode / 参数门（当前 Bonus 交付已具备，后续只复测）；
- 为了 robustness 新增 Agent 框架、RAG、额外模型裁判或第 4 次 LLM 调用；
- 没有真实失败证据的宽松 schema normalize / 关键词特判。

