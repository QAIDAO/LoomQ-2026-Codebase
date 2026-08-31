# LoomQ Architecture

> 本文档描述 LoomQ 提交方案的完整架构、模块职责、数据流与设计决策。

---

## 模块图

```
                    ┌─────────────────────────────────┐
                    │          adapter.py              │
                    │   transpile() / run() /          │
                    │   agent_chat() / compile_hybrid()│
                    │   (评测器唯一入口)                  │
                    └────┬───────┬───────┬────────────┘
                         │       │       │
              ┌──────────┘       │       └──────────┐
              ▼                  ▼                  ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │ transpiler.py│  │  engine.py   │  │  agent.py    │
     │              │  │              │  │              │
     │ tokenize()   │  │ run()        │  │ agent_chat() │
     │ parse()      │  │ normalize()  │  │ classify()   │
     │ decompose()  │──│              │  │ generate()   │
     │ emit_spinq() │  │  ┌────────┐  │  │ fix()        │
     │ emit_braket()│  │  │sim.py   │  │  │ recommend()  │
     │ emit_originq()│ │  │(纯状态) │  │  │ verify()     │
     └──────────────┘  │  └────────┘  │  └──────────────┘
              │        └──────────────┘           │
              │                                    │
              ▼                                    ▼
     ┌──────────────┐                    ┌──────────────────┐
     │ gate_ident   │                    │ backend_capabil  │
     │ ities.md     │                    │ ities.json       │
     │ (12门分解)   │                    │ (平台能力矩阵)    │
     └──────────────┘                    └──────────────────┘
```

---

## 数据流

### L1: transpile() → run()

```
OpenQASM 2.0 字符串
    │
    ▼
tokenize()           ── 文本 → Token 列表，保留行号用于错误定位
    │
    ▼
parse()              ── Token 列表 → circuit IR (dict)
    │                   {version, includes, qreg, creg, instructions[]}
    ▼
decompose_instructions() ── 12门白名单检查 + 门分解
    │                       ccx → 15×基础门, swap → 3×cx, ...
    ▼
emit_{target}()     ── IR → 目标平台原生格式
    │                   spinq: OpenQASM 2.0
    │                   braket: OpenQASM 3.0
    │                   originq: OriginIR
    ▼
simulate()          ── 目标格式 → 状态向量 → 采样 counts
    │                   (纯 Python statevector, 0 依赖)
    ▼
normalize_result()  ── counts → 统一 JSON Schema
    {backend, job_id, shots, counts, bit_order, timestamp, meta}
```

### L2: agent_chat()

```
用户自然语言 prompt
    │
    ▼
classify_task()      ── 关键词匹配 → 四任务类型之一
    │                   generate / fix / recommend / unknown
    ▼
Tier 1 (规则引擎)   ── 无 LLM 凭据时使用
    │  generate: GHZ-N / Bell 模板
    │  fix:      补头补尾补分号 + h→H 等常见错误
    │  recommend: JSON 约束过滤 (qubits/fidelity/gates)
    ▼
Tier 2 (LLM 管线)  ── LOOMQ_LLM_* 环境变量已配时使用
    │  generate → verify (transpile→run→保真度→retry)
    │  fix      → LLM 语义修复
    │  recommend → LLM 推理 (含约束注入)
    ▼
纯文本响应          ── 含 OpenQASM 代码块 (被 evaluator extract_qasm 提取)
```

---

## 模块职责

### `transpiler.py` (~950 行)

| 函数 | 职责 | 设计理由 |
|------|------|----------|
| `tokenize()` | QASM 文本 → Token 流 | 逐一匹配正则，避免组合正则的组名冲突；保留行号做错误定位 |
| `parse()` | Token 流 → circuit IR | 手写状态机，0 外部依赖；QASM 语法简单 (7 种语句)，不需要完整 parser generator |
| `decompose_instructions()` | IR 中的门 → 白名单基础门 | 独立阶段，目标相关；所有分解公式来自 gate_identities.md (官方已验证) |
| `_decompose_gate()` | 单门 → 基础门序列 | 每条分解标注来源 (§1-§6)；ccx→15 指令, swap→3×cx, cu1→5 指令 |
| `emit_spinq()` | IR → OpenQASM 2.0 | 直接重排指令列表，无语义变换 — SpinQ 原生接受 OpenQASM 2.0 |
| `emit_braket()` | IR → OpenQASM 3.0 | 语法差异: qreg→qubit, cx→cnot, cu1→cp, 测量方向反转 |
| `emit_originq()` | IR → OriginIR | 独立语法体系: 无分号, QINIT/CREG, 门名全大写, 逐比特测量 |
| `transpile()` | 组合上述 3 阶段 | parse → decompose → emit，组合优于继承 |

### `simulator.py` (~200 行)

| 函数 | 职责 | 设计理由 |
|------|------|----------|
| `simulate()` | transpiled QASM → 状态向量 → counts | 纯 Python, 0 依赖, ≤8 qubit 精确计算 |
| `_apply_gate()` | 单门 → 状态向量变换 | 直接矩阵乘法 (2^n × 2^n 酉矩阵) |
| `_sample()` | 状态向量 → 8192 次采样 | 用概率分布 + random.choices, 等价于量子测量公理 |

