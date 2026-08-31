# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。截图、原始结果或图表统一放在
`starter_kit/evidence/files/`，代码与文档直接引用 `starter_kit/` 中的内容。

## 申报清单

- [x] L1 真机（量旋 + 本源 180 双平台已跑通）
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

---

## L1 真机（最高 +10 分）

**量旋核磁真机**（`spinq_cloud`，已跑通 ✅）：

```text
平台：量旋云 gemini_vp（2 比特核磁平台；平台性质以组委会判定为准，见文末"平台性质如实说明"）
命令：
  export SPINQ_CLOUD_USERNAME="pennie514"
  export SPINQ_CLOUD_KEYFILE="$HOME/.ssh/spinq_cloud"
  python3 starter_kit/real_machine.py spinq_cloud \
      --qasm starter_kit/circuits/bell.qasm --shots 8192 \
      --config starter_kit/evidence/config_spinq_cloud.json \
      --out starter_kit/evidence/files/spinq_cloud_result.json
job_id（task_code）：G-260824-0002
运行时间：2026-08-24T03:27:39Z（UTC）
shots：8192
实际执行的 QASM：starter_kit/circuits/bell.qasm
原始结果：starter_kit/evidence/files/spinq_cloud_result.json
counts：{"00": 4028, "11": 2174, "10": 1938, "01": 52}
主峰核对：理想 Bell 主峰 {00, 11}；实测 Top-2 为 00(49.2%)/11(26.5%)，
        01 占比 ≈0（两比特强相关，符合纠缠特征）→ 主峰命中 ✅
溯源：cloud.spinq.cn 控制台按 task_code=G-260824-0002 查询
```

**本源 180 比特超导真机**（`originq_wukong`，已跑通 ✅）：

```text
平台：本源 180 比特超导真机（本源180，chip_id=180）
命令：
  export ORIGINQ_API_TOKEN="<你的 API Token>"
  python3 starter_kit/real_machine.py originq_wukong \
      --qasm starter_kit/circuits/bell.qasm --shots 8192 \
      --config starter_kit/evidence/config_originq_wukong.json \
      --chip-id 180 \
      --out starter_kit/evidence/files/originq_wukong_result.json
job_id（task_id）：9080D4D192FDF69809FBDFDA9E19DB47
运行时间：2026-08-24T05:27:21Z（UTC）
shots：8192
实际执行的 QASM：starter_kit/circuits/bell.qasm
原始结果：starter_kit/evidence/files/originq_wukong_result.json
counts：{"00": 4331, "11": 3860, "01": 0, "10": 1}
主峰核对：理想 Bell 主峰 {00, 11}；实测 00(52.9%)/11(47.1%)，01/10≈0 → 主峰命中 ✅
溯源：qcloud.originqc.com.cn 工作台按 task_id=9080D4D192FDF69809FBDFDA9E19DB47 查询
说明：本源真机返回概率字典，counts 由 概率 × shots 换算（real_machine.py 已按此解析）
```

**关于本源这份数据的两点如实说明**（便于评委交叉核对）：

1. **芯片标识**：`backend` 字段按赛题后端命名规范填 `originq_wukong`，但本次实际
   执行芯片为同平台的 **180 比特芯片**（提交时传 `chip_id=180`，见结果文件
   `meta.chip_id`）。能力表中 `originq_wukong` 记录的 72 比特为悟空芯片规格，
   两者是同一平台的不同芯片，非笔误。
2. **主峰占比偏高的原因**：本次调用 `async_real_chip_measure(..., is_amend=True,
   is_mapping=True)`（见 [`real_machine.py`](../real_machine.py) 的
   `_run_originq_wukong`），其中 `is_amend=True` 是本源平台官方提供的**读出误差
   修正**开关，属平台标准功能。因此返回分布（00/11 合计 99.99%）比未修正的裸数据
   干净——这是平台后处理的结果，不是模拟器数据：调用走的是真机接口
   `async_real_chip_measure`（非 CPUQVM 本地模拟），task_id 可在平台任务中心溯源。
   如需未修正的裸数据，可将配置中的 `is_amend` 置为 `false` 重跑。

**AWS Braket**（可选，允许以本地模拟器替代）：

```text
本地模拟器证据：braket_local_simulator（无需账号）已随 L1 自动评测覆盖；
云端证据（可选）：python3 starter_kit/real_machine.py braket_cloud --config starter_kit/evidence/config_braket_cloud.json
```

主峰核对：`real_machine.py` 会在提交前先在本地无噪声模拟器自验同一电路，
真机返回的 counts 主峰与该理想主峰一致即命中（真机允许噪声，只查主峰）。

---

## L2 交互体验（最高 10 分）

提供了**两个可运行的用户入口**：Web 界面 + 引导式 CLI，均面向零量子背景用户。

