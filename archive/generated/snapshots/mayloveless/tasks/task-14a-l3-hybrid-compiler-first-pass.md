# Task 14A：L3 Hybrid-QASM Compiler 第一版 + 随机回归

## 背景

L1 / L2 主线已经稳定，当前另有 Web Quantum DevTools 工作继续推进。

本任务在独立分支 `feat/l3` 上并行实现 L3，目标是尽量减少人工 review 次数：**一次完成 L3 的核心解析、编译、Adapter 接入、公开评测与 hidden-like 随机回归**。

L3 官方接口：

```python
def compile_hybrid(hybrid_qasm_str: str) -> Tuple[list, str]:
    ...
```

输入 Hybrid-QASM，输出：

1. `quantum_ops`：按原顺序剥离出的量子门 / 测量指令列表；
2. `assembly`：实现 `classical { ... }` 经典逻辑的 RISC-V 汇编文本。

官方 RISC-V Emulator 只支持：

```text
li, add, sub, addi, beq, bne, j
```

寄存器映射：

```text
r1..r9  -> x1..x9
c[k]    -> x10+k
x0      -> 常量 0
```

官方隐藏评测会随机生成符合文法的程序并注入不同测量值，验证寄存器终态，因此禁止任何公开样例特判 / 关键词硬编码。

---

## 本任务目标

完成一套真正的 deterministic compiler pipeline：

```text
Hybrid-QASM source
  ↓
Hybrid lexer / parser
  ↓
AST
  ├─ quantum operations extraction
  └─ classical block
         ↓
      RISC-V codegen
         ↓
TinyRISCVEmulator hidden-like regression
```

本任务完成后，L3 **代码应基本可用，但暂时不要把 `submission.yaml` 的 `levels.l3` 改为 true**。是否正式开启留到下一次独立审计 Task。

---

# 1. 隔离原则

L3 必须尽量独立于已经冻结的 L1 / L2。

建议新增：

```text
starter_kit/loomq/l3/
  __init__.py
  ast.py
  lexer.py        # 如实际实现不需要单独 lexer，可合并
  parser.py
  compiler.py
```

文件结构可以根据现有工程风格微调，但要求：

- 不修改现有 L1 `parse_qasm()` 的语义；
- 不修改 L2 Agent / Prompt / semantic verifier；
- 不改 L1 serializer / runner；
- 不新增网络调用；
- 不使用 LLM 参与 L3 编译；
- 除 `adapter.compile_hybrid()` 的最小接入外，避免公共模块耦合；
- 不改 `submission.yaml` 的 `l3:false`；
- 不改 evidence / Web / CLI。

如果为了 L3 需要修改 L1/L2 核心逻辑，先停止并在汇报里解释，不要自行扩范围。

---

# 2. Hybrid-QASM 文法

至少完整支持官方声明的经典子语言：

- 整数字面量（包含 0、正数、负数）；
- `r1..r9`；
- `c[k]`；
- `+`、`-`；
- `==`、`!=`；
- assignment；
- `if / else`；
- 顺序 statements。

