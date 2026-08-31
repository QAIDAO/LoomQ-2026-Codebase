# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 远程评委 5 分钟复现

**为谁：** 会写软件、但不想同时学 SpinQ / OriginIR / Braket 三套方言的人——先看可溯源真机主峰，再用自然语言改电路。

```bash
# fork 根目录（任意干净环境）
./start_demo.sh
# → http://127.0.0.1:8765/
```

| 步 | 动作 | 应看到 |
|---|---|---|
| 1 | 打开 `/` | 量旋真机 Bell 归档柱状图，主峰 **00/11**；job `G-260809-0018`；lede 含本源双云一句 |
| 2 | 打开 `?demo=ghz3`（或点「再看三枚硬币」） | GHZ 主峰 **000/111**；job `S-260810-0001` |
| 3 | 打开 `?demo=repair` 或 `?demo=backend` | 修 Bell 语法说明 / 15 比特零排队能力表（不排队、不烧机时） |

溯源链接（远程可点）：
- 量旋 Bell：https://cloud.spinq.cn/circuitDesign/taskResult/61210  
- 量旋 GHZ：https://cloud.spinq.cn/circuitDesign/taskResult/61216  
- 本源 Bell job：`724E511297B861472AA2441F90F3D5E6` · 仓库内打开 `evidence/files/originq-bell-result.json` 与 `originq-bell-rest-detail.json` 即可核验 counts / `taskState=3`（控制台：https://console.originqc.com.cn/）

**远程核验三点：**  
1）L1 是统一 IR，不是三套 if-else 硬编码。  
2）本源必须用 **chipId=180**；误用退役 72 会假性「维护中」。  
3）真机结果均可在云控制台或本仓 JSON 用 job id 复核；Demo 第一屏是归档回放，不扣机时。  

更完整的远程核验清单：`docs/JUDGE_DEMO_SCRIPT.md`。

## 公开态势对照（2026-08-24，公开 Issue + evidence；非官方排名）

| 队 | 最后 Issue | 真机公开面 | 产品面 |
|---|---|---|---|
| WilderNoTrack | #31 | 量旋+本源 | Web :8787 |
| AphrixZjr | #32 | Origin+SpinQ 多 job | Docker + Web |
| WayneYu1212 | #69 | 量旋+本源厚证据 | :8765 |
| mayloveless / tale03 / 2IKK12 / Junkai 等 | 见官方 accepted 列表 | 双云居多 | 各有 Web/CLI |
| **本队** | **以截止前最后一次 `submission:accepted` 为准** | **量旋 2q+3q + 本源 Bell chip180** | **`./start_demo.sh` → :8765**；踩坑笔记 + 本地 8/8·7/7·9/9 回归 |

> 自动分看隐藏测例；人工分看可溯源 job、L2 远程复现、工程材料。本 commit 含本源成功证据与 chip=180 修复。
## 本包相对早期 Issue 的评委入口资产

| 路径 | 作用 |
|---|---|
| `start_demo.sh` | fork 根目录一键启动 |
| `starter_kit/web/*` | 真机回放第一屏 + 三项任务 |
| `starter_kit/evidence/files/spinq-*` | 量旋 Bell/GHZ |
| `starter_kit/evidence/files/originq-*` | 本源 Bell（含 REST 原始详情） |
| `starter_kit/evidence/README.md` | 本文件 |

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机（量旋 2q+3q + 本源悟空 Bell `724E5112…`；人工分仍按两平台上限 10）
- [x] L2 交互体验（第一屏真机回放 + DeepSeek 三项任务：GHZ / 修 Bell / 15q 后端推荐）
- [x] 工程与产品化（材料已备；终局随 commit）
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus（README + QUANTUM_101 + 真机截图/投影图；无独立 RISC-V）

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

### 量旋（有效 — Bell）

```text
平台名称：量旋云 · 2比特核磁量子计算机
平台 job ID：G-260809-0018
任务页：https://cloud.spinq.cn/circuitDesign/taskResult/61210
运行时间：创建 2026-08-09 11:13:59 → started 11:14:30 → ended 11:15:32（UTC+8）
shots：结果页以投影概率为主展示（未在页头标明整数 shots；见 result JSON）
实际执行的 QASM：evidence/files/spinq-bell.qasm
平台返回的原始结果：evidence/files/spinq-bell-result.json
任务页截图：evidence/files/spinq-bell-hardware-result.png
模拟对照截图：evidence/files/spinq-bell-sim-preview.png
判定：有效（含 H、CNOT；实验柱主峰在 00/11）
```

