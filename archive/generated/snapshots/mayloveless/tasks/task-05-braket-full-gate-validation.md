# Task 05：Braket 全门真实验证与最小修复

【推荐模型】Terra  
【思考强度】中等

## 目标

验证 Task 04 新增的 12 种门是否已经能够通过现有 Braket Runner 在 `amazon-braket-sdk==1.108.0` 的 `LocalSimulator("braket_sv")` 中真实执行。

本任务以验证为主：

```text
OpenQASM 2.0
→ Parser
→ Circuit IR
→ Braket Serializer
→ Braket LocalSimulator
→ LoomQ 统一结果
```

只有真实集成测试失败时，才做最小范围修复。

## 开始前

先阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/target_ir_contract.md`
- `starter-kit/gate_identities.md`
- `starter-kit/adapter.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/serializers/braket.py`
- `starter-kit/loomq/runners/braket.py`
- `starter-kit/loomq/measurements.py`
- `starter-kit/tests/`

保留现有 SpinQ 独立虚拟环境、JSON Worker 和 Docker 结构。

## 范围

验证比赛白名单全部 12 种门：

```text
h x s sdg t tdg ry rz cx cu1 swap ccx
```

不要修改 SpinQ Runner，不实现 OriginQ、L2 或 L3。

## 一、先验证现状

新增 Braket 真实集成测试，优先直接调用：

```python
adapter.run(qasm, "braket", shots)
```

不要先假设 Runner 缺少支持。当前 Runner 已将完整 Braket QASM 3 交给本地模拟器，Task 04 后可能无需修改生产代码。

测试必须使用真实 SDK，不得 mock counts，也不得按门名直接构造结果。

SDK 未安装时测试可以 skip；在 Docker 中必须实际执行。

## 二、测试电路设计

不要只验证“没有抛异常”，还要验证门的可观测语义。

至少覆盖以下独立电路：

1. `x`
   - `x q[0]` 后测量，结果应接近 100% 为 `1`。

2. `h`
   - `h q[0]` 后测量，`0/1` 应接近各 50%。

3. `s / sdg / t / tdg / rz`
   - 相位门不能只作用于 `|0>` 后直接测量，否则错误实现也可能看不出来。
   - 使用 `h → 相位门 → h` 或与其逆门组合等干涉电路，让相位影响最终概率。
   - 对成对逆门可验证：`s; sdg`、`t; tdg`、`rz(theta); rz(-theta)` 后恢复原状态。

4. `ry`
   - `ry(pi)` 后测量应接近 100% 为 `1`。
   - 再覆盖一个非平凡角度，例如 `ry(pi/2)`。

5. `cx`
   - 保留 Bell 电路回归。

6. `swap`
   - 先令 `q[0]=1, q[1]=0`，执行 swap 后应得到交换后的经典位结果。

7. `ccx`
   - 将两个控制位设为 `1`，验证目标位被翻转。
   - 至少再验证一个控制位为 `0` 时目标位不翻转。

8. `cu1`
   - 不能只在计算基上直接测量。
   - 构造含叠加和干涉的电路，使受控相位可观测。
   - 可使用 `gate_identities.md` 的等价分解作为对照，比较原门版和分解版的结果分布。

所有概率判断使用合理容差，避免要求随机采样得到精确次数。建议 shots 使用 4096 或 8192。

## 三、门等价性测试

对 `swap`、`cu1`、`ccx`，增加“原门版 vs 官方分解版”的分布对比测试：

- 两个版本分别通过 `adapter.run(..., "braket", shots)` 执行。
- 使用现有 Hellinger Fidelity 计算函数，或抽取一个小型公共测试辅助函数。
- Fidelity 阈值使用 `>= 0.97`。
- 分解严格参考 `gate_identities.md`，不要自行猜测矩阵。

不得让原门版和分解版共享固定 counts。

## 四、失败时的最小修复原则

若全部真实集成测试直接通过：

- 不修改 `adapter.py`、Serializer 或 Runner。
- 只提交测试和必要的测试辅助代码。

若某些门失败：

1. 先记录实际生成的 QASM 3 和 SDK 错误。
2. 判断是门名、`stdgates.inc`、本地模拟器语法还是 SDK 版本问题。
3. 优先保持 `transpile()` 的目标 IR 契约不变。
4. 本地执行需要特殊形式时，可以像现有 `include_stdgates=False` 一样，在 Runner 执行路径做最小适配。
5. 不要用输入电路名称、文本片段或测试用例名称做分支。
6. 不要在 Runner 中返回预设概率。

Braket LocalSimulator 支持 OpenQASM 3 程序和本地高级特性；以当前锁定 SDK 的真实执行结果为准，不根据最新 SDK 文档盲目修改接口。

## 五、测试结构

建议新增：

```text
starter-kit/tests/test_braket_full_gates.py
```

可以提取测试辅助函数：

- 执行 QASM 并返回 counts
- 将 counts 转为概率
- 比较两个分布的 Fidelity
- 断言某结果概率达到阈值

不要把测试电路加入官方 `starter-kit/circuits/`，避免混淆公开 evaluator 用例。

至少验证：

- 12 种门均被真实执行覆盖
- 参数表达式 `pi`、`pi/2`、`-pi/4`
- `cu1 → cp` 的执行链路
- `ccx` 三量子位执行
- 结果 Schema、shots 和位序不回归
- Bell、GHZ-3 公开用例不回归

## 六、验收

先运行：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

再运行公开 evaluator：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out report.json
```

预期四项继续通过。

然后在干净 Docker 环境验证：

```bash
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
```

Docker 中必须实际运行新增 Braket 全门集成测试。若默认 CMD 不运行单元测试，请明确汇报用户需要执行的 Docker 测试命令，不要为了本任务随意扩大 Dockerfile 职责。

## 七、完成后汇报

简要说明：

1. 12 种门是否都无需修改 Runner 即可运行。
2. 哪些门使用了干涉或等价分解验证。
3. 是否修改生产代码，以及修改原因。
4. 全部单元/集成测试结果。
5. 公开 evaluator 结果。
6. Docker 干净环境结果。
7. 下一步 SpinQ Runner 仍需补齐哪些门。

不要 commit 或 push。
