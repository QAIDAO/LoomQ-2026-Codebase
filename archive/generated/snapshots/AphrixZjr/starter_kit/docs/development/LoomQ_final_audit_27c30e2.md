# LoomQ-2026 最终静态与归档审计报告

审计对象：`AphrixZjr/LoomQ-2026`  
最终提交：`27c30e20e4a87481f73af3d57cd6007d1afe5ac0`  
上游最终提交：`QAIDAO/LoomQ-2026#26`  
归档 SHA-256：`247535f10b17393b24d1e5fffe830714bf25a53d27545cac0fb081460d6d2903`  
审计日期：2026-08-11

## 零、审计结论更新（2026-08-16）

> 下方“一”至“十”保留 2026-08-11 对审计对象 `27c30e2` 的原始判断；当前结论以本节和 [`verification.md`](../acceptance/verification.md) 为准。

| 审计项 | 当前状态 | 可核验证据 / 剩余动作 |
|---|---|---|
| SpinQ 统一 Schema、时间戳与五件套绑定 | **已修复** | 四个既有 job 均新增 `source/submitted/request/raw/summary`，summary 使用 provider `createdTime`，公共 Schema、SHA-256、measurement map、请求/provider shots 进入 [`test_l1_spinq_hardware.py`](../../tests/test_l1_spinq_hardware.py)；旧路径保持逐字节兼容 |
| SpinQ 核磁真机 +5 规则口径 | **外部待确认** | `triangulum_vp` 是真实核磁硬件，但题面“超导”与能力表“超导 / 核磁”仍冲突；仓库没有组委会书面确认，`submission:accepted` 不代表已确认 +5 |
| provider key 方向与 platform snapshot | **声明已降格，实证待补** | 回文 `101` 不再被表述为方向证明；[`bit_order_direction.qasm`](../../circuits/bit_order_direction.qasm) 已作为不进入默认批次的 opt-in 单任务，当前没有新 job/raw/summary。平台能力字段也明确标记未归档，须在有凭证时只读补录 |
| L2 平台、账号、费用与 QPU 否定表达 | **已修复** | 本地直接支配约束覆盖 `without/except/no paid services/real machine/physical quantum computer` 等表达，模型分类不能覆盖 prompt 的确定性事实；见 [`test_l2_audit_regressions.py`](../../tests/test_l2_audit_regressions.py) |
| L2 已知错误候选与 repair 失败 | **已修复** | 已知 Bell/GHZ 语义错误不再回退为答案；repair 失败改用同一 oracle 验证的 canonical target |
| L2 累计预算 | **已修复** | 3 attempts、1 次瞬态 retry、累计输入 8,000、累计输出 2,000、单次默认 900/硬上限 1,000；每次 `max_tokens` 在 transport 前收缩到累计剩余额度，余额为零不发请求。usage 优先，无 usage 时输入按 UTF-8 字节上界、输出按实际请求 cap 预留，畸形 HTTP 成功响应也记账；见 [`test_l2_budget.py`](../../tests/test_l2_budget.py) |
| L2 三轮 adversarial live | **已验证** | 当前源码先通过 12-case smoke 12/12，再运行固定 12 + 压力 72 + adversarial 20 三轮，共 [312/312](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.json)，每轮 104/104；JSON 与 [raw stdout](../../evidence/files/l2-raw-prompt-stress-remediation-20260815.stdout.txt) SHA-256 绑定有效，公开 evaluator [1/1](../../evidence/files/evaluator-l2-remediation-20260815.json)，artifact 未记录模型环境值 |
| L3 continuation 指数膨胀 | **已修复** | 所有可映射宽度均使用共享 CFG；width 22 按 `c[21]=0/1` 特化两条共享路径并恢复 `x31`，width > 22 在汇编生成前硬拒绝。20 个顺序 `if` 为 1,021 行 / 16,494 字节，深度 4 为 700 行 / 10,819 字节，并通过全组合差分、唯一标签与 `max_steps` 门禁 |
| Web measurement collision 与 proposal/run 对齐 | **已修复** | 客户端和服务端均禁止应用/运行结构不安全映射；服务端在最终操作前重新解析验证。目标不一致与结构危险分离，只允许带 `target_supported=false` 和固定边界的探索运行 |
| 真机证据对比视图 | **已修复** | `/api/hardware-evidence` 只读取 SpinQ/OriginQ × Bell/GHZ 四个正式 summary 精确白名单，先过公共 Schema 再校验任务身份、位宽与 counts；Docker 构建只纳入这四份非敏感 summary，缺失/伪造/smoke/垃圾 key 均拒绝并在 UI 显示不完整 |
| 完整八阶段浏览器 E2E | **已验证** | Edge 151/CDP 实跑响应式 4/4、完整流程 22/22；[`browser_agent_flow_check.mjs`](../../browser_agent_flow_check.mjs) 完成 8 次 Agent 发送、真机复盘完整性、验证、运行、结果/边界、删除 CX 与撤销；[`browser_responsive_check.mjs`](../../browser_responsive_check.mjs) 等待真实 DOM，任一缺失/溢出/运行时错误会非零退出 |
| Linux cold build 独立 CI | **workflow 已实现，远端记录待补** | [`starter-kit-cold-build.yml`](../../../.github/workflows/starter-kit-cold-build.yml) 包含 `--pull --no-cache`、容器 268 tests、L1 regression、L1/L3 evaluator、Web health、真机证据集合断言和两项 headless Chrome 检查。完整测试只把 checkout 的 `evidence/` 只读挂载到一次性测试容器；最终 Web 启动不带挂载，镜像仍只含四份 formal summary；本机没有可用 Docker daemon，运行结果由远端 CI 提供 |
| 文档错位 | **已修复** | emitter 格式、L2/transport 职责、Smoke normalization、历史审计醒目标记、预算默认值和证据边界均已校正 |

