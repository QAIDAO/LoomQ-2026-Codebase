# LoomQ Custom-0 量子 RISC-V 扩展指令规格

- 版本：Custom-0 v1
- 状态：随本仓库提交，用于 LoomQ L3 的本地可复现实验
- 范围：定义三个 32 位 Custom-0 指令 `qh`、`qcx`、`qmeas`，并说明其在本项目轻量级模拟器中的确定性执行语义。

## 1. 兼容性与实现位置

本规格**直接扩展赛事 starter kit 官方提供的** [`riscv_emulator.py`](riscv_emulator.py) 中 `TinyRISCVEmulator`；没有另建或替换一个 RISC-V 模拟器。原有的通用寄存器、算术和控制流指令保持原有行为。扩展实现与编码/解码辅助函数位于同一文件，端到端测试位于 [`tests/l3/test_quantum_riscv_extension.py`](tests/l3/test_quantum_riscv_extension.py)。

## 2. 32 位指令格式

所有指令采用 RISC-V Custom-0 主操作码 `0x0B`（二进制 `0001011`），使用 R 型字段布局：

| 位段 | 位数 | 字段 | 规则 |
| --- | ---: | --- | --- |
| `[31:25]` | 7 | `funct7` | 保留，必须为 `0b0000000` |
| `[24:20]` | 5 | `rs2` | 见各指令操作数定义；未使用时必须为 0 |
| `[19:15]` | 5 | `rs1` | 见各指令操作数定义；未使用时必须为 0 |
| `[14:12]` | 3 | `funct3` | `000`=`qh`，`001`=`qcx`，`010`=`qmeas` |
| `[11:7]` | 5 | `rd` | 见各指令操作数定义；未使用时必须为 0 |
| `[6:0]` | 7 | `opcode` | 固定为 `0x0B`（Custom-0） |

解码时，任何 `funct7 != 0`、未知 `funct3`、或未使用字段非零的指令都会被拒绝。量子位字段虽占 5 位，但合法值只允许 `0..7`。

## 3. 指令定义

| 助记符 | `funct3` | 字段赋值 | 语义 |
| --- | --- | --- | --- |
| `qh qd` | `000` | `rd=qd`，`rs1=0`，`rs2=0` | 对量子位 `qd` 施加 Hadamard 门。`qd` 为 `q0..q7`。 |
| `qcx qc, qt` | `001` | `rd=0`，`rs1=qc`，`rs2=qt` | 施加受控 X 门：`qc` 为控制位、`qt` 为目标位。两者必须在 `q0..q7` 且不同。 |
| `qmeas rd, qs` | `010` | `rd` 为经典目标寄存器，`rs1=qs`，`rs2=0` | 测量量子位 `qs`，把结果 `0` 或 `1` 写入整数寄存器 `rd`。`qs` 为 `q0..q7`，`rd` 为 `x0..x31`。 |

`qmeas x0, qs` 在编码上合法，但遵循基础模拟器的 RISC-V 语义：`x0` 恒为零，因此测量发生但结果不会保存在寄存器中。实际程序应使用 `x1..x31` 接收测量结果。

## 4. 量子执行模型与边界

- 模拟器维护固定 8 量子位的 statevector（基态顺序按位索引 `q0..q7`），初态为 `|00000000⟩`。
- `qh` 与 `qcx` 为理想门操作；`qmeas` 按 Born 概率抽样并对 statevector 做投影塌缩及归一化。
- 可在构造时传入 `TinyRISCVEmulator(random_seed=<整数>)`，使测量伪随机序列可复现。
- 每次 `load_program(...)` 都会重置经典寄存器、程序计数器、量子态和随机数发生器；同一 seed 下重新加载同一程序得到可复现的执行过程。
- 这是赛事 starter kit 的轻量级本地模拟语义，不表示真实量子硬件指令集或硬件噪声模型。

## 5. 原始指令字 Bell 端到端示例

以下程序从 `|00⟩` 制备 Bell 态 `( |00⟩ + |11⟩ ) / √2`，随后测量到 `x10` 与 `x11`：

```python
from starter_kit.riscv_emulator import TinyRISCVEmulator

bell_words = [
    0x0000000B,  # qh q0:       funct3=000, rd=0
    0x0010100B,  # qcx q0, q1:  funct3=001, rs1=0, rs2=1, rd=0
    0x0000250B,  # qmeas x10,q0: funct3=010, rd=10, rs1=0
    0x0000A58B,  # qmeas x11,q1: funct3=010, rd=11, rs1=1
]

emu = TinyRISCVEmulator(random_seed=7)
emu.load_program(bell_words)
state = emu.execute()
```

两次测量必须相关：若 `x10` 被写为 `1`，则 `x11` 也为 `1`；若第一次为 `0`，第二次也为 `0`。模拟器返回结果字典时会省略值为零的寄存器，因此 `00` 分支可表现为 `x10`、`x11` 都不在返回字典中，而 `11` 分支表现为 `{"x10": 1, "x11": 1}`。这不是不相关或漏测量。

## 6. 可复现验证

在仓库根目录运行：

```powershell
python -m unittest discover -s starter_kit/tests/l3 -p 'test_*.py' -v
```

与本扩展直接对应的端到端和编码验证在 [`tests/l3/test_quantum_riscv_extension.py`](tests/l3/test_quantum_riscv_extension.py)，其中覆盖：原始 32 位指令字的 Bell 测量相关性、编码/解码往返、固定 seed、重载程序后的状态重置，以及经典指令兼容性。
