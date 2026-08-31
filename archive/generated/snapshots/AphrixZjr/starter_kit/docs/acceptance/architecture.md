# 当前实现架构

本文专门说明人工验收时的代码架构。事实来源是当前源码。

## 边界与入口

- `adapter.py` 是唯一评分接口，分别把 L1、L2、L3 委托给 `loomq_l1.py`、`loomq_l2.py`、`loomq_l3.py`。
- `loomq_l1.py` 负责 OpenQASM 2 解析、统一 `Circuit` 中间表示、三种目标 IR 发射、计数归一化和执行分派。
- `l1_spinq.py`、`l1_originq.py`、`l1_braket.py` 只负责供应商 SDK 适配；相应的 `*_hardware.py` 与 `run_*_hardware.py` 是显式确认、凭证隔离、结果脱敏的真机路径，不进入默认本地评分流程。
- `loomq_l2.py` 实现客观评分用 `agent_chat()`；模型做自然语言理解，本地能力表、QASM parser 和确定性模拟器负责约束与验证。
- `web/app.py` 的 `ExperimentStore` 是交互产品服务层，复用 L1 parser、参考模拟器和后端能力表；`web/server.py` 暴露静态页面及会话、运行、Agent API；`web/static/` 负责单页工作台。
- `loomq_l3.py` 生成官方 `riscv_emulator.py` 可执行的经典控制流。`riscv_emulator.py` 在保持 `TinyRISCVEmulator` 文本 RV32 子集的同时，公开量子 custom opcode 的汇编、解码和机器码执行扩展；`quantum_riscv.py` 是该扩展的兼容导入层。

L1 不是三套互不相关的硬编码转换器；共享层与平台边界如下：

| 阶段 | 共享职责 | 平台特定职责 |
| --- | --- | --- |
| 输入 | `loomq_l1.parse_qasm()` 解析寄存器、门、测量和参数，形成统一 `Circuit` | 无 |
| 转译 | 共享门语义、位序和分解规则 | SpinQ OpenQASM 2.0、OriginIR、Braket OpenQASM 3.0 三种正式 emitter |
| 执行 | shots、counts、bit order 与结果 schema 归一化 | `l1_spinq.py`、`l1_originq.py`、`l1_braket.py` 调用各自本地 SDK |
| 真机 | 统一结果脱敏和证据格式 | 各 `*_hardware.py` 显式确认、提交、恢复和 provider 响应解析 |

共享回归覆盖全局相位等价、参数化/分解门、非连续测量、多量子/经典寄存器 flatten 和非对称位序探针；因此这些边界不会由某个平台适配器自行解释。

## 数据流

1. L1 输入经 `parse_qasm()` 进入统一 `Circuit`，再按目标发射原生 IR 或交给供应商运行器，最终统一为 `{backend, job_id, shots, counts, bit_order, timestamp}`，运行器有额外信息时附加 `meta`。
2. L2 客观入口把单次 prompt 与本地能力事实发送给模型，随后用本地规则校验结构化候选；请求状态不跨 case 共享。
3. Web 入口把 QASM、目标、revision、验证、运行快照和对话保存在进程内 `ExperimentSession`；顶部 Bell 按钮只把当前预设填入 Agent 输入框，发送后才由受限 Agent 工具推进。每个会话由独立可重入锁串行提交，并以不随撤销恢复旧值的 `workbench_revision` 做 compare-and-swap；QASM 同步、Bell 引导推进和 Agent 提案应用具有 revision/stale 检查。Agent 修改先形成提案并等待确认。
4. L3 与 Bonus 共用官方模拟器入口但保持执行路径分离：L3 输出文本 RV32 子集；Bonus 汇编为 32 位机器码，由官方入口暴露的量子扩展执行经典控制和量子提交/读取闭环。

## LLM 不可信边界

- 模型只返回待验证候选，不能定义后端事实；能力、成本、云端和凭证要求只从 `backend_capabilities.json` 读取。
- 自然语言约束必须带有可定位到当前用户原文的证据，再映射到有限 `TargetSpec`；未被证明的约束不会进入求解。
- QASM 候选由本地 parser、完整测量双射和 Bell/GHZ 目标语义 oracle 检查；已知语义错误的候选不会成为 fallback。`loomq_l2.py` 的逐 case `RequestContext` 负责最多 3 次 transport attempt、一次瞬态重试、一次定向 repair、累计 8,000 输入/2,000 输出预算及经同一 oracle 复核的 canonical target recovery；`llm_client.py` 只负责 transport、timeout、response bytes 和单次输出上限。
- 每个客观 case 独立建立上下文，不共享 prompt、候选或修复状态。Web Agent 的写入先形成已验证提案，并以 base revision 防止旧建议应用到新电路。

## 交付与安全边界

- `Dockerfile` 与 `compose.yaml` 构建同一 Python 3.10 环境；容器默认启动 Web 服务，亦可在同一镜像运行 evaluator。
- 所有第三方依赖在 `requirements.txt` 精确锁定。
- 真机凭证仅从环境或私有配置读取，证据写出前脱敏；`.gitignore` 和 Docker 上下文排除私有状态。
- Web 未配置或无法连接模型时，自由问答明确显示不可用且不伪造模型回复；仅当前 Bell 阶段的精确界面预设可调用同一确定性工具并返回显式标注、随代码发布的预置回复。未配置与“已尝试模型但回复非模型生成”使用不同文案和机器字段。工具若已执行，解释失败不会导致重复推进；本地工具失败不自动重试；本地工作台和模拟器始终可运行。