本地验证执行 `starter_kit` 268/268 与仓库级 294/294 单元测试，L2 六模块专项为 115/115；L2/L3 public evaluator 均为 1/1。L2 真实模型三轮为 312/312。L1 evaluator 在当前主机因缺少锁定的 pyQPanda/Braket SDK 只能完成 SpinQ 2/2，另外 4 项明确失败；三平台 L1 regression 同理为 31/93，缺失 SDK 的 62 项失败，均须由新容器 CI 补证。Python/JavaScript 语法、Compose 配置、workflow 静态检查和 `git diff --check` 均通过。

因此，审计中的可离线修复项和 L2 真实三轮均已落地；仍不能把本节写成“稳定 112/112 已完成”。最终闭环还需要：组委会核磁计分书面确认、SpinQ 方向探针与 platform snapshot、远端 cold-build 绿灯，以及 preflight、Issue accepted 与归档回执。

## 一、总评

新提交已经把项目从“理论上只能争取 107/112”推进到“具备争取 112/112 的实际交付条件”：

- OriginQ 和 SpinQ 两个平台均有可追溯真机任务；
- L1 三平台统一软件路径保持完整；
- 修改后真实 `deepseek-v4-flash` 验证为 12/12 与 72/72；
- L3、工程化、量子 RISC-V Bonus 和新手体验交付均仍在正式归档中；
- Issue #26 已获得 `submission:accepted` 和正式归档回执。

但当前版本仍不宜称为“稳定满分”。阻碍稳定取得 112 分的主要问题按优先级为：

1. SpinQ 四个结果 JSON 缺少赛事统一 Schema 必需的 `timestamp`；
2. 题面文字只写 SpinQ “超导真机”，而当前证据是 Triangulum 核磁真机；机器能力表又明确允许“超导 / 核磁”，存在规则口径冲突；
3. SpinQ 证据没有把 source QASM、云端实际提交 QASM、测量配置和 q→c 映射作为一个完整绑定对象归档；
4. 当前所谓“非对称位序探针”的物理态为 `101`，在整体反转下仍是 `101`，不能真正排除 provider key 方向整体反转；
5. L2 后端选择对 `AWS without an account`、`except AWS`、`no paid services`、`real machine` 等自然表达存在确定性错误；
6. L2 已经知道 Bell/GHZ 候选语义错误时，若修复调用失败，仍可能返回该错误候选；
7. 旧 PDF 的累计 8,000 输入 Token / 2,000 输出 Token 约束未被严格实现；
8. L3 对顺序分支复制后续 continuation，输出规模随分支数指数增长；
9. Web 验证为失败的测量映射仍可以被执行，失败的 Agent QASM proposal 仍可确认应用；
10. 当前证据链缺少远端 Linux cold build 和容器内完整测试的独立 CI 记录。

