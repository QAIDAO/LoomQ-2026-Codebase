# Task 14B：L3 独立破坏性审计 + 隐藏测试加固

## 背景

Task 14A 已在独立分支 `feat/l3` 上完成第一版 L3 Hybrid-QASM Compiler，并报告：

- 独立 Lexer / Parser / AST / RISC-V codegen；
- `adapter.compile_hybrid()` 薄接线；
- public L3 evaluator PASS；
- 13/13 L3 tests PASS；
- 5 个固定 seed、120 个随机程序、930 组 measurement 输入 differential test 全通过；
- full tests 234 passed / 46 skipped；
- 已自行修复字符串未闭合、临时寄存器覆盖、assignment scratch、零比较、顶层声明校验等问题；
- 当前 `submission.yaml` 仍为 `l3:false`。

这些只是**待审计的实现声明，不是事实来源**。

本任务必须由新的 Codex thread 执行。你的角色不是继续实现 14A，而是：

> **官方 hidden-test 设计者 + 编译器 reviewer。目标是尽力把现有实现弄坏。**

不要重复做一遍“代码存在、公开测试能过”的基础检查。优先寻找那些 **14A 自测很容易和 production 实现共享同一种错误假设**、但正式随机评测可能暴露的问题。

官方题面 / Starter Kit 是唯一 source of truth。

---

# 0. 先重新建立官方契约

至少独立阅读：

```text
problem_statement.md
starter_kit/README.md
starter_kit/evaluator.py
starter_kit/riscv_emulator.py
starter_kit/adapter.py
starter_kit/loomq/l3/**
starter_kit/tests/test_l3_hybrid.py
```

不要把 Task 14A/14B 文档当规则。

先用自己的话明确：

- `compile_hybrid(hybrid_qasm_str) -> Tuple[list, str]` 的真实返回契约；
- `quantum_ops` 到底应保留什么、排除什么、顺序要求是什么；
- classical mini grammar **明确要求**什么；
- 哪些能力只是当前实现扩展，并非官方要求；
- `r1..r9 -> x1..x9`、`c[k] -> x10+k`；
- TinyRISCVEmulator 的真实寄存器和指令限制；
- hidden evaluator 最可能怎样随机生成和验证。

如果规则存在歧义，必须单独列为 `SPEC_AMBIGUITY`，不要擅自把自己的解释当官方事实。

---

# 1. 本轮最高优先级攻击面

## A. c[k] / scratch 寄存器空间

14A 报告当前策略：

- `c[k] -> x10+k`；
- scratch 从 `x31` 向下分配；
- 排除 x1..x9 与所有程序引用的 measured registers；
- 当前明确风险：只能表示到 `c[21]`，更深表达式可能耗尽 scratch。

请不要只确认“会报错”。要从官方题面与 Emulator 推导：

1. hidden generator 是否可能合法生成 `c[22+]`；
2. 如果题面没规定 creg 上限，而 Emulator 只有 x0..x31，这是规则本身的隐含上限还是实现缺陷；
3. scratch 分配是否在高 c 索引、多 measured bits、nested expression 下错误覆盖输入；
4. 是否存在本来可以合法编译、却因为不必要 scratch pressure 被拒绝的官方语法程序。

如果无法从官方规则证明 `c[22+]` 是必须支持的，不要为了猜测重写架构；但要给出明确风险结论。

## B. 表达式语义：不要让 parser 和 reference 共享同一个误解

重点确认官方 mini grammar 对以下内容的真实语义：

```text
+
-
==
!=
括号
负整数 / unary minus
register / measured bit / integer
```

主动构造能区分错误 precedence / associativity 的程序，例如等价形态：

```text
r1 = 10 - 3 - 2;
r1 = 10 - (3 - 2);
r1 = -3 + 5;
r1 = r2 - (r3 - 4);
if ((r1 - 1) != (c[0] + 2)) { ... }
```

但：**只有官方文法允许的形态才作为 correctness gate。**

如果当前实现支持了题面之外的复杂 condition/括号，只记录为扩展能力，不得因为扩展边缘行为失败就大改生产代码。

## C. quantum_ops 提取与 canonicalization

14A 报告会排除 header/declaration/classical block，并对量子操作做空白 canonicalization。

这里要做语义攻击，而不是只比字符串：

- classical block 前后的 gate / measurement 是否严格保序；
- 参数表达式、负数、小数、`pi` 相关文本若属于现有合法 QASM，canonicalization 是否改变含义；
- 逗号、下标、measurement mapping 是否被错误重写；
- `//` / `/* */` 注释中的 `{ } ; classical` 是否扰乱 block 边界；
- 字符串 `include "qelib1.inc"` 内字符是否扰乱扫描；
- 多字符 gate / operand 不应被错误切分；
- declarations/header 不应进入 quantum_ops。

如果官方只要求“量子门/测量指令列表”，不要为了保留源文件格式做复杂 formatter；正确语义和顺序优先。

## D. Differential test 是否真正独立

14A 声称测试侧有独立 AST/reference interpreter。请检查这种“独立”是否真实：

- expected 不能调用 production compiler/codegen helper；
- expected 最好来自**随机模型本身**或独立 reference evaluator，而不是 production parser 解析出的同一 AST；
- 若 generator → source → production parser/codegen 与 generator model → reference interpreter 对比，这属于较强 differential test；
- 若两边共享 parser/AST 构造逻辑，指出共同失效风险并改进测试。

本轮不要单纯把随机程序数量做大；**先提高 oracle 独立性，再增加数量。**

## E. 顶层 Hybrid-QASM 边界

