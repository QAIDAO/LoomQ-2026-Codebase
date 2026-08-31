# Task 07：L1 隐藏用例级组合电路验证

【推荐模型】Sol  
【思考强度】中等

## 目标

在不接入第三平台之前，验证现有 SpinQ 与 Braket 两条完整链路能正确执行比赛隐藏测试风格的组合电路，而不只是逐个门和公开 Bell/GHZ-3。

本任务以验证为主：

```text
OpenQASM 2.0
→ Parser
→ Circuit IR
→ SpinQ / Braket Runner
→ 统一 counts
→ 组合电路语义验证
```

只有真实测试失败时，才对生产代码做最小修复。

## 开始前

先阅读并遵守：

- `AGENTS.md`
- `starter-kit/docs/l1-spec.md`
- `starter-kit/problem_statement.md`（若路径不存在则阅读仓库根目录的 `problem_statement.md`）
- `starter-kit/target_ir_contract.md`
- `starter-kit/gate_identities.md`
- `starter-kit/adapter.py`
- `starter-kit/loomq/parser.py`
- `starter-kit/loomq/measurements.py`
- `starter-kit/loomq/runners/braket.py`
- `starter-kit/loomq/runners/spinq.py`
- `starter-kit/tests/test_braket_full_gates.py`
- `starter-kit/tests/test_spinq_full_gates.py`

保留现有：

- SpinQ 独立虚拟环境与 JSON Worker；
- Braket execution mode；
- 12 门白名单；
- 统一位序和结果 Schema；
- Docker 的双环境设计。

使用 `apply_patch`，不要 commit 或 push。

## 范围

新增隐藏用例风格的真实集成测试，覆盖官方说明中的电路类别：

```text
GHZ-5
QFT-4
Grover-3
Random Circuit × 3
```

测试必须通过：

```python
adapter.run(qasm, target, shots)
```

分别进入 `spinq` 和 `braket`，不能绕过 Adapter、Worker、Parser、Serializer 或结果归一化。

不要把这些测试电路加入官方 `circuits/` 目录，避免与公开契约混淆。建议新增：

```text
starter-kit/tests/test_l1_hidden_like.py
```

可以在测试文件中用纯函数生成 QASM。

## 一、通用测试工具

在测试模块内提供清晰的小工具：

- 构造完整 OpenQASM 2.0 程序；
- 对指定 target 执行并校验统一 Schema；
- 将 counts 转成概率；
- 计算 Hellinger Fidelity；
- 同一电路分别运行 SpinQ 和 Braket；
- 对确定性结果、目标概率分布和跨后端分布分别断言。

要求：

- 概率比较必须考虑采样误差；
- 概率型测试建议 `shots=4096`；
- 确定性 U+U⁻¹ 测试可以使用较低 shots，但不得只执行一次；
- 正式 Fidelity 阈值使用 `>= 0.97`；
- 每次结果都要经过官方 `validate_schema()`；
- counts 总数必须等于 shots；
- `bit_order` 必须为 `little`。

真实 SDK 未安装或 SpinQ Worker 未配置时允许 skip；Docker 中必须执行。

## 二、GHZ-5

生成：

```qasm
h q[0];
cx q[0], q[1];
cx q[1], q[2];
cx q[2], q[3];
cx q[3], q[4];
measure q -> c;
```

分别在两个后端运行，验证：

- 只允许出现 `00000` 与 `11111`；
- 与 `{00000: 0.5, 11111: 0.5}` 的 Fidelity `>= 0.97`；
- 两后端分布之间 Fidelity `>= 0.97`。

## 三、QFT-4 往返

不要只测试“QFT 后测量均匀分布”，因为那无法有效发现受控相位错误。

请实现一个测试侧 QFT-4 生成器，并对一个非零基态执行：

```text
准备基态
→ QFT-4
→ inverse QFT-4
→ 测量
```

要求：

- QFT 使用 `h`、`cu1(theta)`、`swap`；
- inverse QFT 必须通过按相反顺序应用逆门生成，不要复制一份容易漂移的硬编码文本；
- `cu1(theta)` 的逆门为 `cu1(-theta)`；
- `h` 与 `swap` 自逆；
- 至少测试两个非零输入基态，例如 `0001` 与 `1010`（注意最终 key 为 `c[n-1]...c[0]`）；
- 两个后端都应以 `>= 0.999` 的概率恢复输入状态。

生成器应保持量子位控制/目标顺序明确，并添加少量中文注释解释 QFT 与逆序生成。

## 四、Grover-3

实现一个 3 比特 Grover 电路，目标态为 `111`：

```text
均匀叠加
→ 标记 |111> 的相位 Oracle
→ Diffuser
→ 测量
```

建议 Oracle 使用：

