# LoomQ-2026 静态审计报告

> **历史审计，请勿作为当前版本结论。** 本文锁定的是 2026-08-06 的旧提交；其中 99 分上限及所列交付缺口已由后续提交修复。当前状态应以 [`LoomQ_final_audit_27c30e2.md`](LoomQ_final_audit_27c30e2.md)、当前源码和最新验收记录为准。

审计对象：`AphrixZjr/LoomQ-2026`<br>
锁定提交：`d0900670bace265e805d338a36ec4b418b42106d`<br>
源码基线：`5a09270d2db6c6aff4ee290ef6c1cbd29498584d`（当前 HEAD 相对该提交主要是验收文档与截图整理）<br>
审计日期：2026-08-06<br>
审计性质：代码与申报材料的静态交叉审计；未在本报告生成环境中重新构建供应商 SDK、调用 DeepSeek 或登录量子云控制台。仓库内既有运行记录被视为“项目方留存证据”，而不是本次审计独立复现的结果。

## 一、结论摘要

你希望取得的分数可以理解为 **107/112**：基础 100 分、Bonus 12 分，只缺第二个真机平台的 5 分。

以当前提交严格对照可见规则，**还不能把 107/112 视为稳定可得**。最关键的原因不是 L1/L2 主实现薄弱，而是一个明确的 Bonus 交付缺口，以及两个隐藏集稳定性问题：

1. **自定义量子 RISC-V +8 当前不满足强制交付形态。**<br>
   规则要求扩展官方 `riscv_emulator.py`；当前实现明确放在独立的 `quantum_riscv.py`，并强调“不改变官方模拟器”。这是与规则正面相反的交付选择。严格判定下该项应为 0 分。

2. **正式归档只包含 `starter_kit/`，但完整测试和 Bonus 端到端测试位于仓库根目录 `tests/`。**<br>
   当前申报文档中的多个测试链接和命令，在组委会提取正式归档后会失效；自定义量子 RISC-V 所要求的“可运行端到端测试”也不会进入正式评测根目录。

3. **L3 是真解析、真编译，但没有覆盖题面文法允许的全部表达式。**<br>
   条件两侧的加减表达式、非 2 的幂次的目标寄存器系数，以及 `c[21]` 与 `x31` 临时寄存器冲突，都可能令合法随机用例失败。现有测试只覆盖简单原子条件。

因此，在不修复代码、只修改申报文档的前提下，当前提交的严格理论上限是：

> **112 − 5（缺第二真机）− 8（量子 RISC-V 交付不合规）= 99 分。**

综合可见实现、既有运行记录和主观项不确定性，当前更现实的静态估计区间约为 **85–98/112**。完成本报告列出的 P0/P1 修复并补齐最终提交 SHA 上的可复现证据后，**103–107/112** 是合理目标；其中工程叙事与视觉体验仍含主观评分，不宜表述为保证分。

---

## 二、规则基准存在版本冲突

仓库中的当前题面与随项目提供的 PDF 不是同一版本：

- PDF 仍写“96 小时”，并写明 L2 每 case 最多 3 次模型调用、累计最多 8,000 输入 Token 和 2,000 输出 Token。
- 当前 `problem_statement.md` 已改为 8 月 1 日至 25 日线上赛，并删除公开题面中的调用次数和 Token 限制。
- 当前 `l2_policy.json` 只保留正式模型、12 个 case 和 120 秒时限，没有 Token 或调用次数字段。
- 提交历史中存在“移除 L2 公开文档中的调用次数和 Token 限制”的更新。

本报告的处理方式是：

- 对 **提交边界、Bonus 三件套、L3 文法、评分项定义**，PDF 与当前仓库一致，直接作为硬约束。
- 对 **L2 Token/调用限制**，标记为规则版本冲突，而不直接判定违规。
- 最终申报材料应新增“规则基准”一节，写明采用的当前 `problem_statement.md` commit 与 `l2_policy.json` 版本；若组委会没有公开解释，工程上最好兼容更严格的旧限制。

低成本兼容措施是把每次输出上限降至约 1,000–1,500 Token，并保证两次调用的总上下文明显低于旧版 8,000 输入 Token。当前 `MAX_MODEL_CALLS = 2` 已满足旧版“最多 3 次”。

---

## 三、评分稳定性总表

