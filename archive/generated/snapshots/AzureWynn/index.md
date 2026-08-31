# LoomQ-2026 参赛预研与行动计划

> 赛事：SheNicest 2026 夏季千人烈变黑客松 · **LoomQ 量子接入平权计划**
> 仓库：`QAIDAO/LoomQ-2026` · 截止：**2026-08-25 12:00 (UTC+8)** · 纯线上、无答辩
> 今日：2026-08-17，剩余 **约 8 天**

---

## 一、赛事一句话

做一个**"量子通用中间层 + 说人话的智能体"**：任何懂自然语言的人，都能生成/修复量子程序，并驱动真实的量子云平台（量旋 / 本源 / AWS Braket）。

- 不需要量子物理背景，官方附《QUANTUM 101》30 分钟速成手册。
- 入门档（评奖资格线）本地即可完成：**同一套中间层在 ≥2 个模拟器后端跑通公开电路**，无真机账号、无排队。

## 二、评分体系与目标设定（总分 100 + 12）

| 模块 | 分值 | 核心考点 | 目标 |
|---|---|---|---|
| L1 通用中间层 | 45 | 是否真正"统一"地打通多平台 | **必拿**，保底 12 → 冲 25+ |
| L2 智能体 | 30 | 让不懂 QASM 的人也能用 | 冲 20（客观分）+ 交互 |
| L3 混合编译 | 15 | 量子-经典混合编译 | 视时间，7~15 |
| 工程与产品化 | 10 | 可复现、可交付、有叙事 | 必拿 8~10 |
| Bonus | +12 | 自定义量子 RISC-V / 新手引导 | 视时间 |

**L1 评分阶梯（关键）**：
- 入门档 = 12 分（≥2 模拟器后端跑通公开电路）→ **评奖资格线**
- 进阶 = 第三平台打通 / 隐藏电路保真度达标，线性计分 → 至 35
- 真机 = 每平台主峰命中 +5（最多 2 平台）→ +10
- 满分 = 三平台统一 + 8 电路全过（Fidelity≥0.97，shots=8192）+ 2 平台真机 = 45

> **策略结论**：L1 是地基（L2 的"自验闭环"、工程分都依赖它）。时间线先保 L1 三平台全绿，再上 L2，最后看余量做 L3/Bonus。

## 三、环境搭建（本地）

### 3.1 必装清单
| 组件 | 版本/命令 | 用途 |
|---|---|---|
| Python | **3.10**（官方镜像 `python:3.10-slim`，spinqit 最高只发 cp310 wheel） | 运行时 |
| Docker | 最新 | 容器基线验证 |
| Git | 最新 | 提交流程 |
| uv / pip | 任选 | 依赖管理 |

### 3.2 三个后端 SDK（本地模拟器全部免费、无需账号）
```bash
pip install spinqit==<锁定版本>          # 量旋，自带 Taurus 本地模拟器
pip install pyqpanda==<锁定版本>         # 本源，CPUQVM 本地模拟器
pip install amazon-braket-sdk==<锁定版本> # AWS Braket LocalSimulator
```
> 依赖**必须精确锁定版本**（`==`），写入 `starter_kit/requirements.txt`。禁止 `>=`。

### 3.3 L2 调试（可选但推荐）
自备 OpenAI-compatible Key（DeepSeek 官方即可），仅用于本地调试：
```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<自己的KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
export LOOMQ_LLM_TIMEOUT_SECONDS=120
```
> 代码里**绝不能硬编码** URL / Key / 模型名；必须读取 `LOOMQ_LLM_*`。正式评测由组委会注入 DeepSeek 服务。

### 3.4 真机账号（加分用，可选）
- 量旋 SpinQ Cloud：注册即用，**推荐作为首个打通的真机**
- 本源量子云：注册 + 申请 API Token
- AWS：本赛题允许用 LocalSimulator 替代，无需付费云端

### 3.5 Git 配置（已完成）
```bash
git init && git branch -m main
git config user.name  "A.W"
git config user.email "parabole.aw@gmail.com"
```

## 四、参赛流程（端到端）

