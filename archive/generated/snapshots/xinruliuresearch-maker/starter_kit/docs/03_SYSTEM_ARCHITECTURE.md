# 03 · 系统架构

本文描述当前实现及其真实性边界。功能状态以 `DEVELOPMENT_STATUS.md` 与可复跑测试为准；架构存在不代表隐藏评测或人工得分已确认。

## 1. 产品目标与主流程

LoomQ Pegasus 面向能描述科研或计算问题、但不会 OpenQASM、不熟悉平台方言、也难以自行判断结果可信度的跨学科研究者、学生和工程实践者。系统把生成或修复、转译、执行和验证收敛为一条可审计工作流，同时明确不承诺量子优势、科学结论自动正确或模拟器等同真机。

```text
自然语言任务或 OpenQASM
  → 输入边界与有限意图
  → 生成 / 修复 / 规范化
  → OpenQASM lexer + parser + immutable AST
  → SpinQ QASM 2 / OriginIR / Braket QASM 3
  → 独立回读与语义准入
  → LoomQ 本地参考态矢执行
  → counts / shots / little-endian / schema 验证
  → UI 解释与请求级原子证据
```

正式评分主链只读取 `starter_kit/`。`.codex_reference/`、本地附件和用户目录不在 import graph 中。

## 2. 固定外部合同

`adapter.py` 保持以下签名：

```python
transpile(qasm_str: str, target: str) -> str
run(qasm_str: str, target: str, shots: int) -> dict
agent_chat(prompt: str) -> str
compile_hybrid(hybrid_qasm_str: str) -> tuple[list, str]
```

adapter 只做基本参数检查、委派内部实现和稳定错误边界。它不承载 parser、模拟器、Agent 或 Hybrid 编译器主体，也不在 import 时联网、启动服务或写持久文件。

## 3. 分层与依赖方向

```text
adapter.py
  ↓
loomq/facade.py
  ├── qasm/       lexer、AST、parser、语义验证、规范化、序列化
  ├── targets/    三目标 emitter、registry、独立 round-trip parser
  ├── runtime/    标准库态矢、Provider、结果归一化和验证
  ├── agent/      有限 L2 工作流与确定性 admission
  ├── hybrid/     Hybrid AST、解释器、寄存器分配、compiler
  ├── bonus/      与正式 L3 隔离的量子 RISC-V
  ├── hardware/   可选真实 QPU 运行器与原子证据契约
  └── ui/         loopback HTTP 产品入口和请求级 workspace
```

依赖不变量：

1. `qasm/` 不依赖目标、Agent、UI 或硬件；
2. `targets/` 消费已验证 AST，不用公开样例字符串特判；
3. `runtime/` 不解释自然语言；
4. `agent/` 编排模型和确定性工具，不能替代 L1 parser/runtime；
5. `hybrid/` 不修改官方 `riscv_emulator.py`；
6. `bonus/` 与 `compile_hybrid` 的正式路径隔离；
7. `hardware/` 是可选外部路径，不影响离线评分 import；
8. `ui/` 调用内部服务/facade，不成为 adapter 的反向依赖。

## 4. L1 结构化编译与参考执行

### OpenQASM 前端

`loomq/qasm/` 实现 lexer、递归下降 parser、不可变 AST、语义归一化和确定性序列化，覆盖：

- 多 `qreg` / `creg` 和全局索引映射；
- `h x s sdg t tdg rz ry cx cu1 swap ccx`；
- `pi`、科学计数法、括号与 `+ - * /`；
- 逐位、整寄存器和乱序 measurement；
- 门 arity、参数数量、寄存器类型、索引、测量宽度与有限数检查。

不支持题面外的自定义 gate、barrier、reset 或 OpenQASM `if`；这些输入快速失败，不做猜测式降级。

### Target Provider

三个 Provider 生成完整目标文本：

| target | 输出 | 当前 `run()` 执行引擎 |
|---|---|---|
| `spinq` | OpenQASM 2.0 | LoomQ reference statevector |
| `originq` | OriginIR | LoomQ reference statevector |
| `braket` | OpenQASM 3.0 | LoomQ reference statevector |

目标文本由独立子集 parser 回读并与规范 AST 做语义比较。`run()` 不调用厂商 SDK；结果 metadata 明确 `native_sdk_used=false`。

### 结果不变量

| 字段 | 不变量 |
|---|---|
| `backend` | 明确为 LoomQ 本地参考模拟器，不使用厂商 QPU 名冒充 |
| `job_id` | 请求级本地追踪 ID；只有硬件路径才接受厂商 job ID |
| `shots` | 1..100000 的非 bool 整数，与请求一致 |
| `counts` | 固定宽度二进制 key、非负整数 value、合计严格等于 shots |
| `bit_order` | 固定 `little`，key 最右字符为 `c[0]` |
| `timestamp` | 带时区 ISO 时间 |
| `meta` | 含实际执行引擎；不含 `is_mock=true` 或 secret |

