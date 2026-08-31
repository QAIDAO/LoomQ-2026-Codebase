# LoomQ 架构文档

> 量子接入平权计划 —— 一个"统一中间层 + 说人话的智能体"。

## 一、为谁而做（必答题）

**你的工具，让哪一类原本进不来的人，第一次能够使用并受惠于量子计算？**

我们的答案是：**没有科班量子背景、甚至不认为自己"配得上"碰量子计算机的人** ——
跨界创作者、产品经理、社科研究者、初学者，尤其是长期被"黑话高墙"默认排除在
外的群体。

传统量子计算的使用路径是：读物理教材 → 学 QASM → 选 SDK → 猜平台 API → 真机
排队。这套路径默认把"懂门道"当作准入证。LoomQ 把它倒过来：**用户只需要说出
自己想要什么结果，剩下的由中间层和智能体完成。**

- 一个没写过一行 QASM 的创作者，用自然语言说出"生成 3 比特最大纠缠态并测量"，
  `agent_chat` 返回可运行电路；
- 他把电路交给统一的 `transpile + run`，同一套代码驱动量旋、本源、AWS Braket
  三个平台，位序、Schema 全部归一化，结果格式一致；
- 他看不懂 `{000: 4096, 111: 4096}`？CLI 会把它翻译成"两半对半分，说明三个量子
  比特确实纠缠在了一起"。

**"第一次指挥真实量子计算机"不再需要懂量子理论** —— 这就是平权。

---

## 二、总体架构

```
用户（自然语言 / QASM 2.0）
        │
        ▼
┌─────────────────────────────────────────────┐
│  L2 agent_chat(prompt)                       │
│   · 意图生成 / 代码纠错 / 智能选后端          │
│   · LLM 生成 → L1 自验 → 不对重试            │
│   · 后端能力表(JSON)确定性选型               │
└──────────────────┬──────────────────────────┘
                   ▼ 标准 OpenQASM 2.0
┌─────────────────────────────────────────────┐
│  L1 统一中间层（adapter.py，零第三方依赖）    │
│   QASM 2.0 解析器 → 单一门模型 Circuit        │
│        │                  │                 │
│   transpile()         run()                │
│   spinq → OpenQASM2   内置无噪声             │
│   originq → OriginIR   statevector          │
│   braket → OpenQASM3  模拟器                │
└──────────┬───────────┬──────────┬───────────┘
           ▼           ▼          ▼
     SpinQ Cloud   Origin Cloud   AWS Braket
     (real/taurus) (悟空/CPUQVM)  (LocalSim)
           └─────────┬──────────┘
                     ▼
       统一 JSON Schema（little-endian counts）
```

### 关键设计决策

1. **单一门模型 + 单一模拟器**。三个后端不是三套硬编码分支，而是同一个 QASM 解析
   器产出的同一个 `Circuit` 对象分别渲染成三种目标 IR，并喂给同一个无噪声模拟器。
   这从架构上保证了"通用"——加第四个平台只需新增一个渲染函数。
2. **自动化评测零依赖**。正式评测在隔离容器内、默认禁网、每个 case 独立进程。
   `adapter.py` 只依赖 Python 标准库，保证在任何干净环境原样可跑；真机证据通过
   可选的 `real_backends.py` 单独采集。
3. **LLM 不自证，自验靠 L1**。L2 生成的电路用我们自己的 `parse_qasm + _simulate`
   做语义校验（目标态分布保真度 ≥ 0.97），而不是靠模型自圆其说。这构成
   "生成 → 自验 → 重试"的闭环，且校验器与正式评测的判定标准一致。

---

## 三、模块说明

### 3.1 `adapter.py` —— 统一中间层（L1 核心）

| 函数 | 职责 |
|---|---|
| `transpile(qasm, target)` | 解析 QASM 2.0 → 渲染为目标 IR（spinq=OpenQASM2 / originq=OriginIR / braket=OpenQASM3），输出符合 `target_ir_contract.md` |
| `run(qasm, target, shots)` | 解析 → 内置无噪声 statevector 模拟采样 → 返回统一 Schema（little-endian、counts 总和=shots） |
| `agent_chat(prompt)` | L2 智能体入口（见下） |
| `compile_hybrid(qasm)` | L3 混合编译（见下） |

