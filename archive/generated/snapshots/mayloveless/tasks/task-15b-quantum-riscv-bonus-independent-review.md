# Task 15B：Quantum RISC-V Bonus 独立审计 + 得分收口

## 推荐模型

- 推荐模型：GPT-5.6 Sol（或 Codex 中最新可用 Sol）
- Reasoning：High

## 背景

Task 15A 已完成一个隔离的 Quantum RISC-V Bonus proof-of-concept，当前实现包含：

- `starter_kit/bonus/quantum_riscv/SPEC.md`
- `starter_kit/bonus/quantum_riscv/encoding.py`
- `starter_kit/bonus/quantum_riscv/emulator.py`
- `starter_kit/bonus/quantum_riscv/translator.py`
- `starter_kit/tests/test_quantum_riscv_bonus.py`

Task 15A 报告称：

- 使用 RISC-V `custom-0` opcode `0x0B`；
- 定义 QH / QX / QCX / QMEAS 四条 32-bit custom instruction；
- QMEAS 可写回经典寄存器并驱动后续 beq/bne；
- 通过独立 `QuantumRISCVEmulator` + `QuantumCoprocessor` 做 dispatch；
- 13/13 Bonus tests、L3/public/full regression 均通过；
- 不修改 L1/L2/L3 正式评分路径。

本任务必须作为**新的独立 reviewer**执行。不要默认 Task 15A 的设计一定满足 Bonus 人工评分条件。

---

# 官方 Bonus 目标

重新阅读仓库最新：

```text
problem_statement.md
README.md
starter_kit/evidence/README.md
starter_kit/riscv_emulator.py
```

官方 Bonus 为“自定义量子 RISC-V 扩展指令”，最高 +8；重点核对三项是否真正齐全：

1. 指令编码规格文档；
2. 对官方模拟器的扩展实现；
3. 可运行端到端测试。

特别注意题面中“fork `riscv_emulator.py` 增加指令支持”的措辞。

---

# Part A：先给出评分契约判断

先独立回答以下问题，再改代码：

1. 当前 `SPEC.md` 是否足以构成真实、可审查的 custom opcode encoding spec？
2. `QuantumRISCVEmulator(TinyRISCVEmulator)` 的继承式扩展，是否足以合理满足“对官方模拟器的扩展实现 / fork riscv_emulator.py 增加指令支持”的官方要求？
3. 如果存在人工评分歧义，最小、最安全的改法是什么？
4. 当前四条指令 QH/QX/QCX/QMEAS 是否已经足以展示“量子 RISC-V custom instruction”，还是官方材料暗示必须覆盖更多量子门？不要自行扩大范围，必须以官方文字为准。
5. 当前 E2E 是否真的证明：binary custom word → decoder → quantum dispatch → measurement writeback → 官方经典 control flow。

将无法从官方文字确定的内容明确标为 `SPEC_AMBIGUITY`，不要脑补。

---

# Part B：ISA / bit-level 独立审计

逐项检查：

- `custom-0` / `0x0B` 选择是否符合 RISC-V 官方 opcode map；
- 32-bit 字段布局是否自洽；
- encoder / decoder 是否 bit-exact 互逆；
- reserved bits 是否严格校验；
- opcode/funct3/funct7/q0/q1/rd 范围是否正确；
- QH/QX 未使用字段必须为 0；
- QCX control != target；
- QMEAS 禁止写 x0；
- unsigned 32-bit 边界；
- decoder 不应把非 custom-0 普通 RISC-V word 误识别成量子指令；
- formatter / docs 示例与真正编码一致。

不要只依赖 production encoder 生成测试输入。至少手算 / 独立构造一组 bit pattern，并核对字段。

---

# Part C：模拟器扩展正确性

审计 `QuantumRISCVEmulator` 与官方 `TinyRISCVEmulator` 的关系，重点检查：

- 是否尽量复用官方 parser / register / label / max_steps 语义；
- 为支持 custom instruction 是否复制了官方经典执行逻辑，若复制，是否已经出现或容易出现行为漂移；
- `.word 0xXXXXXXXX` 的装载和执行是否真实经过 decoder，而不是 pseudo-instruction shortcut；
- 普通 `li/add/sub/addi/beq/bne/j` 是否与官方模拟器逐项同义；
- x0 恒零语义；
- PC / branch / label 行为；
- max_steps；
- load_program 后重复执行 / 重复加载的状态语义；
- malformed `.word`、unknown opcode、reserved encoding 的 fail-fast；
- coprocessor 异常是否明确暴露，不被吞掉。

### 必做 differential

针对**纯经典程序**生成/准备一组 deterministic cases，同时在：

```text
TinyRISCVEmulator
QuantumRISCVEmulator
```

执行，比较最终寄存器状态。至少覆盖：