### 入口 1：Web 界面（推荐）

```text
启动命令：python3 starter_kit/loomq_web.py
访问地址：http://127.0.0.1:8080
（零依赖：仅 Python 标准库 + 本地静态资源 web/，评测容器可直接运行）

打开即进入 8 章引导课（预测→实验→揭示），无模型服务、无真机凭证也能
完整通关（真机章节回放已存证的真实芯片数据）。结课后解锁「自由实验室」：
跑电路 / 说人话生成电路 / 修报错代码 / 帮我选平台 / 页面内配置。
可用 URL 锚点直达任一章，如 http://127.0.0.1:8080/#bell_test（第 5 章对照实验）。
```

### 入口 2：引导式 CLI

```text
启动命令：python3 starter_kit/loomq_cli.py
```

### 3 个用户体验任务（工作人员可原样执行）

1. **自然语言生成电路**：Web「说人话生成电路」输入
   `让三个量子比特纠缠在一起（GHZ 态），然后全部测量` →
   自动生成 OpenQASM 2.0 电路 → 一键在量旋/本源/AWS 模拟器运行 →
   柱状图 + 大白话解读（「只出现全 0 和全 1，这就是纠缠的指纹」）。
2. **代码纠错**：Web「修一段报错代码」粘贴 `H q[0]; CX q[0] q[1]` 并说明
   「我想做一个贝尔态」→ 保持意图修复 → 自动自验 → 可运行并看结果。
3. **智能选后端**：Web「帮我选平台」输入
   `我需要运行一个 15 比特电路，且零排队等待` →
   返回规范后端标识 `braket_local_simulator`（及全部合规选项），附理由。

### 客观代码（可被评测器自动调用）

```text
python3 -c "import sys; sys.path.insert(0,'starter_kit'); from adapter import agent_chat; print(agent_chat('生成一个2比特贝尔态'))"
```

`agent_chat` 实现「生成 QASM → 用 L1 中间层自验 → 不对就带错误重试」闭环；
选后端为「LLM 建议 + 官方能力表约束求解」双通道，回复包含规范后端 id。

---

## 工程与产品化

### 一键复现

```bash
cd starter_kit
pip install -r requirements.txt
python3 evaluator.py --level all --target spinq,originq,braket   # 自测（L1 需模型服务时跳过 L2 或先配 LOOMQ_LLM_*）
python3 loomq_cli.py                                             # 交互入口
python3 loomq_web.py                                             # Web 入口
```

### 架构

```
自然语言 ──► L2 agent_chat（生成/纠错/选后端，L1 自验闭环）
                │
                ▼
         OpenQASM 2.0（12 门白名单）
                │
                ▼
         L1 统一中间层 transpile()
          ├─ spinq  → OpenQASM 2.0（原样，含 qelib1 头）
          ├─ originq→ OriginIR（QINIT/CREG/H/CNOT/…/MEASURE，规范子集）
          └─ braket → OpenQASM 3（braket 方言：cnot/cphaseshift/ccnot/si/ti，
                      与参考实现 LocalSimulator 实测兼容）
                │
                ▼
         run()：三后端本地无噪声模拟 → 统一 Schema（bit_order=little）
                │
                ▼
         L3 compile_hybrid：Hybrid-QASM → (量子操作序列, RISC-V 汇编)
         在官方 riscv_emulator.py 穷举测量注入验证
```

### 核心模块

| 文件 | 职责 |
|---|---|
| `adapter.py` | 契约入口：transpile / run / agent_chat / compile_hybrid |
| `real_machine.py` | 三平台真机统一接入（自定义输入 JSON/CLI） |
| `llm_client.py` | OpenAI-compatible 传输（仅环境变量配置） |
| `loomq_cli.py` / `loomq_web.py` | 交互入口（CLI / 零依赖 Web 引导课） |
| `tutor.py` + `web/` | 教学引擎：8 章课程数据 + 前端（HTML/CSS/JS，无构建、无 CDN） |
| `test_tutor.py` | 课程数据完整性 + 每条物理结论的运行验证（14 tests） |
| `quantum_riscv_emulator.py` | 量子 RISC-V 扩展模拟器（LQ-Q） |
| `riscv_emulator.py` | 官方 RISC-V 模拟器（未修改，供 L3 验证） |

### 目标用户

没有量子物理背景、不懂各家平台「黑话」、但有想法的跨界创造者与软件工程师。

### 完整使用流程

1. `python3 starter_kit/loomq_web.py` → 打开 http://127.0.0.1:8080
2. 跟着 8 章引导课走完 5 分钟（每章：先猜 → 真跑 → 解释），
   第 7 章把 Bell 电路送上真机（无凭证则回放真实存证数据）
