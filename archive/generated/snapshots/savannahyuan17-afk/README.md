# LoomQ 2026 — 量子计算跨平台编译与智能体

LoomQ 黑客松参赛项目。实现 OpenQASM 2.0 电路到 SpinQ / Braket / OriginQ 三平台的统一编译、执行与 LLM 智能体交互。

## 快速开始

```bash
# 0 依赖安装 — 只使用 Python 标准库
# Python 3.10+ 即可

# 一键构建与测试
bash starter_kit/setup.sh

# 或手动运行评测器
cd starter_kit
python -m starter_kit.evaluator --level declared --target spinq,braket,originq
```

## 模块架构

```
OpenQASM 2.0 ─→ transpiler ─→ simulator ─→ 统一 JSON 结果
                    │
                    ├── spinq   (OpenQASM 2.0)
                    ├── braket  (OpenQASM 3.0)
                    └── originq (OriginIR)

自然语言 ─→ agent ─→ QASM ─→ 执行 ─→ 自验闭环
```

## 文档

- **架构说明**: [`starter_kit/ARCHITECTURE.md`](starter_kit/ARCHITECTURE.md)
- **评分证据**: [`starter_kit/evidence/README.md`](starter_kit/evidence/README.md)
- **赛题手册**: starter_kit 内 `gate_identities.md`, `target_ir_contract.md`, `QUANTUM_101.md`

## 进度

| 层级 | 状态 | 说明 |
|:---|:---:|------|
| L1 入门 | ✅ | 三后端 6/6 公开电路通过 |
| L2 智能体 | ✅ | agent_chat 公开自测通过 |
| L3 混合编译 | ✅ | Hybrid-QASM → RISC-V 汇编 |
| 工程化 | ✅ | 架构文档 + 一键脚本 + 证据包 |
