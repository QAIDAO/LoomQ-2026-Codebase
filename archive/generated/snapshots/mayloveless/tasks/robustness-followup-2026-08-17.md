# LoomQ Robustness Follow-up

> 独立记录第一波优化实施期间发现的后续工程防线。
>
> 当前已有其他任务在实施既有优化，本文件只用于暂存新增候选，避免修改正在被执行的 `tasks/optimization-backlog.md`。完成当前优化批次后，再统一判断哪些已经被顺带覆盖、哪些需要吸收到正式 task。

## 1. OpenQASM 整寄存器门操作

### 问题

当前 L1 Parser 对门操作数主要按显式下标形式处理，例如：

```qasm
x q[0];
cx q[0], r[0];
```

需要额外覆盖 OpenQASM 2 中整寄存器形式，例如：

```qasm
x q;
cx q, r;
```

预期语义：

- 单比特门作用于整个量子寄存器时，逐位展开；
- 多比特门的操作数均为等长寄存器时，按相同 index 配对展开；
- 不允许不明确的寄存器广播与显式下标混用；
- 多寄存器长度不一致时应明确失败，而不是静默截断或错误展开。

### 建议验收

- `x q;` 与显式逐位 `x q[0]; x q[1]; ...` 语义一致；
- `cx q, r;` 与逐位配对 CX 语义一致；
- 等长、多寄存器、混合非法形式均有单测；
- transpile 到三个目标后仍通过既有 target-native / semantic validation；
- 不扩大正式支持门集，只补齐已有门的合法操作数表达方式。

### 优先级

`P1`。属于标准语法边界，改动面相对有限，适合在 L1 robustness audit 中吸收。

---

## 2. L3 Emulator Execution-Step Budget

### 问题

L3 即使语义正确，也可能生成过长或控制流膨胀的汇编，最终触碰官方 Tiny RISC-V emulator 的执行步数上限。

现有随机程序 + 测量位穷举测试主要验证最终寄存器状态，应再增加资源余量断言，避免“结果正确但隐藏 case 超步数”。

### 建议验收

- 在 L3 differential / fuzz 测试中记录实际执行 step 数，而不只统计汇编文本行数；
- 为官方执行上限保留安全余量，例如测试集峰值不得接近硬上限；
- 覆盖嵌套 `if/else`、顺序赋值、寄存器自引用和多个测量位等较重路径；
- 若未来 codegen 修改导致峰值明显上升，回归测试直接失败并显示最坏 case；
- 自定义量子 RISC-V Bonus 的 E2E 也应有同类资源上限检查。

### 优先级

`P1`。实现成本低，能直接防止隐藏集中的资源型失败。

---

## 3. L2 安全失败分类

### 问题

L2 当前会把模型调用异常统一改写为通用失败，这能避免凭证或底层请求内容泄漏，但也会丢失“配置错误 / 超时 / HTTP 错误 / 网络不可达 / 响应格式异常”等安全的故障类别。

最终 real-model benchmark 如果只看到统一的 `model request failed`，会较难区分 Agent 逻辑失败与外部模型服务失败，影响最后阶段定位问题的效率。

### 建议验收

- 不保留原始异常文本和异常链，不让 API Key、Authorization header、URL 查询参数等进入 trace / benchmark；
- 只映射到有限、稳定的安全类别，例如：`config`、`timeout`、`http_4xx`、`http_5xx`、`network`、`invalid_response`、`unknown`；
- benchmark / trace 只记录类别和必要的非敏感状态，不记录 response body；
- 不因此改变正式 Agent 重试次数、调用预算或返回协议。

### 优先级

`P2`。主要提升最终 benchmark 与线上故障诊断能力，不直接提高客观正确率；等第一波 P0/P1 优化完成后再决定是否实现。

---

## 4. Final Preflight 显式校验 Backend Capability Snapshot

### 问题

L2 后端选择以仓库内 `backend_capabilities.json` 为事实源。最终提交前虽然已有 upstream / contract drift 检查，但应显式把能力表也纳入冻结前核对，避免官方快照更新而本地继续使用旧版本。

运行时不应硬编码某个版本号，否则官方正常更新会让程序自行拒绝合法输入；该检查属于最终提交 preflight，而不是生产路径。

### 建议验收

- 最终冻结前比较本地与最新 upstream 的 `backend_capabilities.json`；
- 至少核对 `version` 与文件内容 / blob hash，不能只检查文件是否存在；
- 若发生漂移，先审阅字段与语义变化，再决定是否更新 selector / tests；
- 更新能力表后重跑 backend-selection hidden-like / adversarial cases；
- 把检查结果记录进 final preflight / release verification，不增加运行时网络依赖。

### 优先级

`P1`。实现成本很低，直接影响 L2 backend hidden case 的事实基准；建议第一波优化完成后纳入最终提交检查清单。

---

## 5. L3 编译期嵌套 / 递归压力测试

### 问题

L3 编译器对嵌套 `if/else` 采用递归遍历。现阶段没有证据需要人为限制合法文法的嵌套深度，因此不建议在 production parser/compiler 中擅自加入固定 `max_nesting_depth`。

更合适的做法是把较深嵌套加入压力测试，同时观察编译期递归、生成汇编规模与最终 emulator 执行步数，防止 hidden case 在资源边界上失败。

### 建议验收

- fuzz / differential 中增加较深但合法的嵌套 `if/else` case；
- 验证 parser/compiler 不出现 `RecursionError` 或异常的编译时间增长；
- 同时记录生成指令规模与实际 execution step，和第 2 项的 step-budget 一起看；
- 若发现真实边界问题，优先优化遍历 / codegen，而不是先定义赛题未规定的任意深度上限；
- 保持与独立 reference interpreter 的最终寄存器状态一致。

