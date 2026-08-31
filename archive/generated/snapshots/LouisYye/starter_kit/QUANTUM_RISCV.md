# LoomQ 量子 RISC-V Custom-0 扩展

本扩展使用 RISC-V 保留的 `custom-0` major opcode `0001011`（`0x0B`），将 L3
分离出的量子操作表示为可审计的指令流。当前模拟器接受下列文本汇编，并把执行结果
记录在 `quantum_trace`；经典寄存器和控制流语义保持不变。

## 32 位编码

| 位 | 字段 | 含义 |
|---|---|---|
| 6..0 | opcode | 固定 `0001011` |
| 14..12 | funct3 | `000` = `qgate`，`001` = `qmeasure` |
| 11..7 | qd | 文本中的第一个量子位；测量时为量子位 |
| 19..15 | qs1 | 文本中的第二个量子位；测量时为经典位 |
| 24..20 | qs2 | 文本中的第三个量子位 |
| 31..25 | funct7 | 门编号 |

门编号：`h=1, x=2, s=3, sdg=4, t=5, tdg=6, cx=7, swap=8, ccx=9`。
索引范围为 0..31。`qmeasure` 的 `funct7` 和 `qs2` 必须为零。

## 文本汇编

```text
qgate h, 0
qgate cx, 0, 1
qmeasure 0, 0
qmeasure 1, 1
```

`encode_quantum_instruction()` 与 `decode_quantum_instruction()` 实际产出并解析上述
32 位字。`l3_compiler.emit_quantum_riscv()` 将无参数量子操作输出为 `.word 0x........`
机器字；`TinyRISCVEmulator` 对机器字解码后才记录和执行量子 trace。文本助记符也会
先经过同一 encode/decode 路径，因此规格与实现共享唯一事实源。非法 opcode、funct、
保留位、门参数数量和越界索引都会失败。端到端复现命令：

```bash
python3 -m pytest tests/test_quantum_riscv.py -q
```
