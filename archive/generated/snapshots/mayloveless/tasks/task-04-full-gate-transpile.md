# Task 04：补齐 12 种门的解析与转译

【推荐模型】Sol  
【思考强度】中等

## 目标

扩展现有 OpenQASM 2.0 Parser、Circuit IR 使用方式和两个 Serializer，使 `transpile()` 能正确处理比赛白名单内全部 12 种门及常见角度表达式。

本任务只完成：

```text
OpenQASM 2.0
→ Parser
→ Circuit IR
→ SpinQ OpenQASM 2.0
→ Braket OpenQASM 3.0
```

Runner 暂时仍只保证当前 `h / cx` 电路可执行。完整 Runner 门映射在下一任务处理。

## 开始前

先阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/target_ir_contract.md`
- `starter-kit/gate_identities.md`
- `starter-kit/loomq/ir.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/serializers/spinq.py`
- `starter-kit/loomq/serializers/braket.py`
- `starter-kit/tests/`

检查当前工作区和最新提交，保留现有 Braket 与 SpinQ Runner、独立 SpinQ Worker 和 Docker 环境设计。

## 比赛白名单

必须支持：

```text
无参单比特：h x s sdg t tdg
有参单比特：ry(theta) rz(theta)
无参双比特：cx swap
有参双比特：cu1(theta)
无参三比特：ccx
```

门规格：

| 门 | 参数数 | 量子位数 |
|---|---:|---:|
| h | 0 | 1 |
| x | 0 | 1 |
| s | 0 | 1 |
| sdg | 0 | 1 |
| t | 0 | 1 |
| tdg | 0 | 1 |
| ry | 1 | 1 |
| rz | 1 | 1 |
| cx | 0 | 2 |
| cu1 | 1 | 2 |
| swap | 0 | 2 |
| ccx | 0 | 3 |

不得接受白名单之外的门。

## 一、参数表达式

当前 Parser 只接受 `float()` 可直接解析的数字，需要扩展为安全的角度表达式解析。

至少支持：

```text
0
1.25
1e-3
pi
-pi
pi/2
-pi/4
3*pi/8
(pi + pi/2) / 3
```

允许语法：

- 十进制和科学计数法数值
- 常量 `pi`，大小写敏感
- 一元 `+`、`-`
- 二元 `+`、`-`、`*`、`/`
- 任意合法嵌套括号
- 普通空格

禁止：

- `eval()`
- 函数调用
- 属性访问
- 下标
- 变量（`pi` 除外）
- `**`、`%` 等未声明运算
- `nan`、`inf`
- 除零

可以使用标准库 `ast.parse(..., mode="eval")`，但必须对白名单 AST 节点和运算符逐个校验；也可以实现小型递归下降解析器。

最终仍将参数保存为 IR 中的 `float`。结果必须是有限数值。

参数解析失败时抛出带行号和原语句的 `QASMParseError`，错误中说明非法参数表达式。

## 二、门语句解析

现有 `_GATE_RE` 的参数部分不应继续依赖简单的 `[^)]*` 来处理嵌套括号。

请以清晰、可测试的方式拆分：

```text
门名
可选参数列表
量子位操作数列表
```

要求：

- 能正确识别嵌套括号中的参数表达式。
- 本次白名单所有参数门都只有 1 个参数，但结构不要写成 `ry/rz/cu1` 专用分支。
- 参数逗号拆分需尊重括号深度。
- 严格校验参数数量和量子位数量。
- 保持已有寄存器声明、索引越界和测量校验行为。
- 不允许门作用于整个寄存器；仍只接受 `q[index]` 操作数。

## 三、SpinQ Serializer

输出完整 OpenQASM 2.0：

- 12 种门保持 qelib1 标准门名。
- `cu1` 输出为 `cu1(theta)`。
- 参数继续使用稳定的高精度浮点格式，例如现有 `.17g`。
- 保留寄存器、操作和测量顺序。

对 SpinQ 输出做 round-trip：

```text
输入 QASM
→ parse
→ serialize_spinq
→ 再 parse
→ Circuit IR 相等
```

## 四、Braket Serializer

输出完整 OpenQASM 3.0，并保持现有 `include_stdgates` 行为。

门名映射：

```text
cx   → cnot
cu1  → cp
其他 → 保持原门名
```

说明：OpenQASM 3 `stdgates.inc` 的受控相位标准门是 `cp(theta)`，其语义对应 OpenQASM 2 qelib1 的 `cu1(theta)`。

需要正确输出例如：

```qasm
ry(1.5707963267948966) q[0];
rz(-0.7853981633974483) q[1];
cp(0.39269908169872414) q[0], q[1];
swap q[0], q[1];
ccx q[0], q[1], q[2];
```

不要在 Serializer 内做后端 SDK 降级分解。Serializer 只生成目标 IR。

## 五、代码结构

建议：

- 将安全参数表达式解析放入独立模块，例如 `loomq/expressions.py`，或作为 Parser 中职责清晰的小模块。
- `SUPPORTED_GATES` 继续作为数据驱动的门规格表。
- Serializer 的门名映射使用字典，不写 12 组重复 `if/elif`。
- 添加少量中文注释，重点解释安全表达式白名单和 `cu1 → cp`。

不要：

- 修改 `adapter.py` 的接口和路由结构。
- 修改 Runner、Worker、Dockerfile 或依赖文件。
- 添加第三方依赖。
- 实现 OriginQ。
- 实现 L2/L3。
- 根据 Bell、GHZ、QFT、Grover 名称或文本做特殊处理。

## 六、测试

继续使用 `unittest`。

至少覆盖：

### 参数表达式

1. 数字、负数和科学计数法。
2. `pi`、`pi/2`、`-pi/4`、`3*pi/8`。
3. 嵌套括号和空格。
4. 除零拒绝。
5. 未知变量拒绝。
6. 函数调用、属性访问、幂运算拒绝。
7. `nan`、`inf` 或非有限结果拒绝。

### Parser

8. 12 种门全部解析成功。
9. 每种门的参数数和量子位数错误均被拒绝。
10. 白名单外的门仍抛出 `UnsupportedGateError`。
11. 参数表达式错误包含行号和原语句。
12. 嵌套括号参数不会破坏操作数解析。

### Serializer

13. SpinQ 12 门 round-trip 后 IR 相等。
14. Braket `cx → cnot`。
15. Braket `cu1 → cp`。
16. Braket 其余门名和参数正确。
17. `include_stdgates=True/False` 行为保持不变。
18. 现有测量和位序相关测试不回归。

建议增加一个三量子位综合测试电路，依次包含全部 12 种门，但不要把它放进官方 `circuits/` 目录。

## 七、验收

运行：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

然后运行现有公开 evaluator，确认任务没有破坏已打通的后端：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out report.json
```

预期 Bell、GHZ-3 四项继续通过。

注意：本任务新增的其他 10 种门尚未接入两个 Runner；不要为了让自定义全门电路执行通过而扩展本次范围。Parser 和 `transpile()` 正确即可。

可额外在测试中验证：

```python
adapter.transpile(full_gate_qasm, "spinq")
adapter.transpile(full_gate_qasm, "braket")
```

## 八、完成后汇报

简要说明：

1. 修改和新增文件。
2. 参数表达式的安全实现方式。
3. 12 种门的 Parser 规格表。
4. SpinQ 与 Braket 门名映射。
5. 单元测试结果。
6. 公开 evaluator 结果。
7. 下一任务扩展 Runner 时仍需处理的门和可能的后端分解。

不要 commit 或 push。