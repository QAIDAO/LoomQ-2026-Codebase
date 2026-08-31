# Task 15A — L1 客观 35 分：三平台 Hidden-like + Target-Native 语义审计

## 背景

产品主线（Learn / Experiments / Explorer / Repair / Backend）已经基本完成。现在进入客观评分加固阶段。

L1 正式语义等价评分为 35 分，是当前最值得优先保护的客观分。官方会使用 8 类电路风格：

- Bell
- GHZ-3
- GHZ-5
- QFT-4
- Grover-3
- Random-Circuit × 3

并检查目标 IR 的真实语义，而不仅是 LoomQ 自己的 `run()` 是否能返回合理 counts。

当前已有：

- SpinQ / OriginQ / Braket 三平台 Adapter / Serializer / Runner；
- 官方 12 门白名单；
- 公开 Bell / GHZ-3 三平台通过记录；
- `tests/test_l1_hidden_like.py` 中 SpinQ + Braket 的 GHZ-5 / QFT round-trip / Grover / Random U+U^-1 / 多寄存器测量回归；
- OriginQ 公开电路与专项 runner/serializer 测试。

当前主要盲区：

1. OriginQ 没有进入与 SpinQ / Braket 同强度的 hidden-like 组合回归；
2. hidden-like 主要验证 `adapter.run()`，但正式评分还会关心 `adapter.transpile()` 返回的 target-native IR；
3. target-native 产物应尽量交给对应厂商 SDK / parser 独立解析和执行，避免 LoomQ Parser / Serializer / 自测共享同一错误；
4. 需要几组有解析答案的非对称 / 相位敏感 case，避免 Bell/GHZ 或 U+U^-1 把方向、位序、参数符号错误掩盖掉。

本 Task 以**审计和补测试为主**。没有真实失败，不重构 production。

---

## 目标

完成下面四层验证：

```text
A. 三平台 adapter.run hidden-like
B. 三平台 adapter.transpile target-native 直接验证
C. 解析答案明确的独立 Oracle case
D. 8192 shots scoring-like 总回归报告
```

原则：

> 先证明哪里会失败，再做最小修复。

禁止为了“更保险”提前重写 Parser / IR / Serializer / Runner。

---

# A. 把现有 Hidden-like 扩到 OriginQ

优先复用 `starter_kit/tests/test_l1_hidden_like.py` 的现有生成器，不重新复制一套电路定义。

当前 hidden-like integration readiness 主要围绕 SpinQ + Braket。调整测试组织，使三个平台能**分别检测可用性、分别执行**：

```text
spinq
originq
braket
```

不要因为某一个 SDK 不可用就把另外两个一起 skip。

至少让以下 case 都通过：

1. GHZ-5；
2. QFT-4 + inverse QFT round-trip；
3. Grover-3；
4. Random U + U^-1 × 3；
5. 多量子寄存器 / 多经典寄存器；
6. 交叉 measurement；
7. 未测量经典位保持 0；
8. 参数门 + `ccx` 的组合。

全部必须通过正式入口：

```python
adapter.run(source_qasm, target, shots)
```

不得绕过 Adapter 直接调用生产 Runner 来冒充端到端通过。

### 测试组织要求

不要把当前测试简单改成“必须三 SDK 都装了才跑”。建议：

- generator / pure tests 永远执行；
- 每个平台单独 `skipUnless` / capability detection；
- 能装哪个 SDK 就验证哪个；
- 最终 Docker / scoring-like audit 时三个平台必须全部实际执行。

---

# B. 直接验证 `adapter.transpile()` 的目标 IR

这是本 Task 的最高优先级。

正式目标 IR 契约见：

```text
starter_kit/target_ir_contract.md
```

对同一组代表性 source QASM：

```python
native = adapter.transpile(source_qasm, target)
```

然后**直接把 `native` 交给目标平台工具链**，不要再次调用 `adapter.run(source_qasm, target, ...)` 来证明 transpile 正确。

## 1. Braket

`adapter.transpile(..., "braket")` 返回公开 OpenQASM 3。

直接使用 pinned Braket SDK：

```text
braket.ir.openqasm.Program
Braket LocalSimulator
```

解析并执行这个返回字符串。

禁止：

```text
native → LoomQ parser → LoomQ serializer → Braket
```

那不能证明公开 target-native artifact 自身可被 Braket 接受。

## 2. OriginQ

`adapter.transpile(..., "originq")` 返回 OriginIR。

直接把该文本送入 pyQPanda 已使用的官方转换路径：

```text
convert_originir_to_qprog
→ CPUQVM
```

可以复用 / 提取当前 OriginQ worker 中的底层执行 helper，但输入必须是 `adapter.transpile()` 的返回值，不能重新从 source Circuit 调 `serialize_originq()`。

验证：

- pyQPanda 能真实 parse；
- 能真实 execute；
- counts / distribution 与预期语义一致。

## 3. SpinQ

`adapter.transpile(..., "spinq")` 返回完整 OpenQASM 2.0。

优先调查当前 pinned SpinQit 是否提供可直接读取 / 导入 QASM 2.0 的真实 API；如果有，必须使用它对 `adapter.transpile()` 返回值做独立 parse / execute。

如果 pinned SpinQit **客观上没有 QASM import API**：

- 不要为了这一个测试引入大型新依赖；
- 至少证明 target artifact 是完整 QASM2、可以被现有 QASM Parser 重新解析并通过真实 SpinQit simulator 执行；
- 在测试 / 报告中明确标注 `SpinQ native validation` 的独立性弱于 OriginQ / Braket，不能假装用了不存在的 vendor parser。

