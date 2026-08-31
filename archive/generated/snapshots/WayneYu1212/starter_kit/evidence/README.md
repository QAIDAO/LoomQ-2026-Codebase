# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

### Canonical L1 scoring summary

L1 hardware scoring relies on exactly two canonical, scoreable platform families:

1. **Origin Quantum Cloud**
   - Canonical job: `D0C7F490B43D9B04FDF19ABF3DB8B342`
   - Provider circuit provenance: `evidence/files/originq-hardware-circuit-logical.svg`, `evidence/files/originq-hardware-circuit-physical.svg`
   - Readable/reproducible QASM: `evidence/files/originq-hardware-bell.qasm`
   - The QASM is faithfully reconstructed from the provider-exported logical SVG. It is not claimed as provider-exported raw QASM bytes.
   - Provider-original result: `evidence/files/originq-hardware-result.raw.csv`
   - Readable JSON transcription/view: `evidence/files/originq-hardware-result.raw.json`

2. **SpinQ Cloud**
   - Canonical job: `G-260820-0008`
   - Provider-exported raw QASM bytes: `evidence/files/spinq-hardware-bell.raw.qasm.gz`
   - Readable semantic QASM copy: `evidence/files/spinq-hardware-bell.qasm`
   - Provider-original result: `evidence/files/spinq-hardware-result.raw.msgpack`
   - Decoded JSON view: `evidence/files/spinq-hardware-result.raw.json`

The later `originq_runtime_*` packages are supplemental engineering/scientific evidence. They do not add another hardware platform and do not replace the two canonical packages.

平台名称：Origin Quantum Cloud
设备：Origin Wukong 180-2
平台 job ID：D0C7F490B43D9B04FDF19ABF3DB8B342
提交时间：2026-08-20T20:29:51.026+08:00
完成时间：2026-08-20T21:16:43.073+08:00
shots：1000
电路 / QASM provenance：provider-exported logical/physical SVGs are the provider circuit record; `evidence/files/originq-hardware-bell.qasm` is a faithful reproducible reconstruction from the logical SVG and is not claimed as provider-exported QASM bytes.
平台返回的原始结果：`evidence/files/originq-hardware-result.raw.csv`
JSON 便读转录：`evidence/files/originq-hardware-result.raw.json`
规范化结果：`evidence/files/originq-hardware-result.normalized.json`
元数据：`evidence/files/originq-hardware-metadata.json`
任务页截图：`evidence/files/originq-hardware-task.png`
真实性边界：该记录来自平台任务页与原始导出文件中的可追溯硬件任务 ID，不是 simulator；组织方仍可登录平台复核。

平台名称：Origin Quantum Cloud（QPanda3 Runtime，新 API 通道）
设备：Origin Wukong 180-2（device_id `WK_C180_2`）
平台 job ID：2C68A9D3E2F6626B55EEC966DBC3CE2B（Bell，物理比特 [49,58]，请求 shots=1000）
Provider 时间戳：当前 captured Runtime API response 未暴露
规范化结果：`evidence/files/originq_runtime_bell-hardware-result.normalized.json`（provider probabilities，非逐 shot counts）
原始 SDK 响应：`evidence/files/originq_runtime_bell-hardware-result.raw.json`
说明：这是从旧 `pyqpanda.QCloud + chip_id=72` 迁移到官方 `qpanda3_runtime.RuntimeService + device('WK_C180_2')` 后，通过新 API 通道在 Wukong 180-2 上成功执行的 Bell 电路（H, CX, measure）。旧 API 网关对 chip 72 返回 maintenance，新 Runtime 通道正常。**本组 Z-basis 计算基测量显示强 00/11 相关（P(00)+P(11)≈1.0），与目标 Bell 电路的计算基相关一致；单凭计算基测量不足以证明纠缠，未作此声明。** 该 job 为独立 evidence 包，见 `originq_runtime_bell-manifest.json`。

平台名称：Origin Quantum Cloud（多样化电路验证 · GHZ-3）
设备：Origin Wukong 180-2（device_id `WK_C180_2`）
GHZ-3 job ID：`B23E5B75D47D124A078F25B1C0083C2A`（物理比特 [49,58,67]，请求 shots=1000）
GHZ-3 结果：`evidence/files/originq_runtime_ghz3-hardware-result.normalized.json`（provider probabilities；逐 shot counts unavailable）
说明：GHZ-3 电路（H, CX, CX, measure）在 WK_C180_2 上执行成功，返回计算基分布：P(000)≈0.703、P(111)≈0.108、P(011)≈0.187。**目标态（000/111）占主要质量，但受硬件噪声影响，其余计算基态有非零概率；这是真机计算基分布，不代表无噪声完美 GHZ 态，也不据此声明证明三比特纠缠。** 独立 evidence 包见 `originq_runtime_ghz3-manifest.json`。

