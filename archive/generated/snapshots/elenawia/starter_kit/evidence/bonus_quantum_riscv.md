# Bonus：自定义量子 RISC-V 扩展指令

本项目申报 Bonus 中的“自定义量子 RISC-V 扩展指令”。本实现包含 custom-0 32-bit 编码规格、模拟器执行支持和 Bell 态端到端测试。

目标是在官方 Tiny RISC-V 模拟器基础上，加入一组可编码、可解码、可执行的量子扩展指令，让一段 RISC-V 风格程序可以直接描述并运行 Bell 态实验。

## 指令设计

本扩展保留官方 Tiny RISC-V 原有 `li/add/sub/addi/beq/bne/j` 行为不变，在模拟器中增加以下量子指令执行支持，并为这些指令提供 custom-0 32-bit 编码/解码：

| 指令 | 格式 | 含义 |
|---|---|---|
| `qinit` | `qinit n` | 初始化 `n` 个量子位到 `|0...0>`，当前轻量实现最多 8 个量子位 |
| `qh` | `qh q0` 或 `qh q[0]` | 对指定量子位执行 Hadamard 门 |
| `qx` | `qx q0` 或 `qx q[0]` | 对指定量子位执行 Pauli-X 门 |
| `qcx` | `qcx q0, q1` | 以第一个量子位为控制位，第二个量子位为目标位执行 CNOT |
| `qmeasure` | `qmeasure q0, x1` | 测量指定量子位，并把 0/1 写入经典寄存器 |

## 32-bit custom opcode 编码约定

本扩展使用 RISC-V `custom-0` opcode 域，并在 `starter_kit/riscv_emulator.py` 中提供可测试的编码/解码函数：

```python
encode_quantum_instruction(...)
decode_quantum_instruction(...)
```

32-bit 指令布局采用 R-type 字段：

```text
31      25 24   20 19   15 14    12 11    7 6       0
+---------+-------+-------+--------+-------+---------+
| funct7  |  rs2  |  rs1  | funct3 |  rd   | opcode  |
+---------+-------+-------+--------+-------+---------+
```

固定字段：

```text
opcode = 0b0001011  # custom-0
funct7 = 0b0000000
```

量子指令字段定义：

| 助记符 | funct3 | funct7 | rs1 | rs2 | rd |
|---|---:|---:|---|---|---|
| `qinit n` | 0 | 0 | `n` | 0 | 0 |
| `qh qA` | 1 | 0 | `qA` | 0 | 0 |
| `qx qA` | 2 | 0 | `qA` | 0 | 0 |
| `qcx qA, qB` | 3 | 0 | `qA` | `qB` | 0 |
| `qmeasure qA, xD` | 4 | 0 | `qA` | 0 | `xD` |

字段含义：

- `rs1` 表示主量子位编号；在 `qinit` 中表示初始化量子位数量 `n`。
- `rs2` 在 `qcx` 中表示目标量子位编号。
- `rd` 在 `qmeasure` 中表示写入的经典 RISC-V 寄存器。

编码示例：

```text
qinit 2          -> opcode custom-0, funct3=0, rs1=2
qh q0            -> opcode custom-0, funct3=1, rs1=0
qcx q0, q1       -> opcode custom-0, funct3=3, rs1=0, rs2=1
qmeasure q1, x2  -> opcode custom-0, funct3=4, rs1=1, rd=2
```

当前提交支持两层验证：执行路径可直接运行量子扩展汇编；编码/解码函数验证同一组量子操作可映射到 32-bit RISC-V custom-0 指令字段。

## 示例：Bell 态端到端程序

```asm
qinit 2
qh q0
qcx q0, q1
qmeasure q0, x1
qmeasure q1, x2
```

运行多次后，`x1x2` 的主结果应集中在：

```text
00
11
```

这说明自定义量子指令确实完成了：

```text
初始化两个量子位 → 制造叠加 → 制造关联 → 测量到经典寄存器
```

## 端到端测试

从仓库根目录运行：

```bash
python -m unittest tests.test_bonus_quantum_riscv
```

该测试会：

1. 执行 Bell 态量子 RISC-V 程序；
2. 多 shots 运行并统计 `x1/x2` 结果；
3. 检查结果只集中在 `00` 和 `11`；
4. 检查两类主结果数量接近；
5. 验证 `qinit/qh/qcx/qmeasure` 的 32-bit custom opcode 编码/解码；
6. 确认原有 Tiny RISC-V 经典指令仍可正常运行。