### 优先级

`P1`（低成本补充）。与第 2 项一起实施最合适，不单独提前打开 L3 production code。

---

## 6. 运行参数的 Plain-language Explanation

### 问题

当前 Explorer 已经重点解释“量子程序这一步做了什么、状态如何变化”，但第一次运行实验的开发者还可能不理解本次执行参数本身，例如：

- 为什么选择这个 backend；
- `shots` 为什么需要重复很多次；
- measured bits / 结果 bit string 应该怎么读；
- 为什么有限次采样不会刚好等于理想概率。

这些问题不需要扩大教学范围，也不应抢占 execution trace 的主视图；更适合成为运行结果附近的轻量上下文说明。

### 建议形态

优先考虑一个默认折叠的“这次实验怎么运行的”区域，仅解释本次真实参数：

- `backend`：在哪里运行，以及本次选择的直接原因；
- `shots`：重复测量次数，以及增加 shots 只会让采样分布更稳定，不会改变理想电路本身；
- `measured bits`：经典位数量、bit string 顺序与本次结果标签如何读取；
- `finite sample vs ideal`：明确区分有限采样波动、理想模拟分布和真机噪声，避免把随机偏差解释成程序错误。

### 建议验收

- 不新增独立教学流程，不要求用户先读完参数说明才能运行；
- 默认信息保持短，技术细节按需展开；
- 文案只解释从真实 execution result / deterministic metadata 可得出的事实，不让 LLM 猜测 backend、shots 或位序；
- 如果已经有 ideal-vs-sampled 可视化，优先复用同一数据源而不是复制一套统计逻辑；
- 在最终无作者参与的三条评委任务里观察：用户是否会对 backend、shots、bit order 产生明显困惑；没有真实困惑则可以不实现。

### 优先级

`P2 / P1-low`。与 Developer-first Explorer 的目标用户契合，但属于主观体验补强，不应打断当前客观评分与稳定性优化。第一波优化结束后再根据无作者体验验收决定是否落地。

---

## 7. 首页补齐 “Why Quantum” 的最小定位文案

### 问题

当前首页已经较清楚回答两件事：

- 这是给谁的：有编程基础、但没有量子专业背景的开发者；
- LoomQ 能做什么：借助 AI 生成、理解、验证、修复量子程序，并选择运行平台。

但第一屏对“为什么一个普通开发者值得花几分钟了解量子计算”回答得还不够直接。该缺口不需要新增应用场景大区块，也不应重做已经稳定的 Learn 流程；只需要在 Hero 中补足一层动机。

### 建议形态

仅调整首页 Hero 的一小段 copy，避免增加新组件或重新设计版式。优先传达：

- 量子计算不是“更快的普通电脑”；
- 它不适合大多数普通程序，但在少数问题上采用与经典程序明显不同的计算方式；
- LoomQ 的价值不是承诺让用户学会完整量子理论，而是帮助开发者从熟悉的编程心智出发，第一次看懂这种差异。

可参考的表达方向：

> 量子计算不适合大多数普通程序，但在一些问题上，它的计算方式和我们熟悉的程序完全不同。LoomQ 带你从这些差异开始探索。

Hero 只负责提出“为什么值得看”；具体的动机与实例继续由 Experiments 页面承接，例如从搜索、变量关系和状态差异切入，不把首页扩展成产业应用科普页。

### 建议验收

- 不改首页信息架构，不新增 section；
- 不改 Learn 的三步教学主流程；
- 优先替换或收敛 Hero 中与右侧 `Intent → Quantum Program → Backend` 重复的能力说明；
- 第一屏在无作者说明时能较快回答“为什么看 / 给谁 / 怎么开始”三个问题；
- 保留“30 秒看懂一个量子程序”和“直接选择实验”两条现有入口，让 Learn 与 Experiments 继续承担不同职责。

### 优先级

`P1（小改）`。这是定位表达优化，不是功能开发；改动成本低，且直接影响评委第一次打开时是否理解产品为何存在。第一波优化结束后优先于纯装饰性视觉 polish 评估，但不应引发首页重构。

---

## 本轮明确不扩展

暂不因为健壮性审计额外扩大 OpenQASM 门集，例如新增 `u2 / u3 / cu3 / ch` 等非当前正式目标门。除非后续官方契约或测试证明确有必要，否则优先保持 Parser / IR / Serializer 的稳定边界。

同样暂不因为维护性建议重构 Prompt 文件结构、引入额外 schema 框架、增加模型调用次数，或为了理论上的通用性扩大当前正式语法范围。第一波优化完成前，优先保护已经稳定的客观评分路径。

## 后续处理

第一波优化完成后统一复核：

1. 对照届时代码确认以上候选哪些已经被其他 task 顺带覆盖；
2. 按优先级和剩余时间重新排序，只保留仍对应真实评分 / 提交风险的项；
3. 未覆盖且仍高价值的项再拆成最小正式 task，不直接整包实施；
4. 修改 Parser / IR / codegen 后，重新跑 L1 target-native validation；
5. 修改 L3 codegen / stress tests 后，重新跑随机程序 + 全测量注入 differential tests 与 step-budget 回归；
6. 修改 L2 transport / failure handling 后，确认不改变调用预算，并用冻结 SHA 重跑最终 real-model benchmark；
7. 最终提交前把 backend capability snapshot 与 upstream drift 检查纳入同一轮 preflight；
8. 运行参数解释只在无作者体验验收中确认存在真实理解阻塞时再实施，避免为了“更多教学”扩大默认 UI；
9. 首页定位只做 Hero 文案级最小调整，先验证能否补齐 “Why Quantum”，不要因此重写 Learn 或 Experiments。