```text
1. fork QAIDAO/LoomQ-2026   ← fork 必须归提交账号（= Team ID）
2. 克隆到本地 → 创建本队实现分支
3. 实现 starter_kit/adapter.py（transpile / run / agent_chat / compile_hybrid）
4. 填写 starter_kit/submission.yaml（levels 勾选）
5. 锁版本依赖 → requirements.txt；可选改 Dockerfile
6. 本地自测：python3 starter_kit/evaluator.py --json-out report.json
   （额外：docker build -t loomq-submission . && docker run --rm loomq-submission）
7. git commit + git push（确保 HEAD 已推送）
8. 预检：python3 starter_kit/prepare_submission.py --team-id <GITHUB用户名>
   （要求：工作区干净、HEAD 已 push、origin 属于自己、必需文件齐全）
9. 在上游 QAIDAO/LoomQ-2026 用 "LoomQ 最终提交" Issue Form 提交：
   Team ID + fork 地址 + 40 位 commit SHA
10. 等待 submission:accepted 标签 + 归档回执 = 提交成功
11. 更新代码后必须新建 Issue（不可编辑旧 Issue），截止前最后一次有效提交生效
```

**提交契约要点**：
- 正式评测只提取 fork 里的 `starter_kit/` 作为评测根目录。
- `submission.yaml` / `adapter.py` / `Dockerfile` / `README.md` 为必需文件。
- 归档 ≤ 100 MiB；不提交任何 Key / Token / 隐私。
- 截止判定以 GitHub 服务器 Issue `created_at` 为准。

## 五、技术方案（做什么 / 怎么做 / 做成什么样）

### L1 通用中间层（45 分，地基）
**接口**（`starter_kit/adapter.py`）：
```python
def transpile(qasm_str: str, target: str) -> str   # target ∈ spinq/originq/braket
def run(qasm_str: str, target: str, shots: int) -> dict
```
**做什么**：
1. **QASM 2.0 解析器**：只需支持 12 个白名单门 `h x s sdg t tdg rz ry cx cu1 swap ccx`（可先用自定义解析器，避免引入重依赖）。
2. **transpile 三路输出**（规范见 `target_ir_contract.md`）：
   - `spinq` → 原样 OpenQASM 2.0（透传 + 门降级即可）
   - `braket` → OpenQASM 3.0（`qubit[2] q; bit[2] c;` + `cnot`，`cx/cnot` 均接受）
   - `originq` → OriginIR（`QINIT 2 / CREG 2 / H q[0] / CNOT q[0],q[1] / MEASURE q[0],c[0]`）
3. **run() 统一 Schema**（所有后端必须一致）：
   ```json
   { "backend": "spinq_taurus", "job_id": "...", "shots": 8192,
     "counts": {"00": 4102, "11": 4090}, "bit_order": "little",
     "timestamp": "...", "meta": {"transpiled_gates": 12, "depth": 5} }
   ```
   - `counts` 总和必须 == shots；bit_order 固定 `little`（最右是 c[0]）——跨平台位序在中间层内归一化。
   - `meta` 中**禁止 `is_mock: true`**（判 0 分）。
4. **门降级**：按官方 `gate_identities.md` 照抄分解（swap=3cx、cu1、ccx、相位门→u1、ry 兜底）。
5. **真机证据**（+10）：提交各平台原始 `result.json`（job_id 可溯源 + timestamp 在赛程内 + 主峰命中）。

**做成什么样（验收标准）**：
```bash
python3 starter_kit/evaluator.py --level l1 --target spinq,originq,braket --json-out report.json
# 全部 PASS：bell + ghz3 × 3 目标，Fidelity ≥ 0.97
# 再用自写 8 电路测试集（Bell/GHZ-3/GHZ-5/QFT-4/Grover-3/Random×3）内部回归
```

### L2 智能体（30 分）
**接口**：`agent_chat(prompt: str) -> str`
**做什么**：
1. 读取 `LOOMQ_LLM_*` 环境变量，完成 ≥1 次有效模型调用（`llm_client.py` 是官方无依赖传输示例）。
2. **三类任务**（真实评测为未公开 prompt 变体，靠硬编码无效）：
   - 意图生成 → 输出 OpenQASM 2.0（如"3 比特 GHZ 全测量"）
   - 代码纠错 → 保持用户声明意图，修复并输出正确 QASM
   - 智能选后端 → 回复必须含规范标识（如 `braket_local_simulator`）
