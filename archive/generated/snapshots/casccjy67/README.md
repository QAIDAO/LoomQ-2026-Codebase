# LoomQ — 量子接入平权计划

> 让不懂"黑话"的人，也能指挥最前沿的算力

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m starter_kit.tests.test_transpile

# 运行 Bell 态电路 (Braket 本地模拟器)
python -c "
from starter_kit.adapter import run
from starter_kit.tests.circuits import BELL_STATE
result = run(BELL_STATE, 'braket', shots=8192)
print(result)
"
```

## 架构

```
starter_kit/
├── adapter.py              # 主接口 (transpile / run / agent_chat / compile_hybrid)
├── submission.yaml         # 提交声明
├── transpiler/             # L1: 通用中间层
│   ├── ir.py               # 量子电路中间表示
│   ├── parser.py           # OpenQASM 2.0 解析器
│   ├── base_backend.py     # 抽象后端基类
│   ├── spinq_backend.py    # 量旋 SpinQit 适配
│   ├── originq_backend.py  # 本源 pyQPanda3 适配
│   └── braket_backend.py   # AWS Braket 适配
├── agent/                  # L2: 智能体
│   └── chat.py             # agent_chat + 自验闭环
├── hybrid_compiler/        # L3: 混合编译器
│   ├── lexer.py            # Hybrid-QASM 词法分析
│   ├── parser.py           # 语法分析 → AST
│   ├── codegen.py          # RISC-V 代码生成
│   └── compiler.py         # 编译入口
└── tests/                  # 测试
    ├── circuits.py         # 公开电路集
    └── test_transpile.py   # 全量测试
```

## 接口说明

### L1: transpile & run

```python
from starter_kit.adapter import transpile, run

# 转译 QASM 到目标后端原生格式
ir_str = transpile(qasm_str, target="braket")  # 'spinq' | 'originq' | 'braket'

# 运行电路
result = run(qasm_str, target="braket", shots=8192)
# result = {
#   "backend": "braket_local_simulator",
#   "job_id": "...",
#   "shots": 8192,
#   "counts": {"00": 4096, "11": 4096},
#   "bit_order": "little",
#   "timestamp": "2026-08-24T12:00:00Z",
#   "meta": {"transpiled_gates": 2, "depth": 1}
# }
```

### L2: agent_chat

```python
from starter_kit.adapter import agent_chat

# 需要设置环境变量:
#   LOOMQ_LLM_BASE_URL - 模型服务地址
#   LOOMQ_LLM_API_KEY  - API密钥
#   LOOMQ_LLM_MODEL     - 模型名称

response = agent_chat("生成一个3比特GHZ态并测量")
print(response)  # 返回包含QASM代码的文本
```

### L3: compile_hybrid

```python
from starter_kit.adapter import compile_hybrid

quantum_ops, riscv_text = compile_hybrid(hybrid_qasm_str)
# quantum_ops: [{"name": "h", "qubits": [0], ...}, ...]
# riscv_text: "li x1, 100\n beq x10, x6, L1\n ..."
```

## 设计决策

### 1. 统一中间层架构
- 所有后端共享同一个 `Circuit` IR，避免三套硬编码
- `BaseBackend` 抽象类定义 `transpile()` 和 `run()` 接口
- 新增后端只需继承 `BaseBackend` 并实现两个方法

### 2. cu1 门处理
- SpinQit 不支持 cu1，使用标准分解: `cu1(λ) → rz(λ/2) + cx + rz(-λ/2) + cx + rz(λ/2)`
- 分解只使用白名单内的门 (rz, cx)，不引入额外门

### 3. Bit Order 归一化
- 所有后端结果统一归一化为 little-endian (c[0] = 最右位)
- 在 `BaseBackend._normalize_counts_little()` 中统一处理

### 4. L2 自验闭环
- Agent 生成 QASM → 调用 L1 的 `run()` 自验 → 验证失败则重试
- 从 `LOOMQ_LLM_*` 环境变量读取配置，不硬编码

### 5. L3 真正的编译器
- 词法分析 → 语法分析 (递归下降) → 代码生成
- 非硬编码输出，可处理任意符合文法的 Hybrid-QASM

## 平权叙事

LoomQ 让以下群体第一次能够使用量子计算：

1. **跨界创造者** — 产品经理、设计师，有独特问题意识但无量子物理背景
2. **学生与教育者** — 可用量子计算做教学演示，无需深入硬件方言
3. **女性及少数群体** — 打破量子计算领域的精英主义壁垒

通过自然语言 Agent，用户只需描述意图，无需编写 QASM 代码，即可在真实量子计算机上运行实验。
