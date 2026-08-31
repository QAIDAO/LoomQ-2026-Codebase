# LoomQ · 说人话的量子算力入口（BH2-4 队提交）

> 让一位从没写过量子代码的跨界创作者，5 分钟内靠智能体引导跑出人生第一个
> 量子实验，并看懂它的原理。——这是本项目的唯一目标。

## ⚠️ 安全红线：密钥管理（改动代码前先读）

**本仓库公开，提交即全世界可见，且最终 commit 会进入组委会评测归档。**
赛题规则明令禁止提交 API Key、Token、Cookie 及任何账户隐私——泄露即违规。

四条铁律：

1. **密钥只进环境变量，不进任何文件。** `LOOMQ_LLM_*`（模型）、平台 Token、
   RSA 私钥一律通过 `export` 或本地 `.env`（不入库）注入；代码中不得出现
   任何硬编码 URL/Key/模型名（`llm_client.py` 契约，官方测试有断言）。
2. **`.gitignore` 只是兜底，不是借口。** 仓库已全局拦截 `.env`/`*.pem`/`*.key`
   等模式，但任何新的凭证形态入文件前都要三思。
3. **报错不得回显密钥。** 所有错误信息只列缺失的环境变量名，绝不打印变量值
   （官方契约测试 `test_missing_environment_fails_without_echoing_secrets` 盯着这条）。
4. **每次提交前自查**：

```bash
git grep -nE "sk-[A-Za-z0-9]{8}|BEGIN (RSA )?PRIVATE KEY|API_KEY=.+[A-Za-z0-9]" -- .
```

（输出为空才可提交。）万一曾经泄露：**立即在对应平台作废该 Key 并重新生成**，
git 历史无法真正撤回公开内容。

## 一键开始

```bash
python3 starter_kit/chat.py --demo      # 零依赖离线体验（30 秒看到量子纠缠）
python3 starter_kit/chat.py             # 自然语言对话（需 LOOMQ_LLM_* 环境变量）
python3 starter_kit/chat.py --doctor    # 环境自检
```

零基础完整指南：[`GETTING_STARTED.md`](GETTING_STARTED.md)（含量子概念速览与错误自救表）。

## 目标用户与使用场景

**为谁而做**：没有任何量子背景的跨界创作者——设计师、文科研究者、产品经理、
中学生。他们被"量子黑话"挡在门外：不懂 QASM、不懂门、不懂后端选型。

**场景**：用户说「生成一个 3 比特 GHZ 态并测量」，助手生成电路 → 本地模拟
4096 次验证正确性 → 画直方图 → 用「总是给出相同答案的骰子」这样的比喻解释
纠缠。全过程用户不写一行代码、不查一个术语。

**完整使用流程**：
1. `--demo` 离线感受 → 2. 配置模型环境变量 → 3. 对话生成/纠错/选平台 →
4. 自动验证 + 可视化解读 → 5.（进阶）把电路交给多平台中间层：
   `adapter.transpile(qasm, "spinq"|"originq"|"braket")` 得到三厂商家原生 IR，
   `adapter.run(...)` 本地无噪声模拟出 counts。

## 架构（含 AI 辅助开发披露）

完整分层与设计决策详见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

```text
starter_kit/
├── adapter.py          # 提交契约入口：transpile/run/agent_chat/compile_hybrid
├── loomq/              # L1 中间层：QASM2 解析 → 统一 IR → 三后端 codegen
│   ├── qasm2.py        #   OpenQASM 2.0 解析器（白名单门集+自定义门展开）
│   ├── sim.py          #   无噪声状态向量模拟器（纯标准库，离线可用）
│   └── codegen.py      #   spinq(QASM2)/braket(QASM3)/originq(OriginIR) 生成
├── loomq_l2/           # L2 智能体：LLM 只做意图理解（JSON），电路确定性生成
│   ├── templates.py    #   Bell/GHZ/均匀叠加/基矢/W态 模板库（含旋转级联构造）
│   ├── validate.py     #   本地验证器：解析+白名单+精确分布对拍
│   ├── selector.py     #   选后端：backend_capabilities 确定性过滤
│   └── repair.py       #   用户坏代码规范化（补声明/修门名/补测量）
├── loomq_l3/           # L3 混合编译：classical 文法→AST→官方 7 指令汇编
├── riscv_emulator_qext.py  # Bonus：官方模拟器扩展 fork（QH/QX/QCX/QMS/QP 量子指令）
├── chat.py             # 用户入口 CLI：对话+自动运行+ASCII 直方图+通俗解读
├── selfcheck.py        # 自建回归：官方 8 电路全集+随机电路，119 项
├── l2_selftest.py      # L2 变体自测：mock/live 双模式 25 例
└── l3_selftest.py      # L3 穷举属性测试 + Bonus 端到端
```

