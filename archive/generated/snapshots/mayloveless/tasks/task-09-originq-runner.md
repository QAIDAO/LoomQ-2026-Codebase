# Task 09：OriginQ 本地 Runner 与三后端回归

## 目标

在现有 OriginIR Serializer 基础上，实现真实的本源量子本地模拟器 Runner，使：

```python
adapter.run(qasm_str, "originq", shots)
```

通过 pyQPanda CPU 模拟器执行，并返回 LoomQ 统一结果 Schema。

本任务完成后，L1 应同时支持 SpinQ、OriginQ、Braket 三个本地模拟器后端。

## 范围

本任务包含：

- pyQPanda 独立运行环境；
- OriginQ JSON Worker；
- OriginIR → pyQPanda QProg → CPU 模拟执行；
- counts 位序与测量映射验证、归一化；
- `adapter.run(..., "originq")` 路由；
- OriginQ 真实集成测试；
- Docker 三后端公开 evaluator。

本任务不包含：

- OriginQ 云端或悟空真机；
- 账号、Token、排队逻辑；
- L2 Agent、前端、可视化；
- L3；
- 修改公开 OriginIR 合同以迁就 SDK。

## 1. 依赖与环境隔离

新增：

```text
starter-kit/requirements-originq.txt
```

固定使用：

```text
pyqpanda==3.8.5
```

不要直接加入主 `requirements.txt`。pyQPanda 是带原生动态库的 SDK，使用独立虚拟环境和子进程，避免影响 Braket、SpinQ 或主解释器。

统一环境变量：

```text
LOOMQ_ORIGINQ_PYTHON
```

本地候选路径可参考 SpinQ Runner：

```text
starter-kit/.venv-originq/bin/python
starter-kit/.venv-originq/Scripts/python.exe
/opt/originq-venv/bin/python
```

找不到解释器时给出明确错误，不允许自动回退到 mock。

## 2. 执行架构

沿用 SpinQ 的隔离 Worker 架构：

```text
Circuit IR
→ serialize_originq(...)
→ OriginIR 文本
→ OriginQ Worker 子进程
→ pyQPanda CPUQVM
→ raw counts
→ LoomQ Result Schema
```

新增建议文件：

```text
starter-kit/loomq/runners/originq.py
starter-kit/loomq/workers/originq_worker.py
```

父进程与 Worker 通过 stdin/stdout 单次 JSON 通信，例如：

```json
{
  "originir": "QINIT ...",
  "shots": 1024
}
```

stdout 只能输出最终 JSON。pyQPanda 的普通输出或诊断必须重定向到 stderr，避免破坏协议。

Worker 异常时返回非零退出码；父进程将 stderr 截断后包装成可读的 `RuntimeError`。设置合理超时。

## 3. pyQPanda 执行方式

优先复用 OriginIR，而不是再实现一套重复的 Circuit IR → pyQPanda 门映射。

Worker 中：

1. 延迟导入 `pyqpanda`；
2. 初始化 CPU 量子虚拟机；
3. 将 OriginIR 写入临时 UTF-8 文件；
4. 使用 `convert_originir_to_qprog(path, machine)` 得到 `prog, qvec, cvec`；
5. 使用 `run_with_configuration(prog, cvec, shots)` 执行；
6. 在 `finally` 中释放/销毁量子机和临时资源。

请先用最小 Bell 电路实际探测 pyQPanda 3.8.5 的 API 签名，不要仅依据旧文档猜测。

## 4. SDK 兼容语法

公开 `adapter.transpile(..., "originq")` 的默认输出必须继续符合 `target_ir_contract.md`，不能为了 pyQPanda 解析器而改变公开合同。

请真实探测 pyQPanda 3.8.5 是否接受当前输出，重点检查：

```text
RY(θ) q[0]
RZ(θ) q[0]
CU1(θ) q[0], q[1]
SDAG
TDAG
TOFFOLI
```

若 pyQPanda 不能直接解析某些合同允许写法，可为 Serializer 增加明确的私有执行模式，例如：

```python
serialize_originq(circuit, execution_mode=True)
```

要求：

- 默认 `execution_mode=False`，公开 `transpile()` 输出完全不变；
- 执行模式只处理已经证实的 SDK 兼容差异；
- 可使用 pyQPanda 文档支持的参数位置或 `CR` 等价门名；
- 不允许在 Worker 中通过脆弱正则临时改写整段文本；
- 必须为默认模式和执行模式分别写测试。