| 模块 | 目标分 | 当前静态判断 | 主要依据与风险 |
|---|---:|---|---|
| L1 语义等价 | 35 | **强支持，约 33–35** | 单一 parser/IR、三 emitter、三 SDK runner、位序归一化与扩展回归均完整；仓库留存三平台 93/93 回归记录。需要在最终 SHA 上重跑并归档日志。 |
| L1 真机 | 5/10 | **一个平台 +5 有支持** | OriginQ 四个可追溯 job、原始响应、QASM、OriginIR 与标准摘要齐全；静态审计无法代替平台控制台复核。 |
| L2 客观 | 20 | **强支持，约 18–20** | 真实模型 12/12 与 72/72 压测记录、确定性本地校验和后端求解均较强；仍有测量映射与少数自然语言边界需要加固。 |
| L2 体验 | 10 | **约 7–10** | 产品层功能丰富；但文档宣称“无模型凭证可完成完整 Bell 引导”，当前实际流程不成立。 |
| L3 | 15 | **约 8–15** | 不是硬编码，但合法文法覆盖不完整，现有测试过窄。 |
| 工程与产品化 | 10 | **约 7–9** | 架构和一键 Compose 较好；正式归档不含测试，Docker 默认命令/健康检查/README 叙述不一致。 |
| 量子 RISC-V Bonus | +8 | **严格判定 0** | 未扩展官方 `riscv_emulator.py`；端到端测试也在正式归档之外。 |
| 新手引导/视觉 Bonus | +4 | **约 +3–4** | 概念边界、可视化、无障碍和错误恢复较强；固定最小宽度、非真实采样叙述等会削弱满分稳定性。 |
| 合计 | 112 | **当前约 85–98** | 修复 P0/P1 后可向 103–107 靠近。 |

以上区间不是正式评分预测，而是“可见契约下的风险折算”。

---

# 四、必须先修复的 P0 问题

## P0-1：自定义量子 RISC-V +8 的交付形态不合规

### 当前申报

`starter_kit/evidence/README.md` 勾选：

```text
[x] 自定义量子 RISC-V Bonus
```

并把实现指向：

```text
quantum_riscv.py，独立于官方 riscv_emulator.py
```

`docs/acceptance/bonus-rationale.md` 和 `quantum_riscv.py` 也把“不改变官方模拟器”视作设计优点。

### 规则要求

当前题面要求同时具备：

1. 指令编码规格；
2. **对官方模拟器的扩展实现（fork `riscv_emulator.py` 增加指令支持）**；
3. 可运行端到端测试。

现状具备第 1 项；第 2 项明确未做；第 3 项存在于仓库根目录，但不进入正式 `starter_kit/` 归档。

### 判定

这是确定性的申报—实现错位。不能靠改写措辞化解。

### 建议修复

应在 `starter_kit/riscv_emulator.py` 中真正纳入扩展，同时保持现有 L3 兼容：

- 保留 `TinyRISCVEmulator` 及文本 RV32 子集行为不变。
- 在同一文件加入量子 custom opcode 的编码/解码和机器字执行入口，或加入一个明确的扩展类。
- `quantum_riscv.py` 可以保留为内部模块，但官方文件必须承载、注册或直接暴露扩展能力，不能只是文档链接。
- 在 `starter_kit/tests/` 中加入从汇编、机器码、量子提交、测量回读到经典分支的端到端测试。
- 申报文档应直接指向 `riscv_emulator.py` 中的扩展入口和归档内测试。

修复前，应暂时取消该项勾选，避免构成显著虚报。

---

## P0-2：正式归档不包含根目录测试

### 事实

正式配置的 `submission_path` 是 `starter_kit`。组委会只提取该目录作为构建和评测根目录。

当前：

- `tests/test_l2_web.py` 位于仓库根目录；
- `tests/test_l3_and_quantum_riscv.py` 位于仓库根目录；
- 完整 `unittest` 测试集也位于根目录；
- `starter_kit/evidence/README.md` 用 `../../tests/...` 链接这些文件；
- `starter_kit/README.md` 给出 `python -m unittest tests...` 命令；
- Docker 构建上下文是 `starter_kit/`，镜像不会复制根目录 `tests/`。

### 后果

在正式归档环境中：

- 证据文档中的相对链接断裂；
- `python -m unittest discover -s tests -v` 无法复现 209/209；
- Bonus 所需端到端测试缺失；
- 评委可能把“测试齐全”视为不可复核陈述。

### 建议修复

将评分相关测试复制或迁移到：

```text
starter_kit/tests/
```

至少包括：

- L1 core / 三后端 / 位序与扩展回归；
- L2 contract、agent、Web；
- L3 随机/差分测试；
- 量子 RISC-V 端到端测试；
- 归档隔离检查。

