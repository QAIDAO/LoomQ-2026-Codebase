# LoomQ L2 客观分 Agent 后端分阶段开发执行计划

## 执行规则

本计划只争取 L2 黑盒 Prompt 注入测试的 20 分客观分，不做主观体验、前端或 UI/UX。唯一交付接口是：

```python
agent_chat(prompt: str) -> str
```

正式评测使用 `deepseek-v4-flash`、关闭 thinking、`temperature=0`，共 12 个隐藏 case，每例 120 秒；每例必须至少完成一次有效模型调用。实现必须读取 `LOOMQ_LLM_*`，不得硬编码服务地址、密钥、模型名、公开样例答案或关键词应答表。

开发遵循“最小基线 → 观察失败 → 增加一个机制 → 测量增益 → 决定保留”的顺序。任何未被官方契约确认的规则都不能硬拒绝候选；任何新增复杂度都必须由可重放失败或真实模型基准证明收益。

每个执行块均执行同一闭环：

1. 完成该块代码或配置修改。
2. 为新增行为补齐测试。
3. 运行定向测试、公开 evaluator 和规定回归。
4. 对比该块前后的分类准确率、超时和调用成本。
5. 仅在收益成立且“完成检查”全部通过后提交。

不得把未通过测试的工作带入下一执行块；不得在同一提交中混入 L1、L3、Bonus、主观分或无关修改。

## Oracle 可信边界

验证器按权威程度分为三类：

1. **无条件硬验证器**：直接来自已确认官方契约，例如输出抽取格式、QASM 语法、门集合、寄存器和索引、能力表字段与规范后端 ID。可以拒绝候选。
2. **有条件语义验证器**：只有目标能从 prompt 通过已确认的有限语法独立恢复，并与官方判定做过差分时，才可以按 Fidelity 或测量要求拒绝候选。
3. **启发式诊断器**：只能给修复模型提供线索，不能单独拒绝候选。第一版不实现“疑似缺少纠缠门”等门级根因猜测。

模型给出的 `target`、`assumptions` 或推荐 ID 都不是事实源。不能独立确认的目标字段保持 `unknown`；目标不可信时只做硬验证，不使用不完整语义 oracle 制造 false negative。

最终流水线为：

```text
prompt
  → 独立 RequestContext（deadline、调用预算、资源上限）
  → 首次模型调用：任务类型 + 任务特定 payload
  → 本地交叉检查任务类型
  ├─ backend_select
  │    → 只解析约束 → 能力表单次全表求值 → 确定性排序 → 只输出一个 ID
  └─ qasm_generate / qasm_repair
       → 枚举候选 → 静态硬验证 → 可信时才做语义验证
       → 有预算时最多一次定向修复 → current/history 中选择 best
       → 只输出一个完整 QASM
```

第二次修复、第二套模拟器、复杂根因诊断和更复杂的模型编排均不属于初始必做项；只有消融基准证明有显著净增益且不威胁时限时才能加入。

## 执行块 1：建立契约矩阵、最小基线与精确输出

### 执行步骤

1. 逐项读取并锁定 `problem_statement.md`、`adapter.py`、`evaluator.py`、`l2_policy.json`、`llm_client.py`、`backend_capabilities.json` 和 `target_ir_contract.md`，生成版本化契约矩阵：

   | 项目 | 官方来源 | 已确认行为 | 本地实现后果 | 可否硬拒绝 |
   |---|---|---|---|---|
   | L2 调用协议 | `l2_policy.json` / `llm_client.py` | 模型、thinking、温度、流式、超时 | 固化请求测试 | 是 |
   | QASM 抽取 | `evaluator.py` | fence 与 `OPENQASM 2.0;` 的实际规则 | final formatter 完全对齐 | 是 |
   | 三类任务 | `problem_statement.md` | 生成、纠错、后端选择 | 联合类型协议 | 是 |
   | QASM/门约束 | 题面与 L1 契约 | 精确白名单和语法边界 | parser 硬验证 | 仅确认项 |
   | 测量与 Fidelity | `problem_statement.md` 及可见 evaluator | 明确要求与 `≥ 0.97` 阈值 | 决定语义 oracle 范围 | 仅确认项 |
   | 隐藏目标族 | `problem_statement.md` | 明确有限范围或开放描述 | 决定能否硬语义判定 | 仅有限语法 |
   | 后端正确答案集 | 能力表及题面 | 满足全部约束的集合，多解是否任一可得分 | 求解与 tie-break | 是 |