选择自研模拟器而非 qiskit Aer 的原因: 沙箱环境限制大型二进制安装；≤8 qubit 下 Python 原生计算完全可行。

### `engine.py` (~120 行)

| 函数 | 职责 | 设计理由 |
|------|------|----------|
| `run()` | transpile → simulate → normalize 全流程 | 后端 dispatch table, 新增平台只加一行 |
| `normalize_result()` | raw counts → 统一 JSON Schema | 独立函数，L1 结果归一化器的唯一实现点 |

### `agent.py` (~550 行)

| 函数 | 职责 | 设计理由 |
|------|------|----------|
| `agent_chat()` | L2 评测器入口 | 统一接口，Tier 1/Tier 2 内部切换 |
| `classify_task()` | 判断任务类型 | 关键词匹配，不依赖 LLM |
| `_generate*()` | NL → QASM | Tier 1 规则模板 / Tier 2 LLM + 自验闭环 |
| `_fix*()` | QASM 纠错 | Tier 1 补头补尾 / Tier 2 LLM 语义修复 |
| `_recommend*()` | 后端推荐 | JSON 约束过滤 + LLM 推理 |
| `_self_verify()` | 生成→运行→验证→重试 | 闭环保证输出 QASM 在实际模拟器上可执行 |

### `adapter.py` (~40 行)

评测器唯一入口。四个导出函数 (`transpile`, `run`, `agent_chat`, `compile_hybrid`) 均委托给对应模块，自身不含任何业务逻辑。设计理由：适配层与业务逻辑分离，模块可独立测试和替换。

---

## 关键设计决策

### 1. 为什么手写 Parser 而不是用 ply/lark/antlr？

- LoomQ 的 QASM 子集只有 ~7 种语句类型
- 手写状态机更易调试，选手能逐行理解错误
- 0 外部依赖 = 提交环境零故障点
- 门定义展开 (`gate xxx { ... }`) 是已知的未实现边界，有明确 NotImplementedError

### 2. 为什么 decompose 独立于 emit？

- 分解是"目标相关"的：不同后端的原生门集可能不同
- emit 应该是纯格式化，不应做任何语义判断
- 独立阶段便于未来对不同后端做差异化分解

### 3. 为什么结果归一化放在 engine 而非各 adapter？

- 统一 JSON Schema 是跨平台的，放在一处避免重复
- bit_order 归一化 (always little-endian) 只有一处实现点
- 新平台接入只需加一个 executor 函数，归一化自动复用

### 4. 为什么 Agent 用双层策略 (Tier 1 + Tier 2)？

- Tier 1 (规则引擎): 公开自测不依赖 LLM 凭据，零网络调用
- Tier 2 (LLM): 正式评分 12 用例的完整管线
- 两层独立：配 LLM 用 Tier 2，不配用 Tier 1，互不干扰
- 开局就能过公开自测，赛程中逐步完善 LLM 策略

### 5. 为什么模拟器不用 qiskit Aer？

- 沙箱环境限制大型二进制 pip install
- ≤8 qubit 下 Python 原生矩阵运算完全精确
- 0 依赖意味着评估器可以 100% 复现结果
- 状态向量模拟是确定性的 (固定种子 = 固定结果)

---

## 文件清单

```
starter_kit/
├── adapter.py              # 评测器入口 (4 个导出函数)
├── transpiler.py           # QASM 解析 + 门分解 + 三平台 IR 生成
├── simulator.py            # 纯 Python statevector 模拟器
├── engine.py               # 执行引擎 + 结果归一化
├── agent.py                # L2 LLM 智能体
├── llm_client.py           # LLM 客户端工具 (starter kit 提供)
├── submission.yaml         # 参赛声明
├── requirements.txt        # 依赖声明 (核心 0 依赖)
├── ARCHITECTURE.md         # 本文档
├── circuits/
│   ├── bell.qasm           # Bell 态测试电路
│   └── ghz3.qasm           # GHZ-3 态测试电路
├── evidence/
│   └── README.md           # 人工评分证据
└── examples/
    ├── run_spinq.py        # SpinQ 示例
    ├── run_braket.py       # Braket 示例
    └── run_originq.py      # OriginQ 示例
```

---

## 构建与测试

```bash
# 0 依赖安装 (核心模块只依赖 Python 标准库)
# 无需 pip install

# 运行公开自测
cd starter_kit
python -m starter_kit.evaluator --level declared --target spinq,braket,originq

# 单独测试 L1
python -m starter_kit.evaluator --level l1 --target spinq,braket,originq

# 单独测试 L2 (需要 LOOMQ_LLM_* 环境变量做 Tier 2)
python -m starter_kit.evaluator --level l2

# 模块自测
python -m starter_kit.simulator
python -m starter_kit.transpiler
python -m starter_kit.engine
python -m starter_kit.agent
```