根目录测试可以保留为上游工具或 wrapper，但所有申报命令必须在只剩 `starter_kit/` 的目录中成立。

新增归档隔离验收：

```bash
tmp="$(mktemp -d)"
cp -a starter_kit "$tmp/"
(
  cd "$tmp/starter_kit"
  python -m unittest discover -s tests -v
  python evaluator.py --level l1 --target spinq,originq,braket
  python evaluator.py --level l3
)
```

容器版本也应从 `starter_kit/` 单独构建后运行同一组命令。

---

# 五、L3 详细审计

## 5.1 已实现的正确部分

当前 `loomq_l3.py` 不是样例硬编码，而是完整的编译流水线雏形：

1. 从 Hybrid-QASM 中按大括号深度提取唯一 `classical` 块；
2. 对经典块进行 tokenize；
3. 构造 `Atom`、`Binary`、`Assign`、`IfElse` AST；
4. 把加减表达式归一化为常量加寄存器线性组合；
5. 生成 `li/add/sub/addi/beq/bne/j` 文本；
6. 为嵌套分支生成唯一标签；
7. 复用 L1 parser 提取、展开并规范化量子操作；
8. 输出官方 `TinyRISCVEmulator` 可执行的汇编。

这足以排除“打表式伪编译器”风险，也是应当在申报文档中更明确呈现的设计亮点。

## 5.2 合法文法覆盖不足

### 问题 A：条件表达式只支持原子操作数

parser 接受：

```text
if (r1 + 1 == c[0]) { ... } else { ... }
if (r1 - r2 != 3) { ... } else { ... }
```

但 emitter 的 `operand()` 只接受：

- 单个寄存器；
- 单个 `c[k]`；
- 单个整数。

带常量或多个项的条件会抛出：

```text
branch operands must be a register, c[k], or integer
```

题面把 `+ - == !=` 都列入经典块文法，并说明将随机生成不同分支结构，因此这不是可以忽略的扩展语法。

### 问题 B：合法重复项可能被拒绝

例如：

```text
r1 = r1 + r1 + r1;
```

线性化后目标寄存器系数为 3。当前实现只接受目标系数绝对值为 2 的幂，因而拒绝该合法表达式。

### 问题 C：`c[21]` 与 `x31` 冲突

代码允许 `c[0]..c[21]` 映射到 `x10..x31`。条件中的非零整数字面量也临时加载到 `x31`。

于是：

```text
if (c[21] == 1) { ... } else { ... }
```

会先把常量 1 写入 `x31`，覆盖测量值，再比较 `x31` 与自身，分支语义错误。

### 问题 D：测试覆盖过窄

当前 L3 测试主要覆盖：

```text
if (c[0] != 0)
```

没有覆盖：

- 条件两侧表达式；
- 嵌套 if/else；
- 负常量；
- 所有测量值组合；
- 多个测量位；
- 目标寄存器重复项；
- `c[21]`；
- 随机 AST 与参考解释器差分。

### 修复建议

不要只增加几个手写 case。应增加一个小型、确定性的文法生成器和参考解释器：

1. 随机生成受深度和节点数限制的合法 AST；
2. 收集所用 `c[k]`；
3. 穷举全部测量位组合；
4. 用 Python 参考解释器计算 `r1..r9` 终态；
5. 运行编译结果；
6. 比较全部寄存器；
7. 固定随机种子并记录失败最小化用例。

条件 lowering 需要真正支持线性表达式。临时寄存器分配不能默认占用 `x31`；应做活跃性分析，或采用可恢复的破坏式比较并在两个控制流出口恢复被借用寄存器。

完成上述修复后，L3 才适合申报“全部文法随机用例稳定通过”。

---

# 六、L2 客观 Agent 审计

## 6.1 当前实现的主要优点

`loomq_l2.py` 的工程策略非常合理，应在申报文档中突出：

- 模型只负责自然语言理解与 QASM 候选生成，不拥有最终事实。
- QASM 由本地 parser 做结构验证和规范化。
- Bell/GHZ 由本地状态向量做相位无关语义等价检查。
- 后端选择只读取官方 `backend_capabilities.json`，由本地求解器确定。
- 模型提取的约束必须附带用户原文中的精确证据。
- 明确约束还会从原始 prompt 做本地交叉恢复，降低模型漏抽风险。
- 每个 case 都有独立 deadline、调用计数、候选和 trace，不跨请求共享状态。
- 首次候选失败时最多一次定向修复。
- 输出是唯一规范 QASM 或规范后端 ID，不让模型写长篇不可判定文本。

这套设计比“Prompt 调优”更接近一个受约束编译前端。

