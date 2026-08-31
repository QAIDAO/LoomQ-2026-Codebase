# Task 06：补齐 SpinQ 12 种门的真实执行

【推荐模型】Sol  
【思考强度】高

## 目标

扩展现有 SpinQ 独立 Worker 与 native Runner，使比赛白名单内全部 12 种门都能通过：

```text
adapter.run(qasm, "spinq", shots)
→ Parser
→ Circuit IR
→ 独立 Python JSON Worker
→ SpinQit native Circuit
→ Basic Simulator
→ LoomQ 统一结果 Schema
```

本任务完成后，SpinQ 与 Braket 两个本地模拟器都应具备 12 种门的真实执行能力。

## 开始前

先阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/target_ir_contract.md`
- `starter-kit/gate_identities.md`
- `starter-kit/adapter.py`
- `starter-kit/loomq/ir.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/measurements.py`
- `starter-kit/loomq/runners/spinq.py`
- `starter-kit/loomq/workers/spinq_worker.py`
- `starter-kit/requirements-spinq.txt`
- `starter-kit/Dockerfile`
- `starter-kit/tests/test_spinq_runner.py`
- `starter-kit/tests/test_braket_full_gates.py`

检查当前工作区与最新提交，保留：

- SpinQit 独立虚拟环境；
- `LOOMQ_SPINQ_PYTHON`；
- stdin/stdout JSON Worker；
- Braket execution mode；
- 现有 Parser、IR、位序归一化和结果 Schema。

使用 `apply_patch`，不要 commit 或 push。

## 比赛白名单

必须真实执行：

```text
h x s sdg t tdg ry rz cx cu1 swap ccx
```

门规格：

| QASM 门 | 参数数 | 量子位数 | SpinQit 候选原生门 |
|---|---:|---:|---|
| h | 0 | 1 | `H` |
| x | 0 | 1 | `X` |
| s | 0 | 1 | `S` |
| sdg | 0 | 1 | `Sd` |
| t | 0 | 1 | `T` |
| tdg | 0 | 1 | `Td` |
| ry | 1 | 1 | `Ry` |
| rz | 1 | 1 | `Rz` |
| cx | 0 | 2 | `CX` |
| cu1 | 1 | 2 | `CP` |
| swap | 0 | 2 | `SWAP` |
| ccx | 0 | 3 | `CCX` |

以上是候选映射，不允许仅凭名称假定语义正确。必须在安装了 `spinqit==0.2.4` 的隔离环境中检查导出对象、调用形式和真实模拟结果。

## 一、先做 SDK 探测

在修改正式代码前，使用当前隔离环境进行一次最小探测：

- 确认上述候选门是否由 `spinqit` 顶层导出；
- 确认单比特、双比特、三比特门的 native Circuit 添加形式；
- 确认参数门的参数位置，例如候选形式：

```python
circuit << (Ry, qubit, theta)
circuit << (CP, (control, target), theta)
```

- 使用 1–3 个最小电路实际编译和执行，不能只检查 `hasattr()`。

探测代码可以写成测试辅助函数或临时命令；不要留下无用途的调试脚本。

如果 `spinqit==0.2.4` 的行为与公开文档不同，以已锁定 wheel 的真实行为为准，并在代码注释和完成报告中说明。

## 二、重构 SpinQSDK

当前 `SpinQSDK` 只保存 `H` 与 `CX`，请改为可维护的数据驱动结构。

建议：

```python
class SpinQSDK(NamedTuple):
    config_class: Type[Any]
    circuit_class: Type[Any]
    gates: Mapping[str, Any]
    simulator_factory: Any
    compiler_factory: Any