平台名称：Origin Quantum Cloud（多样化电路验证 · 多门电路）
设备：Origin Wukong 180-2（device_id `WK_C180_2`）
Multi 电路 job ID：`8575222FE2C04A065B38B9DEE5BA9AEE`（物理比特 [49,58]，请求 shots=1000）
Multi 电路结果：`evidence/files/originq_runtime_multi-hardware-result.normalized.json`（provider probabilities；逐 shot counts unavailable）
说明：含多个 H/CNOT 门的电路在 WK_C180_2 上执行成功。**该电路的计算基分布与 LoomQ reference simulator 对同一电路计算的理想分布做过程序化比较（见 `evidence/files/originq_runtime_multi-reference-comparison.json`），此处仅报告真机返回的计算基分布，不推断纠缠。** 独立 evidence 包见 `originq_runtime_multi-manifest.json`。

平台名称：Origin Quantum Cloud（Bell 三基点估计 · X-basis）
设备：Origin Wukong 180-2（device_id `WK_C180_2`，物理比特 [49,58]，请求 shots=1000）
X-basis job ID：`CA80432C12CFA2EBB33AC9A14C3AFF20`
X-basis 结果：`evidence/files/originq_runtime_bell_xbasis-hardware-result.normalized.json`（provider probabilities）
说明：Bell 制备（H, CX）后加 H,H 做 X 基测量。返回 P(00)=0.5206、P(11)=0.4792，**Cxx = 0.99956**。独立 evidence 包见 `originq_runtime_bell_xbasis-manifest.json`。

平台名称：Origin Quantum Cloud（Bell 三基点估计 · Y-basis）
设备：Origin Wukong 180-2（device_id `WK_C180_2`，物理比特 [49,58]，请求 shots=1000）
Y-basis job ID：`5ABEAE903BE47DDEDCDEFABFBE162904`
Y-basis 结果：`evidence/files/originq_runtime_bell_ybasis-hardware-result.normalized.json`（provider probabilities）
说明：Bell 制备后加 Sdg,Sdg,H,H 做 Y 基测量（Sdg 以 S³ 分解提交，功能等价）。返回 01/10 反相关，**Cyy = −0.99865**。独立 evidence 包见 `originq_runtime_bell_ybasis-manifest.json`。

**三基 Bell 点估计汇总**（同 device、同物理比特 [49,58]、每 job 请求 1000 shots）：
- 关联：Czz = 0.99955（Z job `2C68A9D3...`）、Cxx = 0.99956（X job `CA80432C...`）、Cyy = −0.99865（Y job `5ABEAE90...`）
- 点估计：|Cxx|+|Czz| = 1.99911；F_Φ+ = (1+Cxx−Cyy+Czz)/4 = 0.99944。
- **声明边界：Runtime API 导出了 provider probabilities，而非 raw per-shot counts；因此不能独立建立 binomial/置信区间模型，上述点估计不构成统计性纠缠 witness 或 fidelity-threshold 结论。**
- 理论（可分离上界 |Cxx|+|Czz|≤1 与 fidelity 公式）在提交硬件前经 22 万随机可分离态程序化验证；X/Y 结果保留为三基测量数据，不扩展到 GHZ-3 与 Multi。
- 可复算：`scripts/compute_bell_witness.py` → `evidence/files/bell-witness-analysis.json`。

**评分边界**：上述五个 `originq_runtime_*` 包是 **SUPPLEMENTAL MODERN RUNTIME EVIDENCE**，仅作 participant-side engineering/scientific evidence；不替代 canonical OriginQ package、不构成额外硬件平台、不计入 L1 hardware ladder 或 +10 hardware score。其独立检查：`scripts/validate_runtime_evidence.py`。

平台名称：SpinQ Cloud
设备：SpinQ Cloud 2-qubit NMR quantum computer
平台 job ID：G-260820-0008
提交时间：2026-08-20T19:13:25+08:00
完成时间：2026-08-20T19:15:15+08:00
shots：N/A — SpinQ NMR task page and export expose ensemble projection probabilities; no discrete shot count was provided, so none is fabricated.
Provider-exported raw QASM：`evidence/files/spinq-hardware-bell.raw.qasm.gz`
Readable semantic QASM：`evidence/files/spinq-hardware-bell.qasm`
Provider-original raw result：`evidence/files/spinq-hardware-result.raw.msgpack`
Decoded JSON view：`evidence/files/spinq-hardware-result.raw.json`
规范化结果：`evidence/files/spinq-hardware-result.normalized.json`
元数据：`evidence/files/spinq-hardware-metadata.json`
任务页截图：`evidence/files/spinq-hardware-task.png`
真实性边界：该记录来自平台任务页与原始导出文件中的可追溯硬件任务 ID，不是 simulator；组织方仍可登录平台复核。

## Supplemental scientific validation — Bell Φ+ tomography

- Backend: Origin Wukong 180-2 (`WK_C180_2`); successful job: `F7287E16E8478E4DB5051105468DB638`.
- Requested shots: `1000`; physical block: `[49,58]`.
- Provider fidelity: `0.952449`; independent fidelity: `0.952448944997`.
- PPT minimum eigenvalue: `-0.456096768`; negativity: `0.456096768`.
- At the level of the provider-reconstructed two-qubit density-matrix point estimate, the state is entangled under the 2×2 PPT criterion. **No statistical confidence interval is claimed.**
- Full package: `ORIGINQ_BELL_TOMOGRAPHY.md`; independent audit: `files/originq-tomography/originq_tomography_bell_phi_plus-corrected-density-audit.json`; read-only validation: `python scripts/validate_originq_tomography.py`.
- This is supplemental scientific evidence: it does not add a third L1 hardware platform, increase the L1 hardware +10 ceiling, or replace canonical SpinQ + OriginQ evidence.

