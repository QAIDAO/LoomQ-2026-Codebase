# Task 15A：自定义 Quantum RISC-V Bonus 第一版

## 背景

L1 / L2 / L3 主评分链路已经完成并稳定。当前 `feat/l3` 分支上的 L3 已通过独立审计、随机 differential testing、Docker regression，并已开启 `levels.l3: true`。

官方 Bonus 额外提供：

> **自定义量子 RISC-V 扩展指令：+8 分**
>
> 三项必须齐全：
> 1. 指令编码规格文档；
> 2. 对官方 RISC-V 模拟器的扩展实现；
> 3. 可运行的端到端测试。

本任务目标是在**完全不影响 L1/L2/L3 正式评分路径**的前提下，实现一套最小、完整、可信、可演示的 Quantum RISC-V custom instruction extension。

这不是要实现真正的量子 CPU、QEMU、FPGA 或完整 RISC-V ISA；重点是把“量子操作如何作为 RISC-V custom instruction 被编码、解码并派发给量子协处理器”这件事设计完整并可运行证明。

---

# 第一原则：Bonus 必须旁路隔离

不得修改或破坏以下正式评分路径：

```text
starter_kit/adapter.py
starter_kit/loomq/l3/**
starter_kit/riscv_emulator.py
starter_kit/evaluator.py
starter_kit/submission.yaml
```

尤其：

- `compile_hybrid()` 行为保持完全不变；
- L3 当前生成的普通 RISC-V assembly 保持完全不变；
- 官方 `TinyRISCVEmulator` 本体保持不变；
- 不增加 L1/L2/L3 production dependency；
- 不改变已有 requirements，除非 Bonus 无法用标准库完成；原则上本任务应当只用 Python 标准库。

Bonus 应单独放置，例如：

```text
starter_kit/bonus/quantum_riscv/
  __init__.py
  SPEC.md
  encoding.py
  emulator.py
  demo.py              # 如有必要
  README.md            # 可选，SPEC 已足够时不要重复

starter_kit/tests/test_quantum_riscv_bonus.py
```

文件名可根据现有结构微调，但必须保持隔离。

---

# 目标架构

建议采用“RISC-V CPU + quantum coprocessor dispatch”的真实心智模型，而不是假装普通 CPU 自己计算量子态：

```text
quantum_ops
    ↓
Quantum RISC-V Encoder
    ↓
32-bit custom instruction words
    ↓
QuantumRISCVEmulator
    ↓ decode
Quantum Coprocessor Interface
    ↓
Trace / deterministic test backend
```

经典 RISC-V 仍负责普通：

```text
li / add / sub / addi / beq / bne / j
```

Quantum custom instruction 负责表达：

```text
单量子位 gate
双量子位 gate
三量子位 gate（如需要）
measurement
```

模拟器扩展收到 custom instruction 后，不需要伪造真实量子硬件。

更合理的设计是：

- decode custom instruction；
- 转成稳定的结构化 quantum command；
- dispatch 到一个极小的 `QuantumBackend` / `QuantumCoprocessor` 接口；
- 默认测试 backend 记录命令；
- measurement 可由 deterministic test backend 返回 0/1，并按规格写入指定经典寄存器，证明经典-量子控制链真正串联。

不要用随机 measurement 作为测试依据。

---

# Part A：先重新确认官方 Bonus 契约

开始编码前阅读：

```text
problem_statement.md
starter_kit/README.md
starter_kit/evidence/README.md
starter_kit/riscv_emulator.py
starter_kit/loomq/l3/**
```

写下极简内部 checklist，确认：

- Bonus 是额外 +8，不属于 L3 自动评分接口；
- 三项证据必须齐全；
- 官方要求是 custom opcode + simulator extension + E2E test；
- 不需要把 Bonus 接入 `compile_hybrid()` 正式接口；
- 不要根据猜测扩成完整 CPU / 完整量子 ISA。

如果 RISC-V custom opcode 编码选择依赖规范事实（例如 custom opcode 空间），必须基于可信规范确认后再写入 `SPEC.md`；不要凭模型记忆拍脑袋。如果当前环境不能访问规范，则明确记录选择依据与限制，不要伪造引用。

---

# Part B：设计最小 Quantum RISC-V ISA

## 设计目标

需要一份真正的 **32-bit instruction encoding**，不能只有文本 mnemonic。

设计应满足：

- 使用 RISC-V 为自定义扩展保留的 opcode 空间；
- 32-bit word 可 encode/decode；
- 字段含义明确；
- 非法字段组合 deterministic fail；
- quantum register index 有明确位宽与范围；
- measurement 的 classical destination 有明确语义；
- 保留未来扩展空间；
- 不与当前普通 Tiny RISC-V 指令语义混淆。

