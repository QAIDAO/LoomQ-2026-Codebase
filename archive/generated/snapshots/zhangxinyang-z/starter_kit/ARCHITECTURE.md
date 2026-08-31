# LoomQ 架构与复现说明

## 模块

- `adapter.py`：统一的 L1 转译/模拟接口、L2 Agent 接口、L3 Hybrid-QASM 编译器。
- `llm_client.py`：从 `LOOMQ_LLM_*` 环境变量读取配置并调用 OpenAI-compatible 服务。
- `evaluator.py`：公开 L1/L2/L3 契约自测。
- `riscv_emulator.py`：L3 经典控制流的 TinyRISCV 执行器。
- `chat.py`：面向初学者的自然语言 CLI。

## 复现

```bash
python -m starter_kit.evaluator --level all --target spinq,originq,braket
python -m starter_kit.chat "生成一个 3 比特 GHZ 态并进行全测量"
```

L2 CLI 需要先配置 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY` 和 `LOOMQ_LLM_MODEL`。
使用 Docker 运行全部已声明 Level 时，也要通过 `-e` 传入这三个变量。