当前风险调整后的中心判断约为 **109–111/112**。修复本报告的 P0/P1 项后，112 分将成为合理目标，但 L2 体验、工程叙事和视觉 Bonus 含主观判断，任何静态审计都不能保证评委一定给满。

---

## 二、实际归档核验

本轮下载并检查了 Issue #26 的实际 GitHub Actions Artifact，而不是只读取 fork 工作树。

### 2.1 身份与边界

- 外层 ZIP SHA-256：`04f77d10c87a3a204ea42563cc69ba04a36e70d22475ec98704171a277ecec34`
- 内层 `loomq-submission.tar.gz` SHA-256：
  `247535f10b17393b24d1e5fffe830714bf25a53d27545cac0fb081460d6d2903`
- 内层哈希与上游自动归档回执一致。
- 完整归档包含 168 个文件。
- 正式 `starter_kit/` 包含 147 个文件，展开约 1.77 MB。
- 无符号链接。
- Markdown 相对链接缺失数：0。
- 常见 GitHub/AWS/OpenAI Token 与私钥模式扫描：0 命中。

### 2.2 独立执行

直接在下载后的归档代码上执行：

| 检查 | 结果 |
|---|---:|
| `python -m unittest discover -s starter_kit/tests -v` | 233/233 PASS |
| `python -m unittest discover -s tests -v` | 259/259 PASS |
| L3 公开 evaluator | 1/1 PASS |
| 量子 RISC-V 官方入口 E2E | 4/4 PASS |
| Manifest artifact 哈希 | 67/67 匹配 |
| Manifest 命令日志哈希 | 全部匹配 |

本环境没有 SpinQit、pyQPanda、Braket SDK、Docker daemon 或 DeepSeek 凭证，因此无法独立重跑三供应商 SDK、Docker cold build、真实模型和云端 job 查询。这些部分只确认了归档日志、哈希和结构内部一致；不能代替评委登录云平台复核。

---

## 三、新 SpinQ 真机证据

## 3.1 结果本身满足 Top-K 目标

正式 Bell：

```text
00 = 3709
11 = 2917
01 = 1025
10 = 541
理想支撑质量 = 0.808837890625
```

`00/11` 是前两大主峰。

正式 GHZ-3：

```text
000 = 3520
111 = 3484
110 = 426
100 = 310
其余更低
理想支撑质量 = 0.85498046875
```

`000/111` 是前两大主峰，且两者内部比例接近 1:1。

任务元数据中的 job ID、platform、shots 与 result JSON 一致；创建时间与客户端提交时间顺序合理。概率总和、最大余数法 counts、顶层 classical projection 和分析文件的支撑率均可重新计算。

## 3.2 P0：四个 SpinQ JSON 不符合统一结果 Schema

赛事统一结果至少要求：

```json
{
  "backend": "...",
  "job_id": "...",
  "shots": 8192,
  "counts": {},
  "bit_order": "little",
  "timestamp": "..."
}
```

当前 SpinQ JSON 使用：

```text
submitted_at
completed_at
recovered_at
```

但没有 `timestamp`。将四个文件直接交给仓库自己的 `evaluator.validate_schema()`，结果全部为：

```text
missing fields: timestamp
```

OriginQ 的四个 `*-summary.json` 则全部通过相同 Schema 验证。

### 修复

不要改写或删除当前 provider-oriented JSON。为每个 job 增加标准摘要：

```text
spinq-...-raw.json       # 当前完整 provider-oriented 内容
spinq-...-summary.json   # 赛事统一 Schema
```

summary 的 `timestamp` 应优先使用只读 task metadata 的 `createdTime`，而不是本地恢复时间。`meta` 应包含：

```json
{
  "provider": "SpinQ Cloud",
  "device_code": "triangulum_vp",
  "sdk_api": "spinqit-0.2.4",
  "result_kind": "probabilities",
  "counts_normalization": "probabilities-largest-remainder",
  "measured_qubits": [0, 1, 2],
  "measurement_map": [
    {"qubit": 0, "classical": 0}
  ],
  "source_qasm_sha256": "...",
  "submitted_qasm_sha256": "...",
  "raw_evidence_file": "..."
}
```

同时让未来 `execute_spinq_hardware()` 直接输出 `timestamp` 和标准 `meta`，并增加：

```python
assert evaluator.validate_schema(result) == (True, "schema valid")
```

## 3.3 P0：核磁真机的规则口径需要明确

