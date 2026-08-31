# Task 03：实现 SpinQ 本地 Runner

【推荐模型】Sol  
【思考强度】中等

## 目标

在现有 L1 架构上接入 SpinQit 本地基础模拟器，使 Bell 和 GHZ-3 在 `spinq` 目标上通过公开 evaluator。

本任务完成后的数据流：

```text
OpenQASM 2.0
→ parse_qasm()
→ Circuit IR
→ SpinQit native Circuit
→ SpinQit Basic Simulator
→ 结果位序归一化
→ LoomQ 统一结果 Schema
```

## 开始前

先阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/adapter.py`
- `starter-kit/evaluator.py`
- `starter-kit/target_ir_contract.md`
- `starter-kit/loomq/ir.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/results.py`
- `starter-kit/loomq/runners/braket.py`
- `starter-kit/loomq/serializers/spinq.py`
- `starter-kit/tests/`
- `starter-kit/requirements.txt`
- `starter-kit/Dockerfile`

先检查当前仓库状态和最新 Braket 修复，不要覆盖已经通过的实现。

要求：

- 使用 `apply_patch` 修改文件。
- 不执行 `git commit`、`git push` 或创建 PR。
- 不修改官方 evaluator、公开电路、目标 IR 契约和评分规则。
- 使用少量中文注释解释 SDK 边界、测量映射和位序转换。
- 不给普通语句逐行加注释。

## 当前已知事实

SpinQit 官方基础模拟器的典型调用方式为：

```python
from spinqit import (
    BasicSimulatorConfig,
    Circuit,
    CX,
    H,
    get_basic_simulator,
    get_compiler,
)

circuit = Circuit()
qubits = circuit.allocateQubits(2)
circuit << (H, qubits[0])
circuit << (CX, (qubits[0], qubits[1]))

compiler = get_compiler("native")
executable = compiler.compile(circuit, 0)
config = BasicSimulatorConfig()
config.configure_shots(1024)
result = get_basic_simulator().execute(executable, config)
counts = result.counts
```

SpinQit 文档说明其结果字符串采用自身的 little-endian 表示：字符串第一个字符对应电路中的第一个量子位。LoomQ 官方结果则要求 key 为 `c[n-1]...c[0]`，最右侧字符是 `c[0]`。因此不得直接返回 `result.counts`。

如果安装后的 `spinqit==0.2.4` API 与上述示例存在差异，应以实际安装包和官方文档为准，做最小兼容调整并在完成报告中说明；不要猜测或伪造接口。

## 一、依赖

在 `starter-kit/requirements.txt` 中精确加入：

```text
spinqit==0.2.4
```

保留现有 Braket 依赖。

SpinQit 0.2.4 提供 CPython 3.10 的 Windows 和 manylinux x86-64 wheel，正式验证以比赛的 Python 3.10 Linux Docker 环境为准。

SDK 必须延迟导入：

- 只使用 `transpile()` 或 Braket 时，不应因为缺少 SpinQit 而 import 失败。
- 缺少 SDK 时，`run(..., "spinq", ...)` 应抛出清晰错误，提示安装 `starter-kit/requirements.txt`。

## 二、共享测量映射

Braket Runner 中现有以下逻辑具有平台无关性：

- 按寄存器声明顺序计算量子位全局索引。
- 按寄存器声明顺序计算经典位全局索引。
- 将 `measure q -> c` 展开为逐位映射。
- 将 `measure q[i] -> c[j]` 转成全局索引映射。
- 检测同一经典位被重复写入。
- 按 `c[n-1]...c[0]` 生成最终 key。

请将这些通用逻辑从 `loomq/runners/braket.py` 提取到清晰的公共模块，例如：

```text
starter-kit/loomq/measurements.py
```

公共模块可以提供类似接口：

```python
def measurement_mapping(circuit: Circuit) -> list[tuple[int, int]]:
    """返回 (量子位全局索引, 经典位全局索引) 映射。"""


def classical_bit_count(circuit: Circuit) -> int:
    ...
