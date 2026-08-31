# LoomQ 赛题模块拆解

> 来源: LoomQ-赛题.docx + LoomQ-赛题手册.pdf
> 赛事: SheNicest 2026 · 量子接入平权计划
> 截止: 2026-08-25 12:00 UTC+8

---

## 1. 完整模块清单 (共 23 个模块)

### L1 - 通用中间层 (45分)

| # | 模块 | 职责 | 关键细节 |
|---|------|------|----------|
| 1 | QASM 解析器 | 解析 OpenQASM 2.0，提取门序列、寄存器声明、测量指令 | 输入是标准 QASM 字符串 |
| 2 | 门映射/分解层 | 12 门白名单逐门映射到三家 SDK 原生支持 | 不支持的门用 gate_identities.md 等价分解 |
| 3 | SpinQ Adapter | QASM → SpinQit (OpenQASM 2.0)，调用 spinqit SDK | `uv pip install spinqit`，自带 Taurus 模拟器 |
| 4 | OriginQ Adapter | QASM → OriginIR，调用 pyQPanda/QPanda3 | 需自行申请 API Token |
| 5 | Braket Adapter | QASM → OpenQASM 3，调用 braket SDK | LocalSimulator 免费，无需 AWS 账号 |
| 6 | 执行引擎 | 调用各平台 SDK 运行电路，shots=8192 | 隔离子进程执行，选手只收到当前输入 |
| 7 | 结果归一化器 | 各平台结果 → 统一 JSON Schema | bit_order 固定 "little"，位序差异在中间层归一化 |
| 8 | Fidelity 自测 | Hellinger 保真度 ≥ 0.97 | 公开电路: Bell, GHZ-3 |

**门白名单 (12门)**:
- 单比特无参: h, x, s, sdg, t, tdg
- 单比特含参: rz(θ), ry(θ)
- 两比特: cx, cu1(θ), swap
- 三比特: ccx

**评测电路 (8个)**: Bell, GHZ-3, GHZ-5, QFT-4, Grover-3, Random-Circuit×3
- 公开自测: Bell, GHZ-3
- 隐藏: 其余由组织方评测器在内存中按私有种子生成

**L1 评分阶梯**:
| 档位 | 条件 | 分值 |
|------|------|------|
| 入门 (评奖资格线) | ≥2 个模拟器后端跑通公开电路 | 12 |
| 进阶 | 第三平台打通 / 隐藏电路保真度达标 | 至 35 |
| 真机 | 每平台真机主峰命中 +5 (至多 2 平台) | +10 |
| 满分 | 三平台统一适配 + 8 电路全过 + 2 平台真机 | 45 |

**统一结果 Schema**:
```json
{
  "backend": "spinq_taurus",
  "job_id": "xxxxxxxx",
  "shots": 8192,
  "counts": {"000": 4102, "111": 4090},
  "bit_order": "little",
  "timestamp": "2026-08-01T12:00:00Z",
  "meta": {"transpiled_gates": 12, "depth": 5}
}
```

### L2 - 智能体 Agent (30分)

| # | 模块 | 职责 | 关键细节 |
|---|------|------|----------|
| 9 | agent_chat() 接口 | 评测器直接调用的入口函数 | starter-kit/adapter.py 中实现 |
| 10 | NL→QASM 生成器 | 自然语言意图 → 正确的 OpenQASM 2.0 | 评测: 生成QASM经无噪声模拟器验证 Fidelity≥0.97 |
| 11 | 代码纠错器 | 识别 QASM 语法/语义错误，保持意图下修复 | 评测: 修复产物必须语义等价于目标态 |
| 12 | 后端推荐器 | 根据比特数/拓扑/排队/成本推荐 | 评测: 回复须含规范后端标识，按 backend_capabilities.json 核对 |
| 13 | 自验闭环 | 生成QASM → 调L1的run() → 验保真度 → 不对则重试 | 推荐工程方案，非硬性要求 |
| 14 | 交互入口 (可选) | Web/CLI 供零基础用户操作 | 仅冲完整30分时需要；客观20分不需要 |

**L2 约束**:
- 正式评测: DeepSeek deepseek-v4-flash 驱动
- 环境变量: LOOMQ_LLM_BASE_URL, LOOMQ_LLM_API_KEY, LOOMQ_LLM_MODEL
- 不得硬编码 API 地址、密钥或模型名称
- 每 case 最多调用 3 次，累计 8000 输入 token / 2000 输出 token，120 秒时限
- 共 12 个 L2 case (2 个私有种子)
- 客观分 = 各变体通过率 × 20

