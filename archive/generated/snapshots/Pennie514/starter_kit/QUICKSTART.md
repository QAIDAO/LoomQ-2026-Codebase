# LoomQ 快速入门指南

> 5分钟从零到第一个量子程序

## 前置要求

- Python 3.10+
- pip 或 uv

## 步骤1：安装（1分钟）

```bash
cd starter_kit
pip install -r requirements.txt
```

## 步骤2：第一个量子程序（2分钟）

创建 `my_first_quantum.py`：

```python
from adapter import run

# 这是一个贝尔态（Bell State）：创建两个纠缠的量子比特
qasm_code = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

# 运行100次并统计结果
result = run(qasm_code, "spinq", shots=100)
print("测量结果：", result["counts"])
```

运行：
```bash
python3 my_first_quantum.py
```

**预期输出：**
```
测量结果: {'00': 52, '11': 48}
```

**解释：** 两个量子比特完全纠缠，测量时要么都是0，要么都是1。

## 步骤3：尝试其他平台（1分钟）

修改代码中的后端名称：

```python
result = run(qasm_code, "originq", shots=100)  # 使用本源量子
# result = run(qasm_code, "braket", shots=100)  # 使用AWS Braket
```

**同一份代码，三个平台通用！**

## 步骤4：使用智能体（需要API key）

如果你有DeepSeek API key：

```python
from adapter import agent_chat
import os

# 设置API（评测时由组委会提供）
os.environ["LOOMQ_LLM_BASE_URL"] = "https://api.deepseek.com/v1"
os.environ["LOOMQ_LLM_API_KEY"] = "your-key-here"
os.environ["LOOMQ_LLM_MODEL"] = "deepseek-v4-flash"

# 用自然语言生成量子电路
response = agent_chat("生成一个3比特的GHZ态")
print(response)
```

**无需学习QASM语法，直接描述你想要什么！**

## 常见概念速查

### 什么是量子比特（qubit）？

经典比特只能是0或1，量子比特可以同时是0和1的"叠加态"。测量时会"坍缩"到0或1。

### 常用量子门

- **H (Hadamard)**: 创建叠加态
- **X**: 量子版的NOT门（翻转0↔1）
- **CX (CNOT)**: 两个量子比特间创建纠缠
- **measure**: 测量量子态，得到经典结果

### 什么是纠缠？

两个量子比特纠缠后，测量一个会立即影响另一个，无论距离多远。这是量子计算的核心特性。

## 下一步

- 阅读 `QUANTUM_101.md` 了解更多量子概念
- 查看 `PROJECT_README.md` 了解完整功能
- 尝试 `circuits/` 中的示例电路
- 运行 `python3 evaluator.py` 自测你的实现

## 遇到问题？

**常见错误1：模块找不到**
```
ImportError: No module named 'spinqit'
```
解决：`pip install -r requirements.txt`

**常见错误2：结果为空**
```
counts: {}
```
检查：是否忘记添加 `measure` 语句？

**常见错误3：API调用失败**
```
RuntimeError: LoomQ L2 API returned HTTP 401
```
检查：API key是否正确设置？

## 支持

- 查看 `backend_capabilities.md` 了解各平台能力
- 查看 `gate_identities.md` 了解门分解
- 运行 `python3 evaluator.py --help` 查看测试选项
