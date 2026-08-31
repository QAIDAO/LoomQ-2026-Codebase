# LoomQ Quantum RISC-V Extension v1.1

## 目标与边界

本扩展证明经典控制器可以用可编码指令调度基础量子门、参数门与测量。它使用 RISC-V 明确推荐给自定义扩展的 `custom-0` opcode，不占用标准 ISA 空间。规范依据是 [RISC-V 官方 opcode map](https://docs.riscv.org/reference/isa/unpriv/rv-32-64g.html)。

## 32 位编码

采用 R-type 字段布局：

```text
31          25 24      20 19      15 14   12 11       7 6       0
+--------------+----------+----------+-------+-----------+---------+
| funct7       | q1 / rs2 | q0 / rs1 | funct3| rd        | 0001011 |
+--------------+----------+----------+-------+-----------+---------+
```

- `opcode[6:0] = 0001011` (`0x0B`, RISC-V `custom-0`)
- `funct7[31:25] = 0` 为离散门 profile，`1` 为参数门 profile；其他值拒绝执行
- `q0/q1` 为 5 位量子比特索引，范围 0..31
- `rd` 在 `QMEASURE` 中是经典目标 `xN`，在 `QCCX` 中是第三个量子比特；其他指令必须视为保留字段

| funct3 | 指令 | 语义 |
|---:|---|---|
| `000` | `QH q0` | Hadamard |
| `001` | `QX q0` | Pauli-X |
| `010` | `QS q0` | S phase |
| `011` | `QT q0` | T phase |
| `100` | `QCX q0,q1` | q0 控制、q1 目标 |
| `101` | `QSWAP q0,q1` | 交换两个 qubit |
| `110` | `QCCX q0,q1,rd` | q0/q1 控制、rd 目标 |
| `111` | `QMEASURE q0 -> xrd` | Born 采样、状态坍缩、写经典寄存器 |

## 参数门 profile（`funct7=1`）

| funct3 | 指令 | 字段 | 语义 |
|---:|---|---|---|
| `000` | `QRY q0,xrd` | `q1=0`，`rd`=角度寄存器 | (R_y(x[rd]/10^6)) |
| `001` | `QRZ q0,xrd` | `q1=0`，`rd`=角度寄存器 | (R_z(x[rd]/10^6)) |
| `010` | `QCU1 q0,q1,xrd` | `rd`=角度寄存器 | (CU1(x[rd]/10^6)) |
| `011..111` | 保留 | — | 解码时拒绝 |

角度寄存器包含有符号微弧度整数。QASM 汇编器归一化到 (2\pi) 周期后执行：

```text
li x31, round(remainder(theta, 2*pi) * 1000000)
.word <QRY/QRZ/QCU1 encoding using rd=x31>
```

`x31` 是 QASM 汇编器的角度 scratch register；手写混合程序可使用任意 `x0..x31`，但必须在执行参数门时保持其值。角度误差不超过 0.5 μrad。更紧的组合算子误差界见 [`THEORY.md`](THEORY.md)。

`.qinit N` 是加载器 directive，用于分配 `N` qubit 的 `|0...0〉` 状态，不是自定义 opcode。可执行指令必须以 `.word 0x????????` 进入模拟器；行尾助记注释不参与执行。

## 分解

- `SDG = S³`
- `TDG = T⁷`
- `H/X/S/T/CX/SWAP/CCX/MEASURE` 使用 `funct7=0` 直接编码
- `RY/RZ/CU1` 使用 `funct7=1` 和经典角度寄存器，不牺牲 5 位 qubit 索引

## 参考实现

- 编解码与 QASM 汇编：`loomq/quantum_riscv.py`
- `.word` 解码、状态演化与测量：`riscv_emulator.py`
- 端到端测试：`tests/test_quantum_riscv.py`

```bash
python3 -m loomq riscv circuits/bell.qasm
python3 -m unittest tests.test_quantum_riscv -v
```

测试覆盖 8 种离散指令 + 3 种参数指令往返、保留编码拒绝、Bell 的 100 个测量种子、CCX 语义、角度量化界，以及 `RY/RZ/CU1` 与核心状态向量模拟器的端到端对照。
