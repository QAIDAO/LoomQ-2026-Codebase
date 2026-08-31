# LoomQ 2026 — 量子通用中间层

> **为谁而做**：让没有量子物理背景、只会 Python 和线性代数的开发者，第一次能用自己的代码驱动真实量子计算机。

## 一键自测

```bash
cd starter_kit
pip install -r requirements.txt   # 可选，无 SDK 时自动使用内置无噪声模拟器
python3 evaluator.py --json-out report.json
```

## 架构

```
OpenQASM 2.0 输入
    ├── transpilers.py  → SpinQ / OriginQ / Braket 原生 IR
    ├── qasm_engine.py  → 无噪声 statevector 模拟（本地自测）
    ├── backends.py     → 三平台 SDK 执行 + 统一 JSON Schema 输出
    ├── agent.py        → L2 自然语言 Agent（DeepSeek via LOOMQ_LLM_*）
    └── hybrid_compiler.py → L3 Hybrid-QASM → RISC-V 汇编
```

## L2 Agent 调试

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<YOUR_KEY>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
python3 -c "from starter_kit.adapter import agent_chat; print(agent_chat('生成一个3比特GHZ态'))"
```

## CLI 入口（L2 交互体验）

```bash
python3 starter_kit/cli.py
```

## 平权叙事

本工具面向**跨界创作者、女性开发者、文科转码群体**——他们懂问题、懂产品，却被 OriginIR/QCIS/Qiskit 方言墙挡在门外。LoomQ 用统一的 OpenQASM 中间层 + 自然语言 Agent，让「把一件事翻译成另一种语言」成为唯一需要掌握的技能。

## 提交

```bash
python3 starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>
```

然后在 https://github.com/QAIDAO/LoomQ-2026 创建「LoomQ 最终提交」Issue。