官方示例：

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) {
    r1 = 100;
  } else {
    r1 = 10;
  }
  r1 = r1 + 5;
}
cx q[0], q[1];
```

## 建议 AST

不要使用字符串正则直接完成整套编译。

至少建立可测试的结构，例如：

```text
Program
Assignment
IfElse
IntegerLiteral
RegisterRef
ClassicalBitRef
BinaryExpr(+/-)
Comparison(==/!=)
```

具体 class / dataclass 命名可调整。

Parser 应允许正常空白、换行、注释变化；不要依赖官方样例固定排版。

### 防 hidden case 的合理增强

在不显著增加复杂度的前提下：

- expression 使用真正的 parser，而不是只支持 `r1 = r1 + 5` 单一形态；
- `+/-` 支持 register / integer / `c[k]` 的合理组合；
- condition 支持左右 expression + `==/!=`；
- `if/else` block 使用递归 statement parser，从结构上允许 nested `if/else`，即使公开样例没有出现；
- sequential assignments 必须遵循更新后的寄存器值。

不要自行发明 `* / && || while` 等官方未声明语法。

---

# 3. Quantum operations 提取

`compile_hybrid()` 返回的第一个值必须是 `list[str]`。

要求：

- 按 source 中出现顺序返回所有顶层量子 gate 与 `measure` 指令；
- `classical { ... }` 整块不进入 `quantum_ops`；
- `OPENQASM` / `include` / `qreg` / `creg` 声明不进入 `quantum_ops`；
- classical block 前后的量子操作都必须保留；
- 输出字符串采用稳定 canonical formatting；
- 不要丢失参数 gate、多个 qubit operand 或 measurement mapping。

例如上方示例应等价返回：

```python
[
    "h q[0];",
    "measure q[0] -> c[0];",
    "cx q[0], q[1];",
]
```

无需为 L3 再实现一套量子 gate semantics；这里只负责可靠剥离。

---

# 4. RISC-V Codegen

只生成官方 Emulator 支持的指令：

```text
li, add, sub, addi, beq, bne, j
```

不要输出 pseudo instruction / 其他 RISC-V 指令。

## 必须正确支持

例如：

```text
r1 = 7
r1 = r2
r1 = r2 + r3
r1 = r2 - r3
r1 = r2 + 5
r1 = r2 - 5
r1 = 5 + r2
r1 = 5 - r2
r1 = c[0] + 1
```

以及：

```text
if (c[0] == 1) { ... } else { ... }
if (r1 != r2) { ... } else { ... }
```

更复杂的合法 `+/-` expression 应通过递归/临时寄存器正确求值，而不是靠字符串模板。

## Labels

- 每个 if/else 使用唯一、确定性的 label；
- nested / sequential if 不得 label 冲突；
- assembly 同输入应稳定 deterministic，方便测试。

## Scratch registers

`r1..r9` 与被使用的 `c[k]` 寄存器属于用户语义，不得被临时计算破坏。

如果需要 scratch：

- 实现明确的 scratch allocation；
- 排除 `x1..x9`；
- 排除当前程序所有 `c[k] -> x10+k`；
- 优先从其余通用寄存器安全分配；
- 临时值不得改变最终用户可观察寄存器语义；
- 若合法输入确实没有足够 scratch，抛出清晰 deterministic error，不要静默覆盖用户寄存器。

能用 `addi` / `x0` 避免 scratch 时优先避免。

---

# 5. Adapter 接入

实现当前：

```python
def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    ...
```

要求：

- 只做薄路由；
- 真实逻辑在 `loomq/l3`；
- 签名完全不变；
- 返回 `(list[str], str)`；
- malformed Hybrid-QASM 给出可理解的 deterministic exception；
- 不打印 stdout/stderr。

不要在本任务开启 `submission.yaml -> l3:true`。

---

# 6. 测试：这是本任务的重点

不要只为了通过官方 public sample 写实现。

## A. Parser / compiler 单元测试

至少覆盖：

- literal assignment；
- register copy；
- `+/-` 各种 operand combination；
- negative integer；
- sequential assignment；
- `==` / `!=`；
- if true / false；
- nested if（若 parser 按上方建议支持）；
- multiple sequential if；
- multiple `c[k]`；
- quantum ops 位于 classical block 前后；
- 注释 / whitespace / 单行与多行 block；
- malformed syntax；
- register range `r1..r9`；
- scratch 不覆盖用户映射。

## B. Public evaluator

必须通过：

```bash
python starter_kit/evaluator.py --level l3
```

public branch 中：

```text
c[0]=0 -> x1=3
c[0]=1 -> x1=7
```

都必须正确。

## C. Hidden-like randomized differential testing

这是 14A 的核心完成条件。

请实现**测试侧**的 deterministic random program generator + AST/reference interpreter（不要把 reference interpreter 放生产编译路径）。

固定多个 seeds，随机生成官方文法内的 classical programs，例如组合：

- 1~9 个 r registers；
- 多个 c bits；
- literal / register / c-bit operands；
- + / -；
- == / !=；
- sequential assignment；
- if/else；
- nested if（如果支持）；
- 不同 measurement input combinations。

对每个随机程序：

1. reference interpreter 直接执行 AST，得到期望 `r1..r9`；
2. compiler 生成 assembly；
3. `TinyRISCVEmulator` 注入同一组 `x10+k` measurement values；
4. 执行 assembly；
5. 比较所有 `x1..x9` 与 reference interpreter；
6. 100% 一致才通过。

建议至少覆盖数百组 `(program, measurement input)` 组合；数量根据运行时间合理控制，不要做无意义的超大测试。

测试生成器必须固定 seed、可复现、失败时打印最小必要 case/source/seed，方便下一轮复现。

## D. 回归 L1/L2

在当前分支可运行的环境里跑现有测试，确认 L3 接入没有影响已有逻辑。

至少报告：

```text
pytest / 当前项目标准测试命令
python starter_kit/evaluator.py --level l3
```

若 L1/L2 需要外部 SDK/LLM 导致部分测试无法运行，明确列出原因，不要为了 L3 修改它们。

---

# 7. 自我 Review

因为本任务刻意减少人工 review 次数，请完成代码后自己做一次结构化 review，再汇报。

至少检查：

1. 是否存在 regex / 字符串特判公开 sample；
2. hidden random grammar 是否可能绕过 parser；
3. labels 是否会冲突；
4. scratch register 是否覆盖 `r1..r9` / `c[k]`；
5. sequential assignments 是否读到最新值；
6. branch 跳转是否正确落到 else/end；
7. `!=` 是否真正编译正确；
8. negative integer / subtraction 是否有方向错误；
9. quantum ops extraction 是否跨 classical block 保序；
10. `compile_hybrid()` 是否与 L1/L2 完全隔离。

发现问题直接修复并补 regression test，不需要每个小问题停下来询问。

---

# 8. 本任务明确不做

- 不做 Web Quantum DevTools；
- 不修改 L2 Agent / Debug Trace；
- 不改 L1 parser / serializer / runner 语义；
- 不接真实 RISC-V / QEMU；
- 不做 L3 UI；
- 不做额外量子模拟；
- 不开启 `submission.yaml` 的 `l3:true`；
- 不写最终 evidence；
- 不 commit、不 push。

---

# 9. 完成汇报格式

完成后请一次性汇报：

1. **架构**：新增文件与 pipeline；
2. **支持文法**：实际支持范围，特别说明是否支持 nested if / 复杂 expression；
3. **quantum_ops contract**：如何提取与 canonicalize；
4. **RISC-V codegen**：register mapping / labels / scratch 策略；
5. **测试结果**：unit tests、public evaluator、随机 differential test 的 program/input 数量；
6. **L1/L2 regression**；
7. **自我 review 发现并修复的问题**；
8. **剩余风险**：只列真实风险，不做泛泛而谈；
9. `git diff --check` 结果；
10. `git status --short`。

如果 14A 全部通过，停止，不继续自行开启 L3。下一步由人工 review 后再决定 Task 14B。