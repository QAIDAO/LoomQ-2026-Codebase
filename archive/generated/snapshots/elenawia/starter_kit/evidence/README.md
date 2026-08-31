# LoomQ 人工评分证据

这份文件是本队人工评分材料的统一入口。当前版本申报“工程与产品化”、“L2 交互体验”、“L1 真机”和“自定义量子 RISC-V Bonus”。

## 提交前填写

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

说明：L3 混合编译属于自动评测项，已在 `submission.yaml` 中声明，并由 `adapter.compile_hybrid()` 与 `tests/test_l3_hybrid.py` 覆盖，不作为人工证据项单独勾选。

## L1 真机

当前申报 L1 真机分：两个平台（量旋云、本源量子云）各完成 Bell 与 GHZ3 两个公开电路的真机运行，全部主峰命中。截图和可导出的原始结果文件存于 `starter_kit/evidence/files/`。本源量子云提供了原始 JSON 导出；量旋云当前保留控制台任务详情和概率分布截图、job ID 与时间戳作为可溯源证据。

### 平台一：量旋云（SpinQ Cloud，核磁真机）

任务一：Bell 态制备（实验名 `LoomQ-L1-Bell-20260821`）

```text
平台/机型：量旋云 · 2 比特核磁量子计算机
job ID：G-260821-0007
运行时间：2026-08-21 23:57:34 - 23:59:08 (UTC+8)
实际执行的 QASM（平台线路设计器生成）：
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    h q[0];
    cx q[0],q[1];
结果：投影概率 00 ≈ 42%，11 ≈ 51%（主峰命中；01/10 ≈ 噪声水平），
      平台同图对照理想模拟 00 = 50% / 11 = 49%
原始结果：LoomQ-L1-Bell-spinq-G-260821-0007-result.msgpack（平台导出的 MessagePack 概率分布）
实验步骤：LoomQ-L1-Bell-spinq-G-260821-0007-source.qasm
线路图：LoomQ-L1-Bell-spinq-G-260821-0007-circuit.png
截图：LoomQ-L1-Bell-realchip-G-260821-0007-detail.png（任务详情）
      LoomQ-L1-Bell-realchip-G-260821-0007-probability.png（概率分布）
```

任务二：GHZ3 态制备（实验名 `LoomQ-L1-GHZ3-20260821`）

```text
平台/机型：量旋云 · 3 比特核磁量子计算机
job ID：S-260822-0001
运行时间：2026-08-22 00:20:30 - 00:22:57 (UTC+8)
实际执行的 QASM：H q[0]; cx q[0],q[1]; cx q[1],q[2]（该平台线路模式自动投影测量）
结果：投影概率 000 ≈ 32%，111 ≈ 35%（主峰命中）
原始结果：LoomQ-L1-GHZ3-spinq-S-260822-0001-result.msgpack（平台导出的 MessagePack 概率分布）
实验步骤：LoomQ-L1-GHZ3-spinq-S-260822-0001-source.qasm
线路图：LoomQ-L1-GHZ3-spinq-S-260822-0001-circuit.png
截图：LoomQ-L1-GHZ3-realchip-S-260822-0001-detail.png
      LoomQ-L1-GHZ3-realchip-S-260822-0001-probability.png
```

### 平台二：本源量子云（Origin Quantum，超导真机）

任务三：Bell 态制备（实验名 `LoomQ-L1-Bell-20260822`）

```text
平台/机型：本源悟空 180-2 超导量子计算机（赛题 Q&A 点名的 WK_C180_2）
job ID：0081D156FD19061AB2F55F8A27EFD216
shots：1000
运行时间：2026-08-22 07:23:17 - 07:23:28 (UTC+8)，芯片执行 0.313 秒
映射物理比特：q[49]、q[58]
实际执行的 OriginIR：
    H q[0]
    CNOT q[0],q[1]
    MEASURE q[0],c[0]
    MEASURE q[1],c[1]
编译对照：经平台线路优化，H+CNOT 编译为芯片原生门 R_φ + CZ + R_φ
结果：00 ≈ 49%，11 ≈ 44%（主峰命中，合计 93%）
原始结果：LoomQ-L1-Bell-originqc-WK180-2-0081D156-result.json
截图：LoomQ-L1-Bell-originqc-WK180-2-0081D156-task.png
      LoomQ-L1-Bell-originqc-WK180-2-0081D156-probability.png
      LoomQ-L1-Bell-originqc-WK180-2-0081D156-circuit.png（转换前后对照）
```

任务四：GHZ3 态制备（实验名 `LoomQ-L1-GHZ3-20260822`）

```text
平台/机型：本源悟空 180-2 超导量子计算机
job ID：8B7DEE7A50003DC84339B3E828402C9D
shots：1000
运行时间：2026-08-22 07:32:25 - 07:32:33 (UTC+8)，芯片执行 0.313 秒
映射物理比特：q[38]、q[47]、q[48]
实际执行的 OriginIR：
    H q[0]
    CNOT q[0],q[1]
    CNOT q[1],q[2]
    MEASURE q[0],c[0]
    MEASURE q[1],c[1]
    MEASURE q[2],c[2]
结果：000 ≈ 46%，111 ≈ 40%（主峰命中，合计 86%）
原始结果：LoomQ-L1-GHZ3-originqc-WK180-2-8B7DEE7A-result.json
截图：LoomQ-L1-GHZ3-originqc-WK180-2-8B7DEE7A-task.png
      LoomQ-L1-GHZ3-originqc-WK180-2-8B7DEE7A-probability.png
      LoomQ-L1-GHZ3-originqc-WK180-2-8B7DEE7A-circuit.png
```