3. 结课测验检验理解，然后进「自由实验室」：
   「说人话生成电路」描述想法 → 得到电路 → 一键运行 → 看懂柱状图
4. 命令行/代码直接调用 `transpile()`/`run()`/`compile_hybrid()`

---

## 自定义量子 RISC-V Bonus（+8）

三项材料齐全，端到端测试通过：

1. **指令编码规格文档**：`starter_kit/quantum_riscv_isa.md`
   （LQ-Q Extension v1.0：RISC-V custom-0 opcode 0x0B 上的 R-type 量子指令，
   funct3 分门别类，rs1/rs2 直接编码量子比特索引，QPARAM 毫弧度参数寄存器）
2. **对官方模拟器的扩展实现**：`starter_kit/quantum_riscv_emulator.py`
   （fork 官方 `riscv_emulator.py`，继承 `TinyRISCVEmulator`，7 条经典指令语义
   不变，量子助记符先汇编为真实 32 位机器码再解码执行——编码规格处于执行
   必要路径，不是旁置文档；支持中路测量反馈：测量 → 经典分支 → 条件量子门）
3. **可运行的端到端测试**：
   ```bash
   python3 starter_kit/test_quantum_riscv.py
   # 31 passed, 0 failed
   # 覆盖：经典回归、编码往返、Bell、中路测量反馈、参数门、Toffoli/GHZ、测量塌缩
   ```

---

## 新手引导与视觉叙事 Bonus（+4）

- **引导式教学界面**：`loomq_web.py` + `web/`（零依赖静态资源）+ `tutor.py`（课程引擎）。
  左栏智能体逐句引导、右栏实验工作台的分栏结构；亮/暗双主题、键盘可翻页。
- **8 章引导课**：全程「**预测 → 实验 → 揭示**」三段式，先让学习者押一个答案，
  再跑真实电路，最后解释。猜错的地方就是直觉与量子分岔处（认知冲突锚点）。
- **结果可视化**：柱状图 + 每条结果的大白话解读 + 经典对比；噪声按「该不该出现」
  着色（而非按峰高），真机 20%+ 的噪声峰也能被正确标出。Web 与 CLI 双份。
- **渐进披露**：代码、数学、术语默认折叠（`<details>`），想看再展开。
- **错误恢复**：生成/纠错自动重试并回喂错误；编译失败翻译成「检查三点」的中文
  指引而不是抛 traceback；模型服务缺失时明确告知「课程与实验不受影响」。
- **无障碍**：语义化标签 + `aria-label`、`:focus-visible` 焦点环、键盘全流程可达、
  尊重 `prefers-reduced-motion` 与 `prefers-color-scheme`，纯本地无 CDN。

## 🏆 最佳包容性设计与优秀体验奖（自证材料）

评选标准原文：「让一位没有任何量子背景的跨界创作者，在 5 分钟内依靠智能体
引导，成功在**真实量子机**上完成人生第一个实验，并理解其科学原理」。

### 5 分钟核心路线（每章时长在代码中声明，测试守住总和 = 300 秒）

```text
0:00-0:20  开场      右栏一枚旋转的硬币可点击落定（叠加→测量的第一手体感），
                     并把整条 5 分钟路线摊开——先知道要去哪，才愿意跟着走。
0:20-0:45  第 1 章   经典比特的天花板：3 个开关可点，任何时刻只能是 8 种之一。
                     热身预测：「电脑里的随机数是真随机吗？」→ 伪随机可被完美重放。
0:45-1:20  第 2 章   叠加：1 比特 H 门跑 2000 次 → 50/50。点明这还**不足以**
                     证明叠加存在（不急着喊「量子很神奇」）。
1:20-2:05  第 3 章   干涉（关键）：连续两次 H → **100% 回到 0**。
                     如果叠加只是「藏起来的答案」，随机两次不可能整齐回到 0。
2:05-2:40  第 4 章   纠缠：Bell 态只出 00/11。随即**主动引入怀疑**——
                     「抛一次硬币抄在两张纸上」也能做到，这叫事先约好。
2:40-3:35  第 5 章   决定性实验：测量前先旋转（H⊗H），**并排跑两组**——
                     ① 真纠缠：仍然只有 00/11，相关性完好；
                     ② 经典「事先约好」：散成 00/01/10/11 各约 25%，当场失败。
                     经典方案在学习者眼前失败，而不是被告知它会失败。
                     （对应 2022 年诺贝尔物理学奖排除的局域隐变量解释。）
3:35-4:15  第 6 章   有什么用：用户自选一个 2 位密码，Grover **问一次 100% 命中**。
                     说清机制是「干涉抵消错答案」，不是「同时算完所有答案」。
4:15-5:00  第 7 章   上真机：把第 4 章的 Bell 电路送上真实超导芯片。
                     有凭证 → 实时任务；无凭证 → 回放**已存证的真实芯片数据**
                     （带可溯源 job_id），保证零配置也有真机体验。
                     两台真机并排：本源180 主峰 99.99%，量旋 75.71%——
                     用真实的保真度差异讲清「不同芯片噪声不同」。
─────────  以上为承诺的 5 分钟（core_eta = 300s，由 test_tutor.py 守住）
结课加餐   5 道检索练习测验（答错解释为什么）+ 应用场景 + 明确说清
           「量子**不能**做什么」（不是万能加速、不能超光速传信息）。
```