### 草稿：量旋空电路（无效对照，勿计分）

```text
平台 job ID：G-260802-0004
实际执行的 QASM：evidence/files/spinq-G-260802-0004-empty.qasm
任务页截图：evidence/files/spinq-G-260802-0004-empty-circuit-NOT-valid-hw.png
判定：无效（无门）
```

### 量旋（有效 — GHZ-3 · 第二平台）

```text
平台名称：量旋云 · 3比特核磁量子计算机
平台 job ID：S-260810-0001
任务页：https://cloud.spinq.cn/circuitDesign/taskResult/61216
运行时间：created/ended 2026-08-10 11:30:16 → 11:32:42（UTC+8）
shots：结果页以投影概率为主展示（未在页头标明整数 shots；见 result JSON）
实际执行的 QASM：evidence/files/spinq-ghz3.qasm
平台返回的原始结果：evidence/files/spinq-ghz3-result.json
任务页截图：evidence/files/spinq-ghz3-hardware-result.png
模拟对照截图：evidence/files/spinq-ghz3-sim-preview.png
判定：有效（H + 两级 CNOT；实验主峰在 000/111，有 NISQ 泄漏）
```

### 本源悟空（有效 — Bell · chipId=180）

```text
平台名称：本源悟空（超导，chipId=180）
平台 job ID：724E511297B861472AA2441F90F3D5E6
运行时间：created 2026-08-24 13:14:21 → started 13:14:25 → ended 13:17:56（UTC+8，见 REST 原始 JSON）
shots：100
实际执行的 QASM：evidence/files/originq-bell.qasm
实际提交 OriginIR：evidence/files/originq-bell.originir（平台 mappingQProg，物理比特 [157,166]）
平台原始详情：evidence/files/originq-bell-rest-detail.json（taskState=3 已完成）
归一化结果：evidence/files/originq-bell-result.json
主峰结论：00/11（counts 00:50, 01:1, 10:4, 11:45；概率约 0.556 / 0.443）
判定：有效真机（chipId=180）。本地 SDK 轮询曾超时并附带无害 errorMessage「司南系统读取任务失败。」；已用 getTaskDetail 恢复，未重交。
远程评委核验（无需控制台截图）：打开 originq-bell-result.json 看 counts；打开 originq-bell-rest-detail.json 确认 taskState=3、chipId=180、物理比特 [157,166]。
```

### 本源 / 量旋适配踩坑（工程笔记 · 远程可核）

这些是本队真实排障记录，不是模拟器结果；用于说明「通用中间层」如何消化厂商差异。
1. **chipId=72 vs 180（假维护）**  
   官方 Q&A 写 `WK_C180`，旧 pyqpanda `real_chip_type.origin_72` 仍指向**已退役 72 比特**资源。把 `WK_C180` 映射成 72 时，云端常返回 `Quantum computer under maintenance`。  
   **结论：** 错误/未知 chip 与整机维护文案相同，不能据此断定平台全局不可用。有效真机为 **chipId=180**；本仓 `LOOMQ_ORIGINQ_CHIP` 默认 `180`（`WK_C180`/`wukong` 别名同映射到 180）。

2. **`set_configure(72, 72)` 有害**  
   在 `QCloud.init_qvm` 之后调用 `set_configure(72, 72)` 可能清掉初始化状态，后续提交表现 similarly like 永久维护。  
   **结论：** 云路径已去掉该调用。

3. **SDK 轮询失败 ≠ 任务失败**  
   job `724E511297B861472AA2441F90F3D5E6` 已提交成功；本地 `query_task_state_result` 曾报 `query task error : None` / 超时。REST `getTaskDetail` 显示 `taskState=3`（完成），`probCount`/`taskResult` 主峰 00/11；记录里附带无害 `errorMessage`「司南系统读取任务失败。」  
   **结论：** 先保存 job_id，用控制台或 REST 取结果；**禁止因超时重交**（浪费机时、制造重复证据）。恢复脚本：`tools/_fetch_originq_task_rest.py`。

4. **量旋无效对照（勿计分）**  
   `G-260802-0004` 仅有 `qreg`、无门 → 不计真机分。有效证据必须是含 H/CNOT 的 Bell/GHZ 任务（见上方 G/S job）。

5. **机时与模式**  
   成功一发后 `.env` 保持 `LOOMQ_ORIGINQ_MODE=local`，避免评测/本地误打真机。