## 6.2 现有真实模型证据被申报材料遗漏

仓库中曾记录同一 L2 核心代码的真实 `deepseek-v4-flash` 验证：

- 公开 evaluator：1/1；
- 固定 12-case：生成 4/4、纠错 4/4、后端 4/4；
- 72-case 原始 prompt 并发压力测试：生成、纠错、后端各 24/24；
- 记录了中位数、P95、最大延迟；
- 记录了首轮失败如何驱动 `real -> qpu`、账号、cloud、QPU、模拟器和 no-queue 等恢复规则。

当前 `evidence/README.md` 和 `verification.md` 没有呈现这些结果，只写了单元测试 209/209。对 L2 20 分而言，这是最重要的漏报之一。

建议在最终 SHA 上重新运行：

```bash
python experiments/l2_live_benchmark.py
python experiments/l2_raw_prompt_stress.py
```

把原始终端输出或 JSON 化结果写入：

```text
starter_kit/evidence/files/l2-live-12-current.json
starter_kit/evidence/files/l2-stress-72-current.json
```

必须注明它们是本地 validation，不是组织方私有集。

## 6.3 仍需加固的边界

### 完整测量校验不够严格

当前语义检查只验证“每个量子位都出现于测量源端”，没有验证：

- 经典寄存器宽度是否等于目标宽度；
- 每个量子位是否一一对应到不同经典位；
- 是否存在多个量子位覆盖同一经典位；
- 是否存在额外未使用的经典位导致结果 key 宽度改变。

例如，模型可能生成：

```qasm
measure q[0] -> c[0];
measure q[1] -> c[0];
```

量子态本身仍是 Bell，但正式 counts 不会表示预期的二比特分布。当前本地语义诊断可能放行。

应把目标态检查扩展为“量子态 + 经典测量映射”的联合契约。

### 自然语言别名覆盖不足

本地目标识别主要依赖 `GHZ`、`Bell/贝尔` 和阿拉伯数字。以下改写更依赖模型一次输出正确，缺少本地独立恢复：

- “三比特最大纠缠态”但不出现 GHZ；
- “猫态”；
- 中文数字“十五/二十六比特”；
- “读出所有线路”等测量同义表达。

隐藏 prompt 会改写措辞。建议增加受控别名和中文数字解析，但不要扩大为开放式关键词打表；仍应把它们映射到有限的 `TargetSpec` 与后端约束 schema。

### `without charge` 的后端约束存在语义漏洞

本地 evidence 校验对英文 `without charge` 可能同时容许 `free` 和 `paid`，而本地强约束恢复没有覆盖该短语。模型若错误输出 `paid`，有机会被接受。

应统一成本短语的规范化和证据集合，所有“无需付费”表达只能支持 `free`。

### 网络错误没有专门重试

模型服务 503 曾真实发生。当前请求失败即抛错，没有在模型调用预算内对 429/503 做一次短退避重试。虽然题面承诺基础设施异常会复评，但轻量重试仍能改善现场稳定性。

---

# 七、L2 Web 与新手体验审计

## 7.1 确定性的文档虚报：无模型凭证不能完成完整 Bell 引导

### 文档表述

`starter_kit/README.md` 写：

> 不配置模型凭证也可启动完整本地 Bell 引导流程。

`docs/acceptance/l2-experience.md` 又要求评委启动后按八阶段完成 Bell 引导，没有说明必须配置模型。

### 实际实现

- “本阶段操作”按钮只把一条预设指令填入 Agent 输入框。
- 真正的阶段推进依赖模型返回 `advance_bell_guide` 工具调用。
- `agent_turn()` 在检测 Bell guide 指令之前，先检查 `LOOMQ_LLM_*`。
- 未配置模型时直接返回“Agent 尚未配置”，不会调用本地 `advance()`。
- 默认 Compose 允许三个模型环境变量为空。

因此，干净环境执行文档给出的命令后，第一项现场任务会停在起点。

### 推荐修复

最稳健的产品设计是：

- Bell 引导主按钮直接调用确定性的本地 `advance` API；
- 模型仅负责解释本阶段发生了什么；
- 模型不可用时显示本地固定、技术严谨的解释；
- 自由对话和非预设修改仍由 Agent 处理。

这样既保持“Agent 带领”体验，又避免把核心教学状态机寄托于外部模型可用性。

较弱方案是修改所有文档，明确 Bell Agent 引导必须配置模型；但这会削弱“一键启动”和零门槛叙事。

## 7.2 “三层验证/目标一致性”目前被过度描述