```

具体命名可根据现有代码调整，但要求：

- Braket 和 SpinQ 共用同一套测量映射逻辑。
- 不复制两份寄存器 offset 和测量展开代码。
- 提取后 Braket 的行为和测试结果不得变化。

## 三、SpinQ Runner

新增：

```text
starter-kit/loomq/runners/spinq.py
```

建议入口：

```python
def run_spinq(circuit: Circuit, shots: int) -> dict:
    ...
```

### 3.1 构建 SpinQit Circuit

Runner 接收已经解析好的 `Circuit IR`，不得再次调用 `parse_qasm()`。

按 IR 中量子寄存器的声明顺序向 SpinQit Circuit 分配 qubits，并维护：

```text
QubitRef(register, index) → SpinQit qubit 对象
```

本阶段只转换当前已经支持的门：

- `h` → SpinQit `H`
- `cx` → SpinQit `CX`

遇到其他 GateOperation 时抛出清晰的未支持错误，不静默忽略。

不要通过写临时 QASM 文件再调用 qasm compiler；本任务直接从统一 IR 构建 SpinQit native Circuit，以保持 Runner 边界清晰并避免临时文件管理。

### 3.2 测量范围

从 Circuit IR 的 MeasureOperation 收集被测量量子位。

- 对整寄存器测量展开为逐位测量。
- 去重后按量子位全局索引升序形成 `measured_qubits`。
- 使用 `BasicSimulatorConfig.configure_measure_qubits(...)` 限定模拟器返回的量子位；先通过安装包源码或小型集成测试确认该方法接收的是索引还是 SDK qubit 对象。
- 如果电路没有任何 MeasureOperation，抛出明确错误。
- 当前只支持最终测量：一旦出现 MeasureOperation，后面不得再出现 GateOperation；遇到中途测量应明确报错，不能忽略测量顺序。

### 3.3 执行

执行流程：

```text
SpinQit Circuit
→ get_compiler("native").compile(circuit, 0)
→ BasicSimulatorConfig.configure_shots(shots)
→ configure_measure_qubits(...)
→ get_basic_simulator().execute(...)
→ result.counts
```

要求：

- 复用 `validate_shots()`。
- optimization level 固定为 `0`，避免当前阶段引入优化差异。
- 校验 `result.counts` 存在、非空、key/value 合法且总数等于 shots。
- 不生成随机 job id 之外的伪造执行结果；本地 SDK 没有 job id 时，可生成 `spinq-local-<uuid>`。

## 四、SpinQ counts 归一化

SpinQit 原始 key 的第一个字符对应第一个被测量量子位；LoomQ 最终 key 必须按经典位全局索引倒序排列。

实现独立、可单测的转换函数，例如：

```python
def normalize_spinq_counts(
    circuit: Circuit,
    measured_qubits: Sequence[int],
    raw_counts: Mapping[str, int],
) -> dict[str, int]:
    ...
```

转换步骤：

1. 明确原始 key 每个字符对应哪个量子位。
2. 使用公共 `measurement_mapping(circuit)` 找到每个量子位写入的经典位。
3. 未测量的经典位保持初始值 `0`。
4. 按经典位全局索引倒序拼接，输出 `c[n-1]...c[0]`。
5. 合并归一化后相同 key 的计数。
6. 校验 raw key 长度与 measured_qubits 数量一致。
7. 校验 key 只包含 `0/1`、计数为非负整数。
8. 不得只做字符串反转，因为交叉测量和多寄存器场景需要真正的映射。

示例：

```text
measured_qubits = [0, 1]
SpinQ raw key = "10"  # q[0]=1, q[1]=0

q[0] → c[1]
q[1] → c[0]

