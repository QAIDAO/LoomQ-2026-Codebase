# LoomQ Bonus：量子 RISC-V 扩展指令

`compile_hybrid()` 仍然只输出官方模拟器已支持的 `li/add/sub/addi/beq/bne/j`，以保证 L3 客观分不受影响。下列指令是额外的自定义扩展，供 Bonus 评测。

## 编码

| 助记符 | 格式 | custom opcode | 语义 |
|---|---|---|---|
| `qh rd` | I-type, opcode `0x0B`, funct3=`000` | 对量子比特 `x[rd]` 做 Hadamard |
| `qx rd` | I-type, opcode `0x0B`, funct3=`001` | 对量子比特 `x[rd]` 做 Pauli-X |
| `qcx rd, rs` | R-type, opcode `0x2B`, funct7=`0000001` | CNOT，控制=`x[rd]`，目标=`x[rs]` |
| `qmeas rd, rs` | I-type, opcode `0x0B`, funct3=`111` | 测量量子比特 `x[rd]`，结果写入 `x[rs]` |

量子寄存器固定 8 比特，初态 `|0...0>`。测量采用主导态确定性投影（`P(1)≥0.5` 则得到 1），便于端到端断言。

## 实现位置

- 模拟器：`starter_kit/riscv_emulator.py` 中 `qh` / `qx` / `qcx` / `qmeas`
- 测试：`starter_kit/tests/test_quantum_riscv.py`

## 端到端示例（Bell）

```text
li x1, 0
li x2, 1
qh x1
qcx x1, x2
qmeas x1, x3
qmeas x2, x4
```

期望：`x3 == x4`（贝尔对相关）。