## L2 交互体验

请填写：

```text
启动界面或 CLI 的命令：在 fork 根目录运行 `.\starter_kit\scripts\run_web.ps1 -Port 8765`（启动器会检查 `.venv`、Python 3.10 与 `spinqit==0.2.4`）
测试入口或页面地址：`http://127.0.0.1:8765/`
用于交互体验评测的 3 个用户任务：
1. `帮我生成一个 GHZ 态并测量`
2. `这段 Bell 电路写错了，帮我修好`
3. `我有一个 15 比特任务，不想排队，应该选哪个后端？`
截图或演示视频：`evidence/files/v7.2-zero-knowledge-intro-1440.png`、`evidence/files/v7.2-bell-result-openqasm-1440.png`、`evidence/files/v7.2-api-optional-390.png`、`evidence/files/v7.2-mobile-full-390.png`
最终产品 Demo（80 s）：`evidence/files/loomq-final-demo.mp4`
```

工作人员会在组委会统一模型环境中运行最终代码，测试新手是否看得懂、出错后能否得到有效帮助、结果是否清楚，以及多轮回答是否一致。选手自己的对话截图只用于说明产品流程，不直接证明得分。

### L2 真实模型鲁棒性（参赛者本地补充证据）

参赛者在本地用真实 DeepSeek V4 Flash endpoint 对 L2 链路做了 102 例压力测试（生成/修复/后端推荐，含 adversarial 与私有 prompt 变体），101 例通过，唯一失败为 provider 偶发 transient。详见 `L2_REAL_MODEL_VALIDATION.md` 与 `files/l2-deepseek-v4-flash-stress-summary.json`。这是参赛者本地 robustness evidence，**不替代** 组织方 hidden/private L2 评测，**不代表**官方 L2 满分。

Clean V2 是独立的新实验：固定 seed `20260823`，500 个 unique cases，499/500 通过，509/540 API attempts；唯一失败保留为 provider transient。详见 `L2_REAL_MODEL_VALIDATION_V2.md`、`files/l2-deepseek-v4-flash-validation-v2-summary.json` 与逐例 JSONL。V2 是 participant-side robustness evidence，**不替代**组织方 hidden/private L2 评测，**不代表**官方 L2 满分。

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：`README.md` 的“5 分钟启动”和“一条命令验证”；Windows `.\starter_kit\scripts\setup.ps1` 后运行 `.\starter_kit\scripts\verify.ps1`
架构说明：`ARCHITECTURE.md`；一个 parser/typed IR，三个 emitter 和三个真实 SDK runner，独立 verifier 不冒充 target
目标用户和使用场景：没有量子背景的人文社科学生、设计师、产品经理、艺术创作者与普通 AI 用户，在五分钟内完成第一次可解释、可验证的量子实验
完整使用流程：`USER_GUIDE.md`、Web 首页“承诺与入口” → 理想 Bell 结果 → “开始前，先认四件事” → H/CNOT 与整条电路 → 本地 Bell run → 结果/OpenQASM → 归档硬件桥接 → Agent → X/Y/Z/tomography；截图路径仍见 `evidence/files/`
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

```text
指令编码规格：`QUANTUM_RISCV_EXTENSION.md`
模拟器扩展实现：`riscv_emulator.py` 的 `custom-0` encoder/decoder 与 `quantum_trace`
端到端测试命令：`.venv/bin/python -m unittest starter_kit.tests.test_quantum_riscv_extension -v`（Windows 为 `.\.venv\Scripts\python.exe -m unittest starter_kit.tests.test_quantum_riscv_extension -v`）；演示为 `examples/quantum_riscv_demo.py`
```

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：

```text
真人新手证据（canonical human evidence）：`evidence/NOVICE_BLIND_TEST.md`。这是 small-N qualitative evidence；synthetic walkthrough 不计作人类用户证据。
零基础首次运行指南：`USER_GUIDE.md` 的“五分钟跑完第一次实验”；Web 首页“承诺与入口” → 理想 Bell 结果 → “开始前，先认四件事” → 本地 Bell 入口。第一次 Bell 体验不需要模型 Key。
量子概念解释：`USER_GUIDE.md` 的“Three ideas you need”与 Web 的“验证与解释 / 这证明了什么”
结果可视化：`loomq/web/static/` 中的电路 rails、counts bars 及并列表格；截图见 `evidence/files/`
错误恢复或无障碍引导：`loomq/web/server.py` 的结构化恢复错误；HTML labels/live region/skip link；键盘焦点进入结果区；reduced-motion 与移动单列 CSS
```

以上四项各 1 分。普通项目 README 完整不代表自动获得 Bonus。

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
