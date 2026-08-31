# 自定义量子 RISC-V Bonus

本材料对应仓库中独立的 `bonus/quantum_riscv/` proof-of-concept。它实现量子操作的 32-bit RISC-V `custom-0` 编码、严格解码与协处理器派发，用于验证二进制指令和测量驱动的经典控制流。它不接入 L1/L2/L3 production runner，也不实现量子态或真机后端。

## 1. 指令编码规格

完整规格见 [`bonus/quantum_riscv/SPEC.md`](../../../bonus/quantum_riscv/SPEC.md)，编解码实现在 [`bonus/quantum_riscv/encoding.py`](../../../bonus/quantum_riscv/encoding.py)。

所有指令均为固定 32-bit、R-type 风格的 `custom-0` 指令：

```text
 31          25 24       20 19       15 14    12 11         7 6          0
+---------------+-----------+-----------+--------+------------+------------+
| funct7 = 0    | q1        | q0        | funct3 | rd         | 0001011    |
+---------------+-----------+-----------+--------+------------+------------+
```

- `opcode[6:0] = 0x0B`（RISC-V `custom-0`）；
- `funct7[31:25]` 保留且必须为零；
- `q0[19:15]`、`q1[24:20]` 是 `q[0]..q[31]` 的量子操作数；
- `rd[11:7]` 仅供测量写入 RISC-V 经典寄存器；
- `funct3[14:12]` 定义量子子操作。

| 指令 | funct3 | 字段与语义 |
|---|---:|---|
| `QH q[a]` | `000` | `q0=a`；向协处理器派发 Hadamard 操作。 |
| `QX q[a]` | `001` | `q0=a`；向协处理器派发 Pauli-X 操作。 |
| `QCX q[a], q[b]` | `010` | `q0=a` 为 control、`q1=b` 为 target；两者必须不同。 |
| `QMEAS q[a] -> x[d]` | `011` | `q0=a`；协处理器返回 0/1，写入 `x[d]`；`d` 必须为 1..31。 |

编码器和解码器会拒绝非 `custom-0` opcode、非零保留字段、未定义 `funct3`、非法寄存器范围及不合法的 `QCX`/`QMEAS` 字段组合。示例编码及原始 word 验证见 [`tests/test_quantum_riscv_bonus.py`](../../../tests/test_quantum_riscv_bonus.py)。

## 2. 模拟器扩展实现

扩展执行器为 [`bonus/quantum_riscv/emulator.py`](../../../bonus/quantum_riscv/emulator.py) 中的 `QuantumRISCVEmulator`。它继承官方 [`riscv_emulator.py`](../../../riscv_emulator.py) 的 `TinyRISCVEmulator`，复用原有程序加载、寄存器、标签和经典指令语义；在取指循环中专门处理 `.word`：

```text
.word custom-0
  -> decode_quantum_instruction(word)
  -> QuantumInstruction
  -> QuantumRISCVEmulator._dispatch_quantum()
  -> QuantumCoprocessor.apply_gate() / measure()
```

`QH`、`QX`、`QCX` 经 `apply_gate()` 派发；`QMEAS` 经 `measure()` 取得严格的 0/1，再通过 `set_register()` 写入其 `rd`。因此同一程序中紧随其后的 `beq`、`bne` 可读取测量写回值并改变经典控制流。

随实现提供的 `TraceCoprocessor` 只记录结构化量子命令，并按预先注入的测量位返回 0 或 1。它是 ISA、派发与混合控制流的确定性测试后端，不是 statevector 量子模拟器，也不声明量子态演化结果。

L3 输出的受支持 `quantum_ops` 可由 [`bonus/quantum_riscv/translator.py`](../../../bonus/quantum_riscv/translator.py) 中的 `quantum_ops_to_words()` 编码为 `.word` 所用的 binary word。它支持 `h`、`x`、`cx`、`measure`，并按 L3 映射将 `c[k]` 写回 `x10+k`。

## 3. 端到端测试

测试入口为 [`tests/test_quantum_riscv_bonus.py`](../../../tests/test_quantum_riscv_bonus.py)。Dockerfile 的工作目录为 `/workspace/submission`；构建镜像后，可用以下命令执行：

```bash
docker run --rm loomq-final \
  python -m unittest tests.test_quantum_riscv_bonus -v
```

本次在宿主环境以等价的 `python3` 命令验证，结果为 **22 tests passed**。

端到端用例 `QuantumRISCVE2ETests.test_quantum_ops_to_words_to_emulator_to_trace` 的输入是一个 Hybrid-QASM Bell-like 程序：`h q[0]`、`cx q[0], q[1]`、`measure q[0] -> c[0]`，随后依据 `c[0]` 设置 `r1`，并计算 `r2 = r1 + 1`。

验证链路及断言为：

```text
Hybrid-QASM
  -> compile_hybrid_source()
  -> quantum_ops_to_words()
  -> .word 程序 + L3 经典汇编
  -> QuantumRISCVEmulator(TraceCoprocessor([1]))

words:  [0x0000000B, 0x0010200B, 0x0000350B]
trace:  QH q[0], QCX q[0], q[1], QMEAS q[0] -> x10
state:  x10 = 1, x1 = 200, x2 = 201
```

同一测试文件还覆盖 bit-exact 编解码、手工构造 raw word、保留字段拒绝、扩展执行器与官方经典执行器的 differential test，以及 `QMEAS` 写回控制 `beq`/`bne` 的两条分支。

## 4. 架构说明

```text
Hybrid-QASM
  -> LoomQ L3 compile_hybrid_source()
  -> quantum_ops + RISC-V 经典汇编
  -> quantum_ops_to_words()
  -> .word custom-0 + RISC-V 经典汇编
  -> QuantumRISCVEmulator
  -> decoder
  -> QuantumInstruction
  -> QuantumCoprocessor / TraceCoprocessor
```

经典 RISC-V 指令和量子 custom word 在同一 `QuantumRISCVEmulator` 取指循环中按程序顺序执行；测量结果写回 RV32 寄存器后参与后续经典分支。量子命令最终由可替换的 `QuantumCoprocessor` 接口接收，随仓库提供的实现为测试用 `TraceCoprocessor`。