2. 矩阵中每个“可硬拒绝”项必须链接到具体文件和测试；推断项、自行收紧项和待确认项分别标识，不混写为官方事实。
3. 立即接通最薄的 `agent_chat` 纵向切片：一次模型调用、最简单联合类型解析、三类最小分支、精确 final formatter，并运行公开 evaluator。
4. 模型协议采用任务判别联合类型，而不是通用 `answer/assumptions`：
   - QASM：`task`、`qasm`、可选 `target` 和逐字段 `evidence`；
   - 后端：`task`、`hard_constraints`、`soft_preferences`、`forbidden`、`unresolved`；模型不输出推荐 ID。
5. final formatter 严格最小化：
   - QASM 路径只输出一个完整 OpenQASM 2.0 程序，不附解释、JSON 或第二候选；
   - 后端路径只输出一个规范 ID，可附不含其他规范 ID 的短理由；
   - 排除项、诊断和历史候选只进入脱敏 trace；
   - 无解只使用契约矩阵确认的格式，不默认输出不合格替代项。
6. 建立初始开发集并记录最小基线：三类通过率、格式失败、模型理解失败、QASM 错误、后端事实错误、调用延迟和响应包装。

### 新增测试条件

- 契约矩阵的每个硬规则都能定位到官方来源；
- `agent_chat` 签名、返回字符串和异常传播与公开 evaluator 调用方式一致；
- 正式请求固定 `stream=false`、`temperature=0`，正式模型关闭 thinking；
- QASM 输出只含一个可被公开 `extract_qasm()` 提取的程序；
- 后端输出只出现一个规范 ID；
- 模型返回 Markdown、纯 JSON或附带解释时仍能生成精确最终格式；
- 缺配置、HTTP 错误、空响应和解析失败的行为由契约测试固定。

### 回归测试

- 使用本地 OpenAI-compatible 假服务运行端到端纵向切片。
- 运行 `tests/test_l2_contract.py`、`python evaluator.py --level l2` 和完整 `unittest`。
- 有自备凭证时运行一轮正式同型号小基线；无凭证时明确跳过，不伪造结果。

### 完成检查

- `agent_chat` 已实际接通，而非等待最后集成。
- 已知道最小方案在三类任务上的主要失败来源。
- 本地硬拒绝范围没有超出契约矩阵。

### 阶段性 Git 提交

`Establish the L2 contract baseline`

---

## 执行块 2：完成纵向 runtime、隔离与资源边界

### 执行步骤

1. 每次 `agent_chat` 创建独立 `RequestContext`，包含单调 deadline、模型调用次数、当前/最佳候选、历史 IR 签名和脱敏 trace；用户内容及可变状态不得存入全局变量或跨 case 缓存。
2. 能力表允许以不可变对象缓存，但加载后必须校验版本、字段类型和 ID 唯一性；缓存不得包含请求内容。
3. 冻结并集中管理以下上限；具体数值先依据官方约束和最小基线设保守值，再由压力测试调整：

   ```text
   MAX_MODEL_CALLS
   MAX_REPAIRS
   OVERALL_DEADLINE_SECONDS
   FINAL_RETURN_RESERVE_SECONDS
   HTTP_CONNECT_TIMEOUT
   HTTP_READ_TIMEOUT
   MAX_PROMPT_CHARS
   MAX_RESPONSE_CHARS
   MAX_JSON_DEPTH
   MAX_JSON_ITEMS
   MAX_CODE_FENCES
   MAX_QASM_CANDIDATES
   MAX_QUBITS
   MAX_GATES
   MAX_REGISTERS
   MAX_EXPRESSION_DEPTH
   MAX_LOCAL_VALIDATION_SECONDS
   ```