指导文案写“语法、结构和实验目标是三个不同层次的证据”，但 `_validation(circuit, goal)` 实际忽略 `goal`，只检查：

- QASM 可解析；
- 寄存器；
- 是否有量子门；
- 是否有测量。

这不是实验目标语义验证。

两种修复路径：

1. 对明确识别的 Bell/GHZ 调用已有本地语义 oracle，并显示“目标一致”；其他目标显示“当前未提供语义证明”。
2. 不增加实现，统一把文案改为“四项静态结构检查”，不要使用“实验目标验证”。

## 7.3 `mode="qasm"` 的有效电路会被标成 invalid

`ExperimentStore.create()` 在成功 `_set_qasm()` 后执行：

```python
session.state = "draft" if not session.validation.get("syntax") else "invalid"
```

有效电路的 `syntax` 是 truthy，因此状态被错误设为 `invalid`。默认 Bell 页面未触发该路径，但 API 的 QASM 初始化路径存在真实缺陷。

应删除这次反向赋值，或改为依据 `validation["runnable"]` 设置状态，并加入回归测试。

## 7.4 “有限 shots 采样”与实际算法不一致

Web 内置参考执行器不是随机采样，而是：

1. 计算理想概率；
2. 乘以 shots；
3. 取整；
4. 用最大余数法确定性补齐。

因此 Bell 1024 shots 会稳定得到精确 512/512。界面却称其为“有限 shots 的采样”。

应二选一：

- 使用可控随机种子的 multinomial 采样；或
- 明确称作“由理想概率确定性折算的教学计数”，不要把它描述成真实抽样。

这不影响 L1 SDK runner，但会影响科学叙事的严谨性。

## 7.5 结果边界对供应商本地模拟器描述不准确

即使选择 SpinQit、pyQPanda 或 Braket LocalSimulator，结果 `boundary` 仍统一写：

> 本次结果来自本地理想参考模拟器。

实际执行器可能是供应商本地 SDK。应根据 `backend_id` 动态说明具体模拟器；共同边界可以写“均非真机，不反映真实设备噪声与排队”。

## 7.6 多寄存器 QASM 的 UI 表示会丢失寄存器身份

`_circuit_ir()` 和 `_description()` 只使用 bit 的局部 index，不保留寄存器名或全局 offset。若输入：

```qasm
qreg a[1];
qreg b[1];
```

两者都会被呈现为 `q[0]`。L1 支持多寄存器，Web 若自称通用工作台，应使用 `(register, index)` 或统一 flatten 后的全局 index。

## 7.7 无障碍与视觉实现的优点

当前实现中值得明确申报的部分包括：

- skip link 与可见 `:focus-visible`；
- ARIA expanded/pressed/live 状态；
- 图表旁提供等价数据表；
- reduced-motion 开关并尊重系统偏好；
- 色觉辅助主题，且状态不仅依赖颜色；
- 修复前 diff、应用确认、撤销/重做；
- Agent 提案必须用户确认；
- stale proposal 拒绝；
- 运行结果保存为不可变快照；
- 把“Z 基相关结果”与“纠缠认证”明确区分。

这些不是装饰性特性，而是对“平权”叙事最有说服力的实现证据。

## 7.8 响应式与缩放风险

CSS 设置：

```css
html, body { overflow: hidden; }
body { min-width: 1100px; }
```

在 1024 宽屏幕或 200% 缩放下可能直接裁切内容。无障碍申报不应只测试默认桌面分辨率。

建议至少验证：

- 1366×768；
- 1280×720；
- 浏览器 200% 缩放；
- 键盘全流程；
- 系统 reduced motion；
- 色觉辅助主题。

必要时允许页面级滚动，并在窄宽度改为纵向布局。

---

# 八、L1 详细审计

## 8.1 架构符合“统一中间层”

当前 L1 的核心不是三套独立硬编码：

- `parse_qasm()` 统一解析 OpenQASM 2.0；
- `Circuit`、`Gate`、`Measurement`、`BitRef` 是共享 IR；
- `emit_spinq()`、`emit_originq()`、`emit_braket()` 只负责目标 IR；
- 三家 SDK runner 与核心 IR 分离；
- `adapter.py` 只做统一入口注册；
- 计数、shots、bit order 和结果 schema 在中间层归一化。

这是回答评委“通用是否名副其实”的核心证据。

## 8.2 门集与语义处理较完整

静态检查支持题面 12 门：

```text
h x s sdg t tdg rz ry cx cu1 swap ccx
```

还包括：

