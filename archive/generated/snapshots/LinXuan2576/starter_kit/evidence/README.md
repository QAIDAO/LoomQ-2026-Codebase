# LoomQ 人工评分证据

Team ID：`LinXuan2576`。本文件按组委会模板填写，申报 L2 交互体验、工程与产品化、自定义量子 RISC-V Bonus、新手引导与视觉叙事 Bonus。

## 提交前填写

- [x] L1 真机（量旋云 ✅ + 本源量子云 ✅，双平台已申报）
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

### 平台 1：量旋云 · 2比特核磁量子计算机（5 分）

```text
平台名称：量旋云（SpinQ）- 2比特核磁量子计算机
平台 job ID：G-260823-0016
运行时间：2026-08-23 23:45:51 ~ 23:47:35（UTC+8）
shots：8192（待平台详情页确认后回填）
实际执行的 QASM：starter_kit/evidence/files/bell-qcloud.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-nmr-result.json
平台官方任务结果（msgpack 原始格式）：
  starter_kit/evidence/files/spinq-task-result-G-260823-0016.msgpack
电路图：starter_kit/evidence/files/spinq-bell-2bit-circuit.png（2bit Bell 态）、
  starter_kit/evidence/files/spinq-bell-3bit-circuit.png（3bit 线路图）
任务页截图：starter_kit/evidence/files/spinq-bell-2bit-report.png（2bit 实验报告全图）、
  starter_kit/evidence/files/spinq-bell-3bit-report.png（3bit 实验报告全图）
```

结果摘要（完整见 `spinq-nmr-result.json`）：

| 位串 | 实验概率 | 理想值 |
|---|---|---|
| 00 | 52.27% | 50% |
| 11 | 15.45% | 50% |
| 01 | 15.45% | 0% |
| 10 | 16.82% | 0% |

主态 00/11 合计 67.7%。真实核磁硬件的退相干与读出误差产生杂散分布；
纠缠特征（00 与 11 同向占优，无单比特主导态）清晰可见。

另在同一平台运行 3bit 任务（job `S-260823-0003`），官方结果
（msgpack 原始格式）归档于 `files/spinq-task-result-S-260823-0003.msgpack`，
展示平台多比特能力；该任务不参与申报评分。

### 平台 2：本源量子云 · 悟空 WK_C180_2 超导量子计算机（5 分）

```text
平台名称：本源量子云（OriginQ QCloud）- 悟空 WK_C180_2（180 比特超导）
平台 job ID：7214912EA38E2E609F7FE5E70E7C0B29
运行时间：2026-08-24 01:21（UTC+8）
shots：8192（平台返回概率型结果）
实际执行的 QASM：starter_kit/evidence/files/ghz3-qcloud.qasm（经 pyqpanda3 提交）
平台返回的原始结果：starter_kit/evidence/files/wk_c180_2-ghz3-result.json
平台官方任务报告（平台导出，含起止时间/机器时间/状态）：
  starter_kit/evidence/files/qcloud_reports/7214912EA38E2E609F7FE5E70E7C0B29.json
任务页截图：选填（官方任务报告已覆盖同等信息）
```

结果摘要（完整见 `wk_c180_2-ghz3-result.json`）：

| 位串 | 实验概率 | 理想值 |
|---|---|---|
| 000 | 51.56% | 50% |
| 111 | 48.40% | 50% |
| 001/010/011/100/101/110 合计 | 0.04% | 0% |

主态 000/111 合计 99.96%，接近理想 GHZ-3 纠缠态，保真度 ≈ 0.9995；
纠缠特征（三比特同向 000/111 各半、无单比特主导态）完美呈现。

后端选型说明：同一账号下硅臻光量子 PQPUMESH8（3 比特）经对照实验
（Bell 2 比特 + X 单门翻转，见 `run_qcloud_controls.py`）确认所有量子门
不执行（X(0) 实测仍为 |0⟩ 99.9%），判断该后端当前不可用，改选悟空
WK_C180_2 提交；对照过程与原始响应均留存证据文件，五组任务的平台
官方报告（含起止时间/机器时间/状态）见 `files/qcloud_reports/`：
- PQPUMESH8 故障组：968144DF819A1E90673BE80F61EEBB6C（GHZ-3 全 000）、
  61D061A668A4D5801BD21024119E45F0（Bell 全 00）、
  29D0EB978DD705A2E822961614C82B3B（X 翻转仍 |0⟩ 99.9%）
- WK_C180_2 成功组：7214912EA38E2E609F7FE5E70E7C0B29（GHZ-3 主态 99.96%）、
  B669FC201A1C8A943D90F608522B0E76（Bell 纠缠正常）

## L2 交互体验