4. 资源上限必须分成两类：官方明确上限可硬拒绝；仅为本地安全设置的上限不得静默伪装成语义错误，应在不威胁评测时限的前提下尽量覆盖官方 case，并记录为资源拒绝。
5. 在进入 JSON parser、QASM parser 和状态向量模拟器之前检查对应规模，避免指数级状态空间、深层嵌套或超量候选耗尽 120 秒。
6. 禁用 HTTP 客户端隐式重试；429、5xx、连接和读取错误只由 runtime 在剩余 deadline 与总调用预算内显式决定是否重试，并计入 `MAX_MODEL_CALLS`。
7. 若现有 `urllib` 传输无法分别设置 connect/read timeout，契约中如实记录限制并使用整体请求 timeout；只有基准证明需要时才替换客户端，不为接口美观引入依赖。
8. 对 `unknown` 任务类型执行本地交叉判断；仍无法确定且有预算时进行一次“分类并重答”，无预算时选择最可能且可解析的分支。`unknown` 只作为失败指标，不是稳定得分路径。

### 新增测试条件

- 并发请求的 deadline、调用数、候选和 trace 完全隔离；
- 超长 prompt/响应、深层 JSON、大数组、多 code fence、超大 qreg、过多门和深表达式及时终止；
- 慢服务、429、5xx、断连和截断响应不触发隐式无限重试；
- 所有重试计入同一调用预算，并为 final formatter 留出时间；
- trace 不含 API Key、Authorization、完整环境变量或跨 case 内容；
- `unknown` 能进入重判/重答路径而非直接停止。

### 回归测试

- 使用并发假服务和可控慢服务运行隔离、deadline、错误和重试测试。
- 运行三类最小纵向 case、公开 evaluator、L2 契约和完整 `unittest`。

### 完成检查

- 最坏路径有明确 CPU、内存、响应大小、调用次数和时间上限。
- `agent_chat` 的异常契约由测试复刻 evaluator，而不是主观选择“返回还是抛出”。
- runtime 加固没有改变精确最终输出。

### 阶段性 Git 提交

`Bound and isolate the L2 agent runtime`

---

## 执行块 3：优先完成后端约束确定性求解

### 执行步骤

1. 模型只把自然语言转换为结构化硬约束、软偏好、禁止项和未解析项，不提供推荐 ID，也不把能力表完整内容塞入 prompt。
2. 约束字段和值必须来自契约矩阵确认的能力表 schema；模型字段附带 prompt 证据片段或字符范围，本地确认其确实存在并映射为规范值。无法确认的字段进入 `unresolved`，不得用模型假设补全为硬约束。
3. 生产求解器只进行一次全表求值，每个后端得到：

   ```python
   eligible: bool
   violations: list[str]
   preference_score: tuple
   ```

   该次扫描同时完成硬约束筛选、排除原因和软偏好评分，不再建设重复的“正向 + 反向”生产校验路径。
4. 对全部合格项使用明确且稳定的 tie-break。若官方允许正确答案集中的任一 ID，则选择排序首项并只输出该 ID；不得声称虚假唯一性。
5. 无满足项时只输出契约确认的无解表示。删除默认“违反约束最少的替代后端”；只有题面或真实失败证明需要且官方输出可判定时，才单独设计替代策略。
6. 在测试中实现独立朴素全表筛选 oracle，与生产求解器做组合穷举差分；oracle 不复用生产 predicate。
7. 对自然语言约束提取失败，若有调用预算则定向重答；不能可靠确认的约束不应被确定性求解器伪装为已知事实。

### 新增测试条件