### L3 - Hybrid-QASM × RISC-V 混合编译 (15分)

| # | 模块 | 职责 | 关键细节 |
|---|------|------|----------|
| 15 | Hybrid-QASM 解析器 | 解析扩展的 OpenQASM 2.0 + classical{} 块 | 需自写 parser/lexer |
| 16 | 量子/经典分离器 | 剥离量子门/测量指令 vs 经典控制逻辑 | 输出两部分 |
| 17 | 经典块编译器 | if/else/赋值 → RISC-V 汇编 | 支持 li, add, sub, addi, beq, bne, j |
| 18 | compile_hybrid() 接口 | 返回 (量子操作序列, RISC-V 汇编文本) | Tuple[list, str] |

**Hybrid-QASM 语法示例**:
```
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
measure q[0] -> c[0];
classical {
  if (c[0] == 1) { r1 = 100; }
  else { r1 = 10; }
  r1 = r1 + 5;
}
cx q[0], q[1];
```

**经典块文法**: 整数字面量, r1..r9 寄存器, + - == != 运算符, if/else, 顺序赋值
**寄存器映射**: c[k] → x10, x11, ...; r1..r9 → x1..x9
**评测**: 随机生成用例，穷举所有测量值组合，逐一比对寄存器终态

### 跨层级模块

| # | 模块 | 职责 | 分值 |
|---|------|------|------|
| 19 | 提交基础设施 | submission.yaml, adapter.py, prepare_submission.py | — |
| 20 | 工程化 | 一键setup+run, README, 依赖锁定, 架构文档 | 10 |
| 21 | 平权叙事 | "你的工具让哪一类原本进不来的人第一次能用上量子计算" | (含在工程10分内) |
| 22 | Bonus: 自定义量子RISC-V扩展指令 | 自定义opcode + 模拟器扩展 + 端到端测试 | +8 |
| 23 | Bonus: 包容性设计与视觉叙事 | 新手引导, 可视化 | +4 |

---

## 2. 官方接口 (4个函数)

```python
def transpile(qasm_str: str, target: str) -> str:
    """target ∈ {'spinq','originq','braket'}"""

def run(qasm_str: str, target: str, shots: int) -> dict:
    """返回统一 Schema 字典"""

def agent_chat(prompt: str) -> str:
    """[L2] 从 LOOMQ_LLM_* 读配置"""

def compile_hybrid(hybrid_qasm_str: str) -> Tuple[list, str]:
    """[L3] 返回 (量子操作序列, RISC-V 汇编)"""
```

---

## 3. 三个平台接入方式

| 平台 | 安装 | 模拟器 | 真机 |
|------|------|--------|------|
| 量旋云 SpinQit | `uv pip install spinqit` | Taurus 本地模拟器 (推荐首选) | 超导真机 |
| 本源量子云 | `pyqpanda` / `QPanda3` | 本地模拟器 | 悟空真机 |
| AWS Braket | braket SDK | LocalSimulator (免费) | AWS 云端 |

---

## 4. 评分总表

| 模块 | 分值 | 核心考点 |
|------|------|----------|
| L1 通用中间层 | 45 | 是否真正"统一"地打通多平台 |
| L2 智能体 | 30 | 能否让不懂 QASM 的人也能用 |
| L3 混合编译 | 15 | 量子-经典混合编译硬核能力 |
| 工程与产品化 | 10 | 可复现、可交付、有叙事 |
| Bonus | +12 | 极客深度与包容性设计 |
| **合计** | **100 (+12)** | |

---

## 5. 关键约束与红线

- **入门档 = 评奖资格线**: ≥2 个模拟器后端跑通公开电路 (12分)，纯本地可完成
- **反作弊**: 隐藏电路/L2 prompt变体/L3随机用例均评测时生成，硬编码无法通过
- **三套硬编码分支不算"通用"**: 评委会审查架构是否真正抽象
- **可复现性**: 依赖精确锁定版本，固定 Linux 容器构建，40位 commit SHA
- **提交方式**: fork QAIDAO/LoomQ-2026，运行 prepare_submission.py，创建 Issue