**内部结构**
- `parse_qasm()`：递归下降解析器，覆盖 12 门白名单（`h x s sdg t tdg rz ry cx cu1 swap ccx`），支持寄存器/逐比特操作、表达式参数（`pi/2` 等）、多行语句、注释。
- `_simulate()`：纯标准库 statevector 模拟器，实现全部 12 门的幺正矩阵，采样按 little-endian 位串返回 counts。
- 12 门矩阵经官方参考模拟器行为逐一验证（Bell / GHZ / QFT-4 / 随机电路）。

### 3.2 `adapter.py` —— L2 智能体

三类任务，两类策略：

| 任务 | 策略 |
|---|---|
| 意图生成 | LLM 生成 QASM → `_validate_generated_qasm` + `_expected_from_prompt` 语义校验 → 失败带错误反馈重试（≤3 次） |
| 代码纠错 | 同上，prompt 中保留用户声明的目标态 |
| 智能选后端 | **确定性**：加载 `backend_capabilities.json`，解析约束（比特数/排队/费用/本地），过滤出规范 `id` 集合，保证回复含官方标识原文 |

模型服务通过 `LOOMQ_LLM_*` 环境变量注入（`base_url/api_key/model`），不硬编码
任何地址或密钥；每次真实调用经由标准库 `urllib` 完成 OpenAI-compatible 协议。

### 3.3 `adapter.py` —— L3 混合编译

- `_split_hybrid()`：剥离 `classical { }` 块，得到量子部分文本。
- 词法/递归下降解析：`r1..r9`、`c[k]`、整数字面量、`+ - == !=`、`if/else`、括号。
- `_RiscvEmitter`：生成可被 `riscv_emulator.py` 执行的汇编（`li/add/sub/addi/beq/bne/j`）。
  寄存器映射 `r_i→x_i`、`c[k]→x10+k`、临时寄存器栈式分配。分支语义经 200 组随机
  用例 × 穷举测量注入与参考解释器比对，寄存器终态 100% 一致。

### 3.4 `real_backends.py` —— 真机证据（可选层）

- `spinq_cloud_run()`：提交至 SpinQ Cloud（真机 `gemini/triangulum/superconductor` 或云模拟器），自动剥离显式 measure（云端自动测量），保存 `evidence/files/spinq-*.json`。
- `originq_cloud_run()`：提交至本源悟空真机（`origin_72`）或全振幅云模拟器。
- 输出统一 Schema + 原始 counts/probabilities + job_id，供 L1 真机证据核验。

### 3.5 `quantum_riscv/` —— 自定义量子 RISC-V 扩展（Bonus）

- `QUANTUM_RISCV_SPEC.md`：指令编码规格，在 RISC-V CUSTOM-0 空间（opcode `0x0B`）
  定义量子门/测量/声明指令，`rd/rs1/rs2` 复用为量子比特索引，参数门角度用 1/16 π
  定标立即数。**指令字驱动**：汇编→机器码→解码→执行，opcode 真实参与运行
  （主办方 Bonus 方向 1）。
- `quantum_riscv_emulator.py`：官方 `riscv_emulator.py` 的向后兼容 fork，包含
  `assemble()`（文本→32 位指令字）、`decode_word()`（按 opcode/funct3/funct7 解码）、
  `load_machine_code()`（直接加载机器码）、量子协处理器（statevector + Born 测量坍缩）。
- `test_quantum_riscv.py` / `test_instruction_chain.py`：端到端测试（量子门分布、
  Bell/GHZ 频率、混合程序、指令字往返、与官方模拟器 200 组随机程序一致）。

---

## 四、可复现性

### 自动化评测（无第三方依赖）

```bash
# 一键自测：只测提交声明启用的 Level
cd starter_kit
python3 evaluator.py --json-out report.json

# 全量三平台 L1
python3 evaluator.py --level l1 --target spinq,originq,braket
```

依赖锁定：`adapter.py` 仅用标准库；第三方依赖（若有）全部精确锁版于
`requirements.txt` / `requirements-real.txt`。

### 真机证据采集（可选）