无论采用哪条路径，都禁止针对测试 case 写专用转换分支。

---

# C. 增加独立 Oracle case

现有 Bell/GHZ 和 U+U^-1 很重要，但不足以暴露所有“双方一起错”的情况。

新增少量**手算结果明确**的 case，直接针对以下错误类型：

```text
bit order
control / target 顺序
RY 参数符号
RZ / phase 参数符号
CU1 控制相位
SWAP
CCX
多 classical register measurement mapping
```

这些 case 应尽量是确定性输出，避免依赖另一套 LoomQ 模拟器生成 expected。

建议至少包含以下思想，具体 QASM 可由实现者在测试中清晰写出并注释数学理由：

### 1. CX 方向

准备控制位为 1、目标位为 0，执行 CX，测量应得到唯一确定结果。

如果 control / target 被交换，测试必须失败。

### 2. SWAP

准备非对称基态（例如一个 qubit 为 1、另一个为 0），SWAP 后测量。

### 3. CCX

两个 control 都为 1、target 为 0，执行 CCX 后应得到唯一确定结果。

### 4. RY 符号

例如构造：

```text
|0>
→ ry(pi/2)
→ h
→ measure
```

使 `+pi/2` 与 `-pi/2` 导向不同的确定性结果，专门防参数符号翻转。

测试前先人工 / 独立数学确认 expected，不以 production simulator 的输出作为 expected。

### 5. RZ 相对相位符号

构造会把相位重新转回可测概率的干涉电路，例如通过 `H + RZ + S/SDG + H` 组合，使 `+theta` 与 `-theta` 最终可区分。

不要写只在 Z-basis 下永远看不出正负号的无效相位测试。

### 6. CU1 相位

让 control 固定为 1，target 进入叠加，使用 `cu1(theta)` 后再用已知 phase gate + H 把相位差转成确定测量结果。

必须能发现：

- control / target 错误；
- 参数符号 / 数值错误；
- CU1 被错误当成普通单比特 phase。

### 7. 多经典寄存器映射

使用非对称量子基态 + 交叉写入经典位，手工给出最终完整 key。

目标是直接攻击：

```text
c[n-1]...c[0]
全局 classical bit flatten 顺序
未测量 classical bit = 0
```

### 断言要求

这些解析 Oracle case：

- 应同时走 `adapter.run()` 三平台；
- 关键代表 case 同时走 target-native direct execution；
- expected 写成测试中的明确常量，并用注释说明来源；
- 不调用 production simulator 计算 expected。

---

# D. Scoring-like 8192 shots 总回归

新增一个**可重复执行的 audit / report 脚本**或测试入口，用于接近正式评分形态地验证当前源码。

推荐：

```text
starter_kit/scripts/audit_l1_scoring.py
```

也可以使用现有测试工具，只要最终能输出结构化报告。

至少包含：

```text
source_sha
case_id
target
path = run | transpile_native
shots
fidelity / deterministic_probability
status
elapsed_seconds
sdk/version（能稳定读取则记录）
```

正式 scoring-like run：

```text
shots = 8192
```

至少覆盖：

- GHZ-5；
- QFT round-trip；
- Grover-3；
- Random × 3；
- 独立 Oracle case 的代表子集；
- 三平台。

### 报告原则

本 Task 可以生成本地报告，但不要把它当最终 submission evidence。

最终 evidence 必须在**代码冻结 SHA**后重新生成。

当前报告若提交仓库，应明确：

> audit report for this exact source SHA; later executable changes invalidate it.

---

# E. 失败后的修复规则

只有真实测试失败，才允许改 production。

定位顺序：

```text
测试 expected / 电路本身
→ QASM Parser / expression
→ IR operand / register flatten
→ measurement mapping / bit order
→ serializer
→ vendor-native syntax
→ runner / SDK normalization
```

修复必须落在最小正确层。

允许：

- 通用 Parser / expression bug；
- 通用 operand / parameter / bit-order bug；
- serializer 的 target-native 合同错误；
- vendor SDK 兼容问题；
- runner 的真实结果归一化错误。

禁止：

- 按 Bell / GHZ / QFT / Grover / seed 写分支；
- 固定 counts；
- 一个 backend 结果冒充另一个；
- 修改 evaluator 来让错误实现通过；
- 为了 audit 添加新的大型量子框架；
- 顺手改 L2 / L3 / Web；
- 没有失败证据就重构三平台 adapter。

---

# F. 回归与验收

至少运行：

```bash
cd starter_kit
python -m unittest discover -s tests -v
python -m unittest tests.test_l1_hidden_like -v
python evaluator.py --level l1 --target spinq,originq,braket
```

如新增 target-native test 模块，也单独运行。

最终还应在三 SDK 都存在的干净 Docker 中运行：

```text
all L1 tests
hidden-like
native validation
8192-shots scoring-like audit
public evaluator
```

### 完成汇报

只需汇报：

1. OriginQ 新增了哪些 hidden-like 覆盖；
2. 三种 `transpile()` artifact 分别如何独立验证；
3. 独立 Oracle case 覆盖了哪些错误类型；
4. 是否发现 production bug，若有修在哪里；
5. 三平台 scoring-like 结果；
6. 哪些测试因本机 SDK 环境未执行；
7. 仍然存在的 L1 客观评分风险。

没有 CI / Docker / SDK 的真实执行证据时，不得写“全部通过”。

完成后停止，让我 review；不要继续做 L2、L3 或 submission。