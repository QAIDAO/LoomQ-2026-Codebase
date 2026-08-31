# Task 15C: L3 Differential Audit

## Goal

对 L3 Compiler / Evaluator 做最终客观分审计。

目标不是扩展语言能力，而是在提交前确认：

- Python subset 编译正确；
- target IR 语义正确；
- measurement / classical mapping 正确；
- hybrid control flow 稳定。

原则：

> 先发现真实失败，再做最小修复。
> 没有失败不要重构。

---

## Audit Scope

### 1. Hidden-like cases

覆盖：

### Quantum operations

- 单量子门
- 参数门
- CX / SWAP / CCX
- RY / RZ 符号
- 多 qubit mapping


### Classical logic

- if / else
- nested if
- multiple classical conditions


### Expression

- integer
- negative number
- float parameter
- variable reference


### Hybrid

- measurement 后 classical feedback
- measurement 控制后续 quantum operation
- 多 classical register


### Boundary

- empty branch
- unsupported syntax
- invalid variable
- whitespace / formatting variation


---

## Differential Validation

不要只比较生成文本。

比较语义：

- gate sequence
- qubit index
- gate parameters
- classical register mapping
- measurement target
- conditional expression


重点检查：

- control / target 顺序
- bit order
- measurement mapping
- condition 编译结果


---

## Random Differential

增加有限随机测试：

范围：

- qubit: 1~5
- classical bits: 1~3
- depth <= 8

生成：

- random gates
- random measurement
- random classical branch


记录：

- seed
- source
- expected result
- compiled result
- mismatch


不生成复杂程序。

---

## Failure Handling

如果失败：

不要立即修改。

输出：

- case
- source
- expected
- actual IR
- mismatch
- root cause

分类：

- parser
- AST
- IR generation
- serializer
- runtime


只修最小正确层。

---

## Restrictions

禁止修改：

- L1 adapter
- L2 agent
- SYSTEM_PROMPT
- Web
- evaluator

除非确认 L3 regression。

禁止：

- 重写 compiler
- 修改 IR 设计
- 为单个 case 特判

---

## Final Report

记录：

- source SHA
- dirty status
- case-set version
- total cases
- pass/fail
- runtime
- remaining risk

如果缺少依赖：

标记 SKIP。

完成后停止 review。