```qasm
h q[2];
ccx q[0], q[1], q[2];
h q[2];
```

Diffuser 使用标准的 H/X/多控 Z 结构，可用 `h + ccx + h` 表达多控 Z。

要求：

- 不根据测试名称或目标态在生产代码中写分支；
- `111` 必须是最高概率状态；
- `P(111)` 建议要求 `>= 0.70`，理论上一轮约为 `25/32`；
- 两后端分布 Fidelity `>= 0.97`。

若实际标准 Grover 构造与上述阈值不符，先检查电路语义和位序，不能通过降低到无意义阈值掩盖错误。

## 五、Random Circuit × 3：U 后接 U⁻¹

使用标准库 `random.Random(seed)`，固定三个种子生成小型随机电路，例如：

```text
20260801
20260802
20260803
```

每个随机电路：

1. 使用 3–5 个量子位；
2. 先准备一个固定非零基态；
3. 生成 12–24 个合法门操作 U；
4. 追加 U 的逆操作序列；
5. 最后统一测量；
6. 应恢复初始基态。

随机门池必须覆盖全部 12 种门，三个种子的合计结果中每种门至少出现一次：

```text
h x s sdg t tdg ry rz cx cu1 swap ccx
```

逆门规则：

```text
h   → h
x   → x
s   → sdg
sdg → s
t   → tdg
tdg → t
ry(a)  → ry(-a)
rz(a)  → rz(-a)
cx  → cx
cu1(a) → cu1(-a)
swap → swap
ccx → ccx
```

要求：

- 逆序列必须由结构化操作记录自动生成，不要对 QASM 字符串做正则反转；
- 多比特门的量子位必须互不重复；
- 参数从一组稳定角度中选择，例如 `pi/2`、`-pi/4`、`3*pi/8`；
- 测试同时覆盖参数表达式 Parser；
- 每个种子在两个后端上恢复初始态的概率 `>= 0.999`；
- 统计并断言三个种子合计覆盖 12 门，避免随机改动导致覆盖退化。

## 六、额外结构用例

再增加少量非算法用例，验证隐藏输入的结构变化：

1. 多量子寄存器和多经典寄存器；
2. 寄存器声明顺序影响全局索引；
3. 单比特交叉测量，例如：

```qasm
measure qa[0] -> cb[0];
measure qb[0] -> ca[0];
```

4. 未测量经典位保持 `0`；
5. 注释、空行和多语句同一行；
6. 最终测量前包含参数门与三比特门。

这些用例应在两后端得到相同的经典位语义。

## 七、失败处理原则

测试失败时按以下顺序定位：

```text
测试电路是否正确
→ bit order / 测量映射
→ Parser 参数与量子位顺序
→ Serializer / native gate 映射
→ SDK 特性或分解
```

只修改真正有问题的最小层级。

允许的修复：

- 通用 Parser、位序、测量映射 bug；
- 通用门参数或 operand 顺序 bug；
- 已锁定 SDK 的真实兼容性修复；
- 通用门分解修复。

禁止：

- 根据 GHZ、QFT、Grover、seed 或完整 QASM 文本写分支；
- 返回固定 counts；
- 用一个后端结果直接冒充另一个后端结果；
- 修改官方 evaluator 或公开电路；
- 顺手实现 OriginQ、L2 或 L3；
- 新增第三方依赖或测试用量子模拟器。

## 八、验收

主环境：

```bash
cd starter-kit
python -m unittest discover -s tests -v
```

单独运行隐藏风格测试：

```bash
python -m unittest tests.test_l1_hidden_like -v
```

公开 evaluator：

```bash
python evaluator.py \
  --level l1 \
  --target spinq,braket \
  --json-out report.json
```

干净 Docker：

```bash
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
```

并在容器内单独执行：

```bash
docker run --rm loomq-l1 \
  python -m unittest tests.test_l1_hidden_like -v
```

预期：

- 现有全部单元测试通过；
- GHZ-5、QFT-4 往返、Grover-3、Random × 3 在两个后端通过；
- 公开 Bell/GHZ-3 四项继续 PASS；
- Docker 从干净构建上下文完成安装和执行。

如果某些集成测试耗时较长，可以汇报各阶段耗时，但不要为了提速降低语义断言或跳过 Docker 验证。

## 九、完成后汇报

简要说明：

1. 新增测试文件与生成器；
2. GHZ-5、QFT-4、Grover-3 的验证结果；
3. 三个随机 U+U⁻¹ 电路的门覆盖与结果；
4. 两后端交叉 Fidelity；
5. 是否发现生产代码缺陷以及修复位置；
6. 全部单元测试结果；
7. 公开 evaluator 四项结果；
8. 干净 Docker 结果；
9. 进入 OriginQ 前仍存在的风险。

不要 commit 或 push。