```

`_load_spinq_sdk()` 建立 QASM 门名到 SpinQit 门对象的映射。

要求：

- 缺少必要门时抛出清晰错误，包含门名；
- 不在主 Braket 环境 import SpinQit；
- 不破坏 mock 单元测试；
- 不写 12 个散落的 SDK 字段。

## 三、构造 native Circuit

扩展 `_build_spinq_circuit()`，支持全部门。

建议使用门规格表描述：

```text
SpinQit gate object
参数数
量子位数
调用类别（无参 / 有参）
```

行为：

- 无参单比特：`(gate, qubit)`；
- 有参单比特：按真实 SDK API 传入一个 `float` 参数；
- 无参多比特：按真实 SDK API 传入量子位 tuple；
- 有参双比特 `cu1`：映射至经过真实语义验证的 `CP`，并正确传入参数；
- 保持操作顺序；
- 参数与量子位数量继续严格校验；
- 不重新解析源字符串；
- 不针对 Bell、GHZ、QFT 或 Grover 写特殊分支。

优先使用 SpinQit 0.2.4 的原生门。

只有以下情况才允许按 `gate_identities.md` 分解：

1. 目标门没有导出；
2. native compiler 或 Basic Simulator 明确不支持；
3. 实测语义与 qelib1 不一致。

若需要分解：

- 分解逻辑放在独立、可测试的函数中；
- 使用 IR 级或 native 指令级通用展开；
- 不通过字符串替换 QASM；
- 注释说明为何不能使用原生门；
- `swap`、`cu1`、`ccx` 必须严格遵守官方 `gate_identities.md`；
- `sdg`、`tdg` 可分别使用 `S` 三次、`T` 七次兜底。

## 四、Worker 边界

保持现有协议：

```json
{"qasm": "...", "shots": 4096}
```

Worker：

- 从 stdin 读取一次请求；
- 使用自己的 Parser 恢复 Circuit IR；
- 在隔离环境调用 `run_spinq_native()`；
- stdout 只输出一个结果 JSON；
- SpinQit 普通输出继续重定向到 stderr；
- 出错时不得输出半截 JSON；
- 不泄露环境变量或本地路径之外的敏感信息。

不要改成导入主环境中的 SpinQit，也不要重新合并依赖环境。

## 五、真实全门测试

新增或扩展 SpinQ 真实集成测试，测试必须经：

```python
adapter.run(source, "spinq", shots)
```

进入独立 Worker，而不是直接只测 `_build_spinq_circuit()`。

可以参考 Braket 全门测试的结构，但不要让两个后端测试互相依赖。

至少覆盖：

1. `x` 将 `|0>` 翻转为 `|1>`。
2. `h` 产生近似均匀分布。
3. `s / sdg / t / tdg / rz` 放在干涉电路中验证相位，不能只测量 `|0>`。
4. `ry(pi)` 近似得到 `|1>`；`ry(pi/2)` 得到近似均匀分布。
5. `cx` Bell 回归。
6. `swap` 与官方 3 个 `cx` 分解分布等价。
7. `ccx`：
   - 两个控制位均为 1 时翻转 target；
   - 少一个控制位时不翻转；
   - 与官方分解分布等价。
8. `cu1(pi/2)`：
   - 在能观察相位的电路中运行；
   - 与 `gate_identities.md` 的分解分布等价。
9. 参数来自 Parser 的 `pi/2`、`-pi/4` 等表达式。
10. 交叉测量映射与 little-endian 结果不回归。
11. 非法 shots、缺少独立 Python、Worker 非法 JSON 等已有边界测试继续通过。

真实集成测试：

- 在未配置 SpinQ 隔离环境时允许 skip；
- 在 Docker 和已配置开发环境中必须执行；
- 建议 `shots=4096`；
- 概率或 Hellinger Fidelity 阈值采用 `>= 0.97`；
- 对确定性状态可要求概率 `>= 0.999`；
- 不依赖随机结果恰好出现每个状态。

## 六、单元测试

除真实集成测试外，使用 fake gates / fake circuit 覆盖 native 调用形状：

- 6 个无参单比特门；
- `ry/rz` 参数位置和值；
- `cx/swap` 的量子位顺序；
- `cu1→CP` 的控制位、目标位和参数；
- `ccx` 的三个量子位顺序；
- 未知门与缺失 SDK gate 的清晰错误；
- 如使用分解，逐条验证展开顺序。

测试不要依赖对象的字符串表现形式；记录 fake Circuit 收到的 gate、operands、parameters 后断言结构。

## 七、不要做

- 不修改 `adapter.py` 固定接口；
- 不修改 Parser 白名单；
- 不修改 Braket 全门逻辑，除非 SpinQ 测试暴露了真正共享层回归；
- 不实现 OriginQ；
- 不实现 L2/L3；
- 不接真机或 SpinQ Cloud；
- 不新增第三方依赖；
- 不取消 SpinQ 独立环境；
- 不为公开电路返回固定 counts。

## 八、验收

先运行主环境单测：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

确认隔离环境：

```bash
"${LOOMQ_SPINQ_PYTHON}" -c "import spinqit; print('SpinQit OK')"
```

运行 SpinQ 全门集成测试（使用实际测试模块名）：

```bash
python -m unittest tests.test_spinq_full_gates -v
```

运行公开 evaluator：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out report.json
```

预期 Bell、GHZ-3 四项继续通过。

最后在干净 Docker 中构建并运行：

```bash
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
```

Docker 默认命令应继续得到四项公开 PASS，并且 SpinQ 全门集成测试在容器中可单独运行。

## 九、完成后汇报

简要说明：

1. SpinQit 0.2.4 实际导出的门与真实调用形式；
2. 哪些门使用原生实现，哪些门需要分解及原因；
3. 修改和新增文件；
4. 12 种门的 fake 单元测试结果；
5. 12 种门的真实 SpinQ 集成测试结果；
6. 公开 evaluator 四项结果；
7. 干净 Docker 构建与运行结果；
8. 当前尚未支持的 L1 内容。

不要 commit 或 push。