- li/add/sub/addi；
- beq/bne 两个方向；
- j；
- 多 label / sequential branch；
- x0；
- 负数；
- max_steps / loop error。

如果发现继承式扩展为了 custom dispatch 被迫复制大量官方经典 execute 逻辑，评估是否存在一个**更小、更明显符合官方“fork/扩展模拟器”要求、同时不污染正式评分路径**的实现方式。

只在确有价值时最小修改，不为架构洁癖重写。

---

# Part D：Quantum E2E adversarial tests

至少补/确认这些 case：

- 每条 custom instruction 的固定已知 32-bit word；
- encode → decode round trip；
- 非法 funct/reserved bits；
- QH/QX/QCX dispatch 顺序；
- 多次 QMEAS 按顺序消费 measurement；
- QMEAS=0 / 1 分别改变后续 beq/bne；
- measurement 写回 x10 与 L3 c[0] contract 对齐；
- quantum op 位于 classical branch 前后时，程序顺序可解释；
- translator 对 unsupported gate 必须明确失败，不能 silent drop；
- translator 保持 quantum_ops 顺序；
- c[21] 边界与 c[22] fail-fast；
- q[31] 边界与越界失败；
- 同一 program 重复运行是否 deterministic（TraceCoprocessor 注入相同 measurement 时）。

不要引入 statevector 模拟器来“证明量子物理”。Bonus 核心是 ISA 编码和经典-量子 dispatch/control-flow，不需要伪装真实量子硬件。

---

# Part E：Bonus 得分材料收口

当前实现只有代码和 SPEC 还不够，最终人工评分入口必须清楚。

如果技术实现通过审计，请**最小更新**：

```text
starter_kit/evidence/README.md
```

只填写/勾选“自定义量子 RISC-V Bonus”相关部分，不动其他尚未最终确认的人工评分项。

必须给出：

```text
指令编码规格：starter_kit/bonus/quantum_riscv/SPEC.md
模拟器扩展实现：[实际最终路径]
端到端测试命令：python -m unittest starter_kit.tests.test_quantum_riscv_bonus -v
```

如最终认为继承式 `emulator.py` 已足够满足官方要求，则在 SPEC/evidence 中用一两句话明确它如何扩展官方 TinyRISCVEmulator。

如认为“fork riscv_emulator.py”的字面评分风险真实存在，则做**最小的显式派生/扩展方案**，仍放在 Bonus 目录，绝不修改正式 `starter_kit/riscv_emulator.py`，并在文件头注明来源/扩展点，确保评委一眼能看懂。

不要为了 Bonus 修改：

```text
starter_kit/adapter.py
starter_kit/loomq/l3/**
starter_kit/riscv_emulator.py
starter_kit/submission.yaml
```

除非官方最新材料明确要求必须直接修改根 `riscv_emulator.py`，若出现这种情况先在报告中标记 BLOCKER，不要擅自污染 L3 正式路径。

---

# Part F：回归

完成确认问题的最小修复后运行：

```text
Bonus 专项测试
L3 专项测试
Public L3 evaluator
Starter Kit full tests
Docker Python 3.10 Bonus tests
git diff --check
```

同时检查：

- 无 secret；
- 无本地绝对路径；
- 无临时产物；
- 无额外依赖；
- L1/L2/L3 正式路径无语义变化。

---

# 不要做

- 不扩展成完整 12 门 Quantum ISA，除非官方 Bonus 明确要求；
- 不做 QEMU / LLVM / FPGA；
- 不接真实量子硬件；
- 不写 statevector simulator；
- 不修改 L3 compiler 来生成 Bonus ISA；
- 不把 Bonus 接进 `adapter.compile_hybrid()`；
- 不做 Web；
- 不大规模重构；
- 不 commit、不 push。

---

# 最终报告

一次性汇报：

## 1. Scoring-contract verdict

明确说明三项 Bonus 要求是否满足，以及“继承式模拟器扩展 vs 官方 fork 措辞”的结论。

## 2. Findings

按 Critical / High / Medium / Low 列出；无则写 none。

## 3. ISA evidence

列出 custom opcode、field layout、支持指令及至少一个独立核验的 binary/hex 示例。

## 4. Emulator evidence

说明如何扩展官方 emulator、纯经典 differential 结果、measurement/control-flow E2E 结果。

## 5. Evidence package

确认 `starter_kit/evidence/README.md` 中 Bonus 三项是否已经可直接交给评委核验。

## 6. Regression

列出全部实际测试结果。

## 7. Final recommendation

只能输出一个：

```text
READY_TO_CLAIM_QUANTUM_RISCV_BONUS
NOT_READY_TO_CLAIM_QUANTUM_RISCV_BONUS
```

发现确定问题可直接做最小修复并补测试；不要中途等待确认。