- 安全 AST 角度求值；
- `pi` 与四则表达式；
- register-wide gate 展开；
- 多 qreg/creg flatten；
- OriginQ 中 `sdg/tdg` 的 RZ 等价分解；
- Braket `cu1 -> cp`；
- 非连续测量；
- Qiskit 风格 little bit order；
- 目标 IR 的确定性输出。

`l1_regression.py` 还包含：

- 全部门及正、负、零、非平凡参数角；
- GHZ-5、QFT-4、Grover-3；
- 非对称位序；
- 非连续测量；
- 三个固定随机电路；
- swap/cu1/ccx 分解的全局相位等价检查；
- 每平台 8192 shots 与 0.97 阈值。

## 8.3 重要运行证据被当前申报遗漏

历史 L1 验收记录写明：

- 三目标公开 evaluator 6/6；
- 三平台完整扩展回归 93/93；
- Linux 容器 Braket 定向回归 44/44；
- 12 门、位序、非连续测量、QFT、Grover 和固定随机电路均超过 0.97。

当前 L1 主代码相对该阶段没有实质改动，但最终证据入口没有呈现这组结果。

应在最终 SHA 和最终 Docker image 上重跑：

```bash
python l1_regression.py --target spinq,originq,braket
python evaluator.py --level l1 --target spinq,originq,braket \
  --json-out evidence/files/evaluator-l1-current.json
```

并把完整日志归档，而不是只写“209/209 单元测试通过”。

## 8.4 OriginQ 真机申报总体谨慎、可信

当前材料明确只申报一个平台，没有把 SpinQ/AWS 本地模拟器说成真机。每个任务提供：

- job ID；
- 平台时间；
- shots；
- QASM；
- OriginIR；
- 脱敏原始响应；
- 标准摘要；
- Top-state 支撑率。

材料也明确说明平台原始结果是概率分布，counts 是按 shots 做的确定性最大余数换算，不冒充逐 shot 原始记录。这种边界声明是正确的。

仍建议：

- 为每个计分任务提供一个命名明确的 canonical `result.json`；
- 保留原始 provider 响应；
- 加一张不含账号隐私的控制台 job 页面截图；
- 在最终提交前自行确认每个 job ID 仍可从控制台检索。

本次静态审计不能验证平台可追溯性，因此 +5 最终仍依赖组委会登录复核。

---

# 九、工程与产品化审计

## 9.1 Dockerfile、Compose 与文档存在三方不一致

当前：

- Dockerfile 默认 `CMD` 运行公开 evaluator；
- Dockerfile `HEALTHCHECK` 却访问 Web 的 8765 端口；
- Compose 覆盖命令，启动 Web；
- 架构文档称“容器默认启动 Web 服务”；
- README 又推荐 `docker run --rm loomq-submission` 作为基础验证；
- `submission.yaml` 声明 L1/L2/L3 都启用；
- evaluator 默认运行所有 declared levels；
- 未配置 LLM 时 L2 evaluator 会失败。

因此，直接执行 README 的：

```bash
docker build -t loomq-submission .
docker run --rm loomq-submission
```

很可能以 L2 缺少环境变量失败；同时 evaluator 容器也无法通过 Web healthcheck。

应统一一种语义：

### 推荐方案

- Dockerfile 默认启动 Web，与 healthcheck 一致。
- 公开 evaluator 使用显式命令：

```bash
docker run --rm loomq-submission \
  python evaluator.py --level l1 --target spinq,originq,braket
```

- L2 evaluator 命令必须明确要求注入 `LOOMQ_LLM_*`。
- Compose 保持一键 Web。
- 文档不要把“启动产品”和“执行全部评分自测”混为一条命令。

## 9.2 “所有写操作检查 revision”是过度表述

架构文档称所有写操作都检查 revision。实际：

- QASM 更新可以检查 `circuit_revision`；
- Bell guide 推进可以检查 revision；
- Agent proposal 应用检查 circuit 与 goal revision；
- `update_goal()`、`select_backend()`、`undo()`、`redo()` 没有客户端 revision 参数。

应把文档改为：

> QASM 同步、引导推进和 Agent 提案应用具有 revision/stale 检查；其余本地交互由会话内顺序操作管理。

或者给全部写 API 增加一致的版本前置条件。

## 9.3 架构文档的 L1 结果 schema 表述不准确

架构文档写最终结果为：

```text
{counts, shots, target}
```

实际统一 schema 是：

```text
backend, job_id, shots, counts, bit_order, timestamp, meta
```

应按实际 contract 改写，避免评委怀疑文档不是由当前代码生成。

## 9.4 验收记录缺少原始日志

