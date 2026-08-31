# LoomQ 人工评分证据

## 申报项

- [x] L1 真机证据（量旋云 triangulum_vp，job `S-260824-0006`）
- [x] L2 交互体验（CLI: `python3 starter_kit/cli.py`）
- [x] 工程与产品化（见 PROJECT_README.md / starter_kit/README.md 本队实现）
- [x] Bonus 量子 RISC-V 扩展（QUANTUM_RISC_V.md + tests/test_quantum_riscv.py）

## L2 交互体验

启动命令（在 fork 根目录）：

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
python3 starter_kit/cli.py
```

截图：`starter_kit/evidence/files/cli-ux-three-tasks.png`

三个用户体验任务（已实测通过）：
1. 「帮我生成一个贝尔态」→ 完整 Bell QASM，自验 counts `00/11` 约各半
2. 「我想制备贝尔态，但 H q[0]; CX q[0] q[1] 报错了，帮我修」→ 补全 qreg/creg 与小写门名后自验通过
3. 「我需要运行一个 15 比特电路，且零排队等待，选哪个平台？」→ `braket_local_simulator`

## L1 真机证据

| 字段 | 值 |
|---|---|
| 平台 | `spinq_cloud_qpu`（`triangulum_vp`，3Q 核磁） |
| job_id | `S-260824-0006` |
| 运行时间 | 2026-08-24T10:44:59Z |
| shots | 8192 |
| 电路 | Bell（`h q[0]; cx q[0],q[1]`） |
| 主峰 | `00`=4052，`11`=2755（噪声旁峰 `01`/`10` 符合真机） |
| 原始结果 | `starter_kit/evidence/files/spinq/result.json` |
| 提交 QASM | `starter_kit/evidence/files/spinq/bell.qasm` |
| 控制台截图 | `starter_kit/evidence/files/spinq/console-job.png` |

复现命令：

```bash
export SPINQ_USERNAME=czrczrczr
export SPINQ_KEYFILE=$HOME/.ssh/id_rsa
export SPINQ_PLATFORM=triangulum_vp
export SPINQ_SHOTS=8192
python3 starter_kit/examples/run_spinq_cloud.py
```

## 平权叙事

目标用户：无量子背景的跨界开发者。LoomQ 让他们用自然语言在 5 分钟内完成第一个量子实验，无需学习 OriginIR/QCIS 等「黑话」。
