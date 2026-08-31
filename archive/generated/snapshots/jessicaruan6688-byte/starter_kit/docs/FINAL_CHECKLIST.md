# 终局提交清单（私有备忘，截止前最后一次 Issue）

截止：**2026-08-25 12:00 UTC+8**。公开 fork 平时尽量少动；终局一次覆盖。

## 生效策略

- 资格件：已受理 Issue #9（仅 L1）— 先保留。  
- 终局件：约 8/22–8/24 推公开 `submission` → 新建最终提交 Issue。  
- 只认最后一次 `submission:accepted`。

## 建议终局申报

| 项 | 条件 |
|---|---|
| L1 | 三后端本地 + Docker 自检绿（已有私有验证记录） |
| L3 | `compile_hybrid` 已接；测试 7/7 |
| L2 | DeepSeek 本地实测已通；私有 `l2: true` + `required_for_l2: true`（公开终局再推） |
| 真机 | 两平台已齐：①量旋 2q Bell `G-260809-0018`；②量旋 3q GHZ `S-260810-0001`（本源过审仅作加成/保险） |

## `submission.yaml`（勾 L2 时必须改）

```yaml
levels:
  l1: true
  l2: true   # 未实测前保持 false
  l3: true
network:
  required_for_l1: false
  required_for_l2: true   # 勾 L2 时必为 true（否则官方 L2 case 会全挂）
  allowed_hosts: []       # 正式评测由组委会注入模型；本地调试用环境变量
```

路径必须是 **`starter_kit/`**（不要再用旧 `starter-kit/`）。

## 终局前自检命令

```bash
# 契约（按声明 Level）
PYTHONPATH=starter_kit python starter_kit/evaluator.py --level declared --target spinq,braket,originq

# L3
PYTHONPATH=starter_kit python starter_kit/tests/test_hybrid.py

# L2 单测（无 Key）
PYTHONPATH=starter_kit python starter_kit/tests/test_agent_unit.py

# L2 真调用（需 .env）
PYTHONPATH=starter_kit python starter_kit/tools/l2_chat_cli.py '生成一个 3 比特 GHZ 态并全测量'

# 预检
python3 starter_kit/prepare_submission.py --team-id jessicaruan6688-byte
```

## 真机证据（重要）

操作卡：[`SPINQ_HARDWARE.md`](SPINQ_HARDWARE.md)。

### 无效例（勿再交这类）

量旋 `G-260802-0004`：只有 `qreg`，**无门** → 不计真机分。  
**全振幅模拟器**任务 → 不计真机分。

### 平台二（现在就做）：3 比特核磁 GHZ

网页选 **3 比特核磁**，粘贴 `evidence/files/spinq-ghz3.TODO.qasm`（无 `measure`）。  
模拟主峰约 `000`/`111` → 提交真机 → 截图 + job_id → 填 `evidence/README.md`。

### L2 实测（并行）

```bash
cp starter_kit/.env.example starter_kit/.env
# 填 LOOMQ_LLM_BASE_URL / API_KEY / MODEL（DeepSeek 例见 .env.example）
PYTHONPATH=starter_kit python starter_kit/tools/l2_chat_cli.py '生成一个 3 比特 GHZ 态并全测量'
```

通了再改 `submission.yaml`：`l2: true` **且** `network.required_for_l2: true`。

### Bonus（并行，诚实勾）

- 工程与产品化：已有 ARCHITECTURE + Docker 命令 — 终局可勾  
- 新手引导：README「一分钟上手」+ QUANTUM_101 — 可勾  
- 自定义 RISC-V：**已实现并按 Q3 补机器码闭环** — 规格 `docs/LOOMQ_QISA_V1.md` + `load_machine_words` + `tests/test_quantum_riscv_e2e.py`

### 主办方 Q&A 对照（2026-08 群同步）

- **Q1** L2 门集：仅 OpenQASM 2.0 白名单 12 门（本仓 parser 已限制）。  
- **Q2/Q4** 本源：维护期正常；可用 `WK_C180` / `WK_C180_2` 等动态后端，不必死盯旧名。额度开放时再补第二厂商材料（量旋双机已够 HW 上限）。  
- **Q3** RISC-V Bonus：要第 1 种——编码进可运行链路；已用 `assemble → load_machine_words → decode → execute` 闭环。接到开源/明确 GPU 设备指令集是**加分项**，非满分刚需。

### 关于华为云机时

**不能替代**量旋/本源可溯源 job。本源审核可继续等，不挡量旋第二台。

## 证据包勾选前核对

- [ ] `evidence/README.md` 对应项改成 `[x]` 且字段填满  
- [ ] 两个真机平台（若申报 10 分）路径都在 `evidence/files/` 且进了终局 commit  
- [ ] 无 API Key / Cookie  
- [ ] 工程叙事指向 `docs/ARCHITECTURE.md` + README 复现命令  
- [ ] L2 体验写明 CLI 启动命令与 3 个现场任务（且已真调用过）  

## 泄露控制

终局前：不把完整 L2/L3 推到公开默认分支展示进度。  
终局时：一次打包推送 + 一个 Issue。