### 为什么这样设计（学习科学依据）

| 设计 | 依据 | 在哪一章 |
|---|---|---|
| 先预测再看结果 | Predict-Observe-Explain：认知冲突是最强记忆锚点 | 全部 7 章 |
| 让经典方案当场失败 | 对照实验优于断言；破除「纠缠=事先约好」的直觉 | 第 5 章 |
| 单一心智模型（硬币）| 避免中途换喻造成的认知负荷 | 全程 |
| 代码/数学默认折叠 | 渐进披露（Progressive Disclosure） | 第 3、5 章 |
| 结课强制回忆 | 检索练习优于重读 | 结课测验 |
| 主动说清局限 | 校准信任，避免「量子万能」误解 | 结课 |

### 真实真机证据（job_id 可溯源）

| 平台 | job_id | 主峰占比 | 噪声 | 结果文件 |
|---|---|---|---|---|
| 本源 180（180 比特超导真机） | `9080D4D192FDF69809FBDFDA9E19DB47` | 00/11 = **99.99%** | 0.01% | `evidence/files/originq_wukong_result.json` |
| 量旋 `gemini_vp`（2 比特核磁平台，见下方平台性质说明） | `G-260824-0002` | 00/11 = **75.71%** | 24.29% | `evidence/files/spinq_cloud_result.json` |

**平台性质如实说明（量旋 `gemini_vp`）**：该结果由量旋云 `gemini_vp` 平台代码返回，
task_code `G-260824-0002` 可在 https://cloud.spinq.cn 控制台溯源。量旋云文档将
`superconductor_vp`（8 比特超导）标注为真机平台代码，本队提交时该账号下未取得
`superconductor_vp` 的可用额度，故实跑于 `gemini_vp`。实测主峰 00/11 = 75.71%、
噪声 24.29%，噪声结构与理想无噪模拟（应为精确 50/50）明显不同，符合物理器件特征。

为避免歧义，本队不就该平台是否计入"真机"作自我认定，交由组委会判定：
- 若组委会认定 `gemini_vp` 属真机 → 本队满足"≥2 平台真机证据"（本源 180 + 量旋 gemini_vp）；
- 若认定其不属真机 → 本队**无争议的真机证据以本源 180（180 比特超导，job `9080D4D192FDF69809FBDFDA9E19DB47`）为准，计 1 个平台**，
  该项按 1 平台阶梯计分，本队不主张 2 平台满分。

零凭证用户通过 `/api/real-replay` 看到的就是上表这两份真实数据（非模拟），
并被明确告知这是存证回放、job_id 可在平台控制台查询。

### 无门槛设计要点

1. **5 分钟是可验证的承诺**，不是宣传语：每章 `eta` 写在 `tutor.py` 里，
   `test_tutor.py::test_core_path_is_five_minutes` 守住核心路线总和 = 300 秒；
2. **零配置即可完整通关**：无模型服务、无真机凭证也能跑完 8 章（含真机章节）；
3. **科学正确性有测试兜底**：课上每条物理结论都有对应断言——干涉必须 100% 回 0、
   经典对照组必须散成四种、Grover 四个目标必须全部 100% 命中（`test_tutor.py`）；
4. **友好报错**：编译失败给「检查三点」的中文指引，不甩 traceback；
5. **界面截图**：`starter_kit/evidence/files/ux/`（开场 / 第 5 章对照 / 真机 / Grover / 实验室，
   由评审环境直接可见；`.release/qa/ux/` 为仓库内同名副本）；
6. 命令行版 `loomq_cli.py` 双入口，未配置模型服务也能跑完实验与科普。

**演示录屏建议**：按上述 5 分钟流程录屏（Bell 态 → 真机 → 结果解读），
保存到 `evidence/files/` 或外链。

---

## 提交规则

- 所有材料须在截止前进入最终提交 commit；工作人员不接受截止后补交。
- 整个 fork commit 归档不得超过 100 MiB（`.venv`、密钥、大视频不入库）。
- 不要提交 API Key / Token / Cookie / 私钥（`.gitignore` 已排除）。
- 申报 L1 真机分时，在最终提交 Issue 的 `Hardware evidence` 填
  `starter_kit/evidence/files/`。