`verification.md` 只写：

- 209/209；
- 36/36；
- py_compile；
- node check；
- compose config。

但没有对应日志、机器环境、最终 full SHA、Docker image digest 或 CI run。自述结果不能完全替代证据。

建议每次最终冻结生成：

```text
evidence/files/verification-manifest.json
evidence/files/unittest-current.txt
evidence/files/l1-regression-current.txt
evidence/files/l2-live-current.json
evidence/files/l3-differential-current.json
evidence/files/docker-image-current.txt
```

`verification-manifest.json` 至少包括：

- 完整 40 位 commit SHA；
- UTC 时间；
- Python/Node/Docker 版本；
- OS 与架构；
- 执行命令；
- 返回码；
- 输出文件 SHA-256；
- Docker image ID/digest。

---

# 十、申报材料虚报/漏报矩阵

## 10.1 需要删除、降格或修正的表述

| 当前表述 | 审计结论 | 修正方式 |
|---|---|---|
| `[x] 自定义量子 RISC-V Bonus` | **不成立** | 修复官方模拟器扩展和归档内 E2E 前取消勾选。 |
| `quantum_riscv.py 独立于官方 riscv_emulator.py` 可满足 Bonus | **与规则相反** | 真正扩展 `riscv_emulator.py`，再把独立模块作为内部组织方式说明。 |
| `tests/...` 是正式端到端证据 | **归档后不存在** | 移入 `starter_kit/tests/`。 |
| 不配置模型可完成完整 Bell 引导 | **不成立** | 让引导本地确定性推进，或明确要求模型配置。 |
| 引导提供“实验目标”验证 | **不成立** | 实现语义 oracle，或改称静态结构验证。 |
| 所有写操作都有 revision guard | **不成立** | 缩小表述或补全实现。 |
| Docker 容器默认启动 Web | **Dockerfile 本身不成立** | 统一 CMD、healthcheck 和文档。 |
| `docker run --rm` 是无配置基础验证 | **大概率失败** | 显式指定 L1/L3，L2 单独注入模型。 |
| L1 数据流输出 `{counts, shots, target}` | **字段错误** | 改为完整统一 schema。 |
| Web 计数是有限 shots 随机采样 | **不成立** | 使用真实随机采样或说明确定性折算。 |
| 所有本地后端结果都来自内置参考模拟器 | **不成立** | 根据所选后端动态生成边界说明。 |

## 10.2 已实现但当前申报明显不足的亮点

| 实现亮点 | 当前材料缺口 | 建议呈现 |
|---|---|---|
| L1 统一 parser/IR 与三 emitter/runner 分层 | 架构文档提到，但没有用“为什么不是三套硬编码”组织 | 增加一张数据流和共享/平台特定职责表。 |
| L1 三平台 93/93 SDK 回归 | 当前证据入口完全漏掉 | 在最终 SHA 重跑并附日志。 |
| 分解门的全局相位差分验证 | 未突出 | 作为隐藏电路稳定性设计亮点。 |
| 位序、非连续测量、多寄存器 flatten | 未突出 | 对应“通用中间层”的边界清单。 |
| L2 真实 DeepSeek 12/12 与 72/72 | 当前验收材料漏掉 | 重跑后加入客观分证据。 |
| 失败驱动的约束同义词与本地恢复 | 未说明工程演进 | 用两三个失败→修复案例说明稳健性，不必写长日志。 |
| 模型不拥有后端事实，约束需原文证据 | 只零散写在架构中 | 单列“LLM 不可信边界”。 |
| Agent 不直接改状态，先生成验证过的提案 | 未充分突出 | 作为防误操作和新手安全设计核心。 |
| proposal stale 检查 | 未突出 | 说明不会把旧建议应用到新电路。 |
| 运行结果不可变快照 | 只一句带过 | 说明为何支持可追溯比较。 |
| 概念边界：相关性不等于完整纠缠认证 | 有写，但可作为叙事主轴 | 在现场任务中要求评委实际观察。 |
| 图表与数据表等价、reduced motion、色觉辅助 | 有列举但无验收路径 | 添加键盘/读屏/缩放的短验收清单。 |
| L3 AST→线性 IR→标签→官方模拟器 | 几乎没有面向评委解释 | 修复文法后单列编译流水线。 |
| 真机客户端的确认、凭证隔离、恢复而不重复提交 | 架构材料提到很少 | 作为工程安全亮点，避免只展示结果文件。 |

---

# 十一、按得分收益排序的修复计划

## P0：直接决定 8–15 分