最终 c[1]c[0] = "10"
```

普通映射：

```text
q[0] → c[0]
q[1] → c[1]
```

同一 raw key `"10"` 应归一化为：

```text
c[1]c[0] = "01"
```

## 五、统一 Schema 与 Adapter

`run_spinq()` 最终调用现有 `create_result()`：

```python
{
    "backend": "spinq_basic_simulator",
    "job_id": "spinq-local-...",
    "shots": shots,
    "counts": normalized_counts,
    "bit_order": "little",
    "timestamp": "...Z",
    "meta": {
        "simulator": "basic",
        "compiler": "native",
        "optimization_level": 0,
    },
}
```

更新：

```text
starter-kit/loomq/runners/__init__.py
starter-kit/adapter.py
```

使：

- `run(qasm, "spinq", shots)` → Parser → `run_spinq()`
- `run(qasm, "braket", shots)` 保持当前行为
- `originq` 继续明确未实现
- 未知 target 继续抛出 ValueError

Adapter 不得包含 SDK 调用、门映射或 counts 转换细节。

## 六、测试

继续使用标准库 `unittest`。

建议新增：

```text
starter-kit/tests/test_spinq_runner.py
```

并更新公共测量映射与 Braket 测试。

至少覆盖：

1. 公共测量映射支持整寄存器测量。
2. 公共测量映射支持单 bit 和交叉映射。
3. 多量子寄存器和多经典寄存器的全局 offset 正确。
4. 同一经典位重复写入时报错。
5. Braket 提取公共逻辑后原测试全部通过。
6. SpinQ raw key 的普通映射归一化正确。
7. SpinQ raw key 的交叉映射归一化正确。
8. 未测量经典位补 0。
9. raw key 宽度错误时报错。
10. 非二进制 key、非法 count、counts 总数不等于 shots 时拒绝。
11. H/CX 被正确映射到 SpinQit Circuit。
12. 不支持的门明确报错。
13. 没有测量和中途测量明确报错。
14. 缺少 SpinQit SDK 时错误信息清晰。
15. Adapter 正确路由 spinq、braket，originq 仍未实现。
16. 现有 Parser、Serializer、Braket Runner 和 results 测试不回归。

SDK 边界优先使用 `unittest.mock`，避免普通单元测试依赖随机采样。

增加真实 SpinQit 集成测试；SDK 未安装或当前平台无兼容 wheel 时允许 skip，但 Docker 中必须执行：

- Bell
- GHZ-3

集成测试检查：

- 返回 Schema 合法。
- counts 总和等于 shots。
- Bell 只出现 `00`、`11`。
- GHZ-3 只出现 `000`、`111`。
- Fidelity 达到官方阈值。

不要固定要求每个合法状态都一定出现，以免低 shots 时偶发失败。

## 七、验收

在 `starter-kit/` 下运行：

```bash
python -m unittest discover -s tests -v
```

本地平台可以安装 SpinQit 时：

```bash
python evaluator.py \
  --level l1 \
  --target spinq \
  --json-out report-spinq.json
```

重新构建 Docker，这是正式验收环境：

```bash
docker build -t loomq-l1 .
```

运行 SpinQ：

```bash
docker run --rm loomq-l1 \
  python evaluator.py \
  --level l1 \
  --target spinq \
  --json-out /tmp/report-spinq.json
```

预期：

```text
PASS l1:bell.qasm:spinq
PASS l1:ghz3.qasm:spinq
```

再运行两个已实现后端：

```bash
docker run --rm loomq-l1 \
  python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out /tmp/report-l1-baseline.json
```

预期四个公开 case 全部通过。

如果当前机器不能安装 SpinQit wheel，不要修改系统 Python 或用 mock 代替集成验证；应在 Python 3.10 x86-64 Linux Docker 中完成真实验证。

## 八、任务边界

本次不要：

- 实现 OriginQ。
- 新增其余 10 种门。
- 实现参数表达式。
- 修改 L2、L3 或前端。
- 接入 SpinQ 真机或云平台。
- 修改 submission level 声明。
- 为 Bell/GHZ 硬编码结果。
- 返回 mock counts。

## 九、完成后汇报

简要说明：

1. 新增和修改了哪些文件。
2. 公共测量映射如何抽取。
3. SpinQit Circuit 如何从统一 IR 构建。
4. SpinQ 原始位序如何转换为 LoomQ 位序。
5. 单元测试结果。
6. 本地或 Docker 真实集成测试结果。
7. evaluator 的公开结果与 Fidelity。
8. 当前已知限制。
9. 下一步补齐 12 种门时可复用哪些部分。

不要扩展本任务范围。
