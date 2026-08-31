# LoomQ QISA v1 — 自定义量子 RISC-V 扩展规格

**版本**: 1.0  
**实现**: `starter_kit/riscv_emulator.py`  
**Opcode 族**: RISC-V **custom-0**（`opcode[6:0] = 0b0001011`）

本文档定义 LoomQ 在 TinyRISCVEmulator 上的**最小可评分**量子指令集扩展（QISA）。
经典基线（`li` / `add` / `addi` / `sub` / `beq` / `bne` / `blt` / `bge` / `jal` / `jalr` / `j` / `mv`）语义不变；
量子指令仅增加内部 statevector 与测量写回 GPR 的能力。

---

## 1. 文本助记符与机器码闭环（评分口径）

依据主办方 Q&A **Q3**：Bonus 期望第 **1** 种方向——自定义编码须进入**可运行、可验证**的执行链路，不能只存在于文档。不要求完整汇编器/链接器；在官方 `riscv_emulator.py` 上做最小闭环即可。

本实现的闭环：

```text
(mnemonic, fields) → assemble_quantum_word → 32-bit CUSTOM-0 word
       → load_machine_words → decode_quantum_word → (op, args) → execute
```

文本 `load_program` 仍保留：用于 L3 经典控制流与可读汇编；**Bonus 验真以 `load_machine_words` 路径为准**（见 `test_bell_via_machine_words_closed_loop`）。

| 助记符 | 操作数 | 语义 |
|--------|--------|------|
| `qinit n` | `n` ∈ 1..8 | 分配/重置 `n` 个量子比特为 \|0…0⟩ |
| `qh q` | 量子比特下标 | 对 qubit `q` 施加 Hadamard |
| `qx q` | 量子比特下标 | 对 qubit `q` 施加 Pauli-X |
| `qcx c, t` | 控制、目标 | CNOT：control=`c`，target=`t`（须不同且 < n） |
| `qmeas q, rd` | 量子比特、经典寄存器 | Z 基测量 qubit `q`，坍缩态矢量；将 0/1 写入 GPR `rd`（如 `x10`） |

约定：

- 量子比特编号从 **0** 开始；状态索引的 **bit k = qubit k**（小端）。
- 必须先 `qinit`，再执行其它量子指令。
- `qmeas` 使用模拟器内置 RNG；默认种子 **`rng_seed=42`**（见 `TinyRISCVEmulator(rng_seed=...)`）。`load_program` 会按当前种子重置 RNG，保证可复现。
- 经典控制流与量子指令可交错；测量结果进入 GPR 后可供 `beq`/`bne` 等使用。

---

## 2. 32-bit 二进制编码（CUSTOM-0）

所有 QISA v1 指令共用 R-type 风格字段布局：

```
31        25 24     20 19     15 14  12 11    7 6      0
┌───────────┬─────────┬─────────┬──────┬───────┬────────┐
│  funct7   │   qs2   │   qs1   │funct3│  rd   │ opcode │
│   7 bit   │  5 bit  │  5 bit  │ 3bit │ 5bit  │  7bit  │
└───────────┴─────────┴─────────┴──────┴───────┴────────┘
```

固定字段：

| 字段 | 位域 | v1 取值 |
|------|------|---------|
| `opcode` | `[6:0]` | `0b0001011`（CUSTOM-0） |
| `funct7` | `[31:25]` | `0`（保留；非零视为保留将来扩展） |
| `rd` | `[11:7]` | 仅 `qmeas` 使用：目的 GPR 编号；其余指令为 0 |
| `qs1` | `[19:15]` | 主操作数（见下表） |
| `qs2` | `[24:20]` | 次操作数（见下表） |
| `funct3` | `[14:12]` | 操作码选择 |

### 2.1 funct3 映射

| funct3 | 助记符 | qs1 | qs2 | rd |
|--------|--------|-----|-----|----|
| `000` | `qinit` | `n`（量子比特数） | 0 | 0 |
| `001` | `qh` | qubit | 0 | 0 |
| `010` | `qx` | qubit | 0 | 0 |
| `011` | `qcx` | control | target | 0 |
| `100` | `qmeas` | qubit | 0 | 目的 GPR 索引 |

### 2.2 编解码 API

模块 `riscv_emulator` 导出：

```python
assemble_quantum_word(mnemonic, *, qs1=0, qs2=0, rd=0, funct7=0) -> int
decode_quantum_word(word: int) -> dict  # mnemonic/opcode/funct3/qs1/qs2/rd/...
decoded_to_op_args(decoded) -> (op, args)
assemble_quantum_program_words([(mnemonic, fields), ...]) -> list[int]
TinyRISCVEmulator.load_machine_words(words)  # decode+load for execute()
```

示例（CNOT 0→1）：

```text
assemble_quantum_word("qcx", qs1=0, qs2=1)
  = funct7=0 | qs2=1 | qs1=0 | funct3=011 | rd=0 | opcode=0001011
  = 0x0010300B
```

---

## 3. 状态与门语义（实现诚实边界）

- **状态表示**: 长度 `2^n` 的复振幅列表（纯 Python `complex`，无 numpy 硬依赖）。
- **H / X**: 标准 2×2 酉矩阵作用在指定比特。
- **CNOT**: 控制为 1 时翻转目标比特。
- **Measure-Z**: 按 \|1⟩ 子空间概率采样，坍缩并归一化后写回 `rd`。
- **上限**: `n ≤ 8`（评分用例仅需 2 比特 Bell）。

本扩展是**可评分的最小教学 ISA**，不是完整量子 RISC-V SoC；不声称与第三方自定义 opcode 二进制兼容。

---

## 4. 例程：Bell 态制备与测量

```asm
# Bell |Φ+> = (|00>+|11>)/√2
# RNG seed = 42（TinyRISCVEmulator 默认）
qinit 2
qh 0
qcx 0, 1
qmeas 0, x10
qmeas 1, x11
# 期望：x10 == x11（完美相关）；单次取值 00 或 11
```

与经典混合示例：

```asm
qinit 1
qh 0
qmeas 0, x10
li x1, 0
bne x10, x1, WAS_ONE
li x2, 3          # measured 0
j DONE
WAS_ONE:
li x2, 7          # measured 1
DONE:
```

---

## 5. 复现命令

```bash
cd <repo-root>
PYTHONPATH=starter_kit python starter_kit/tests/test_quantum_riscv_e2e.py
# 经典 L3 回归（勿回归）：
PYTHONPATH=starter_kit python starter_kit/tests/test_hybrid.py
```

---

## 6. 与 L3 Hybrid-QASM 的关系

L3 评分仍使用官方 Hybrid-QASM → 经典汇编路径（测量值由评测注入 GPR）。
本 QISA 是**独立 Bonus**：在同一模拟器上原生执行量子助记符，用于展示自定义指令编码 + 模拟扩展 + E2E 证据，不替换 `compile_hybrid` 契约。
