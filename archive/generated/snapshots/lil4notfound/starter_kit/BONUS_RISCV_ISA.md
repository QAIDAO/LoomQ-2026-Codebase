# LoomQ 量子 RISC-V 扩展 v1.0

本可选扩展与基础 L3 契约相互隔离。`adapter.compile_hybrid()` 仍然只生成官方规定的 `li`、`add`、`sub`、`addi`、`beq`、`bne` 和 `j` 指令子集。量子机器字仅由 `loomq_bonus.compile_hybrid_bonus()` 生成，并且仅由 `loomq_bonus.QuantumRISCVEmulator` 执行。

## 机器字布局

所有机器字均为无符号 32 位 RISC-V 指令字，按小端序存储。本扩展使用两个 RISC-V 自定义操作码空间：

| 空间 | 位 `6:0` | 用途 |
|---|---:|---|
| custom-0 | `0001011`（`0x0b`） | 量子初始化、量子门和测量 |
| custom-1 | `0101011`（`0x2b`） | 有符号定点角度锁存（`QPARAM`） |

custom-0 使用 R 型布局：

```text
31          25 24      20 19      15 14   12 11       7 6       0
+--------------+----------+----------+-------+-----------+---------+
| function[6:0]| rs2[4:0] | rs1[4:0] | 000   | rd[4:0]   | 0001011 |
+--------------+----------+----------+-------+-----------+---------+
```

未使用的字段必须为零。量子比特标识符和 RISC-V 寄存器标识符均为无符号 5 位值。为限制内存使用，参考状态向量模拟器有意将 `QINIT` 限制在 20 个量子比特以内。

## 指令表

| 助记符 | 功能码 | `rs1` | `rs2` | `rd` | 参数 |
|---|---:|---|---|---|---|
| `QINIT n` | 1 | 0 | 0 | 量子比特数 | 无 |
| `QH q` | 2 | 量子比特 | 0 | 0 | 无 |
| `QX q` | 3 | 量子比特 | 0 | 0 | 无 |
| `QS q` | 4 | 量子比特 | 0 | 0 | 无 |
| `QSDG q` | 5 | 量子比特 | 0 | 0 | 无 |
| `QT q` | 6 | 量子比特 | 0 | 0 | 无 |
| `QTDG q` | 7 | 量子比特 | 0 | 0 | 无 |
| `QRY q` | 8 | 量子比特 | 0 | 0 | 前置 `QPARAM` |
| `QRZ q` | 9 | 量子比特 | 0 | 0 | 前置 `QPARAM` |
| `QCX control, target` | 10 | 控制比特 | 目标比特 | 0 | 无 |
| `QCU1 control, target` | 11 | 控制比特 | 目标比特 | 0 | 前置 `QPARAM` |
| `QSWAP first, second` | 12 | 第一个比特 | 第二个比特 | 0 | 无 |
| `QCCX a, b, target` | 13 | 控制比特 a | 控制比特 b | 目标比特 | 无 |
| `QMEASURE q, xN` | 14 | 量子比特 | 0 | 目标寄存器 | 无 |

`QMEASURE` 会使量子态坍缩，并将 `0` 或 `1` 写入 `xN`。本扩展保留 Hybrid-QASM 的映射约定：经典位 0 映射到 `x10`，经典位 1 映射到 `x11`，依此类推。

## 角度编码

`QPARAM` 使用 custom-1。位 `31:20` 存放一个有符号 12 位二进制补码整数；位 `19:7` 必须为零。角度按下式计算：

```text
angle_radians = signed_value * pi / 1024
```

可表示范围为 `-2*pi` 至 `2047*pi/1024`。编译时采用最接近偶数的舍入方式，并拒绝非有限值或超出范围的值。`QPARAM` 后必须紧接 `QRY`、`QRZ` 或 `QCU1`；参数被消费前再次出现参数、出现其他指令，或程序直接结束，均属于非法序列。

## 拒绝规则

解码器和模拟器会拒绝以下情况：未知操作码或功能码、保留字段非零、量子门操作数重复、`QINIT 0`、测量结果写入 `x0`、在 `QINIT` 前执行量子门、量子比特超出已初始化范围、参数顺序无效，以及指令流长度超过继承的步数限制。

## 实现与测试

- 规格和指令定义：`BONUS_RISCV_ISA.md`、`loomq_bonus/isa.py`
- 编码器和解码器：`loomq_bonus/encoder.py`、`loomq_bonus/decoder.py`
- 官方模拟器扩展：`loomq_bonus/emulator.py`，继承 `riscv_emulator.TinyRISCVEmulator`
- Hybrid 编译器独立扩展入口：`loomq_bonus/compiler.py`
- 端到端测试：`tests/test_bonus_riscv.py`

从仓库根目录运行：

```bash
python -m unittest starter_kit.tests.test_bonus_riscv -v
```

测试覆盖已知的 32 位布局和编码／解码回读、赛事规定的全部量子门、定点角度精度、保留字段和指令顺序拒绝规则、运行时量子比特边界、编码后的 Bell 程序驱动继承的经典分支，以及 Bonus 与基础 L3 契约的隔离。
