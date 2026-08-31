# L2 语义自验与量子 RISC-V Bonus 设计

## 目标

提高 L2 正式 `agent_chat` 对隐藏提示变体的实际正确率，并完整交付手册中自定义量子 RISC-V 扩展的三个必需材料。

## 范围与边界

- 保持正式 L2 的唯一模型配置来源为 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL`；本地百炼 profile 仅用于开发探测。
- 不硬编码题目答案。语义判断基于通用 OpenQASM 解析、全幅测量和小型 statevector 概率计算。
- 保留未知量子任务：若无法从用户意图安全提取目标，则仅作已有的 QASM 语法验证，避免误拒绝合法的隐藏任务。
- 直接扩展官方 `starter_kit/riscv_emulator.py` 的 `TinyRISCVEmulator`，不新建平行模拟器或独立 ISA。

## L2 设计

将目前只被本地探测使用的 QASM 语义检查提取为生产模块。`agent_chat` 从用户 prompt 推导三个可验证的意图：

1. GHZ：提取请求中的正整数比特数；验收为所有比特均测量，且分布仅为全零与全一、各为 1/2。
2. Bell：验收为两比特全测量，且分布仅为 `00` 与 `11`、各为 1/2。
3. 后端选择：从 prompt 提取至少比特数、是否要求零排队/免费等明确约束；验收模型给出的 canonical backend id 是否同时满足能力表。

模型第一次回答不满足对应验收器时，向同一模型给出不含凭据和响应正文的精确失败原因，并最多重试一次。模型传输、HTTP、配置和未知意图沿用现有安全错误边界。

## 量子 RISC-V 扩展设计

使用 RISC-V Custom-0 主 opcode `0b0001011` (`0x0B`)；该编码空间为自定义扩展保留。扩展指令与 `TinyRISCVEmulator` 原有 `li/add/sub/addi/beq/bne/j` 共存：

| 指令 | 功能 | 编码字段 |
| --- | --- | --- |
| `qh qd` | 对量子位施加 Hadamard | `funct3=000`, `rd=qd`, `rs1=0`, `rs2=0` |
| `qcx qc, qt` | 以 `qc` 为控制、`qt` 为目标施加 CNOT | `funct3=001`, `rs1=qc`, `rs2=qt`, `rd=0` |
| `qmeas rd, qs` | 测量 `qs`，将 0/1 写入经典 RISC-V 寄存器 `rd` | `funct3=010`, `rd=rd`, `rs1=qs`, `rs2=0` |

模拟器新增受限量子协处理器：固定小尺寸 statevector，支持 H、CX 与可设随机种子的 Born 测量；`load_program` 同时接受助记符并保留现有汇编语法。端到端用 Bell 程序验证 raw-word 编码/解码、量子相关性和测量结果进入普通寄存器；原有经典指令回归必须不变。

## 文档与证据

- 增加指令编码规格，说明 32 位布局、寄存器语义、限制与端到端运行命令。
- 更新 `starter_kit/evidence/README.md` 的 Bonus 栏位，填写真实路径与命令。
- 将四个百炼候选的三题实跑结果写入 L2 证据，但区分“模型答错”与“账户/端点拒绝”。截至 2026-08-24：`qwen3.8-max` 3/3 通过；`deepseek-v3.2` 与 `kimi/kimi-k2.5` 返回 403；`deepseek-r1` 返回 404。

## 验收

- L2 新增测试先覆盖：错误但可解析的 GHZ/Bell QASM 被拒绝；正确分布通过；错误后端因约束不符被拒绝；未知意图继续接受任何可解析 QASM。
- L3/BONUS 新增测试先覆盖：每个编码字段的 encode/decode round-trip、Bell 端到端相关性、`qmeas` 写入普通寄存器、原经典指令回归。
- 在 Docker 中重新运行全量单元测试、L1/L3 公开 evaluator；真实模型探测仅记录为本地开发证据，不取代组委会 DeepSeek 评测。