量旋双平台 + 本源均有可溯源 job；人工真机分仍按规则上限 10（两平台封顶）。本源用于「两家中国云」叙事与适配深度，不是第 11 分。

## L2 交互体验

```text
启动界面或 CLI 的命令：
  ./start_demo.sh
  # 或 cd starter_kit && ./tools/start_l2_web.sh
  # 浏览器 http://127.0.0.1:8765/
  # 真机回放无需 LOOMQ_LLM_*；Agent 三项需 starter_kit/.env
  cd starter_kit && python tools/l2_chat_cli.py
测试入口或页面地址：http://127.0.0.1:8765/
适合远程复现的 3 个用户任务：
   1. 第一屏 Bell 归档（G-260809-0018）或 ?demo=ghz3 / 任务 1：GHZ 000/111 + Agent OpenQASM
   2. ?demo=repair / 任务 2：三处 OpenQASM 语法坑 + Bell 真机对照
   3. ?demo=backend / 任务 3：15 比特零排队 → 能力表高亮本地模拟器
本地实测（2026-08-20，DeepSeek deepseek-v4-flash）：
1. 通过 — GHZ 返回含 qreg q[3] 的 OpenQASM；页面可对照真机 S-260810-0001
2. 通过 — 修 Bell 补全头/寄存器/h/cx
3. 通过 — 回复含 braket_local_simulator 或 originq_local_simulator
截图（仓库内可打开，无需线下演示）：
  - 启动 + Bell 真机回放：evidence/files/l2-web-ui-home.png
  - 任务 1 GHZ：evidence/files/l2-web-ghz3-demo.png
  - 任务 2 修 Bell：evidence/files/l2-web-bell-repair-demo.png
  - 任务 3 15q 后端：evidence/files/l2-web-backend-15q-demo.png
```

## 工程与产品化

```text
干净环境中的构建和启动命令：
  ./start_demo.sh
  cd starter_kit && docker build -t loomq-submission . && docker run --rm loomq-submission
  # 自测请用已装 SDK 的 venv（系统 python3 常缺 spinqit/braket/pyqpanda）：
  PY=../LoomQ-2026-Jessica/.venv/bin/python
  export PYTHONPATH=starter_kit
架构说明：starter_kit/docs/ARCHITECTURE.md
厂商适配踩坑（chip 180 / set_configure / SDK 假失败 / 量旋空电路）：见上文「本源 / 量旋适配踩坑」
目标用户和使用场景：跨平台开发/产品——统一 OpenQASM 中间层，先归档真机主峰再调 Agent；见上文「远程评委 5 分钟复现」
完整使用流程：starter_kit/README.md「一分钟上手」；远程核验清单：docs/JUDGE_DEMO_SCRIPT.md

本地回归数字墙（2026-08-24，解释器 $PY 如上；非隐藏测例、非正式分数）：
  1) "$PY" evaluator.py --level declared --target spinq,braket,originq
     → {"passed": 8, "failed": 0, "total": 8}
       L1 bell/ghz3 × spinq+braket+originq 保真度 6/6；L2 public-ghz；L3 public-branch
  2) "$PY" tests/test_hybrid.py
     → 7/7 passed（含 randomized differential / flat chains）
  3) "$PY" tests/test_agent_unit.py
     → 9/9 OK（白名单拒绝、重试接受合法 QASM、backend 容量重试等）
说明：系统裸 python3 会因缺 SDK 报 L1 ImportError，不代表实现失败；正式评测在固定容器装依赖。
```

## 自定义量子 RISC-V Bonus

```text
指令编码规格：starter_kit/docs/LOOMQ_QISA_V1.md
模拟器扩展实现：starter_kit/riscv_emulator.py（qinit/qh/qx/qcx/qmeas；assemble/decode；**load_machine_words 机器码闭环**，对齐主办方 Q3 方向 1；CUSTOM-0 opcode=0b0001011）
端到端测试命令：PYTHONPATH=starter_kit python starter_kit/tests/test_quantum_riscv_e2e.py（含 test_bell_via_machine_words_closed_loop）
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：README「一分钟上手」+ QUANTUM_101.md
量子概念解释：QUANTUM_101.md（Bell / 测量 / 多后端动机）
结果可视化：http://127.0.0.1:8765/ 第一屏真机/理想柱状图（Bell 00/11、GHZ 000/111）+ evidence/files 真机 JSON
错误恢复或无障碍引导：Web 白话报错（缺模型钥匙时仍可看真机）；agent 本地校验失败后最多重试 3 次；CLI 见 tools/l2_chat_cli.py
```

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