旧题面和当前 `problem_statement.md` 都把 SpinQ L1 路径写成“Taurus 模拟器或超导真机”。当前真机是 `triangulum_vp`，即三比特核磁共振真机。

另一方面，当前官方机器能力表把 `spinq_cloud_qpu` 明确写为：

```text
量旋云真机（超导 / 核磁，2–8 比特）
```

量旋官方产品资料也将 Triangulum 描述为真实三比特核磁量子系统，并支持远程硬件访问。

因此它事实上的确是真实量子硬件，但赛事文字存在“超导专指”与“超导/核磁均可”的冲突。`submission:accepted` 只证明归档合法，不代表评委已经确认该物理路线可得 +5。

### 最稳妥处理

向组委会提交一个非常窄的书面确认问题：

> `backend_capabilities.json` 将 `spinq_cloud_qpu` 定义为“超导 / 核磁”真机。请确认通过 SpinQ Cloud `triangulum_vp` 执行并可追溯的核磁真机任务，符合 L1“每个平台真机 +5”的口径。

取得肯定答复后，把回复或公开 issue 链接放入证据入口。

若组委会坚持“SpinQ 必须超导”，则只有在账号有权限时改跑 `superconductor_vp`；不要在未确认前盲目消耗另一批算力。

## 3.4 P1：证据没有完整绑定实际测量请求

SpinQ Cloud 不接受显式 `MEASURE` 指令，测量通过：

```python
configure_measured_qubits(...)
```

单独配置。当前 evidence `.qasm` 保存的是去掉 measurement 的实际云端程序，但 JSON 没有保存：

- `measured_qubits`
- 原 QASM 的 q→c 映射
- 完整 source QASM
- task request 的 platform/shots/name/description

因此，仅凭 evidence `.qasm` 无法重建最终 classical counts 的含义。

### 修复

每项任务归档四个对象：

```text
*-source.qasm       # 含 measurement 的 LoomQ 输入
*-submitted.qasm    # 实际交给 SpinQ compiler 的无 measurement QASM
*-request.json      # platform/shots/measured_qubits/measurement_map/哈希
*-raw.json
*-summary.json
```

程序层还应验证 provider 返回的 `_shots` 与请求 shots 完全一致；当前代码会在概率存在时直接按请求 shots 重新折算，未硬拒绝 provider shots 不一致。

## 3.5 P1：当前位序探针不能排除整体 key 反转

当前 probe 制备：

```text
q0 = 1
q1 = 0
q2 = 1
```

provider 原始主峰是 `101`。由于 `101` 在字符串反转后仍为 `101`，无论 provider 的左端对应 q0 还是 q2，都得到同一个 raw key。

它确实验证了当前 classical permutation 代码的一部分，但不能支撑“排除明显整体位序错误”的强表述。

### 新 probe

只需再跑一个 100-shot 任务：

```qasm
OPENQASM 2.0;
qreg q[3];
creg c[3];
x q[0];
measure q[0] -> c[2];
measure q[1] -> c[0];
measure q[2] -> c[1];
```

期望 classical key 为 `100`。provider raw key 在两种相反 qubit-order 假设下将分别是 `100` 与 `001`，可以真正区分方向。

若不愿新增任务，则把现有文案降格为：

> 支持当前 q→c permutation 的结果一致性，但该物理态本身不能独立区分 raw key 的整体反转方向。

## 3.6 建议增加只读平台快照

当前 task metadata 只保存：

```text
platform = triangulum_vp
raw_status = S
shots
createdTime
```

建议再通过只读平台查询归档：

```json
{
  "code": "triangulum_vp",
  "name": "...",
  "max_bitnum": 3,
  "simu": false,
  "online_machine_count": "...",
  "support_gate_names": []
}
```

这能直接证明 `triangulum_vp` 不是 SpinQit 的 `simulator` platform，并减少评委对 `_vp` 后缀的疑问。

---

## 四、L2 客观分

## 4.1 当前实证明显增强

冻结源码上的真实模型结果为：

```text
固定 12-case：12/12
72-case 压力集：72/72
generate：24/24
repair：24/24
backend：24/24
P95：6.859 秒
最大：11.640 秒
```

这对 20 分客观项是强证据。源码 S 之后没有可执行 L2 变化，因此证据与最终提交在代码上对齐。

但这两套集合没有覆盖以下已复现失败表达，因此不能视为隐藏集保证。

## 4.2 P0/P1：后端自然语言恢复有确定性错误

