# Q-extension：量子 RISC-V 自定义扩展指令集规格

> 本文档定义 LoomQ 提交中的自定义量子 RISC-V 扩展指令（Q-extension），
> 用于把量子门/测量操作编码进经典 RISC-V 指令流，实现「经典-量子统一指令流」。

## 1. 设计动机

L3 的 Hybrid-QASM 编译把量子操作与经典控制分成两份输出。Q-extension 更进一步：
让 RISC-V 指令流本身携带量子操作，处理器执行到量子指令时即可触发对应量子门，
使经典控制与量子操作在**同一条指令流**中顺序执行、共享寄存器空间。

## 2. 指令编码（32 位）

采用 RISC-V 自定义扩展区 `custom-0`（`opcode = 0b0001011`），R 型格式：

```
31        25 24     20 19     15 14     12 11      7 6       0
[  funct7  ][  rs2   ][  rs1   ][ funct3 ][   rd   ][ opcode  ]
[ 0000001  ][ 00000  ][  qb    ][  f3    ][   qa   ][ 0001011 ]
```

| 字段 | 位段 | 含义 |
|---|---|---|
| `opcode` | `[6:0]` | `0b0001011`（0x0B，custom-0） |
| `funct7` | `[31:25]` | `0b0000001`（Q-extension 标识） |
| `rs2` | `[24:20]` | 保留，置 0 |
| `rs1` | `[19:15]` | 操作数 B（qubit 或 cbit 索引） |
| `funct3` | `[14:12]` | 量子操作码 |
| `rd` | `[11:7]` | 操作数 A（qubit 索引） |

## 3. 指令表

| 指令 | `funct3` | 语义 |
|---|---|---|
| `qh rd` | `000` | 对 qubit `rd` 施加 Hadamard 门 |
| `qx rd` | `001` | 对 qubit `rd` 施加 Pauli-X 门 |
| `qcx rd, rs1` | `010` | 受控非门：`rs1` 为控制 qubit，`rd` 为目标 qubit |
| `qmeasure rd, rs1` | `011` | 测量 qubit `rd`，结果写入经典位 `c[rs1]` |

## 4. 与 QASM 的对应关系

| Q-extension 汇编 | 等价的 OpenQASM 2.0 |
|---|---|
| `qh x0` | `h q[0];` |
| `qx x1` | `x q[1];` |
| `qcx x1, x0` | `cx q[0], q[1];` |
| `qmeasure x0, x0` | `measure q[0] -> c[0];` |

## 5. 示例程序

把 Bell 态制备编码进 RISC-V 指令流：

```asm
qh x0            # h q[0]
qcx x1, x0       # cx q[0], q[1]
qmeasure x0, x0  # measure q[0] -> c[0]
qmeasure x1, x1  # measure q[1] -> c[1]
li x1, 5         # 经典后处理示例：r1 = 5
addi x1, x1, 1   # r1 = 6
```

## 6. 模拟器扩展位置

`starter_kit/qriscv_emulator.py` —— 基于官方 `riscv_emulator.py` 的扩展实现，
新增 `qh / qx / qcx / qmeasure` 四条指令，并维护量子操作轨迹
`quantum_trace`（记录执行的量子门/测量序列，便于校验与 L1 模拟器对接）。