1. **把量子 custom opcode 真正接入 `riscv_emulator.py`。**
2. **把评分相关测试移入 `starter_kit/tests/`。**
3. **补全 L3 合法文法 lowering，并建立随机差分测试。**

这三项完成前，不建议做大规模文案润色，因为最高分结构仍不成立。

## P1：决定 L2 体验与工程满分稳定性

4. 让 Bell guide 在无模型配置时仍能确定性推进。
5. 修复有效 QASM 初始化为 invalid 的 bug。
6. 加强 L2 全测量映射校验和自然语言别名。
7. 统一 Dockerfile CMD、healthcheck、Compose 和 README。
8. 修正文档中的目标验证、revision、schema、采样和后端边界表述。
9. 加响应式/200% zoom 验收。

## P2：把已有能力转化为得分证据

10. 在最终 SHA 上重跑三平台 L1 93-case 级别回归。
11. 重跑 DeepSeek 12-case 与 72-case。
12. 归档 L3 随机差分结果。
13. 生成带 SHA、环境和输出哈希的 verification manifest。
14. 在 `evidence/README.md` 顶部增加一页式“得分项—实现—证据”索引。
15. 保持 OriginQ 只申报一个真机平台，不扩大口径。

---

# 十二、推荐的最终复现命令

以下命令以测试已迁入 `starter_kit/tests/` 为前提。

```bash
cd starter_kit

# 1. 归档根目录内的完整测试
python -m unittest discover -s tests -v \
  | tee evidence/files/unittest-current.txt

# 2. 三平台 L1 扩展回归
python l1_regression.py --target spinq,originq,braket \
  | tee evidence/files/l1-regression-current.txt

# 3. 公开机器契约
python evaluator.py --level l1 --target spinq,originq,braket \
  --json-out evidence/files/evaluator-l1-current.json

python evaluator.py --level l3 \
  --json-out evidence/files/evaluator-l3-current.json

# 4. L2 真实模型；显式加载自己的安全环境变量
python experiments/l2_live_benchmark.py \
  | tee evidence/files/l2-live-12-current.txt

python experiments/l2_raw_prompt_stress.py \
  | tee evidence/files/l2-stress-72-current.txt

# 5. Compose 产品入口
docker compose build
docker compose up -d
python - <<'PY'
import json, urllib.request
v = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/health"))
assert v["status"] == "ok"
print(json.dumps(v, ensure_ascii=False, indent=2))
PY
docker compose down
```

再做一次只保留正式目录的归档隔离测试：

```bash
tmp="$(mktemp -d)"
cp -a starter_kit "$tmp/"
cd "$tmp/starter_kit"
python -m unittest discover -s tests -v
docker compose build
```

---

# 十三、最终提交前的 go/no-go 清单

只有以下项目全部为“是”，才适合把目标写成 107/112：

- [ ] 自定义量子指令由 `riscv_emulator.py` 实际支持。
- [ ] 指令规格、模拟器扩展、E2E 测试全部位于 `starter_kit/`。
- [ ] 只提取 `starter_kit/` 后所有申报命令仍可运行。
- [ ] L3 随机差分覆盖题面完整文法，并穷举测量组合。
- [ ] `c[21]` 与条件常量不会发生临时寄存器冲突。
- [ ] Bell guide 在文档所宣称的环境中确实能完成八阶段。
- [ ] L2 完整测量映射被本地验证。
- [ ] Docker CMD、healthcheck、Compose 与 README 一致。
- [ ] 申报文档已移除全部过度表述。
- [ ] L1 三平台回归在最终 full SHA 上通过并留存日志。
- [ ] L2 真实模型验证在最终 full SHA 上通过并留存日志。
- [ ] OriginQ job ID 可从平台控制台追溯。
- [ ] `prepare_submission.py` 在干净、已 push 的最终提交上通过。
- [ ] 最终 Issue 获得 accepted 标签与归档回执。

## 最终判断

当前项目的核心开发质量明显高于一般黑客松提交：L1 的统一抽象、L2 的本地确定性约束、Web 的提案确认和科学边界都是真实实现，不是包装性文案。主要问题恰恰在于最后一公里：

- 一个 Bonus 采取了技术上合理、但与赛事字面契约相反的隔离设计；
- 测试体系没有被纳入正式归档边界；
- L3 的测试强度没有追上其文法承诺；
- 验收文档删除了最有力的 L1/L2 实际运行证据，却保留了几处超出实现的产品表述。

先修复 P0，再统一申报口径。完成后，这份提交才会从“功能很多、整体很强”变成“每一分都能由当前归档中的代码和证据直接追溯”。
