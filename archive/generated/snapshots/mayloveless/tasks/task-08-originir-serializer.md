# Task 08：实现 OriginIR Serializer 并接入 transpile

【推荐模型】Terra  
【思考强度】中等

## 目标

在现有统一 Parser 与 Circuit IR 基础上，实现第三个目标格式 `originq` 的 OriginIR 文本输出，并接入：

```python
adapter.transpile(qasm_str, "originq")
```

本任务只完成转译，不安装 PyQPanda、不实现 OriginQ Runner。

完成后的链路：

```text
OpenQASM 2.0
→ Parser
→ Circuit IR
→ OriginIR Serializer
→ OriginIR 文本
```

## 开始前

阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/target_ir_contract.md`
- `starter-kit/gate_identities.md`
- `starter-kit/adapter.py`
- `starter-kit/loomq/ir.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/measurements.py`
- `starter-kit/loomq/serializers/`
- `starter-kit/tests/`

保留现有 SpinQ、Braket Runner、独立 Worker、Docker 和测试结构。

使用 `apply_patch`，不要 commit 或 push。

## 一、OriginIR 输出契约

输出必须是完整 OriginIR 文本：

```text
QINIT 2
CREG 2
H q[0]
CNOT q[0], q[1]
MEASURE q[0], c[0]
MEASURE q[1], c[1]
```

规则：

- `QINIT` 为所有量子寄存器位数之和；
- `CREG` 为所有经典寄存器位数之和；
- 量子位与经典位都按寄存器声明顺序展平成全局索引；
- 每条指令独占一行；
- 输出末尾保留换行；
- 不输出 OpenQASM 头、`include`、寄存器原名或注释；
- 不根据输入电路内容返回固定字符串。

## 二、门映射

实现全部 12 种白名单门：

| OpenQASM 2 | OriginIR |
|---|---|
| `h q[a]` | `H q[a]` |
| `x q[a]` | `X q[a]` |
| `s q[a]` | `S q[a]` |
| `sdg q[a]` | `SDAG q[a]` |
| `t q[a]` | `T q[a]` |
| `tdg q[a]` | `TDAG q[a]` |
| `ry(theta) q[a]` | `RY(theta) q[a]` |
| `rz(theta) q[a]` | `RZ(theta) q[a]` |
| `cx q[a], q[b]` | `CNOT q[a], q[b]` |
| `cu1(theta) q[a], q[b]` | `CU1(theta) q[a], q[b]` |
| `swap q[a], q[b]` | `SWAP q[a], q[b]` |
| `ccx q[a], q[b], q[c]` | `TOFFOLI q[a], q[b], q[c]` |

要求：

- 保持控制位、目标位及操作顺序；
- 参数使用 IR 中已经安全计算好的 `float`；
- 参数序列化采用稳定格式，例如 `format(value, ".17g")`；
- 不重新解析原始 QASM 字符串；
- 不在 Serializer 内执行门分解；
- 使用数据驱动的门名映射，避免大段重复分支；
- 对 IR 中不支持的门或错误参数数量抛出清晰错误。

`target_ir_contract.md` 同时接受 `CU1/CR` 与 `TOFFOLI/CCX`，本任务统一输出 `CU1` 和 `TOFFOLI`。

## 三、全局索引

OriginIR 不保留 OpenQASM 的寄存器名称，必须展平。

例如：

```qasm
qreg qa[2];
qreg qb[1];
creg ca[1];
creg cb[2];
x qb[0];
measure qb[0] -> ca[0];
measure qa[1] -> cb[1];
```

应映射为：

```text
QINIT 3
CREG 3
X q[2]
MEASURE q[2], c[0]
MEASURE q[1], c[2]
```

优先复用：

- `quantum_bit_indices(circuit)`；
- `measurement_mapping(circuit)`；
- `classical_bit_count(circuit)`；

不要在 Serializer 中另写一套可能漂移的寄存器 offset 算法。

## 四、测量

无论输入是单比特测量还是整寄存器测量，OriginIR 都输出逐位形式：

```text
MEASURE q[global_q], c[global_c]
```

要求：

- 保留原始测量操作的出现顺序；
- 整寄存器测量按寄存器内部索引从小到大展开；
- 支持交叉测量映射；
- 未测量经典位只需要保留在 `CREG` 数量中，不额外输出指令；
- 重复写同一经典位继续使用共享测量逻辑的现有错误行为；
- 不假设 `q[i]` 总是测到 `c[i]`。

## 五、代码结构

建议新增：

```text
starter-kit/loomq/serializers/originq.py
```

并更新：

```text
starter-kit/loomq/serializers/__init__.py
starter-kit/adapter.py
```

`adapter.transpile()` 的 serializer 路由应包含：

```python
{
    "spinq": serialize_spinq,
    "originq": serialize_originq,
    "braket": serialize_braket,
}
```

注意：

- `adapter.run(..., "originq", ...)` 本任务仍保持 `NotImplementedError`；
- 不要把未实现的 Runner 伪装成已支持；
- 未知 target 的错误信息应自然包含当前三个可转译目标；
- 不修改 `SUPPORTED_TARGETS` 的现有含义。

## 六、测试

新增独立测试，例如：

```text
starter-kit/tests/test_originq_serializer.py
```

至少覆盖：

1. Bell 电路完整 OriginIR 精确输出；
2. 全部 12 种门及参数格式；
3. 参数表达式经 Parser 计算后输出，例如 `pi/2`、`-pi/4`、`3*pi/8`；
4. 多量子寄存器按声明顺序展平；
5. 多经典寄存器按声明顺序展平；
6. 整寄存器测量展开；
7. 交叉测量映射；
8. 未测量经典位仍计入 `CREG`；
9. 门和测量操作顺序不变；
10. `adapter.transpile(..., "originq")` 路由成功；
11. `adapter.run(..., "originq", ...)` 仍明确未实现；
12. SpinQ、Braket 现有序列化与 Runner 测试不回归。

测试应直接断言完整文本或逐行文本，不只检查是否包含某个门名。

## 七、不要做

- 不安装或引入 `pyqpanda`；
- 不实现 `run_originq()`；
- 不修改 Dockerfile 或 requirements；
- 不接本源云或悟空真机；
- 不修改 Parser 白名单；
- 不修改 SpinQ/Braket Serializer 与 Runner，除非发现真正共享层回归；
- 不实现 L2/L3；
- 不把 OriginIR 写成 QASM；
- 不为 Bell、GHZ、QFT、Grover 写特殊分支。

## 八、验收

运行全部主环境测试：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

单独运行 OriginIR 测试：

```bash
python -m unittest tests.test_originq_serializer -v
```

运行公开双后端 evaluator，确认没有回归：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out report.json
```

Docker 仍需确认原有双后端命令通过，但本任务不要求在容器中安装 OriginQ SDK：

```bash
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
```

## 九、完成后汇报

简要说明：

1. 新增和修改的文件；
2. 12 种门的 OriginIR 映射；
3. 多寄存器与测量展平方式；
4. OriginIR 测试数量与结果；
5. 全部测试结果；
6. 公开 evaluator 四项结果；
7. Docker 结果；
8. OriginQ Runner 尚未实现的边界。

不要 commit 或 push。