3. **推荐工程闭环**：生成 QASM → 调用自己的 `run()` 在本地模拟器自验 Fidelity ≥ 0.97 → 不对就重试（这是最大提分点）。
4. **选后端知识库**：直接加载 `backend_capabilities.json` 做约束筛选，别靠模型背诵。
5. **交互入口**（冲完整 30 分）：Web / CLI 均可，零基础可操作；证据包写明启动命令 + 3 个用户体验任务。

**做成什么样**：`python3 evaluator.py --level l2` PASS；再用自己的 key 做 12 组变体回归。

### L3 混合编译（15 分）
- 解析 Hybrid-QASM 的 `classical { }` 块（迷你文法：`r1..r9` 寄存器、`+ - == !=`、if/else、顺序赋值）。
- 输出：量子操作序列 + RISC-V 汇编文本（指令子集 `li add sub addi beq bne j`）。
- 测量位 `c[k]` → 寄存器 `x10+k`；用官方 `riscv_emulator.py` 穷举注入验证。

### 工程与产品化（10 分）
- README：一键 `setup + run`（干净环境可复现）。
- 架构文档：说明主要模块、目标用户、完整使用流程（可引用主 README）。
- 必答题叙事：**"你的工具让哪一类原本进不来的人，第一次能用上量子计算？"**

### Bonus（+12）
- 自定义量子 RISC-V 扩展（+8）：指令编码规格文档 + fork 模拟器加指令 + 端到端测试，三者齐备。
- 新手引导与视觉叙事（+4）：首次运行指南、概念解释、结果可视化、错误恢复/无障碍。

## 六、证据包（人工分）
- 只需编辑 `starter_kit/evidence/README.md`，勾选申报项并填写；附件放 `evidence/files/`。
- 真机分：每平台填 平台/job ID/运行时间/shots/实际执行 QASM/原始结果路径 + 截图。
- L2 交互：启动命令 + 测试入口 + 3 个用户任务。
- 不申报就留空，不影响自动分。

## 七、8 天行动计划（2026-08-17 → 08-25）

| 日期 | 任务 | 产出/验收 |
|---|---|---|
| D1 (8/17) | 环境搭建 + fork/克隆 + 阅读 starter_kit | 3 个 SDK 装好、本地 evaluator 基线能跑 |
| D2 (8/18) | L1：QASM 解析器 + spinq/braket 两模拟器打通 | `bell/ghz3 × spinq/braket` PASS（**先达入门档 12 分**） |
| D3 (8/19) | L1：originq 打通 + 门降级 + 位序归一化 + 自写 8 电路回归 | 三平台全绿，fidelity≥0.97 |
| D4 (8/20) | 真机申请（SpinQ Cloud）+ 提交真机任务拿原始结果 | 1 平台真机证据（+5） |
| D5 (8/21) | L2：agent_chat + 自验闭环 + backend_capabilities 选型 | `evaluator --level l2` PASS |
| D6 (8/22) | L2 交互入口（CLI/Web）+ 3 个用户体验任务 | 完整 30 分形态 |
| D7 (8/23) | L3 或 Bonus；README/架构文档 + evidence 填写 | 工程分拿满 |
| D8 (8/24) | 全量回归（含 Docker）+ 预检 + **创建最终提交 Issue** | `submission:accepted` 回执 |
| D8+ (8/25 12:00 前) | 缓冲：修复 / 重新提交（新建 Issue） | 截止前最后一次有效提交 |

## 八、风险与注意
1. **别硬编码**：L2 的 prompt 变体、L3 随机用例、L1 隐藏电路都是评测时生成——针对公开样例打表必挂（相关模块判 0 分）。
2. **bit 位序**：跨平台 counts 位序不同，必须在中间层归一化为 little-endian。
3. **依赖锁版本**：容器内精确重建，`==` 必须。
4. **只读环境**：评测默认禁止网络（L2 只有注入的模型服务），不要依赖外部 API。
5. **Key 安全**：任何 Key/Token 不得进仓库；错误信息不得回显 Key。
6. **提交流程**：先跑 `prepare_submission.py` 预检；Issue 创建后不可编辑替换，更新需新建 Issue。
7. **归档体积** ≤ 100 MiB，大视频用稳定只读链接。

---
*Git config 已设：Author: A.W <parabole.aw@gmail.com>（分支 main）*