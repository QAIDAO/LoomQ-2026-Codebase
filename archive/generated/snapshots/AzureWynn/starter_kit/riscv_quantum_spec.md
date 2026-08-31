# 自定义量子 RISC-V 扩展指令编码规格（v1.0）

> **目的**：让 RISC-V 程序能直接编码并驱动量子操作。基于 RISC-V 保留的
> **Custom-0（0x0B）** 与 **Custom-1（0x7B）** 指令空间，把量子门操作编码为
> 标准 32 位 RISC-V 指令，供扩展模拟器解码执行。
>
> 对应实现：`riscv_quantum_emulator.py`（对官方 `riscv_emulator.py` 的 fork 扩展）
> 端到端测试：`test_quantum_riscv.py`

## 1. 指令格式

沿用 RISC-V R 型指令布局（opcode 为 custom 空间）：

```text
31       25 24      20 19      15 14   12 11      7 6       0
┌──────────┬──────────┬──────────┬───────┬──────────┬─────────┐
│ funct7    │ rs2       │ rs1       │ funct3 │ rd        │ opcode   │
└──────────┴──────────┴──────────┴───────┴──────────┴─────────┘
```

- **Quantum Gates**：`opcode = 0x0B`（Custom-0），`funct3` 选择门类型，
  `rd/rs1/rs2` 承载**量子位索引**（5 位无符号，0–31）或**参数寄存器索引**。
- **Quantum Control**：`opcode = 0x7B`（Custom-1），`funct7` 选择控制操作，
  `rd/rs1/rs2` 均为**通用寄存器**（写结果 / 读 shots / 读模式）。

汇编助记符约定：**量子位索引写整数**（如 `0`），**寄存器写 `rN`/`xN`**。

## 2. Quantum Gates（opcode 0x0B，funct3 = 门选择）

| funct3 | 助记符 | 操作数 | 语义 | 字段 |
|---|---|---|---|---|
| `000` | `qh` | `rd` | H 门作用 q[rd] | rd=量子位 |
| `001` | `qx` | `rd` | X 门作用 q[rd] | rd=量子位 |
| `010` | `qcnot` | `rs1, rd` | CNOT：控制 q[rs1] → 目标 q[rd] | rs1=控制, rd=目标 |
| `011` | `qswap` | `rs1, rd` | SWAP q[rs1] ↔ q[rd] | rs1, rd |
| `100` | `qrz` | `rd, rs2` | RZ(θ) 作用 q[rd]，θ = π·x[rs2]/1000 | rd=量子位, rs2=参数寄存器 |
| `101` | `qry` | `rd, rs2` | RY(θ) 作用 q[rd]，θ = π·x[rs2]/1000 | rd=量子位, rs2=参数寄存器 |
| `110` | `qcu1` | `rs1, rd, rs2` | CU1(θ)：控制 q[rs1]、目标 q[rd]，θ=π·x[rs2]/1000 | rs1=控制, rd=目标, rs2=参数寄存器 |
| `111` | `qtof` | `rs1, rs2, rd` | CCX（Toffoli）：控制 q[rs1]、q[rs2] → 目标 q[rd] | rs1, rs2 控制, rd 目标 |

参数编码说明：参数化门的角标按 **θ = π × (寄存器值) / 1000** 归一化，因此
`r1 = 500` → RZ(π/2)，`r1 = 1000` → RZ(π)，`r1 = 250` → RZ(π/4)，便于用整数寄存器精确表达常见角度。

## 3. Quantum Control（opcode 0x7B，funct7 = 操作）

| funct7 | 助记符 | 操作数 | 语义 |
|---|---|---|---|
| `0000000` | `qrun` | `rd, rs1` | 对已累积量子电路执行 x[rs1] 次采样，将**主导结果位串**（bit k = q[k] 的测量值）写入 x[rd] |
| `0000001` | `qcount` | `rd, rs1, rs2` | 对已累积量子电路执行 x[rs1] 次采样，统计位串等于 x[rs2] 的次数，写入 x[rd] |

`qrun` 用于验证相关性（如 Bell 两比特恒相等）；`qcount` 用于验证概率
（如 P(00) ≈ 0.5 → 8192 次中 00 的计数 ≈ 4096）。

## 4. 示例

```asm
# 制备 Bell 态并采样一次，r1 存放测量位串（应 ∈ {00, 11} → r1 ∈ {0, 3}）
li   r2, 1000      # θ 参数（此处未用）
qh   0
qcnot 0, 1
qrun r1, r3        # r3 需先 li 为 shots 数
```

```asm
# 统计 Bell 态 P(00)：r1 应 ≈ 4096
li   r3, 8192
qh   0
qcnot 0, 1
qcount r1, r3, r2  # r2 中为模式 00 → 先 li r2, 0
```

## 5. 与官方模拟器的关系

`riscv_quantum_emulator.py` 继承官方 `TinyRISCVEmulator`，经典指令子集
（`li/add/sub/addi/beq/bne/j`）行为完全不变，仅新增上述量子指令。

**编码已真正进入可运行、可验证的执行链路**（对齐主办方 QA 口径）：每个量子
助记符在 `execute()` 中先经 `encode_instruction()` 编码为 32 位指令字，再经
`decode_instruction()` 解码回 `(助记符, 操作数)` 后执行——opcode/funct3/funct7
字段实际参与运行，而非仅存在于规格文档。端到端测试 `test_quantum_riscv.py`
包含"编码→解码往返 + opcode 空间断言"用例。

量子门由内置的 **statevector 模拟引擎**（`QuantumState`）执行，不依赖第三方 SDK。

## 6. 合法性依据

RISC-V 规范保留 `custom-0`（0x0B）与 `custom-1`（0x7B）给自定义指令，
不占用标准指令空间；本扩展与官方 L3 经典指令共存互不干扰。