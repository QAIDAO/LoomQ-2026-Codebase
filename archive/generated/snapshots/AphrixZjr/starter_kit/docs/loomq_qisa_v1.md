# LoomQ-QISA-v1 最小量子 RISC-V 扩展

本规格定义比赛 Bonus 使用的最小“汇编 → 32 位指令 → 解码 → 执行”闭环；它不是完整 RV32I、QEMU、ABI 或真实量子协处理器。

## 执行模型

- PC 是字节地址，每条指令 4 字节并要求 4 字节对齐；分支和跳转偏移相对当前 PC。
- `x0..x31` 保存无符号 32 位值，算术按 `2^32` 回绕，`x0` 恒为零。
- 支持 `add/sub/addi/beq/bne/lui/jal x0`，以及伪指令 `li` 和 `j`。I/B/J 立即数采用标准 RV32I 布局和符号扩展。
- instruction memory 只接收 `0..0xffffffff` 的整数；executor 只消费机器字及 decoder 结果。

## QGATE（custom-0，opcode `0x0b`）

位 `31:25` 为 `gate_id`，`24:20` 为 `aux`，`19:15` 为 `q1`，`14:12` 为固定零 mode，`11:7` 为 `q0`。

| ID | 门 | ID | 门 |
|---:|---|---:|---|
| 1 | h | 7 | rz |
| 2 | x | 8 | ry |
| 3 | s | 9 | cx |
| 4 | sdg | 10 | cu1 |
| 5 | t | 11 | swap |
| 6 | tdg | 12 | ccx |

单比特门使用 `q0`；双比特门使用 `q0/q1`；`ccx` 使用 `q0/q1/aux`。`rz/ry/cu1` 的 `aux` 是参数寄存器。其有符号值按 Q16.16 弧度解释。assembler 用十进制精确运算及 round-to-nearest、ties-to-even 量化，超出 32 位装载范围时报错。mode、门 ID 0/13..127 和未使用的非零字段均拒绝。

汇编形式为 `qgate <gate>, <qubits...>`；参数门追加 `<x-register>, <radian-literal>`，例如 `qgate rz, 0, x6, 1.5`。assembler 会显式生成参数寄存器的 `li` 机器指令。

## QCTRL（custom-1，opcode `0x2b`）

位 `31:25` 保留为零，`24:20` 为 slot，`19:15` 为 q，`14:12` 为 op，`11:7` 为 rd。

| op | 汇编 | 语义 |
|---:|---|---|
| 0 | `qreset` | 清空 pending circuit、测量和结果 |
| 1 | `qmeasure q, slot` | 声明测量映射 |
| 2 | `qsubmit` | 将 pending circuit 一次提交给本地 backend |
| 3 | `qread rd, slot` | 将最近结果的 0/1 写入 rd |

保留 op、保留字段、重复 slot、空提交、提交前读取和未知结果均 fail closed。v1 的本地参考 backend 只用于确定性单次演示；也可注入符合相同窄接口的 backend。

## 可复现验证

```bash
python tests/test_quantum_riscv_e2e.py -v
```

官方 `riscv_emulator.py` 直接承载 `assemble()`、`decode()` 和 `QuantumRISCVEmulator`。`TinyRISCVEmulator` 的文本指令和 Python 整数语义保持不变，因此 L3 兼容路径不受机器码的 RV32 回绕语义影响。`quantum_riscv.py` 仅保留为旧导入路径的兼容层。