```bash
cd starter_kit
# 准备 Python 3.10 环境并安装真机 SDK
uv venv --python 3.10 .venv310
.venv310/bin/pip install -r requirements-real.txt

# macOS 上 spinqit 的 dylib 需要 DYLD_LIBRARY_PATH 指向包目录
export DYLD_LIBRARY_PATH="$(dirname $(python -c 'import spinqit;print(spinqit.__file__)' ))"
# 或用 x86_64 Linux 容器（官方评测同架构）：
# docker build -t loomq . && docker run --env-file ../.env loomq

# 采集真机证据（需要 .env 提供 LOOMQ_SPINQ_* / LOOMQ_ORIGINQ_TOKEN）
.venv310/bin/python real_backends.py --backend both --shots 8192
```

### 真机接入与凭证配置（环境变量注入，绝不硬编码/提交）

真机连接（SpinQ Cloud / 本源悟空）属于 L1 的额外加分，**不在 L2 智能体交互的强制
要求内**。LoomQ 的真机凭证全部通过环境变量注入，代码不包含任何账号、Token 或密钥：

| 环境变量 | 用途 |
|---|---|
| `LOOMQ_SPINQ_USERNAME` | SpinQ Cloud 账号（登录用户 ID） |
| `LOOMQ_SPINQ_KEYFILE` | SpinQ Cloud RSA 私钥文件路径（如 `~/.spinq/spinq_key`） |
| `LOOMQ_ORIGINQ_TOKEN` | 本源量子云 API Token |
| `LOOMQ_ORIGINQ_CHIP` | 本源真机标识（可选；如 `origin_72`=悟空72、`WK_C180_2`=悟空180；缺省 `origin_72`） |

> 主办方确认真机不限于悟空 72：本源云上可选择其他当前在线的物理后端
> （如悟空 180 WK_C180_2），通过 `--chip` 或 `LOOMQ_ORIGINQ_CHIP` 指定。
> 真机只用于采集证据，不需放入 `run()`（`run()` 负责本地模拟器转译）。

配置方式（模板见仓库根目录 `.env.example`）：

```bash
# 从模板创建本地 .env（.env 已在 .gitignore 中，绝不提交）
cp .env.example .env
# 编辑 .env，填入你的凭证后即可使用

# 或用环境变量临时注入（不落盘）
export LOOMQ_SPINQ_USERNAME=your-spinq-id
export LOOMQ_ORIGINQ_TOKEN=your-token
```

`real_backends.py` 的 `_load_env()` 会自动读取同目录上级的 `.env`（若存在）并回退到
环境变量；`.env` 已被 `.gitignore` 排除，确保密钥不会进入提交归档。提交包中只含
采集到的**证据文件**（原始 counts、job_id、timestamp），不含任何凭证；`.env.example`
是纯占位符模板，可安全提交。

真机评分的判定依据（主办方规则）：
1. 返回结果的 Schema 合法且字段完整；
2. counts 的主峰与理想分布一致（真机允许噪声，只查主峰命中）；
3. 真实返回的 job_id 可在平台控制台溯源，且 timestamp 落在赛程窗口内。

---

## 五、为什么这样设计

- **"通用"名副其实**：单解析器、单模拟器、三渲染器。不是三套硬编码。
- **门槛真的降低**：L2 让不懂 QASM 的人用自然语言生成/修复电路，且回复是"人话"；
  L1 让同一电路零改动跑通三家平台。
- **可复现**：零依赖自测一条命令；真机证据脚本化采集，job_id 可溯源。
- **反作弊安全**：不硬编码答案；L2 客观题按模型调用 + 语义校验，靠关键词匹配无法
  通过；L3 是真正的解析 + 编译，硬编码样例输出会在随机用例上失败。

---

## 六、目标用户与使用流程

**目标用户**：零物理背景的跨界创作者、产品/研究员、初学者。

**完整使用流程**
1. 用户向 LoomQ 说一句中文意图（或贴一段报错代码）；
2. `agent_chat` 返回可运行 QASM（并自验）；
3. `transpile` 选定目标平台；
4. `run` 执行并返回统一结果；
5. CLI 把结果翻译成用户能理解的话（如"00 与 11 各占一半，纠缠态成立"）。

**运行一个量子程序的最短路径**（CLI 入口）：

```bash
python3 cli_agent.py "生成 3 比特 GHZ 态并测量，跑在本地模拟器上"
```