- 比特边界、零排队、真机/模拟器、免费/免费额度/付费、账号要求和平台偏好；
- 否定表达、中英文数字、同义表达、硬/软约束冲突和 `unresolved`；
- 多解、唯一解和无解；最终文本始终只含一个合格 ID或确认的无解格式；
- 能力表字段缺失、错误类型、未知/重复 ID 时快速失败；
- 生产求解结果与独立 oracle 的约束组合穷举完全一致。

### 回归测试

- 每次修改运行能力表全部记录、字段边界和组合穷举差分。
- 使用假模型走通 prompt → 约束 → 单次全表求值 → final formatter。
- 运行三类固定回归、公开 evaluator 和完整 `unittest`。

### 完成检查

- 后端事实只来自 `backend_capabilities.json`。
- 生产中没有模型推荐 ID、重复反向校验或默认近似替代。
- 与最小基线相比，后端类别准确率提升且延迟未明显恶化。

### 阶段性 Git 提交

`Solve L2 backend constraints deterministically`

---

## 执行块 4：实现 QASM 抽取、候选选择与静态硬验证

### 执行步骤

1. 复用 L1 已验证 parser/IR；L2 不维护第二套门、寄存器、参数或测量语法。只有契约矩阵确认的规则可以硬拒绝。
2. 从模型回复中枚举受资源上限约束的 QASM 候选，按公开 `extract_qasm()` 兼容规则抓取完整程序；不把零散门语句拼成假完整程序。
3. 对每个候选执行安全规范化和静态硬验证：头部/声明、官方门集合、元数、寄存器、索引、参数语法，以及契约确认的测量要求。自行偏好的风格不得成为拒绝条件。
4. 多候选选择规则为：
   - 零个静态合法候选：进入一次修复；
   - 一个静态合法候选：选择它；
   - 多个规范 IR 相同候选：去重后选择一个；
   - 多个不同且合法候选：仅在可信目标 oracle 可区分时选择，否则进入修复，不武断挑选。
5. 静态诊断只输出稳定错误码、位置和必要字段，不回填整个 trace，也不进行“缺少某类门”的启发式归因。
6. 为修复任务保留原始代码与编辑距离信息，但“更接近原代码”只作为所有硬正确性之后的 tie-break；没有明确目标态时只做静态和契约硬验证，不擅自推断 Bell/GHZ。
7. 在每次模拟前检查 qreg、门数和状态空间上限；静态合法不等于资源安全。

### 新增测试条件

- 无 fence、单 fence、多个 fence、注释内伪 fence、解释包围和截断代码；
- 缺声明/分号、错误大小写/元数/索引，以及官方允许的参数表达式；
- 多候选中零个、一个、IR 等价多个和语义不同多个合法候选；
- 仅改变空白或 Markdown 包装的候选规范化为相同 IR 签名；
- 无明确目标的修复不会被强行解释成某个目标态；
- 超大 qreg、过多门和表达式深度在模拟前被资源边界拦截。

### 回归测试

- 运行 QASM 抽取、parser/IR、静态验证和候选选择测试。
- 重跑 L1 的 12 门、参数、寄存器、测量和错误输入回归。
- 运行三类固定回归、公开 evaluator 和完整 `unittest`。

### 完成检查

- 送往模拟器的候选均完整、静态合法且资源安全。
- 本地验证器没有比官方契约更严格地误拒绝答案。
- 静态 harness 相比最小基线带来可测 QASM 通过率增益。

### 阶段性 Git 提交

`Validate and select L2 QASM candidates`

---

## 执行块 5：增加条件语义验证、历史最佳与一次修复

### 执行步骤