## 推荐最小指令集合

不要一开始覆盖所有 12 个 L1 gate。

优先设计一组足以证明完整模型、又有实际量子意义的指令，例如：

```text
QH       单量子位 H
QX       单量子位 X
QCX      双量子位 controlled-X
QMEAS    measurement -> classical register
```

若当前编码结构自然支持，可以额外支持少量 gate；但不要为了“全门集”引入 angle encoding、浮点立即数、多字指令协议等大复杂度。

参数化 `ry/rz/cu1` 不作为本任务必须项。

在 `SPEC.md` 明确写：

> Task 15A 是 custom ISA proof-of-concept / Bonus extension，不替代 L1/L3 的完整量子 IR。

## 编码文档至少说明

例如按 RISC-V 常见字段风格定义：

```text
31 ... 25 | 24 ... 20 | 19 ... 15 | 14 ... 12 | 11 ... 7 | 6 ... 0
```

具体字段由你在确认规范后设计。

必须写清楚：

- opcode；
- funct / sub-opcode；
- q0 / q1 等 operand 在哪些 bit；
- classical destination 如何表示；
- reserved bits；
- 每条指令的语义；
- encode 示例（十六进制 word）；
- decode 示例；
- 非法编码如何处理。

不要只写伪汇编名称。

---

# Part C：实现 encoder / decoder

实现纯函数风格 API，例如：

```python
encode_qh(qubit: int) -> int
encode_qx(qubit: int) -> int
encode_qcx(control: int, target: int) -> int
encode_qmeas(qubit: int, classical_reg: int) -> int

decode_quantum_instruction(word: int) -> QuantumInstruction
```

具体 API 可调整。

要求：

- 返回真正 32-bit unsigned instruction word；
- encode/decode round-trip；
- 范围检查明确；
- 非法 opcode / funct / reserved bits deterministic fail；
- 数据结构稳定、可测试；
- 不依赖 production L3 parser/codegen helper 来“证明自己正确”。

可提供 mnemonic formatter 方便 demo，但 binary word 才是 source of truth。

---

# Part D：扩展官方模拟器，但不要修改官方文件

实现单独的：

```text
QuantumRISCVEmulator
```

推荐基于官方 `TinyRISCVEmulator` 继承或非常薄的扩展，而不是复制一大份后漂移。

要求：

1. 原来的经典指令仍按官方语义运行；
2. 可以在 program 中执行 Quantum custom instruction；
3. custom instruction 必须走 Part C 的 decoder；
4. decoded command dispatch 到 `QuantumCoprocessor` 接口；
5. emulator 可公开一个稳定的 quantum trace 供测试/演示；
6. measurement 返回值必须能写入规范指定的经典寄存器，从而让后续 `beq/bne` 真正依赖量子测量结果。

建议支持一种不污染官方汇编 parser 的表示方式，例如：

```text
.word 0xXXXXXXXX
```

或等价的明确机制。

如果选择文本 pseudo-mnemonic，也必须最终 encode 成 32-bit word 再 decode/执行，不能绕过 binary encoding 直接调用 handler。

## QuantumCoprocessor

接口应非常小，例如：

```python
apply_gate(...)
measure(...)
```

测试 backend 可以：

- 记录 QH/QX/QCX 的执行顺序；
- 对 measurement 使用预先注入的 deterministic bit；
- 不伪装成真实量子模拟器。

若你发现复用现有 Braket statevector 可以极低成本且不增加正式依赖，也不要在 15A 主动做；本任务只需要证明 ISA / dispatch / hybrid control。

---

# Part E：从现有 quantum_ops 到 custom instructions

增加一个极薄 translator：

```text
L3 quantum_ops subset
      ↓
Quantum RISC-V words
```

只需要支持 SPEC 中明确承诺的 gate subset。

例如 Bell：

```text
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
```

应能得到对应的 custom instruction words。

不要修改 L3 的 `compile_hybrid()` 返回值；Bonus translator 单独调用。

对不支持的 gate 明确报：

```text
unsupported by Quantum RISC-V Bonus ISA
```

不要 silent drop。

---

# Part F：端到端测试

这是 Bonus 得分的关键证据，不要只做 encode 单测。

至少实现三个层次。

## 1. Encoding unit tests

覆盖：

- 每条 instruction encode/decode round-trip；
- 边界 qubit / classical register index；
- 非法 opcode；
- 非法 funct；
- reserved bits；
- 超范围 operand。

## 2. Emulator integration tests

例如：

```text
QH q0
QCX q0,q1
QMEAS q0 -> x10
beq x10, x0, ZERO_PATH
...
```

分别注入 measurement=0 与 measurement=1。

验证：

