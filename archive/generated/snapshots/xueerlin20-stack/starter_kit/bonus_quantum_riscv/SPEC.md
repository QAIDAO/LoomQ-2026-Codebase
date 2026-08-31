# LoomQ 自定义量子 RISC-V 扩展指令规范

版本：1.0  
实现目录：`starter_kit/bonus_quantum_riscv/`

## 1. 目标

本扩展把 LoomQ L1 支持的 12 类量子门和测量编码为 32 位 RISC-V 自定义指令，并让量子测量结果直接进入 L3 使用的经典寄存器 `x10..x31`。

现有 L1、L2、L3、`adapter.py` 和官方 `riscv_emulator.py` 保持不变。Bonus 编码器和扩展模拟器位于独立目录，可以单独测试，不影响正式自动评分入口。

RISC-V 官方指令表建议自定义扩展使用 `custom-0` 到 `custom-3` 的 major opcode。本扩展使用：

| 用途 | RISC-V 名称 | 二进制 | 十六进制 |
|---|---|---|---:|
| 量子门与测量 | `custom-0` | `0001011` | `0x0B` |
| 角度参数 | `custom-1` | `0101011` | `0x2B` |

参考：[RISC-V RV32/64G opcode map](https://docs.riscv.org/reference/isa/unpriv/rv-32-64g.html)。

## 2. Q-type：量子门与测量

量子门采用与 R-type 相同的字段位置：

```text
31          25 24       20 19       15 14    12 11        7 6          0
+--------------+-----------+-----------+--------+------------+------------+
| gate_id (7)  | q1 (5)    | q0 (5)    | 000    | rd (5)     | 0001011    |
+--------------+-----------+-----------+--------+------------+------------+
```

字段含义：

| 字段 | 含义 |
|---|---|
| `gate_id` | 量子门编号 |
| `q0` | 第一个量子比特，或 `qinit` 的量子比特总数 |
| `q1` | 第二个量子比特；单比特门固定为 0 |
| `rd` | `qccx` 的第三个量子比特，或 `qmeasure` 的经典目标寄存器 |
| `funct3` | 版本 1.0 固定为 `000` |
| `opcode` | 固定为 `custom-0 = 0001011` |

量子比特编号字段为 5 位，可编码 `q0..q31`。`qinit` 的数量范围为 1 到 31；当前轻量状态模拟器默认最多运行 12 个量子比特，避免内存随 `2^n` 快速增长。

## 3. 指令列表

| `gate_id` | 助记符 | 操作数 | 含义 |
|---:|---|---|---|
| 0 | `qinit n` | `q0=n` | 初始化 `n` 个量子比特为全 0 状态 |
| 1 | `qx qA` | `q0=A` | X 门 |
| 2 | `qh qA` | `q0=A` | H 门 |
| 3 | `qs qA` | `q0=A` | S 门 |
| 4 | `qsdg qA` | `q0=A` | S 的逆门 |
| 5 | `qt qA` | `q0=A` | T 门 |
| 6 | `qtdg qA` | `q0=A` | T 的逆门 |
| 7 | `qrz qA` | `q0=A` | RZ 门，读取参数暂存值 |
| 8 | `qry qA` | `q0=A` | RY 门，读取参数暂存值 |
| 9 | `qcx qA, qB` | `q0=A, q1=B` | 受控 X 门 |
| 10 | `qcu1 qA, qB` | `q0=A, q1=B` | 受控相位门，读取参数暂存值 |
| 11 | `qswap qA, qB` | `q0=A, q1=B` | 交换两个量子比特 |
| 12 | `qccx qA, qB, qC` | `q0=A, q1=B, rd=C` | 双控制 X 门 |
| 13 | `qmeasure qA, xD` | `q0=A, rd=D` | 测量 `qA`，把 0 或 1 写入 `xD` |

双比特和三比特指令要求所有量子比特编号互不相同。`qmeasure` 的目标必须是 `x10..x31`，与 L3 的 `c[k] -> x10+k` 规则一致。

## 4. QPARAM-type：角度参数

`ry`、`rz` 和 `cu1` 的角度由前一条 `qparam` 指令装入专用参数暂存值，不占用 `x1..x31`：

```text
31                                      7 6          0
+----------------------------------------+------------+
| signed angle in micro-radians (25 bits)| 0101011    |
+----------------------------------------+------------+
```

编码规则：

1. 输入角度单位为弧度；
2. 编码前按 `2*pi` 归一化；
3. 乘以 `1,000,000` 后四舍五入；
4. 使用 25 位有符号二进制保存；
5. 误差不超过约 `0.000001` 弧度；
6. 参数值保持有效，直到下一条 `qparam` 覆盖它。

示例：

```text
qparam 1.570796
qry q0
```

## 5. 编码示例

以下指令组成一个两比特 Bell 电路的核心：

| 汇编 | 32 位机器码 |
|---|---:|
| `qinit 2` | `0x0001000b` |
| `qh q0` | `0x0400000b` |
| `qcx q0, q1` | `0x1210000b` |
| `qmeasure q0, x10` | `0x1a00050b` |
| `qparam pi/2` | `0x0bfbf62b` |

`encoding.py` 同时提供编码与解码函数。解码器会拒绝未知 opcode、未知门编号、非零保留字段和非法操作数组合。

## 6. 执行语义

扩展模拟器遵循以下规则：

- `q0` 对应状态编号中的最低有效位；
- 所有量子门使用 OpenQASM `qelib1.inc` 的标准含义；
- `qmeasure` 在计算基中测量并更新量子状态；
- 测量值立即写入指定的经典寄存器；
- 后续 `beq`、`bne`、`add` 等官方经典指令可以直接读取该值；
- `run_shots()` 每次重新初始化量子状态和经典寄存器，并按 `c[n-1]...c[0]` 返回计数。

扩展模拟器保留官方模拟器的全部七类指令：

```text
li  add  sub  addi  beq  bne  j
```

## 7. 编译与执行流程

```text
Hybrid-QASM
    |
    +-- 现有 L3 解析器提取量子操作和经典语句
    |
    +-- Bonus 编码器把量子操作转换为 32 位 custom 指令
    |
    +-- 现有 L3 编译器生成经典 RISC-V 汇编
    |
    +-- 扩展模拟器解码量子机器码
            |
            +-- 执行量子门与测量
            +-- 测量写入 x10...
            +-- 继续执行经典分支
```

Python 入口：

```python
from starter_kit.bonus_quantum_riscv import (
    QuantumRISCVEmulator,
    compile_quantum_riscv,
)

program = compile_quantum_riscv(hybrid_qasm)
emulator = QuantumRISCVEmulator(seed=7)
emulator.load_words(program.quantum_words, program.classical_assembly)
registers = emulator.execute()
```

## 8. 端到端测试

在仓库根目录运行：

```powershell
python -B -m unittest discover -s starter_kit\bonus_quantum_riscv\tests -v
```

测试覆盖：

- 32 位编码与解码；
- `custom-0` 和 `custom-1` opcode；
- L1 全部 12 类量子门与测量；
- 参数门固定点编码；
- Bell 态多次采样；
- `CCX` 与 `SWAP`；
- 量子测量写入 `x10` 并驱动经典 `if/else`；
- 原官方七类经典指令兼容；
- 非法 opcode 和模拟器容量错误。