1. 只为契约矩阵确认的有限目标语法建设 reference oracle。目标字段由本地从 prompt 证据重新构造；模型提供的 `target/evidence` 只帮助定位，不自动成为可信事实。
2. 可信 `TargetSpec` 的每个字段必须满足：证据确实存在、规范化规则明确、字段组合属于官方保证范围。无法确认的字段保持 `unknown`，不参与硬语义拒绝。
3. 使用已有且经过测试的 L1 本地模拟路径或最小状态向量验证；固定并用公开 evaluator/已知解析结果差分确认 Fidelity 定义、端序、全局相位和测量处理。除非发现不一致，不建设第二套模拟器。
4. 第一版诊断仅包含客观信息：错误码、静态位置、expected/actual width、Fidelity、最大振幅差和测量差异；不实现启发式门级根因。
5. 默认只允许一次定向修复。修复请求包含可信目标摘要、当前完整候选和最小客观诊断，并要求返回完整替代程序，而不是 diff。
6. 始终维护：

   ```python
   current_candidate
   best_candidate
   history_ir_signatures
   ```

   `best_candidate` 使用稳定字典序：可抽取 → 静态合法 → 契约测量硬约束 → 可信语义通过 → Fidelity → 与原修复代码接近/程序更短。未知语义不能被当作语义通过。
7. 防重复和振荡使用规范化 IR hash，不使用原始文本 hash。时间耗尽或修复退化时从历史中返回得分最高的候选，而不是盲目返回最后版本。
8. 若目标不可信，修复只针对协议、抽取和静态硬错误；不得把模型自报 TargetSpec 用作拒绝或修复目标。
9. 只有真实模型 validation 显示第二次修复带来预先设定的显著绝对通过率增益，且最坏耗时仍保留充分余量时，才提出新增第二次修复的独立变更；否则保持一次。

### 新增测试条件

- 模型错误 TargetSpec 但证据不支持时不会形成错误硬 oracle；
- 可信 Bell/GHZ 等官方有限目标的正确/错误电路可按官方定义区分；
- 相同 counts 但相位错误的电路仅在官方 Fidelity 语义确认后拒绝；
- 无目标修复只做静态验证；
- A（较优）→ B（静态失败）→ C（较差）后超时会返回 A；
- 只改空白无法绕过 IR 重复检测；
- 首轮正确仅调用一次，首轮失败最多进行一次修复。

### 回归测试

- 使用手写小电路、非对称状态和公开 evaluator 做端序/Fidelity 差分。
- 使用脚本化假模型覆盖成功、退化、振荡、超时和历史最佳选择。
- 运行 QASM 全集、三类固定回归、公开 evaluator 和完整 `unittest`。

### 完成检查

- 硬语义判定只发生在可独立恢复的目标上。
- 一次修复与历史最佳相对无修复基线有可测净增益。
- 未引入第二模拟器、复杂根因诊断或未经证明的第二次修复。

### 阶段性 Git 提交

`Add trustworthy L2 QASM repair and ranking`

---

## 执行块 6：贯穿式评测、对抗验证与发布冻结

### 执行步骤

1. 数据分为四层：
   - `unit/contract`：每次改动运行；
   - `development`：允许查看逐例失败并调试；
   - `validation`：允许反复查看聚合分类指标，用于版本选择；
   - `final_holdout`：冻结前只运行一次，若失败修复后最多再运行一次，并记录次数。
