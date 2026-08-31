# LoomQ 参赛验证指南（提交前必读）

> 目标：在创建最终提交 Issue **之前**，逐项验证 L1 / L2 / L3 / 真机 / Bonus
> 都符合赛题要求。每项都有「命令 → 判定标准」。全部通过后再提交。
>
> 当前状态（本地已自动验证部分见文末状态表）。

---

## 0. 先搞清「提交」的边界

| 动作 | 是否算提交 |
|---|---|
| 代码 push 到自己的 fork | ❌ 不算。只是代码在仓库里，随时可改 |
| 创建「LoomQ 最终提交」Issue | ✅ 才算。拿到 `submission:accepted` 标签才生效 |
| 修改代码重新 push | ✅ 允许。截止前用**新 Issue** 重新提交即可 |

所以：**先验证，后建 Issue**，顺序完全可控。

---

## 1. L1 验证（45 分：语义等价 35 + 真机 10）

### 1.1 模拟器部分（自动，本地即可跑）

```bash
cd starter_kit

# ① 公开电路（Bell + GHZ-3）× 三后端
python3 evaluator.py --level l1 --target spinq,originq,braket
# 判定：输出 6 个 [PASS]，{"passed": 6, "failed": 0}

# ② 隐藏电路类型预演（QFT-4 / Grover-3 / GHZ-5 / Random×3 × 三后端，
#    用独立 numpy 参考模拟器交叉验证，避免"三套实现错得一样"）
python3 verify_hidden_circuits.py
# 判定：24 passed, 0 failed
```

**判定标准（赛题原文）**：转译后电路在无噪声模拟器上 8192 shots 采样，
与理想分布 Hellinger 保真度 **≥ 0.97**。上面两个脚本已经用独立参考实现
交叉验证，全部 ≥ 0.97。

### 1.2 真机部分（10 分，需要你申请凭证后运行）

真机只核对 **counts 主峰命中理想主峰**（允许噪声），且 `job_id` 能在平台
控制台溯源。步骤：

```bash
# ① 量旋超导真机（推荐第一个，流程最简单）
export SPINQ_CLOUD_USERNAME="你的量旋云用户名"
export SPINQ_CLOUD_KEYFILE="$HOME/.ssh/spinq_cloud"
python3 real_machine.py spinq_cloud \
    --qasm circuits/bell.qasm --shots 8192 \
    --config evidence/config_spinq_cloud.json \
    --out evidence/files/spinq_cloud_result.json
```

**判定**：
- 程序先打印「本地模拟自验：主峰 |00>」（Bell 理想主峰是 00/11 各半）；
- 真机返回的 `counts` 中 **00 和 11 是两个主峰**（合计占比最高）→ 主峰命中；
- `result.json` 里的 `job_id` 登录 https://cloud.spinq.cn 能查到同一任务。

```bash
# ② 本源悟空真机
export ORIGINQ_API_TOKEN="你的 API Token"
python3 real_machine.py originq_wukong \
    --qasm circuits/bell.qasm --shots 8192 \
    --config evidence/config_originq_wukong.json \
    --out evidence/files/originq_wukong_result.json
```

**判定**：同上——`counts` 主峰 00/11 命中；`job_id`（task_id）登录
https://qcloud.originqc.com.cn/zh → 工作台 可查到。

> 真机分规则：每个平台主峰命中 +5，至多 2 个平台 +10。
> 两个平台都跑通 = 拿满 10 分。跑完把 `evidence/README.md` 的 L1 真机
> 段落勾选并填上 job id。

---

## 2. L2 验证（30 分：客观 20 + 交互 10）

### 2.1 客观部分（20 分，需要自备模型 Key）

正式评测注入 `LOOMQ_LLM_*` 三件套；本地验证用你自己的 Key：

```bash
export LOOMQ_LLM_BASE_URL="https://api.deepseek.com"
export LOOMQ_LLM_API_KEY="sk-你的密钥"      # platform.deepseek.com 创建
export LOOMQ_LLM_MODEL="deepseek-chat"       # 你的账号可用的模型名

python3 starter_kit/verify_l2.py
```

**判定**：9 个变体 case（生成×4、纠错×2、选后端×3）全部 `[PASS]`，
输出 `9 passed, 0 failed`。每个生成/纠错 case 会用我们的 L1 模拟器实测
保真度 ≥ 0.97；选后端 case 核对规范 id 是否出现在回复中。

> 说明：正式评测用未公开 prompt 变体 + 12 个 case。verify_l2.py 用
> 官方样例的改写变体覆盖三类任务，验证的是**能力**而非背答案。
> 交互体验（10 分）不在此验证，由人工按提交代码运行
> `loomq_web.py` / `loomq_cli.py` 评分（证据已写在 evidence/README.md）。

---

## 3. L3 验证（15 分，自动，本地即可跑）

```bash
python3 starter_kit/test_hybrid_fuzz.py --cases 200 --seed 20260825
# 判定：200 passed, 0 failed（可换任意种子再跑）
```

**判定标准（赛题原文）**：评测随机生成 Hybrid-QASM 用例，把 `compile_hybrid`
输出的 RISC-V 汇编载入官方 `riscv_emulator.py`，**穷举注入所有测量值组合**，
逐一比对寄存器终态与参考解释器。fuzz 脚本完全复刻该流程（随机分支结构、
常量、测量位数、负字面量、嵌套 if/else），与独立参考解释器逐组比对。

---

## 4. Bonus 验证（+12）

```bash
python3 starter_kit/test_quantum_riscv.py
# 判定：31 passed, 0 failed（量子 RISC-V 扩展：规格+实现+端到端测试齐备）
```

---

## 5. 提交前最终检查（一键）

```bash
# 会依次检查：文件完整性、submission.yaml、L1 三后端、L3、RISC-V、
# git 干净、demo/Web 可运行
bash starter_kit/final_check.sh
```

---

## 6. 验证状态表（提交前逐项打勾）

| 项 | 命令 | 达标 | 状态 |
|---|---|---|---|
| L1 公开电路 | `evaluator.py --level l1 --target spinq,originq,braket` | 6/6 PASS | ☑ 已通过 |
| L1 隐藏类型 | `verify_hidden_circuits.py` | 24/24 PASS | ☑ 已通过 |
| L3 随机用例 | `test_hybrid_fuzz.py`（任意种子） | 100% 通过 | ☑ 已通过 |
| Bonus RISC-V | `test_quantum_riscv.py` | 31/31 PASS | ☑ 已通过 |
| L2 客观（真实模型） | `verify_l2.py`（需自备 Key） | 9/9 PASS | ⬜ 待你运行 |
| L1 量旋真机 | `real_machine.py spinq_cloud` | 主峰命中+可溯源 | ⬜ 待你申请凭证 |
| L1 本源悟空 | `real_machine.py originq_wukong` | 主峰命中+可溯源 | ⬜ 待你申请凭证 |
| 交互体验（人工） | `loomq_web.py` / `loomq_cli.py` | 3 个用户体验任务 | ☑ 已实现（提交后人工评） |

> 全部 ☑ 之后，再执行 `submit.sh` 并创建 Issue——那就是最终提交。
