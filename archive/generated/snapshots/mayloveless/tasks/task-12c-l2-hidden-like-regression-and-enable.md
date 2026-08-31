# Task 12C：L2 Hidden-like 真实回归与开启门槛

## 背景

Task 12A 已完成真实 DeepSeek / OpenAI-compatible API 打通。

Task 12B 已完成：

```text
候选 QASM
→ Parser / L2 结构校验
→ 独立 target judge（只看原始 prompt）
→ Braket LocalSimulator statevector
→ pure-state Fidelity
→ 失败时最多修复一次
```

当前剩余风险主要是：

1. target judge 本身仍受模型输出稳定性影响；
2. `verification_mode=unsupported` 会降级为 Parser-only，无法提供语义保证；
3. QASM 最坏路径有 3 次串行模型调用，必须确认整个 case 能稳定落在正式 120 秒限制内；
4. L2 语义路径运行时依赖 pinned Braket SDK，必须在干净环境确认；
5. 复杂相位 Prompt 仍可能存在模型非确定性；
6. `submission.yaml` 目前仍未开启 L2。

本任务不再扩功能，目标是用真实 DeepSeek 做 hidden-like 压测、收敛风险，并在满足明确门槛后再开启 L2。

---

## 目标

完成以下闭环：

```text
真实 DeepSeek hidden-like 回归
→ 记录 target judge / unsupported / Fidelity / 调用次数 / 总耗时
→ 仅根据真实失败案例做最小 Prompt 或协议修正
→ 全量回归
→ 干净 Docker L2 验证
→ 官方 public L2 evaluator
→ 满足开启门槛后才修改 submission.yaml
```

不要为了“看起来更智能”增加新 Agent 能力。

---

## 一、真实 DeepSeek hidden-like 测试集

使用本地 `starter_kit/.env.l2.local` 注入真实配置：

```bash
set -a
source .env.l2.local
set +a
```

不要输出该文件内容，不要打印 API Key / Authorization Header。

至少执行以下 12 类 case，Prompt 必须自然表达，不要把期望 QASM 直接写在 Prompt 里。

### A. 自然语言生成 QASM

1. 3-qubit GHZ，要求全测量；
2. 3-qubit GHZ，同义改写，要求全测量；
3. Bell+，只制备态、不要求测量；
4. Bell+，要求测量；
5. Bell- 或等价“`(|00> - |11>)/sqrt(2)`”相位目标；

### B. 修复 QASM

6. Bell 目标，输入存在明确语法错误的 QASM；
7. Bell 目标，输入 QASM 语法完全合法但实际是四态均匀叠加；
8. 明确要求测量，但候选 QASM 缺测量；
9. 相位目标明确，但输入 QASM 的相对相位错误；

### C. 后端选择

10. 至少 15 qubit + 零排队；
11. 至少 5 qubit + 必须真机 + 免费或免费额度；
12. 免费 + 不允许注册/登录账号；

额外补 1 个“必须真机 + 零排队”的无解组合用于 no-match 行为检查，但它不计入上述 12 类基础矩阵。

---

## 二、每个 case 必须记录的诊断

只记录非敏感信息：

- case 名称 / 输入类别；
- 最终成功或失败；
- 模型调用次数；
- wall-clock 总耗时（从 `agent_chat()` 开始到返回 / 抛错）；
- target judge 的 `verification_mode`；
- 是否出现 `unsupported`；
- statevector 模式下的最终 Fidelity；
- 是否触发 repair；
- backend case 的最终 canonical ID 列表或 no-match；
- 若失败，只记录清洗后的错误类型 / 原因。

不得记录：

- API Key；
- Authorization Header；
- `.env.l2.local` 内容；
- traceback 中的本机绝对路径；
- 完整模型原始响应日志（除非测试失败时仅在本地临时查看，且不提交）。

可以新增一个**不包含敏感数据**的本地/测试脚本或回归报告生成器，但不要提交真实模型原始响应。

---

## 三、target judge 稳定性专项

这是本 Task 的最高优先级。

至少对以下 4 类 Prompt 做重复真实调用：

- GHZ 全测量；
- Bell+；
- Bell- / 相位目标；
- 一个稍微换一种自然语言表达的等价目标。

每类至少重复 3 次，检查：

1. `verification_mode` 是否一致；
2. `qubit_count` 是否一致；
3. target amplitudes 在数值容差内是否等价；
4. 相对相位是否一致；
5. 是否偶发 `unsupported`；
6. 是否出现 invalid target JSON / 未归一化 / basis 顺序错误。

### 对 `unsupported` 的处理原则

不要先猜策略，先统计真实结果。

若评分型明确 pure-state 请求（如 Bell/GHZ/明确振幅目标）出现 `unsupported`：

- 视为 target judge 失败；
- 优先通过最小 Prompt / structured protocol 修正；
- **不要把这种情况静默当作“语义验证成功”**。

对于确实无法可靠表示为 pure state 的自由请求，仍允许保留 `unsupported → Parser-only` 降级。

如果需要区分“评分型明确 pure-state 请求”和“无法验证的自由请求”，优先通过 judge 输出协议和明确失败语义解决；不要用 Bell/GHZ 关键词硬编码答案。

---

## 四、相位与 basis-order 专项

必须证明 verifier 不只是比较 Z-basis 概率。

至少验证：

