# QUANTUM-RISC-V 自定义量子指令编码规格（Bonus）

> 版本 1.0 · 本文档、`starter_kit/quantum_riscv.py`（扩展模拟器）与
> `tests/test_quantum_riscv.py`（端到端测试）三者构成 Bonus 申报材料。
> 扩展方式：继承官方 `TinyRISCVEmulator`（不改动原文件），新增 custom-0
> 指令空间，使一份程序内可同时完成经典运算与真实量子态演化。

## 1. 指令字格式

沿用 RV32I 的 R 型布局，opcode 固定为 **custom-0 = 0x0B**：

```text
 31        25 24    20 19    15 14   12 11     7 6      0
+-----------+--------+--------+-------+--------+--------+
|  funct7   |  rs2   |  rs1   | funct3|   rd   | opcode |
+-----------+--------+--------+-------+--------+--------+
   7 bits      5 bits   5 bits   3 bits  5 bits   7 bits
   操作码       立即数/   量子比特   恒 000  目标      0x0B
              第二操作  索引/控制           寄存器
```

## 2. funct7 分配表

| funct7 | 助记符 | 语法 | 语义 |
|---:|---|---|---|
| 1 | `qh`  | `qh rs1`          | 对量子比特 `x[rs1]` 施加 Hadamard |
| 2 | `qx`  | `qx rs1`          | Pauli-X（量子非门） |
| 3 | `qz`  | `qz rs1`          | Pauli-Z（相位翻转） |
| 4 | `qrz` | `qrz rs1, imm`    | RZ(imm·π/8)，imm 为 5 位二补码（rs2 字段），范围 [-16, 15] |
| 5 | `qcx` | `qcx rs1, rs2`    | CNOT：control=`x[rs1]`，target=`x[rs2]` |
| 6 | `qmeas` | `qmeas rs1, rd` | 测量 `x[rs1]` 并坍缩，把 0/1 写入通用寄存器 `rd` |
| 7 | `qinit` | `qinit`         | 量子态重置为 \|00…0⟩ |

约定：

* **寄存器传址**：所有"量子比特编号"都来自通用寄存器的当前值，
  例如 `li x5, 0` 后 `qh x5` 表示对 0 号量子比特做 H。这让经典计算
  结果可以直接决定后续量子操作——真正的 hybrid。
* **测量语义**：按玻恩规则采样（P(1)=Σ|含该比特为 1 的振幅|²），
  随后状态坍缩归一；结果写入目标通用寄存器，可立刻参与 beq/bne 分支。
* **确定性**：采样器使用可注入的 `random.Random(seed)`，端到端测试
  因此完全可复现。
* **规模上限**：扩展模拟器支持 1–12 量子比特（构造参数可调）。

## 3. 编解码示例

```python
from starter_kit.quantum_riscv import encode, decode

word = encode("qh", "x5")            # -> (1<<25)|(5<<15)|0x0B = 0x02A000EB
decode(word)                         # -> ("qh", ["x5"])
word = encode("qrz", "x6", -3)       # RZ(-3π/8)
decode(word)                         # -> ("qrz", ["x6", "-3"])
```

## 4. 完整示例：贝尔态制备与读取

```text
li    x5, 0        # x5 = 量子比特 0
qh    x5           # H q0            -> (|00>+|10>)/√2
li    x6, 1        # x6 = 量子比特 1
qcx   x5, x6       # CNOT q0,q1      -> 贝尔态 (|00>+|11>)/√2
qmeas x5, x10      # 测量 -> x10 ∈ {0,1}
qmeas x6, x11      # 与 x10 强关联：只出现 (0,0) 或 (1,1)
```

## 5. 端到端测试

```bash
# 仓库根目录
python -m unittest tests.test_quantum_riscv -v
# 或全量回归（含本扩展）
python -m unittest discover -s tests
```

测试覆盖：贝尔/GHZ 关联统计、编码-解码往返、混合经典分支
（测量结果驱动 X 校正）、非法操作数报错路径。