### 同题跨芯片对比

同一 Bell 电路在两家真机上的一致性：量旋核磁 93% vs 本源超导 93%（00+11 合计概率），
说明 LoomQ 的转译层在不同硬件方言间保持了语义一致。

## L2 交互体验

当前申报 L2 交互体验分。

`starter_kit/submission.yaml` 中 `levels.l2` 已设置为 `true`，`adapter.agent_chat()` 已实现客观评测入口。

```text
L2 客观接口：
- 实现位置：adapter.py
- 模型调用：通过 llm_client.py 读取 LOOMQ_LLM_* 环境变量
- 支持任务：Bell/GHZ 生成、Bell/GHZ 类步骤修复、后端推荐
- 本队测试：python -m unittest tests.test_l2_agent

L2 交互体验 UI：
启动命令：进入 starter_kit/ 后运行 python -m loomq.web.server --port 8765
测试入口：http://127.0.0.1:8765

用于交互体验评测的 3 个用户任务：
1. 让两枚量子硬币总是一起落下
2. 帮我修复这段代码：H q[0]; CX q[0] q[1]
3. 我有一个 15 比特实验，希望免费并且零排队，推荐运行平台

隐藏题抗压覆盖：
- 4 个量子位全局关联态生成，会输出 4-qubit GHZ 类 QASM。
- 3 比特 GHZ 错误步骤修复，会补全寄存器、测量和门参数格式。
- 英文约束后端推荐：`15 qubits, no queue, free, no account`。
- 冲突约束后端推荐：真实硬件 + 高比特数 + 免费 + 不排队时返回无满足项说明。

本地抗压测试命令：
python -m unittest tests.test_l2_agent

说明：
网页第一屏就是实验台，不要求用户先阅读 QASM。
实验类任务会生成 OpenQASM 2.0，调用 L1 本地模拟器运行 1000 次，并把 counts 翻译成人话。
后端推荐任务会读取 backend_capabilities.json，由程序筛选符合条件的平台。
```

## 工程与产品化

```text
干净环境中的构建和启动命令：
无需安装第三方依赖。进入 starter_kit/ 后运行：
python evaluator.py --level l1 --target spinq,originq,braket

本队单元测试命令：
从仓库根目录运行：
python -m unittest tests.test_adapter_qasm

架构说明：
核心实现位于 starter_kit/adapter.py。
程序先解析 OpenQASM 2.0，得到寄存器、量子门和测量指令。
然后根据目标后端输出三种格式：
- spinq：OpenQASM 2.0
- originq：OriginIR
- braket：OpenQASM 3.0
运行时三个后端复用同一个本地状态向量模拟器，并返回统一 counts schema。

目标用户和使用场景：
目标用户是第一次接触量子计算、不了解各平台 SDK 和专有指令格式的开发者。
用户只需要提供标准 OpenQASM 2.0 电路，就可以看到三种平台格式和统一模拟结果。
这个工具降低的是“平台方言”和“环境安装”的门槛，而不是要求用户先学完整量子计算理论。

完整使用流程：
1. 用户准备 OpenQASM 2.0 电路。
2. 调用 adapter.transpile(qasm, target)，选择 spinq、originq 或 braket。
3. 调用 adapter.run(qasm, target, shots)，获得统一 counts。
4. 使用官方公开 evaluator 验证 Bell 和 GHZ-3 电路在三个后端通过。

相关文档：
- README.md
- target_ir_contract.md
- QUANTUM_101.md
```

## 自定义量子 RISC-V Bonus

当前申报自定义量子 RISC-V Bonus。

`adapter.compile_hybrid()` 已实现 Hybrid-QASM 经典控制块到 Tiny RISC-V 汇编的编译，支持顺序赋值、表达式比较、嵌套 `if/else`、多测量位映射和量子操作剥离；`starter_kit/submission.yaml` 中 `levels.l3` 已设为 `true`。

在 L3 基础上，本项目进一步扩展了 `starter_kit/riscv_emulator.py`，加入一组可编码、可解码、可执行的自定义量子 RISC-V 指令：

```text
qinit      初始化量子寄存器
qh         Hadamard 门
qx         Pauli-X 门
qcx        CNOT 门
qmeasure   测量量子位并写入经典寄存器
```

证据材料：

```text
指令编码与设计文档：starter_kit/evidence/bonus_quantum_riscv.md
模拟器扩展实现：starter_kit/riscv_emulator.py
端到端测试：tests/test_bonus_quantum_riscv.py
测试命令：python -m unittest tests.test_bonus_quantum_riscv
```

## 新手引导与视觉叙事 Bonus

当前已完成新手引导与视觉叙事页面材料，并作为 L2 交互体验和产品化材料提交，供评委评定。

已有的新手说明材料：

```text
零基础首次运行指南：README.md
量子概念解释：QUANTUM_101.md
结果可视化：L2 网页提供柱状图 counts、实验结论说明、跨平台结果展示
错误恢复或无障碍引导：README.md 中包含基础运行与检查命令
```

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。