当前平台否定逻辑是在平台名称前后 12 个字符内搜索：

```text
不要 / 不使用 / 排除 / avoid / not / without
```

并把本地结果作为 hard constraint 覆盖模型输出。

实际复现：

| Prompt | 当前结果 | 正确结果 |
|---|---|---|
| `Use AWS without an account for 20 qubits.` | `spinq_taurus_simulator` | `braket_local_simulator` |
| `Use AWS without requiring an account...` | `spinq_taurus_simulator` | `braket_local_simulator` |
| `Use AWS but no paid services...` | `braket_cloud` | `braket_local_simulator` |
| `I don't want AWS; choose a 25-qubit simulator.` | `braket_local_simulator` | `originq_local_simulator` |
| `Choose any 25-qubit simulator except AWS.` | `braket_local_simulator` | `originq_local_simulator` |
| `Run 20 qubits without using AWS.` | `braket_local_simulator` | `spinq_taurus_simulator` |
| `Use a real machine for 8 qubits.` | 本地模拟器 | QPU |
| `Use a physical quantum computer for 9 qubits.` | 本地模拟器 | `originq_wukong` |

其中：

- `without an account` 被误认为“排除 AWS”；
- `no paid services` 中的 `paid` 被误认为“必须付费”；
- `except AWS`、`don't want AWS` 没有被识别为平台排除；
- `real machine`、`physical quantum computer` 没有归一化为 `qpu`。

### 修复原则

不要再使用固定字符窗口判断平台否定。改用直接支配关系：

```text
avoid AWS
exclude Braket
do not use AWS
without using Braket
except AWS
but not AWS
不要 AWS
不使用 Braket
```

只有这些模式才形成 forbidden platform。

下列句子中的 AWS 应保持正向 platform constraint：

```text
AWS without an account
AWS without registration
AWS with no paid services
```

同时统一 model evidence 和本地 recovery 的同义词集合。

## 4.3 P0：本地已知语义错误候选仍会被返回

流程中，静态合法且测量映射合法的 QASM 会先进入 `best_candidate`，然后才做 Bell/GHZ 语义诊断。

若模型第一次返回：

```qasm
qreg q[3];
h q[0];
measure q -> c;
```

本地明确知道它不是 GHZ；但第二次 repair 调用失败时，函数仍返回这份候选。

一次 HTTP 503 也会消耗当前两次调用预算，导致后续没有语义修复机会。

### 修复

1. 对可信 Bell/GHZ target，只有 `semantic_diagnostic is None` 的候选才可进入 `best_candidate`。
2. 将总调用尝试上限设为 3，兼容旧 PDF：
   - 一次瞬态 HTTP 重试；
   - 一次有效初始响应；
   - 一次语义 repair。
3. 若至少已经完成一次有效模型响应，但 repair 失败，使用 `TargetSpec` 生成本地 canonical Bell/GHZ，再通过相同 oracle 验证后返回。
4. 未识别目标仍保持当前策略，只做静态验证，不擅自重写。

本次审计附带的 proposed patch 已实现这一恢复策略，并通过修改后的 237 项归档内测试；它没有写入用户仓库。

## 4.4 P1：兼容旧 PDF 的累计 Token 预算

旧 PDF 明确要求：

```text
最多 3 次模型调用
累计最多 8,000 输入 Token
累计最多 2,000 输出 Token
120 秒
```

当前机器 `l2_policy.json` 只保留 120 秒和 12 case；当前 transport 是每次默认 1,500、每次上限 2,000，未实现累计预算。

如果评委只按当前机器 policy，现状没有违规；若按 PDF，则两次响应理论上可申请 4,000 输出 Token。

### 稳定兼容方案

- 最多 3 次 attempt；
- 每次成功响应 `max_tokens <= 1000`；
- 正常流程最多两次成功响应，因此累计请求上限 <= 2,000；
- HTTP 429/503 不减少成功输出预算；
- 优先读取 provider `usage.prompt_tokens/completion_tokens`；
- provider 不返回 usage 时，用 UTF-8 byte count 作为保守 input-token 上界；
- 累计输入上界 8,000。

附带 patch 采用每次 900、硬上限 1,000，并增加保守累计输入预算。

