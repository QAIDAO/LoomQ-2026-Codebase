# Bonus：量子 RISC-V 扩展复现指南

本目录与 `loomq/bonus/` 构成赛事 Bonus 要求的完整三件套：

1. 指令编码规格：`loomq/bonus/quantum_riscv_spec.md`（规范正文）与 `docs/bonus/QUANTUM_RISCV_ISA.md`（评审指南）
2. 官方模拟器接口扩展：`loomq/bonus/emulator.py`
3. 可执行端到端演示与测试：`loomq/bonus/demo.py`、`tests/test_bonus_*.py`

## 设计来源与边界

`QuantumRISCVEmulator` 明确继承赛事官方 `starter_kit/riscv_emulator.py` 中的 `TinyRISCVEmulator`，保留其公开 API 与七条经典指令行为。官方文件没有被修改；扩展实现独立放置，便于评委对照审阅。新增 ISA、编码器、解码器和态矢执行均为本项目实现，只使用 Python 3.10 标准库。

这是本地理想模拟器，不生成、冒充或替代任何量子真机证据。

## 一条命令跑演示

在 `starter_kit/` 目录使用 Python 3.10：

```bash
python -m loomq.bonus.demo
```

演示程序用 GPR 携带量子位编号和 Q16.16 旋转角，覆盖 QINIT、QH、QX、QRY、QRZ、QCX、QSWAP、QCCX、QMEASURE，输出完整 JSON 日志，同时检查 Toffoli 目标位与 Bell 关联。进程返回码为 0 表示两项检查均通过。

## 运行测试

```bash
python -m unittest discover -s tests -p "test_bonus_*.py" -v
```

测试覆盖：

- 八个固定机器码与小端序字节；
- 全指令 encode/decode/disassemble 正反向；
- 1,000 组随机寄存器字段往返；
- 200 个随机量子电路的助记符/`.word` 差分执行；
- 官方经典指令行为兼容；
- 初始化、单/双/三比特门、参数化旋转、动态 GPR 量子位、经典分支控制量子指令；
- 64 个 seed 的 Bell 测量关联；
- 重载状态清理、JSON 日志和错误边界。

## 最小 API 示例

```python
from loomq.bonus import QuantumRISCVEmulator

program = """
li x1, 0
li x2, 1
qh x1
qcx x1, x2
qmeasure x3, x1
qmeasure x4, x2
"""

emulator = QuantumRISCVEmulator(seed=2026)
emulator.load_program(program)
registers = emulator.execute()
report = emulator.execution_report()
assert emulator.get_register("x3") == emulator.get_register("x4")
```

二进制工具 API 位于 `loomq.bonus.isa`：

- `encode_instruction()` / `decode_instruction()`
- `assemble_quantum_line()` / `disassemble_word()`
- `word_to_little_endian_bytes()`