- quantum command trace 正确；
- measurement 真正写入经典寄存器；
- 后续经典 branch 根据 measurement 走不同路径；
- 普通 RISC-V 指令语义没有被扩展模拟器破坏。

这条测试要清楚体现：

> quantum instruction → measurement → classical control flow

## 3. Existing `quantum_ops` E2E

至少一个 Bell-like demo：

```text
quantum_ops
→ translator
→ 32-bit custom words
→ QuantumRISCVEmulator
→ QuantumCoprocessor trace
```

证明输入到输出全链路可执行。

若 measurement 使用 deterministic backend，文档必须明确：这是 ISA/control-flow 测试 backend，不是真实量子结果。

---

# Part G：评分证据准备

本任务暂时不要修改 `starter_kit/evidence/README.md` 的 checkbox；先把实现做稳。

但最终报告必须给出三项可直接填入 evidence 的路径：

```text
指令编码规格：...
模拟器扩展实现：...
端到端测试命令：...
```

理想情况最终类似：

```text
指令编码规格：starter_kit/bonus/quantum_riscv/SPEC.md
模拟器扩展实现：starter_kit/bonus/quantum_riscv/emulator.py
端到端测试命令：python -m unittest starter_kit.tests.test_quantum_riscv_bonus -v
```

实际路径按实现为准。

---

# Part H：Regression

完成后至少运行：

```text
Bonus 专项 tests
L3 tests
Public L3 evaluator
Starter Kit full tests
git diff --check
```

如果当前环境支持，额外在 Python 3.10 Docker 环境跑 Bonus 专项测试。

确认：

- `submission.yaml` 没有变化；
- `adapter.py` 没有变化；
- `loomq/l3/**` 没有变化；
- `riscv_emulator.py` 没有变化；
- L1/L2/L3 regression 均无新增失败；
- 无 secret、本地绝对路径、临时文件。

---

# 不要做

本任务不要：

- 修改 L3 正式编译结果为 custom instruction；
- 修改官方 `riscv_emulator.py`；
- 把 Bonus 接进 evaluator；
- 做完整 RV32I；
- 做 QEMU / LLVM backend / FPGA；
- 做真实量子硬件 driver；
- 做完整量子 statevector simulator；
- 为 12 个 L1 gate 强行设计复杂参数编码；
- 做 Web UI；
- 修改 evidence checkbox；
- commit / push。

---

# 自我 Review

完成实现后自行进行一次结构化 review，重点检查：

1. Binary encoding 是否真实存在，还是只有 pseudo-mnemonic；
2. emulator 是否真的 decode binary word，而不是绕过 encoder；
3. measurement 是否真正能影响后续 classical branch；
4. QuantumCoprocessor 是否明确是 dispatch interface，而非伪造量子物理；
5. 是否无意修改了正式评分路径；
6. SPEC 与代码 bit layout 是否逐位一致；
7. E2E test 是否真的从输入走到最终执行，不是几个互不相关的单测；
8. 三项 Bonus 证据是否已经齐全。

确认问题直接最小修复并补测试，再统一汇报。

---

# 最终汇报格式

一次性汇报，不要中途等待确认。

## 1. ISA design

说明：

- custom opcode 选择与依据；
- 32-bit layout；
- 支持的 quantum instruction；
- measurement / classical register 语义；
- 明确未支持什么。

## 2. Files

列出新增文件与职责。

## 3. E2E flow

用一条具体程序说明：

```text
quantum_ops
→ words
→ decode
→ quantum coprocessor
→ measurement
→ classical branch
```

并给实际输出摘要。

## 4. Tests

列出：

- encoding tests；
- emulator tests；
- E2E tests；
- L3 regression；
- full regression；
- Docker（若执行）；
- git diff --check。

## 5. Isolation check

明确回答以下文件是否 untouched：

```text
adapter.py
loomq/l3/**
riscv_emulator.py
submission.yaml
```

## 6. Bonus evidence paths

给出可以直接填入：

```text
指令编码规格：
模拟器扩展实现：
端到端测试命令：
```

## 7. Final recommendation

只能输出其中一个：

```text
READY_FOR_QUANTUM_RISCV_BONUS_REVIEW
NOT_READY_FOR_QUANTUM_RISCV_BONUS_REVIEW
```

---

# 验收标准

Task 15A 完成要求：

1. 有真实 32-bit custom opcode 编码规格；
2. 有可测试 encoder/decoder；
3. 有独立扩展模拟器；
4. custom word 真正经过 decode 后 dispatch；
5. measurement 可以影响后续经典 branch；
6. 有至少一条 `quantum_ops -> encoded words -> emulator` E2E；
7. SPEC 与实现一致；
8. Bonus 三项官方证据路径齐全；
9. 不影响 L1/L2/L3 正式评分路径；
10. 回归通过；
11. 不 commit、不 push，等待 review。