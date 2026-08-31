# LoomQ 中间层架构说明

本文档回答评委关心的问题：**为什么这是"一个真正抽象的中间层"，而不是三套硬编码分支。**

## 数据流

```text
                 ┌─────────────────────────┐
 OpenQASM 2.0 →  │ qasm.py: 解析器          │ → Circuit IR（唯一内部表示）
                 └─────────────────────────┘            │
        ┌───────────────────────┬───────────────────────┤
        ▼                       ▼                       ▼
 transpilers.py          transpilers.py           transpilers.py
 emit_spinq              emit_originq             emit_braket
 (OpenQASM 2.0)          (OriginIR 子集)          (OpenQASM 3)
        │                       │                       │
        └───────────┬───────────┴───────────┬───────────┘
                    ▼                       ▼
        parse_target_ir() 把目标 IR 读回 Circuit IR
                    ▼
        simulator.py: 无依赖态矢量参考模拟器 → 统一 counts schema
```

关键设计决策：

1. **单一 IR，纯函数发射器。** `transpile()` = 解析 → IR → 发射。三个后端共享同一解析器与 IR；
   后端支持只是 IR 的纯函数。新增后端 = 新增一个发射器函数，无需触碰其他代码。
2. **`run()` 执行的是转译产物本身。** 每次 `run()` 都把 `transpile()` 的输出**解析回 IR** 再采样。
   转译器与执行器不可能互相掩盖错误——这也是我们的免费回归测试（selftest.py 利用同一性质
   对 GHZ-5 / QFT-4 / Grover-3 做保真度验证，QFT 还逐输入态与 16x16 DFT 矩阵数值对比）。
3. **位序归一化在中间层完成。** 模拟器以小端约定（counts key 最右字符为 c[0]）产出，
   三家后端输出完全一致。
4. **cu1 的唯一降级点。** Braket 的 stdgates.inc 无 cu1；按 `gate_identities.md` 已验证的
   p/cnot 恒等式降级（`transpilers._lower_for_braket`），其余 11 门全部直译。

## 模块清单（全部零第三方依赖，Python 标准库）

| 文件 | 职责 |
|---|---|
| `loomq_core/qasm.py` | OpenQASM 2.0 解析器（12 门白名单 + 内部 u1/p），参数表达式安全求值 |
| `loomq_core/simulator.py` | 态矢量模拟器：全部门矩阵、受控门、测量采样（little-endian counts） |
| `loomq_core/transpilers.py` | 三个目标 IR 发射器 + 对应的回读解析器 |
| `loomq_core/hybrid.py` | L3：Hybrid-QASM 经典块递归下降解析 → RISC-V 代码生成 |
| `loomq_core/agent.py` | L2：系统提示词（含后端能力表）、模型调用、QASM 抽取与自检重试 |
| `adapter.py` | 合同接口（transpile / run / agent_chat / compile_hybrid） |
| `loomq_cli.py` | 新手交互 CLI：自然语言 → 电路 → 本地运行 → 直方图 + 大白话解释 |
| `loomq_web.py` + `webui/index.html` | 零依赖 Web 界面：Agent 对话、实验台（直方图 + Qiskit 标准电路图）、三后端 IR 对比 |
| `run_real.py` | L1 真机证据运行器：转译 → 平台提交 → 原始结果落盘 → 主峰校验（无 Mock） |
| `riscv_emulator_ext.py` | Bonus：LoomQ-Q 量子 RISC-V 扩展模拟器（规格见 quantum_riscv_spec.md） |
| `check_secrets.py` | 提交前密钥/隐私扫描（工作树 + git 历史），防止 Token 入库 |
| `selftest.py` | 扩展自测：8 类电路 × 3 后端保真度 + 25 组随机 L3 用例全注入比对 |
| `test_quantum_riscv.py` | Bonus 端到端测试 |
| `test_l2_plumbing.py` | L2 本地联调（stub 模型服务，验证真实模型调用链路） |
| `test_web_api.py` | Web UI 端到端测试（19 项：三后端保真度/错误路径/chat 提示） |

## L2 智能体工作原理

`agent_chat` 的提示词把三类任务（意图生成 / 纠错 / 选后端）的硬性规则与
`backend_capabilities.json` 的全文一并注入系统消息；模型回答后，凡是包含 QASM 的回答
都会被抽取、解析、并在本地模拟器试跑——失败则把错误信息回喂给模型重试（至多 3 轮）。
除传输外不依赖任何服务；端点、密钥、模型名全部来自 `LOOMQ_LLM_*` 环境变量。

## L3 编译器工作原理

经典块使用真正的递归下降解析（整数字面量、`r1..r9`、`c[k]`、`+ - == !=`、嵌套 if/else），
代码生成器将 `r_i` 映射到 `x_i`、`c[k]` 映射到 `x(10+k)`，x27–x31 为求值暂存器。
赋值统一先求值到 x27 再写回目标寄存器，正确处理 `r1 = c[0] + r1 - 14` 这类自引用表达式。
`selftest.py` 用独立的 Python 参考解释器对随机生成的用例做**全测量注入**交叉验证。

## 可复现性

- 零依赖：`requirements.txt` 无需任何第三方包，`python:3.10-slim` 容器直接可跑。
- 一键自检 + 启动：fork 根目录 `./run.sh`（密钥扫描 → selftest → 量子 RISC-V → Web API 测试 → 打开 Web UI）。
- 手动分步：`python3 starter_kit/evaluator.py --level all --target spinq,originq,braket`
  与 `python3 starter_kit/selftest.py`、`python3 starter_kit/test_quantum_riscv.py`、
  `python3 starter_kit/test_web_api.py --spawn`。
- L2 本地调试：`export LOOMQ_LLM_BASE_URL/LOOMQ_LLM_API_KEY/LOOMQ_LLM_MODEL` 后
  `python3 starter_kit/evaluator.py --level l2`。

## 本工具让谁第一次用上量子计算？

**完全没写过 QASM 的跨界创作者。** 打开 `loomq_cli.py`，说一句"帮我做一个两个比特永远
同面的硬币"，就能得到可运行的电路、真实的采样直方图和一句人话解释。转译层保证这段电路可以不改一字地流向量旋、本源、Braket 任一后端——用户不需要知道 OriginIR
或 OpenQASM 3 的存在。

*AI 辅助声明：本项目代码由 AI 辅助编写，各模块工作原理如上所述，可供异步审查。*