1. Bell+ 与 Bell- 的 Z-basis 概率相同，但 statevector Fidelity 能区分；
2. global phase 不应导致失败；
3. target judge 的 basis 顺序与 Braket statevector / 项目 qubit 顺序一致；
4. 3-qubit GHZ 的 `000/111` 目标不会因 bit-order 错误产生假失败；
5. 含 `ry/rz` 的简单 pure-state Prompt 至少做 1 个真实回归，用于暴露相位 / 数值解析问题。

如发现 bit-order 问题，修复应落在 L2 semantic verifier / target protocol，不要修改 L1 Parser 对外语义。

---

## 五、调用次数与 120 秒时限

正式 `l2_policy.json` 是**每个 case 总时限 120 秒**。

必须测量完整 `agent_chat()` wall-clock 时间，而不是单次 HTTP timeout。

期望：

```text
backend selection：1 次模型调用
QASM 正常：2 次模型调用（候选 + judge）
QASM 失败后修复：最多 3 次模型调用
```

### 门槛

- 任一 case 不得超过 120 秒；
- 建议给正式环境保留明显余量，不要把“119 秒能过”视为稳定；
- 若最坏路径耗时过高，优先优化 Prompt 长度、调用顺序和 timeout budget；
- 不要通过取消 semantic verifier 来换速度；
- 不增加第 4 次模型调用。

如需调整 `LOOMQ_LLM_TIMEOUT_SECONDS` 的内部使用方式，必须保持环境变量契约兼容，并保证整个 case 的 deadline 意识清晰。

---

## 六、只根据真实失败做最小修正

真实回归暴露问题后，允许修改：

- `starter_kit/loomq/l2_agent.py` 中的 system prompt / target judge prompt；
- structured JSON 解析的轻量容错；
- `semantic_verifier.py` 的 bit-order / statevector 适配；
- L2 专项测试；
- 必要的回归脚本。

每一个修正都必须对应一个真实失败案例，并补成确定性测试。

不要：

- 针对上述 12 个 Prompt 写关键词固定答案；
- 硬编码 Bell/GHZ QASM；
- 让候选模型自己给出 expected target 后自验；
- 增加新的量子 SDK；
- 引入大 Agent/RAG 框架；
- 修改 `backend_capabilities.json`；
- 修改 L1 Parser 语义；
- 开始 L3；
- 做 UI / CLI。

---

## 七、干净环境验证

L2 语义路径必须证明 pinned Braket SDK 在正式类似环境能运行。

至少完成：

1. 从当前 `starter_kit/Dockerfile` 构建干净镜像；
2. 确认 `requirements.txt` 中 pinned `amazon-braket-sdk` 正常安装；
3. 在容器中不带真实 Key 先跑全量离线单元测试；
4. 再通过运行时环境变量注入真实 L2 配置，至少跑：
   - 1 个 Bell/GHZ semantic case；
   - 1 个 backend selection case；
5. 确认容器内没有依赖 `.env.l2.local` 文件本身。

真实 Key 只能以运行时环境变量方式注入，不能 COPY 进镜像、不能写进 Dockerfile、不能出现在镜像层或提交文件里。

---

## 八、官方 public evaluator

真实回归稳定后，从 `starter_kit/` 目录运行：

```bash
python evaluator.py --level l2
```

确认 public L2 evaluator 通过。

随后再跑完整测试套件，确保：

- L1 无回归；
- L2 单元测试通过；
- semantic verifier 测试通过；
- backend selector 测试通过；
- 公共 evaluator 通过。

---

## 九、L2 开启门槛

只有以下条件**全部满足**时，才允许修改 `starter_kit/submission.yaml`：

- 12 类 hidden-like 基础矩阵全部最终成功；
- 明确 pure-state 的评分型请求没有静默 `unsupported`；
- Bell+/Bell-/GHZ 相位与 Fidelity 专项通过；
- target judge 重复测试没有发现无法解释的不稳定输出；
- 所有 case 总耗时 < 120 秒，且最坏路径有合理余量；
- 最多 3 次模型调用的上限保持；
- backend selection 仍为 1 次模型调用；
- 干净 Docker 中 L2 semantic 路径可运行；
- `python evaluator.py --level l2` 通过；
- 全量测试无 L1 回归；
- Key / `.env` / Authorization 等敏感信息未进入 git。

满足后修改：

```yaml
levels:
  l2: true

network:
  required_for_l2: true
```

不要修改 L3。

如果任一开启门槛不满足：

- **不要开启 L2**；
- 保持 `submission.yaml` 原状；
- 汇报具体失败项和建议的最小下一步。

---

## 十、测试要求

除了真实 DeepSeek 回归外，至少补齐或确认确定性测试覆盖：

1. pure-state 请求若 judge 返回 unsupported，不能被误当作已完成语义保证；
2. Bell+ / Bell- 相位区分；
3. global phase；
4. bit-order；
5. target judge malformed JSON / 非法 target spec；
6. 2-call 正常路径；
7. 3-call 修复路径；
8. 不出现第 4 次调用；
9. backend 仍恰好 1 次调用；
10. L1 回归。

---

## 完成后汇报

只汇报：

1. 12 类 hidden-like case 的成功率；
2. target judge 重复测试结果；
3. `unsupported` 次数、出现在哪类请求、如何处理；
4. 相位 / bit-order 专项结果；
5. 每类模型调用次数，以及最慢 case 总耗时；
6. 是否做过最小 Prompt / 协议修正，以及对应的真实失败原因；
7. Docker L2 验证结果；
8. `python evaluator.py --level l2` 结果；
9. 全量测试结果；
10. `submission.yaml` 是否满足门槛并已开启 L2；若未开启，明确阻塞项。

不要提交真实 API 响应、API Key 或敏感日志。

不要 commit，不要 push。
