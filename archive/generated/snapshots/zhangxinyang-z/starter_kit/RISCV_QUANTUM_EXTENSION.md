# LoomQ 自定义量子 RISC-V 扩展（LQX-1）

LQX-1 使用 RISC-V 保留的 `custom-0` opcode 空间（`0b0001011`）表达量子操作。它不改变标准 RISC-V 指令语义。

## 32 位编码

```text
31          25 24     20 19     15 14   12 11      7 6       0
|   funct7    |   q2    |   q1    | 000   |    rd    | 0001011 |
```

- `funct7`：量子操作码。
- `q1`：第一个量子比特索引（`q0`–`q7`）。
- `q2`：第二个量子比特索引，仅 `QCX` 使用，其他操作写零。
- `rd`：测量结果写入的标准 RISC-V 寄存器，仅 `QMEAS` 使用，其他操作写零。
- `0001011`：RISC-V `custom-0` opcode。

| 助记符 | `funct7` | 语义 |
|---|---:|---|
| `QH q1` | 0 | 对 q1 施加 Hadamard 门 |
| `QX q1` | 1 | 对 q1 施加 Pauli-X 门 |
| `QCX q1,q2` | 2 | q1 为控制位、q2 为目标位的 CNOT 门 |
| `QMEAS q1,rd` | 3 | 测量 q1，并将 0/1 写入 rd |

## 模拟器行为

`riscv_emulator.py` 接受汇编伪指令 `qword <32 位整数>`，解码后执行 LQX-1 指令。模拟器维护 8 个量子比特的状态向量和 `quantum_trace`。为保持自动测试可复现，测量使用最高概率结果；概率相同时选择 0，并执行状态坍缩。

## 端到端测试

```bash
python -m unittest tests.test_quantum_riscv_extension
```