> 当前实现（2026-08-16）：上文保留的是审计时观察到的历史现状。累计上限已写入 `l2_policy.json` 和请求上下文账本；每次请求的 `max_tokens` 在进入 transport 前收缩为“配置上限与累计剩余额度的较小值”，剩余额度为零时不再发请求。HTTP 成功响应即使正文无法形成可用模型对象，也按该次实际请求 cap 预留输出；非成功 HTTP 与未收到响应的 transport 异常不误记为输出。provider 返回 usage 时使用实际值，否则采用保守上界。

## 4.5 live benchmark 还应增加什么

在提交替换版前，新增 20–30 个 adversarial backend prompts，至少包含上述失败句式；然后：

```text
固定 12-case × 3
现有 72-case × 3
adversarial set × 3
```

记录：

- 每类通过率；
- repair 次数；
- HTTP retry 次数；
- canonical local recovery 次数；
- median/P95/max latency；
- 每 case 总输入/输出预算。

不要只保存汇总手写 JSON；同时保存原始程序 stdout 和 SHA-256。

---

## 五、L3

## 5.1 正确性仍然很强

当前实现确实覆盖：

- 完整线性条件；
- 顺序赋值；
- 任意整数系数；
- 负常量；
- 嵌套 if/else；
- `c[21]` 与 x31 边界；
- 量子操作序列保序和规范化。

现有差分测试和此前额外随机测试均支持其语义正确性。

## 5.2 P1：continuation 复制导致指数膨胀

当前每遇到一个分支，会分别编译：

```text
then_body + remainder
else_body + remainder
```

因此顺序 if 数量增加时，整个 remainder 被反复复制。

本轮实测：

| 顺序 if 数 | 汇编行数 | 字节数 |
|---:|---:|---:|
| 4 | 266 | 2,996 |
| 6 | 1,100 | 12,628 |
| 8 | 4,468 | 52,262 |
| 10 | 18,046 | 213,091 |
| 12 | 72,720 | 873,820 |
| 14 | 292,682 | 3,561,475 |

正确路径执行步数未必指数增长，但 compile output、parser load、内存和隔离进程传输会迅速放大。官方私有生成器的语句数未公开，这仍是 L3 满分的主要资源风险。

### 推荐实现

对 `classical_width <= 21` 的实际用例，保留 `x31` 为 compiler scratch，生成共享 CFG：

```text
evaluate condition into x31
branch to ELSE
compile THEN
j JOIN
ELSE:
compile ELSE
JOIN:
compile remainder once
```

赋值直接基于运行时 `r1..r9` 编译，不再把 branch environment 展开为完整 path tree。

`classical_width == 22` 时 x31 是 `c[21]`，可保留当前无临时寄存器的 symbolic fallback，或实现更复杂的 scratch 保存策略。由于评测会穷举测量组合，实际宽度通常不会很大，优先优化 <=21 能覆盖最现实的资源风险。

> 当前实现（2026-08-16）：没有保留上述 width-22 fallback。编译器先按原始 `c[21]` 分成 0/1 两条常数特化路径，再在每条路径中以 `x31` 生成共享 CFG，并于退出前恢复 `x31`。因此 22 位边界也只有固定两倍代码，顶部更新表中的 20-if 与深度-4 压力门禁已经覆盖该路径；上表 72,720 行等数字只描述旧实现。

至少应新增：

```text
10–20 个顺序 if
嵌套深度 4
5–8 个测量位
输出字节数上限
compile/load/execute time
最大执行 steps
```

若暂不重写，必须向组委会确认随机生成器的最大分支数，并把已验证范围写入验收材料。

---

## 六、Web、主观项与 Bonus

## 6.1 当前优势

- Agent-first 与显式非模型 fallback；
- proposal/diff/用户确认；
- stale revision 和 per-session lock；
- Bell/GHZ 目标语义验证；
- 模拟器、真机和教学计数边界清楚；
- 图表与数据表等价；
- reduced motion、色觉辅助、焦点和窄屏；
- 真机证据可用于展示理想与噪声差异。

这些足以支撑高 L2 体验分和视觉 Bonus。

## 6.2 P2：验证失败不阻止运行或应用

可构造两个量子位都写入 `c[0]` 的电路：

```text
validation.measurements.status = fail
validation.runnable = false
```

但 `run()` 只检查“至少有一个 measurement”，仍可执行；`runnable=false` 的 Agent QASM proposal 也可确认应用。

### 修复

- `run()` 拒绝结构性 measurement collision；
- 目标不一致可以允许运行，但必须显式标注“本次运行不支持当前目标”；
- proposal 增加：
  ```json
  {"safe_to_apply": true/false}
  ```