**关键设计**：L2 中 LLM 永远不直接写 QASM——它只把自然语言映射为结构化意图
（模板+参数），电路由模板库确定性生成并经本地模拟器验证，失败才把机器可读
错误回喂修复。这保证了评测隐藏措辞变体下的正确率（QUASAR 论文验证的路线，
arXiv:2510.00967）。L1/L3 全部确定性、零第三方依赖（评测环境默认禁网，本地
模拟器即唯一正解）。

**AI 辅助开发披露**（按赛题反作弊条款 4）：本项目代码由 AI 辅助编写、人工
审查验收；上表即各模块工作原理说明。所有提交物均通过公开评测器、自建回归
（119+25+200×穷举）与官方契约测试验证；无任何针对公开样例的特判分支。

## 质量验证命令

```bash
python3 starter_kit/evaluator.py --target spinq,originq,braket   # 公开契约（declared: L1+L2+L3）
python3 starter_kit/selfcheck.py          # 119 项：8 电路全集+随机回环回归
python3 starter_kit/l2_selftest.py --mock # L2 快速回归（--live 真模型 25 例）
python3 starter_kit/l3_selftest.py        # L3：200 用例×全注入组合穷举（--bonus 为 Bonus 闭环）
python3 -m unittest discover -s tests     # 官方契约测试
```

以上全部通过，且已在 **Python 3.10**（与正式评测镜像一致的版本）下复验。
容器基线：`docker build -t loomq-submission starter_kit && docker run --rm loomq-submission`
离线即可验证 L1（三目标）+ L3；L2 需注入 `LOOMQ_LLM_*` 环境变量（正式评测由组委会注入）。

## 人工评分材料索引

- L1 真机 + L3 Bonus：[`evidence/README.md`](evidence/README.md)（双平台 job 可溯源；采集与复现工具见 [`tools/qpu/README.md`](../tools/qpu/README.md)，凭证走环境变量、不入库）
- 量子 RISC-V 扩展规格：[`l3_bonus_spec.md`](l3_bonus_spec.md)
- 新手引导与可视化：[`GETTING_STARTED.md`](GETTING_STARTED.md) + `chat.py --demo`

---

## 官方提交契约要点（保留自 Starter Kit v1.1.0）

`starter_kit/` 是构建与评测根目录；必需文件 `submission.yaml`/`adapter.py`/
`Dockerfile`/`README.md` 齐备。依赖零第三方（`requirements.txt` 维持基线），
Python 3.10，与官方镜像一致。

**Adapter 契约**（`adapter.py`）：
- L1：`transpile(qasm_str, target) -> str`、`run(qasm_str, target, shots) -> dict`
- L2：`agent_chat(prompt) -> str`（读 `LOOMQ_LLM_*` 环境变量）
- L3：`compile_hybrid(hybrid_qasm_str) -> (quantum_ops, assembly)`

**公开自测**：`python3 evaluator.py --json-out report.json`，退出码 0 为全部
通过。正式评测使用组织方私有 runner、随机 case 与私有期望值。

**L2 统一模型**：正式评测为 DeepSeek `deepseek-v4-flash`（组委会注入）；
本地调试设置 `LOOMQ_LLM_BASE_URL/_API_KEY/_MODEL/_TIMEOUT_SECONDS`。
实现不含任何硬编码 URL/Key/模型名；缺配置时报错只列变量名。

**最终提交**：截止 2026-08-25 12:00 UTC+8。fork 根目录运行
`python3 starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>`，
随后在上游创建最终提交 Issue；`submission:accepted` 回执才算成功。

**版本政策**：合同版本 1.0；`1.x` 向后兼容。
