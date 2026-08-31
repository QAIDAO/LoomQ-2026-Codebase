# LoomQ Quantum RISC-V Custom ISA v0.1

## 1. 范围与依据

本规范是 Task 15A 的 32-bit custom ISA proof-of-concept / Bonus extension，用来证明量子命令的二进制编码、协处理器派发和测量驱动经典控制流。它不替代 L1/L3 的完整量子 IR，也不模拟量子态。

本扩展使用 RISC-V `custom-0` major opcode：二进制 `0001011`，十六进制 `0x0B`。选择依据是 RISC-V International 的官方 *Unprivileged ISA Specification* 中 [RV32/64G base opcode map](https://docs.riscv.org/reference/isa/unpriv/rv-32-64g.html)：`custom-0` 至 `custom-3` 会避开未来标准扩展，并推荐用于基础 32-bit 格式中的自定义指令。本版本选择 `custom-0`，不占用 reserved opcode。

## 2. 32-bit 编码布局

所有指令采用固定 32-bit、R-type 风格字段布局：

```text
 31          25 24       20 19       15 14    12 11         7 6          0
+---------------+-----------+-----------+--------+------------+------------+
| funct7 = 0    | q1        | q0        | funct3 | rd         | 0001011    |
+---------------+-----------+-----------+--------+------------+------------+
       7 bits       5 bits      5 bits     3 bits    5 bits       7 bits
```

- `opcode[6:0]`：固定为 `0x0B` (`custom-0`)。
- `funct7[31:25]`：本版本保留，必须全为零。
- `q0[19:15]`：第一量子操作数，范围 `q[0]..q[31]`。
- `q1[24:20]`：第二量子操作数；未使用时必须为零。
- `funct3[14:12]`：量子 sub-opcode。
- `rd[11:7]`：QMEAS 的 RV32 经典写回寄存器；其他指令必须为零。

字段按下式组装，结果视为 unsigned 32-bit word：

```text
word = (q1 << 20) | (q0 << 15) | (funct3 << 12) | (rd << 7) | 0x0B
```

## 3. 指令集合与语义

| 指令 | funct3 | q0 | q1 | rd | 派发语义 |
|---|---:|---|---|---|---|
| `QH q[a]` | `000` | a | 0 | 0 | `apply_gate(QH, a)` |
| `QX q[a]` | `001` | a | 0 | 0 | `apply_gate(QX, a)` |
| `QCX q[a], q[b]` | `010` | control a | target b | 0 | `apply_gate(QCX, a, b)`；a 与 b 必须不同 |
| `QMEAS q[a] -> x[d]` | `011` | a | 0 | d | `measure(q[a])` 返回 0/1并写入 `x[d]` |

QMEAS 的 `rd` 必须是 `x1..x31`；`x0` 是 RISC-V 常零寄存器，作为测量目的地会丢失经典控制信息，因此编码非法。写回在 QMEAS 完成时发生，程序顺序中后续的 `beq`/`bne` 读取该寄存器，形成真实的数据依赖。

协处理器是 dispatch interface：gate 命令交给 `apply_gate`，measurement 交给 `measure`。随实现提供的 `TraceCoprocessor` 只记录命令并返回预先注入的确定性 0/1，用于验证 ISA 和 hybrid control flow；它不是 statevector simulator，也不声称产生真实量子物理结果。

## 4. 编解码示例

Bell-like 指令序列：

```text
QH    q[0]            -> 0x0000000B
QCX   q[0], q[1]      -> 0x0010200B
QMEAS q[0] -> x10     -> 0x0000350B
```

例如解码 `0x0010200B`：`opcode=0x0B`、`funct7=0`、`q1=1`、`q0=0`、`funct3=010`、`rd=0`，得到 `QCX q[0], q[1]`。

汇编载体使用 `.word 0xXXXXXXXX`。`.word` 只是把二进制 word 放进测试程序；模拟器执行时仍必须调用严格 decoder，再派发结构化命令，不接受绕过编码的量子 pseudo-mnemonic。

## 5. 非法编码

decoder 对下列情况确定性抛出 `QuantumInstructionError`：

- word 不是 unsigned 32-bit integer；
- opcode 不是 `custom-0`；
- `funct7` 任一保留位非零；
- `funct3` 为 `100..111`；
- QH/QX 的 `q1` 或 `rd` 非零；
- QCX 的 `rd` 非零，或 control 与 target 相同；
- QMEAS 的 `q1` 非零或 `rd=0`。

encoder 同样拒绝非整数及越界的量子位/经典寄存器索引。

## 6. quantum_ops translator 契约

独立 translator 只支持 L3 `quantum_ops` 中的：

```text
h q[n];
x q[n];
cx q[a], q[b];
measure q[n] -> c[k];
```

它保持原顺序，并沿用官方 L3 映射将 `c[k]` 写入 `x10+k`；所以本 ISA 中可翻译的经典位范围是 `c[0]..c[21]`。其他 gate、参数化指令、越界操作数均明确失败，不会 silent drop。translator 不修改或接入 `compile_hybrid()`。

## 7. 保留空间与非目标

- `funct3=100..111`、全部 `funct7` 非零编码保留给未来版本。
- 当前最多寻址 32 个量子位，不定义多字扩展。
- 不支持 S/SDG/T/TDG、RY/RZ、CU1、SWAP、CCX 或角度立即数。
- 不定义异步 completion、异常/中断、量子态存储、QEMU/LLVM/FPGA 或真实硬件 driver。
- 本实现完全旁路 L1/L2/L3 production 路径。

## 8. 可复现证据

`bonus/quantum_riscv/emulator.py` 中的 `QuantumRISCVEmulator` 直接继承官方
`TinyRISCVEmulator`，复用其 parser、寄存器、标签与状态初始化；仅 fork 官方取指循环，
在原七条经典指令语义旁增加 `.word` custom-0 的严格解码和协处理器派发。经典路径由
同一组程序在官方类与扩展类间做 differential tests，避免复制逻辑发生无证据漂移。

```bash
python -m unittest starter_kit.tests.test_quantum_riscv_bonus -v
```

测试覆盖 bit-exact encoding、独立手构 word、严格非法字段、官方经典指令 differential、
QMEAS 写回后 `beq`/`bne` 分支，以及
`quantum_ops -> words -> emulator -> coprocessor trace` 端到端链路。