```text
启动界面或 CLI 的命令：
  python starter_kit/cli.py          # 交互式对话
  python starter_kit/cli.py --once "生成一个2比特贝尔态电路"   # 单轮演示

测试入口或页面地址：无（CLI 终端入口）

用于交互体验评测的 3 个用户任务：
1. 零基础用户：启动 CLI 后输入"生成一个2比特贝尔态电路"，观察电路生成、
   自动验证、执行与可视化输出的完整流程（结果应为 "00"/"11" 各约 50%）。
2. 纠错场景：输入"帮我修复这个报错的电路：OPENQASM 2.0; include 'qelib1.inc';
   qreg q[2]; creg c[2]; h q[0]; cx q[0], q[1]; measure q[0] -> c[0]; measure q[1] -> c[0];"
   （包含两个 measure 写入同一 clbit 的典型错误），验证 Agent 发现错误、
   生成修正电路并运行。
3. 选型场景：输入"3比特的GHZ纠缠态，用哪个后端跑？"，验证 Agent 依据
   比特数约束与后端能力表推荐合适的后端（braket_local_simulator）。
```

其他说明：
- 命令均从 `starter_kit/` 目录执行；零第三方依赖，标准库即可运行
- 自然语言路径读取 `LOOMQ_LLM_*` 环境变量（与 L2 评测协议一致）；
  未配置时 `/run`、粘贴 QASM、`/backends`、`/help` 全部离线可用
- 结果可视化：纯 ASCII 直方图，终端编码无关（见 `cli.py` `print_histogram`）
- 新手可读性设计：启动横幅、`/help` 中文引导、错误提示含修复建议

## 工程与产品化

```text
干净环境中的构建和启动命令：
  cd starter_kit && pip install -r requirements.txt && python cli.py
  （或离线：python cli.py --run circuits/bell.qasm braket 8192）

架构说明：主 README「架构」章节
  - adapter.py：统一转译 + 执行（三后端：spinq / braket / originq），统一结果 Schema
  - l2_agent.py：自然语言 Agent（LLM 生成 + 模拟器自验闭环 + 规则选后端）
  - hybrid_compiler.py：L3 混合编译器（词法 → 语法 → RISC-V 代码生成）
  - cli.py：交互入口（本作品新增，L2 交互体验载体）
  - riscv_emulator_qext.py：Q-Ext 量子扩展指令模拟器（Bonus）

目标用户和使用场景：完全不懂量子计算的普通开发者/学生 —— 在终端用自然语言
 描述电路意图，由 Agent 完成电路生成、正确性自验、后端选型与结果可视化，
  全程无需量子知识与云平台账号。

完整使用流程：主 README「使用示例」+ docs/FIRST_RUN.md（零基础首次运行指南，
  10 分钟从零到跑通第一条量子电路）
```

## 自定义量子 RISC-V Bonus

```text
指令编码规格：starter_kit/docs/riscv-quantum-ext.md
  5 条 Q-Ext 扩展指令（qh / qx / qcx / qrz / qmeas），RISC-V 标准位段布局，
  opcode 0x77，含 R 型/I 型编码表、语义模型（statevector + 确定性坍缩）与设计取舍。

模拟器扩展实现：starter_kit/riscv_emulator_qext.py
  官方 riscv_emulator.py 的 fork 扩展：官方 7 条经典指令完全兼容，
  新增量子态（复数 statevector，零第三方依赖）与 5 条量子指令。

端到端测试命令：
  python starter_kit/riscv_emulator_qext.py
  预期 6 项全过（经典兼容 / 贝尔纠缠一致性 / X 翻转 / RZ 相位 / 经典-量子混合控制流）
```

三项齐备且测试通过，申请 +8 分。

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/docs/FIRST_RUN.md
  10 分钟从零到跑通第一条量子电路：安装 → 一句人话生成电路 → 看懂结果
  （含"纠缠"的通俗解释）→ 4 个进阶尝试 → 常见错误恢复表。

量子概念解释：starter_kit/QUANTUM_101.md
  门/叠加/纠缠/测量的零基础比喻解释（本仓库原已提供，纳入申报）。

结果可视化：cli.py 的 print_histogram()
  测量结果渲染为 ASCII 概率直方图 + 位串，零基础用户可直接读图；
  示例见 FIRST_RUN.md 中的贝尔态输出。

错误恢复或无障碍引导：cli.py
  - 缺少 LLM 配置时提示替代路径（粘贴 QASM / /run，完全离线可用）
  - Agent 生成电路自动自验，失败自动回喂修正（l2_agent.py 自验闭环）
  - 未知命令/未知后端给出可选列表；运行失败打印具体原因
```

## 提交规则

- 所有材料均在最终提交 commit 内（2026-08-25 12:00 UTC+8 前）
- 未提交 API Key / Token / 个人隐私（.env.local 已在 .gitignore 中）
- 如申报 L1 真机分，最终提交 Issue 的 `Hardware evidence` 填本文件路径
