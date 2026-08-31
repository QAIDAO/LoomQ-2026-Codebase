# LoomQ Judge Guide — 60-second evidence map

> LoomQ 把自然语言量子意图变成经过程序验证、可运行在统一后端层上的电路，并同时说明结果能支持什么、不能支持什么。

**Final product demo — 80 s**
`evidence/files/loomq-final-demo.mp4`

评委只有 60 秒时，按下表从上到下核验；本文件是唯一的快速入口，其他材料只承担对应证据的细节。

| 评分 / 风险区 | 60 秒内看什么 | Canonical evidence |
|---|---|---|
| L1 unified execution | 同一 OpenQASM 经 typed IR 输出到 SpinQ、OriginQ、Braket；官方 L1 evaluator | `evidence/files/l1-public-report.json`、`loomq/compiler/`、`emitters/`、`runners/` |
| L2 objective robustness | 历史 Clean V2 保留 499/500；当前 candidate 的 `backend-34-cloud-sim` post-fix 5/5（canonical `braket_cloud`）、`backend-40-real` 5/5（canonical `originq_wukong`）、old 12 unseen paraphrases 12/12、new cloud-simulator paraphrases 8/8、balanced 6/6；Agent service 10/10、focused timeout/campaign/watchdog 18/18 | `evidence/L2_REAL_MODEL_VALIDATION_V2.md`、`FINAL_RELEASE_CHECKLIST.md`、agent tests |
| L2 retained failures | full 30-case smoke 为 29/30；provider timeout 为 0；唯一 retained failure 为 `backend-9-real` semantic failure。其后 3/3 是独立 diagnostic replay，标记为 stochastic residual，不覆盖原始 29/30，也不改写为 30/30 | `FINAL_RELEASE_CHECKLIST.md`、外部 smoke 输出不作为归档原始证据 |
| L2 product interaction | Hero → H → CNOT → Bell → 运行 → QASM；首个 Bell 路径无需 API Key | `loomq/web/`、`evidence/WEB_QA.md` |
| L3 hybrid compiler | Hybrid-QASM 经典控制与量子操作编译为 stock RISC-V，并保留量子操作顺序 | `loomq/hybrid/`、官方与本地 L3 tests |
| Real hardware +10 | 两个 canonical 平台 SpinQ + OriginQ；job ID、circuit / QASM provenance、provider-original raw export、metadata、截图可追溯 | `evidence/HARDWARE_EVIDENCE_SUMMARY.md`、`evidence/files/` |
| Custom quantum RISC-V +8 | `custom-0` 编码、decoder/emulator、端到端测试 | `QUANTUM_RISCV_EXTENSION.md`、`tests/test_quantum_riscv_extension.py` |
| Newcomer +4 | Canonical human evidence: two independent low-background sessions; final first-time mobile participant completed Bell with some hesitation; small-N qualitative only | `evidence/NOVICE_BLIND_TEST.md`; `evidence/SYNTHETIC_COGNITIVE_WALKTHROUGH.md` remains non-human regression evidence |
| Engineering / reproducibility | 新 clone、新环境从 candidate source 构建并跑核心 suite | `evidence/CLEAN_ROOM_REPRODUCTION.md`、`ARCHITECTURE.md` |
| Scientific honesty | Z-basis correlation 不冒充 entanglement proof；tomography、density matrix、fidelity、PPT 的结论范围写清 | `evidence/SCIENTIFIC_CLAIMS_AUDIT.md` |
| Security | 浏览器无硬编码 key；LLM 只读 server-side `LOOMQ_LLM_*`；current tree、staged diff、history 和路径 sweep | `evidence/SECURITY_SWEEP.md` |

## 60-second product route

1. Hero 点 **先看结果 ↓**，先看到理想 Bell `00/11`，不要把它当作纠缠证明。
2. 点 **跟着做一次完整实验 →**，看 `|0⟩`、H 的约 50/50 重复测量和 CNOT 控制位/目标位。
3. 点 **重做刚才的 Bell 实验**，再点 **运行这个实验**（载入后状态文案可能显示 **执行这个实验**），检查真实本地 SDK counts、解释、电路、OpenQASM 与验证结果。
4. 打开归档 SpinQ / OriginQ 硬件桥接，再看 X/Y/Z 与 tomography 的科学边界。
5. 点 **已经懂基础？直接问 LoomQ →**，查看生成、修复、后端推荐三个 L2 任务；首次 Bell 路径无需模型 Key，但这些 L2 交互需要服务端注入 `LOOMQ_LLM_*` 配置。

## Verification commands

Windows commands use `./.venv/Scripts/python.exe` from the repository root:

- `starter_kit/evaluator.py --level l1 --target spinq,originq,braket` with JSON output directed to a temporary path.
- `starter_kit/tests/public_l2_fake.py` for the public protocol contract.
- `starter_kit/evaluator.py --level l3` plus the hybrid and RISC-V test modules.
- `python -m unittest discover -s starter_kit/tests -v` and `python -m unittest discover -s tests -v`.
- `starter_kit/scripts/run_web.ps1 -Port 8765`, then open `http://127.0.0.1:8765/`.
- `starter_kit/scripts/verify.ps1` only after confirming its output paths will not overwrite canonical evidence.

## Dependency and evidence boundaries

Core L1/L2/L3, SpinQ, Braket and RISC-V checks do not require the optional OriginQ Runtime packages. The canonical SpinQ and OriginQ packages are the only hardware packages counted for the two-platform ladder; `WK_C180_2` Runtime and tomography packages are supplemental.

Simulator results are never real-QPU evidence. Real-QPU claims require recorded provider task IDs and exports. `00/11` in the computational basis is reported as correlation consistent with the circuit, not proof of entanglement. Provider-reconstructed fidelity and PPT values are point estimates with no confidence interval claim; they are not device-independent certification, loophole-free certification, or quantum advantage. GHZ hardware distributions are noise-affected and do not carry a multipartite-entanglement claim.

The science section is a reference-based technical review, not a physical-expert endorsement. Existing provenance discrepancies remain recorded; raw bytes, metadata, manifests, checksums, hashes and canonical hardware evidence are not rewritten for tidiness.

## Human handoff

Submission identity and acceptance are determined by the upstream Final Submission Issue; this guide does not infer remote acceptance or replace organizer review.