若默认 OriginIR 已能直接执行，则不要引入多余执行模式。

## 5. 测量与 counts 位序

不能假设 pyQPanda 返回 key 的字符顺序。

先用确定性电路实际验证：

- `x q[0]` 与 `x q[1]` 分别对应 raw key 的哪一位；
- 多经典寄存器声明顺序；
- 交叉测量；
- 未测量经典位是否保留为 `0`；
- `c[n-1]...c[0]` 是否与 LoomQ 规范一致。

最终输出必须满足：

```text
bit_order = "little"
counts key = c[n-1]...c[0]
sum(counts.values()) == shots
```

若 pyQPanda raw counts 已严格等于 LoomQ 格式，可在代码和测试中明确证明后直接使用。

若不一致，新增显式 `normalize_originq_counts(...)`，复用 `measurement_mapping()` / `build_classical_key()`，不要硬编码 Bell/GHZ 位序。

校验：

- key 只能包含 `0/1`；
- key 宽度正确；
- count 是非负整数且总数精确等于 shots；
- 至少存在一个测量；
- 与现有 Runner 一致，仅支持末尾测量，门出现在测量之后时给出明确错误。

## 6. 统一结果 Schema

使用现有 `create_result()`，返回至少：

```json
{
  "backend": "originq_cpuqvm",
  "job_id": "originq-local-...",
  "shots": 1024,
  "counts": {},
  "bit_order": "little",
  "timestamp": "...",
  "meta": {
    "simulator": "CPUQVM",
    "sdk": "pyqpanda"
  }
}
```

禁止 `meta.is_mock=true`，禁止固定 counts。

## 7. Adapter 与导出

更新：

```text
starter-kit/loomq/runners/__init__.py
starter-kit/adapter.py
```

使：

```python
adapter.run(source, "originq", shots)
```

调用真实 `run_originq(parse_qasm(source), shots)`。

删除原有 OriginQ `NotImplementedError`，其他未知 target 仍返回明确 `ValueError`。

## 8. Docker

更新 Dockerfile：

- 复制 `requirements-originq.txt`；
- 创建 `/opt/originq-venv`；
- 安装固定版本 pyQPanda；
- 设置：

```text
LOOMQ_ORIGINQ_PYTHON=/opt/originq-venv/bin/python
```

保留 SpinQ 独立环境。

Docker 默认命令改为运行三后端公开 evaluator：

```text
spinq,originq,braket
```

必须执行一次无缓存构建验证。

## 9. 测试要求

新增 OriginQ Runner 专项测试，至少覆盖：

1. 未配置/找不到独立 Python 时的明确错误；
2. Worker 非零退出、超时、无效 JSON；
3. Bell 真实运行与 Schema；
4. GHZ-3 真实运行与 Fidelity；
5. 全部 12 种门至少通过真实 OriginQ 执行链路一次；
6. QFT-4 → inverse QFT-4 恢复非零基态；
7. Grover-3 中 `111` 为最高概率且 `P(111) >= 0.70`；
8. 至少一组固定种子随机 `U + U^-1` 100% 恢复；
9. 多寄存器、交叉测量和未测量经典位，目标 key 为 `0110`；
10. 与 SpinQ、Braket 的相同电路 Fidelity 达到现有阈值。

集成测试应根据 `LOOMQ_ORIGINQ_PYTHON` 是否存在进行条件跳过，但 Docker 中必须真实执行，不能跳过。

不要复制一套独立 Parser 或 IR。

## 10. 验收命令

至少执行：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

三后端公开 evaluator：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,originq,braket \
  --json-out report.json
```

干净 Docker：

```bash
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
```

并在同一镜像中运行 OriginQ 专项测试及隐藏风格组合电路测试。

## 11. 完成汇报

完成后不要 commit 或 push，只汇报：

- pyQPanda 版本和实际使用的 API；
- 是否需要 OriginIR 私有执行模式，以及原因；
- raw counts 位序实测结论与归一化方式；
- Bell、GHZ、QFT、Grover、随机逆电路、交叉测量结果；
- 三后端公开 evaluator 结果；
- 全量测试数量；
- 无缓存 Docker 构建与镜像内测试结果；
- 修改文件清单及仍存在的风险。