从官方规则判断并测试：

- header/include/qreg/creg 合法/非法形态；
- classical block 前后存在量子操作；
- 是否明确只要求一个 classical block；
- 若 multiple classical blocks 未被官方承诺，不把它作为 enable 阻塞项；
- braces/semicolon 出现在注释或字符串里时不能破坏顶层扫描；
- malformed input 必须 deterministic fail，不能 silent miscompile。

---

# 2. Compiler / RISC-V codegen 审计

重点确认最终寄存器语义，而不是汇编“看起来合理”。

必须攻击：

- `==` / `!=` 分支方向；
- if / else label 唯一性；
- nested / sequential if（仅在官方语法允许范围内）；
- `a-b` 操作数顺序；
- self assignment；
- register-to-register；
- 0、正数、负数；
- 未初始化 r 寄存器与 Emulator 初始值语义；
- temp 生命周期与复用；
- 深表达式；
- 多次连续 `compile_hybrid()` 是否 deterministic 且无 counter/state 泄漏；
- assembly 只能使用官方 Emulator 支持的：

```text
li, add, sub, addi, beq, bne, j
```

禁止通过修改 `riscv_emulator.py` 来让 production compiler 通过测试。

---

# 3. Adversarial + randomized differential testing

本轮目标不是简单重复 14A 的 120 programs。

先新增一组**手写 adversarial cases**，专门覆盖上述 A–E 风险；再做固定 seed differential test。

随机测试建议：

- 至少 1000 个合法 program；
- 每个 program 根据涉及 measured bits 选择穷举或有代表性的 measurement combinations；
- 总执行 case 数清楚记录；
- 覆盖 r1/r9、c[0]/高位 c、正负/零、顺序赋值、if 两分支、多个 if、复杂 subtraction、scratch pressure；
- whitespace / line comment / block comment 变体；
- 失败必须打印 seed + 最小必要 source。

**重要：**随机 generator 自己也必须遵守你从官方题面重新推导出的 grammar，不要用实现扩展去制造“假 hidden failure”。

Reference Interpreter 必须与 production codegen 独立。

---

# 4. Mutation / metamorphic checks（低成本高价值）

在不增加复杂框架的前提下，对一部分合法程序做语义保持变换，确认编译结果终态不变，例如：

- 改空白 / 换行；
- 加 `//` / `/* */` 注释；
- 对允许的表达式增加不改变语义的括号；
- 更换无关 label 不适用，因为 label 由 compiler 生成；
- 重复调用同一输入应产生 deterministic assembly。

不要引入 property-testing 第三方依赖。

---

# 5. 修改原则

先审计，后修改。

允许修改：

```text
starter_kit/loomq/l3/**
starter_kit/tests/test_l3_hybrid.py
starter_kit/adapter.py   # 仅 compile_hybrid 接线必要时
```

不要：

- 修改 L1/L2 语义；
- 修改官方 `riscv_emulator.py` 来迁就 compiler；
- 开启 `submission.yaml` 的 `l3:true`；
- 做 Web；
- 为 L3 增加 LLM；
- 针对 public evaluator 样例硬编码；
- 因为“可能存在”就无限扩 grammar；
- 为代码风格做大重构。

发现确定的 contract bug，可以直接做最小修复并补 regression test。

---

# 6. 最终回归

至少运行：

```bash
python starter_kit/evaluator.py --level l3
```

以及：

- L3 tests；
- 当前项目完整 Python tests；
- `git diff --check`；
- 确认 `submission.yaml` 仍为 `l3:false`；
- 确认没有新增不必要依赖；
- 确认 L1/L2 生产代码没有被本任务改动。

---

# 7. 最终报告

一次性汇报，不要中途等待确认。

## Independent contract summary

只写从官方规则推导出的契约，并单列：

```text
SPEC_AMBIGUITY
```

如无则写 none。

## Findings

按：

```text
Critical
High
Medium
Low
```

每项写：触发输入、违反什么契约、是否修复、对应测试。

特别回答五个问题：

1. `c[22+]` 是实现缺陷、官方隐含不支持，还是无法从题面确定？
2. scratch allocator 是否存在合法程序误拒绝/覆盖风险？
3. expression precedence / associativity 是否与官方文法一致？
4. quantum_ops canonicalization 是否可能改变合法量子指令语义？
5. 14A differential oracle 是否真正独立？

## Random / adversarial evidence

写清：

- hand-written adversarial case 数；
- seeds；
- random program 数；
- measurement 策略；
- 总执行 cases；
- mutation/metamorphic case 数；
- 修复前后失败数。

## Architecture verdict

回答：

- Lexer / Parser / AST / Codegen 分层是否健康；
- 是否存在 public sample 特判；
- 是否与 L1/L2 不必要耦合；
- 是否需要重构，还是应该停止改动。

## Regression evidence

列出 public evaluator、L3 tests、full tests、diff check、`l3:false`。

## Final recommendation

只能输出：

```text
READY_FOR_L3_ENABLE_REVIEW
```

或

```text
NOT_READY_FOR_L3_ENABLE_REVIEW
```

并给 2–5 条理由。

---

# 验收标准

1. 不重复相信 14A 报告，从官方规则独立重建契约；
2. 重点攻击 14A 已知风险与可能 shared-oracle blind spot；
3. hand-written adversarial + 独立 differential + metamorphic checks 都有证据；
4. 确认 bug 只做最小修复；
5. public evaluator 与完整回归通过；
6. `l3:false` 保持不变；
7. 给出明确 enable review 结论。

完成后不要 commit、不要 push，等待人工复核。