# LoomQ 评测韧性设计

本实现只采用通用的软件工程思想，数据结构、模块边界、命名、算法和测试均在本仓库内独立设计。公开 `adapter.py` 接口保持不变。

## 1. 十二门策略与阶段化管线

`loomq/gate_policy.py` 是 L1、L2、L3 和自定义 RISC-V 扩展共用的唯一门策略：

`h, x, s, sdg, t, tdg, rz, ry, cx, cu1, swap, ccx`

题面保证所有正式输入都在这十二门内，因此当前 lowering pass 是有意设计成的幂等验证边界，而不是擅自接受题面外门。这样不会扩大语法面或引入未经评测的分解误差。L2 确定性合成和 L3 quantum operations 也必须经过同一白名单断言。

`loomq/pipeline.py` 记录六个阶段：

1. `receive`：输入摘要；
2. `parse`：寄存器与操作统计；
3. `public-basis`：白名单及 lowering 报告；
4. `canonicalize`：规范 OpenQASM 2.0；
5. `emit-public`：严格按照 `target_ir_contract.md` 输出给官方评测器的 IR；
6. `emit-runtime`：输出已实测可被当前厂商 SDK 接受的执行方言。

`adapter.transpile()` 只返回 `public_ir`。三厂商 runner 只接收 pipeline 生成的 `runtime_ir`，不再从原始 QASM 重建电路；执行结果记录 public/runtime SHA256，诊断阶段还会核对 runner 的 runtime hash 是否与 pipeline 完全一致。两条方言都来自同一 canonical program，但解决了 OriginIR `SDAG/TDAG` 与 PyQPanda `DAGGER`、Braket `stdgates.inc` 与本地 SDK 等合同/运行时差异。

## 2. 原生结果诊断

`loomq/diagnostics.py` 使用题面同款 Hellinger fidelity。接受阈值以 `sqrt((k-1)/(8N))` 的多项分布采样尺度为依据，小 shots 调试时适当放宽，8192 shots 时上限仍为 0.97。

每个原生结果同时比较当前 bit order 与完整反转后的 fidelity。只有反转至少改善 0.02 才自动纠正；对 Bell 这类对称分布会标记 `ambiguous`，不会武断翻转。诊断写入 `result.meta`：

- `pipeline`
- `bit_order_probe`
- `acceptance`
- 使用参考模拟器时的 `fallback`

`LOOMQ_REQUIRE_NATIVE=1` 下，低于阈值会直接失败；普通开发模式会保留被丢弃的原生诊断并回退参考模拟器。`LOOMQ_RELEASE_MODE=1` 是更严格的发布策略：缺 SDK、强制参考模拟器、低 fidelity 或 artifact hash 不一致都会立即失败。

## 3. L2 spec normalization 与 capability matrix

模型表达同一意图时可能使用不同字段，例如：

- `generate` / `generate_circuit` / `generate_qasm`
- `state=cat state` / `target_state=ghz`
- `qubits="5"` / `n_qubits=5`

`loomq/synthesis.py` 先把这些写法归一成 `CircuitSpec(family, qubits, target)`。模型调用仍然是必需步骤；对于 Bell、GHZ、W、QFT、三比特 Grover、均匀叠加、基态和相位干涉，调用后由确定性构造器生成白名单参考 QASM 和理想分布，用它校验模型 QASM 并在失败时要求模型重试。参考 QASM 永远不会替换模型输出，避免退化为关键词匹配式伪 Agent。修复任务同样只使用模型修改后的 QASM。

`backend_capabilities.json` 是 capability matrix：每行陈述一个后端可验证的比特数、类型、队列、费用、账号和平台能力。`loomq/capabilities.py` 对表结构做类型与唯一性校验，把 `minimum_qubits`、`zero_queue`、`free_only` 等模型别名归一化，再由代码筛选后端。模型负责理解约束，不负责发明后端 ID。

模型 `summary` 是不可信文本。如果其中出现代码围栏或 `OPENQASM 2.0;`，展示层会丢弃摘要，确保官方 evaluator 的“第一个 OpenQASM 头”提取规则只能看到已解析、规范化和模拟验证后的 QASM。

`tests/live_l2_deepseek_harness.py` 提供显式 `--live` 的真实模型 campaign。固定 24 例覆盖生成、修复、后端选择；扩展集提供 60/192 例。量子案例同时通过生产模拟器和独立 oracle，报告记录每例模型调用数、token、耗时、prompt/reply/QASM 哈希，以及脚本与能力表 provenance。报告含整体完整性哈希，`verify_campaign_report()` 可离线复核且不会再次调用 API：

```powershell
python tests/live_l2_deepseek_harness.py --live --env-file .env.l2.local --suite baseline24
```

## 4. L3 独立 oracle 与生成式 corpus

`loomq/hybrid_oracle.py` 直接解释 Hybrid-QASM AST，不读取编译出的 RISC-V。测试将同一测量注入分别送入：

- 源级 interpreter；
- compiler 生成的汇编 + 官方 `TinyRISCVEmulator`。

两条路径逐个比较 `x1..x9`。`loomq/hybrid_stress.py` 用固定种子生成量子门、classical block 位置、嵌套分支、负常数和连续赋值的组合，确保回归可重复。

## 5. 最终验证与依赖锁

`loomq/verification.py` 构造题面公布的八个电路族代理：Bell、GHZ-3、GHZ-5、QFT-4、Grover-3 和三个固定随机电路。`scripts/verify_all.py` 会执行 24 个 public IR 回环、24 个 runtime vendor parser 检查和 24 个 exact-artifact 原生执行。

正式冻结前使用发布闸门；它要求三套 SDK、0 fallback、0 skip、全部原生语义阈值通过，并离线验证至少 24 例全通过的真实模型报告：

```powershell
python scripts/verify_all.py --release
```

直接依赖继续维护在 `requirements.txt`。`requirements-lock.txt` 是 Python 3.10 Windows 原生 SDK 环境的完整传递依赖快照，并记录 direct requirements SHA256、解析器版本和目标平台。更新方式：

```powershell
py -3.10 scripts/generate_requirements_lock.py
py -3.10 scripts/generate_requirements_lock.py --check
```

Docker 仍使用跨平台的 direct requirements；不能把 Windows 二进制解析结果误称为 Linux 通用锁。