参考态矢支持题面 12 门；默认最终测量最多 20 qubit，中途测量 fallback 最多 12 qubit。它是逻辑 oracle，不模拟厂商噪声、拓扑、队列或可用性。

## 5. L2 有限工作流

```text
RECEIVE → BOUNDARY_CHECK → INTENT → MODEL_REQUEST
       → BOUNDED_JSON → DETERMINISTIC_GENERATE/REPAIR/FILTER
       → L1_PARSE_AND_RUN_ADMISSION
       → SUCCESS
          或（仅准入失败）ONE_MODEL_REPAIR → FINAL_ADMISSION
```

关键约束：

- 每个有效正式 case 至少一次真实 OpenAI-compatible HTTP 请求；
- 正常一次，只有准入失败才允许第二次；
- URL、Key、模型与 timeout 只读 `LOOMQ_LLM_*`；
- JSON 有大小/深度边界，错误和日志不回显 secret；
- Bell、GHZ-n、均匀叠加、纠缠链和计算基态由参数化代码合成；
- 修复时 prompt 明示意图优先于不可信模型候选；
- 推荐只从 `backend_capabilities.json` 机械筛选规范 ID；
- 最终最多返回一份明确 QASM 或一个规范 backend ID，不暴露 chain-of-thought。

本地 stub 真实监听 socket 并接收模型 HTTP 请求，用于验证传输和失败策略；它不等于正式 `deepseek-v4-flash` 结果。

## 6. L3 与 Bonus

正式 L3：

```text
Hybrid-QASM → lexer/parser → Hybrid AST
  ├── reference interpreter（测试 oracle）
  ├── ordered quantum statements
  └── register allocator → Tiny RISC-V emitter → official emulator
```

映射固定为 `r1..r9 → x1..x9`、`c[k] → x10+k`。只发射 `li/add/sub/addi/beq/bne/j`；label 确定性唯一，临时寄存器避开用户与测量寄存器，量子序列保持原顺序。

Bonus 在 `loomq/bonus/` 中继承官方 TinyRISCV 接口并添加 RISC-V `custom-0` 量子指令编码、反汇编、态矢与测量日志。它不改变 L3 输出合同，并始终报告 `hardware_execution=false`。

## 7. UI 与 Evidence

`python -m loomq.ui.server` 启动仅绑定 `127.0.0.1` 的标准库 HTTP 服务。静态资源为本地 HTML/CSS/JavaScript/SVG，无 CDN、远程字体或远程脚本。

工作台提供：

- QASM、Hybrid 和 Agent 请求入口；
- 三目标 IR tabs、SVG 电路线与门、counts 柱状图和 Top states；
- 中英文、新手术语、键盘焦点、跳转链接和 390px 窄屏布局；
- 有行列位置的结构化错误、保守修复和重试建议；
- 请求级 UUID 目录、原子写入、SHA-256 manifest 和 artifact allowlist。

adapter 仍然无状态。UI workspace 只服务产品演示与证据，不成为评分接口的隐藏前置条件。UI 始终区分“目标方言产物”“LoomQ 本地模拟”和“未运行 Vendor QPU”。

## 8. 真实硬件准备层

`scripts/hardware/run_spinq.py` 与 `run_originq.py` 有互斥模式：

- `--dry-run`：验证输入和命令，不读取凭证、不联网、不写 job ID；
- `--record`：必须由账号持有人提供环境凭证并明确选择真实 QPU；只有完整且通过 schema/时间/job/计数检查的响应才原子写入五件证据。

当前只验证了 dry-run 和证据契约。仓库没有真机 job、原始 QPU counts 或截图，因此 Evidence 不勾 L1 真机。

## 9. 安全与可复现边界

- 正式验证 Python 3.10.11；核心与 UI 无第三方依赖；
- L1/L3/Bonus/UI 本地路径零外网；L2 只访问注入模型端点；硬件路径只在显式 `--record` 下访问选定厂商；
- 无 `eval`、`exec`、shell 拼接或 import 副作用；
- secret redaction、路径 allowlist、请求大小、shots、JSON 深度和证据原子性均有测试；
- 当前 119/119 单元/集成测试通过，另有公开与随机差分报告；
- Dockerfile 已提供但尚未在本机构建；标准 clone 已完成迁移和全量复测，`main` 已 commit/push 且远端页面已核验。官方预检已在一个已 push 的干净 HEAD 上完整通过；任何后续 commit 必须重跑，Final Submission Issue 与接收回执仍待完成。