2. 从执行块 1 起持续补充参数化变体，而非实现结束后一次建设：措辞/语序/中英文变化、比特和目标参数、组合语法错误、后端字段边界、否定约束、冗余上下文和格式噪声。
3. QASM 故障注入始终独立保存用户声明目标；后端期望集由不复用生产 predicate 的测试 oracle 生成。固定 case ID/seed，保证失败可重放。
4. 每次只针对一个最高影响失败簇修改一个主要变量，并依次运行目标簇、该类别 development、三类固定回归和 validation。连续两轮 validation 稳定是冻结条件；不得用 final holdout 日常调参。
5. 消融仅用于决定机制是否进入生产，至少比较：最小基线、静态 harness、条件语义验证、一次修复；后端比较模型直答基线与本地求解。完整学术式消融不是交付要求。
6. 对抗测试覆盖：资源耗尽、网络错误、Unicode/嵌套 fence、注释内注入、伪造 validator 结果、多个候选、任务误分类、并发隔离和响应截断。
7. 在正式同型号配置上记录三类首轮通过率、最终通过率、修复挽回率、false accept/false reject、超时率、模型调用数和延迟分位数。
8. 冻结时量化门禁至少包括：
   - 公开 evaluator 100%；
   - 已确认确定性静态 oracle：已知用例零 false accept、零 false reject；
   - 后端表驱动与组合差分全集 100%；
   - development/validation 三类分别达到预先写入配置的阈值，不只看总体；
   - validation 零本地资源超时；
   - 最大端到端耗时明显低于 120 秒并保留 `FINAL_RETURN_RESERVE_SECONDS`；
   - 默认最多一次修复，第二次修复未满足增益门槛则禁止启用。
9. prompt 版本、代码 commit、能力表版本、数据集版本和预算配置共同记录；失败报告、模型原文和 trace 不提交。
10. 最终将 `starter_kit/submission.yaml` 的 `levels.l2` 与 `network.required_for_l2` 设为 `true`，更新 README 的接口、环境、客观任务、验证边界和测试命令。

### 新增测试条件

- 四层数据集 case ID 无重叠，final holdout 运行次数受控；
- seed 可复现、故障注入不改变 oracle 目标、失败记录可单 case 重放；
- 指标按任务、失败阶段和迭代轮数正确聚合；
- 单变量实验能显示前后变化，类别退化会阻止合并；
- prompt injection 不能跳过验证、泄漏系统信息或伪造本地结果；
- 冻结配置中的所有资源和准确率门禁都有自动测试。

### 回归测试

- 常规运行 unit/contract、development 定向集、三类固定回归、公开 evaluator 和完整 `unittest`。
- 候选冻结版本运行 validation、并发/资源/网络压力测试和 Docker 内等价测试。
- 最终版本有限运行 final holdout，并执行：
  - `python evaluator.py --level l2`
  - `python -m unittest discover -s tests -v`
  - `python -m py_compile competition/*.py starter_kit/prepare_submission.py`
  - `python starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>`

### 发布前缺陷处理规则

- 协议/格式修复：重跑响应解析、精确 final formatter、prompt injection 和三类固定回归。
- QASM 静态修复：重跑 L1 parser 回归、候选选择和全部 QASM development。
- 目标/Fidelity 修复：重跑可信目标提取、端序差分和全部条件语义用例。
- 后端修复：重跑能力表字段边界与组合 oracle 差分。
- runtime 修复：重跑慢服务、错误重试、资源耗尽和并发隔离。
- 任何缺陷先增加最小失败复现；冻结后不接受没有 validation 证据的 prompt 微调。

### 完成检查

- 每一层复杂度都有相对更简单基线的可测准确率收益。
- final holdout 没有被反复用于调参。
- 三类最终输出均精确、唯一、可被官方确定性提取器直接消费。
- 提交不包含 UI/UX、主观体验、凭证、trace、模型原文、临时 QASM 或评测报告。

### 阶段性 Git 提交

`Finalize the L2 objective-score agent backend`

## Git 提交通用门禁

任何阶段性提交都必须满足：

- 暂存区只包含当前执行块改动；
- 相关定向测试、公开 evaluator 和规定回归全部通过；
- 只有契约矩阵确认的规则可以硬拒绝候选；
- QASM 语义只在目标可独立恢复时裁决，后端事实只来自官方能力表；
- 新机制有相对基线的准确率或风险收益证据；
- 每个已修复缺陷都有可重放的最小回归；
- 没有缓存、trace、模型响应、评测报告、临时 QASM 或凭证；
- 提交主题简短、祈使式、单一职责；
- 只能声明 L2 客观三类任务能力，不能声明主观体验、UI/UX 或完整 30 分已经完成。