- 结构 fail 时禁用确认按钮；
- 或把文案从“经本地验证后应用”改为“展示验证结果，由用户决定是否应用”。

## 6.3 用新真机证据提升 +4 的稳定性

当前 Web 只运行本地模拟器。建议增加一个不调用云端的“真机证据复盘”视图：

- 同时加载 SpinQ 和 OriginQ 的正式 Bell/GHZ 摘要；
- 展示 ideal、SpinQ、OriginQ 三组 counts；
- 标出 job ID、时间、平台和“已归档真机结果”；
- 用同一数据表呈现泄漏、主峰和结论边界；
- 明确不是实时新提交。

这能把新真机成果直接转化为“视觉叙事”和“平权叙事”证据，而不把凭证或付费提交暴露给零基础用户。

再增加一个真实浏览器完整八阶段 E2E，覆盖：

```text
启动引导
八次发送
验证
运行
结果表格
结论边界
删除 CX
撤销
```

---

## 七、工程证据

当前归档哈希、测试、路径、秘密边界和两阶段证据模型内部一致。Issue #26 已正式 accepted。

剩余不足是没有公开远端 CI status；Manifest 也没有把以下过程作为一条不可编辑的单链：

```text
docker compose build --pull
容器内 233 tests
L1 regression
L1/L3 evaluator
Web start + healthcheck
browser checks
```

建议增加 GitHub Action，在 Ubuntu/Python 3.10 上 cold build 并上传日志。这样可证明 Docker image 确由目标 source snapshot 构建，而不是只证明“某个本地 image ID 曾运行通过”。

---

## 八、文档修正

1. `architecture.md` 把 L1 emitter 写成 SpinQ JSON / Braket JAQCD，实际正式 contract 是：
   - SpinQ OpenQASM 2.0
   - OriginIR
   - Braket OpenQASM 3.0
2. evidence 索引把模型调用预算和 retry 归到 `llm_client.py`，实际：
   - `loomq_l2.py`：总调用预算、retry、repair
   - `llm_client.py`：transport、timeout、response bytes、单次 output cap
3. SpinQ smoke Bell JSON 缺少 `counts_normalization`，而其 raw probabilities 明确存在；应补标准 summary，而不是让四个 job 的字段不一致。
4. 位序分析文案应在新增真正非对称 probe 前降格。
5. `docs/development/LoomQ_static_audit_d0900670.md` 顶部增加“历史问题已由后续提交修复”的醒目标记，避免评委误读旧的 99 分上限。

---

## 九、最终修改顺序

### P0：先做，直接影响 5–20 分

1. 为 SpinQ formal Bell/GHZ 增加标准 Schema summary，补 `timestamp`；
2. 取得组委会对 Triangulum 核磁真机 +5 口径的书面确认；
3. 修复 L2 platform/account/cost 否定解析；
4. 禁止返回本地已知语义错误 Bell/GHZ 候选；
5. 实现兼容旧 PDF 的累计模型预算。

### P1：显著提高隐藏集稳定性

6. 新跑真正方向非对称的 100-shot bit-order probe；
7. 归档 source/submitted QASM、measurement request 和 platform snapshot；
8. 将 L3 改为共享 CFG，或确认官方分支上限并加 stress；
9. adversarial L2 集重复三轮；
10. provider shots 必须与请求 shots 完全一致。

### P2：提高主观满分概率

11. Web validation fail 与 run/proposal 对齐；
12. 真机证据对比视图；
13. 完整八阶段浏览器 E2E；
14. Linux cold-build CI；
15. 修正文档小错位。

---

## 十、提交策略

保留 Issue #26 作为有效安全基线。不要编辑它替换 SHA。

完成 P0/P1 后：

1. 新代码冻结为 S；
2. 在 S 上运行全部本地、Docker、L2 live 和浏览器验收；
3. 真机无需重新跑 formal Bell/GHZ，标准 summary 可以从现有 raw + task metadata 确定性生成；
4. 若新增 bit-order probe，只提交这一项 100-shot 新任务；
5. 形成仅证据提交 E；
6. 确认 `S..E` 无可执行源码变化；
7. push E；
8. 运行 `prepare_submission.py`；
9. 新建最终提交 Issue；
10. 等待新的 `submission:accepted` 和归档回执。

截止前最后一个 accepted Issue 生效。
