# LoomQ 自定义量子 RISC-V 扩展（custom-0）

本扩展把 12 门白名单中的基础门（H / X / CNOT）和测量编码进 RISC-V **custom-0** 操作码空间，并在官方 `riscv_emulator.py` 中实现。经典指令（`li/add/sub/addi/beq/bne/j`）语义不变，L3 公开评测不受影响。

## 1. 指令编码

RISC-V 32-bit R-type：

```
31        25 24    20 19    15 14    12 11     7 6      0
   funct7      rs2      rs1     funct3     rd     opcode
```

| 字段 | 值 |
|---|---|
| opcode | `0001011`（custom-0，十进制 11 / `0x0B`） |
| rd / rs1 / rs2 | 5-bit 寄存器编号；量子比特下标用同一编号（`x0` = qubit 0） |

### funct3 分配

| 助记符 | funct3 | rd | rs1 | rs2 | 语义 |
|---|---|---|---|---|---|
| `qinit` | `000` | 0 | 0 | n | 分配 n 个量子比特，态 \|0…0⟩ |
| `qh` | `001` | 0 | q | 0 | Hadamard on qubit q |
| `qx` | `010` | 0 | q | 0 | Pauli-X on qubit q |
| `qcx` | `011` | 0 | control | target | CNOT |
| `qmeas` | `100` | dest | q | 0 | 测量 qubit q，0/1 写入 dest 寄存器 |

编码辅助：`TinyRISCVEmulator.encode_custom(op, rd, rs1, rs2)`。

汇编示例（Bell）：

```text
qinit 2
qh x0
qcx x0, x1
qmeas x0, x10
qmeas x1, x11
```

约定：测量结果写入 `x10, x11, …`，与 Hybrid-QASM 的 `c[0]→x10` 一致。

## 2. 模拟器实现位置

`starter_kit/riscv_emulator.py` 中的 `TinyRISCVEmulator`：

- 新增量子指令执行路径与态矢量
- `load_and_shot(asm, shots)` 做重复采样
- 原有经典指令测试与 L3 `compile_hybrid` 输出仍只使用 `li/add/...`

## 3. 端到端测试

```bash
cd starter_kit
python test_quantum_riscv.py
```

该测试会：编码 custom-0 字、运行 Bell 汇编、核对 `00/11` 主导分布，并确认经典 `li/add` 回归仍通过。
