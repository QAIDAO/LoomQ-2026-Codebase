# Task 13D — Web UX 信息减法 + 场景化示例入口

## 背景

13B/13C 已经证明：Web Quantum Debugger 能复用真实 Agent/Circuit Trace，并通过初始化、逐 Gate 回放、概率变化、Teaching Explainer、JIT 概念解释帮助非量子背景的软件开发者理解 Bell / GHZ / phase case。

当前主要问题已经从“缺少解释”变成“信息层级过多”：

- 左侧同时展示 Circuit Steps 和完整 Agent 生成/验证过程，调试完成后 Agent Trace 会持续抢占注意力；
- 当前步骤已经有“为什么需要 / 发生了什么”，但完整 QASM 仍长期占据主区域，短电路尤其显得重复；
- 示例入口仍使用 Bell / GHZ / Bell- 等量子术语，第一次接触量子的用户在进入 Debugger 前就需要先懂名词。

本 Task 只做 UX 信息层级与入口包装，不改变 L2 correctness、Circuit Trace、Teaching Explainer 的语义。

---

## 目标

让首次使用者的主线变成：

> 我想理解一个普通问题 → 量子版本为什么值得看 → 进入 Debugger → 当前在做什么 → 为什么做 → 状态怎么变

同时把 Agent Trace 从“结果页长期占位的信息”改成“请求执行期间的过程反馈”。

---

## 1. Loading 阶段：展示 LoomQ 正在做什么，但不要伪造实时 Trace

当前 `/api/debug` 是一次请求完成后返回完整 payload，本 Task **不要**为了 loading 动画引入 SSE / WebSocket / polling / 新后端协议。

请求执行期间，在空工作区或主区域展示一个轻量的过程面板，例如：

- 理解需求
- 生成量子程序
- 本地语法校验
- 验证量子状态
- 准备可视化解释

要求：

- 可以使用逐项高亮 / pulse / step animation 提供过程感；
- 不要在真实结果返回前显示“✓ 已通过”“Fidelity 1.0”“repair 成功”等未经返回结果确认的信息；
- 不要称其为“实时 Agent Trace”；
- loading 结束后，该过程面板消失。

错误时直接进入现有错误态，不需要保留一份假的流程历史。

---

## 2. 调试完成后：移除主界面的 Agent Trace

普通 Circuit Debugger 结果页不再长期展示 `SidebarProcess / 生成与验证过程`。

保留真实 Agent Trace 数据和底层协议，但不要让它继续占主工作区。

结果页只需要一个很轻的可信度状态，例如：

> ✓ 已生成并通过 LoomQ 验证

如果能从真实事件安全得出 fidelity，可以在非常轻的 secondary text 中展示；不是必须。

不要新增复杂“验证详情”抽屉。本 Task 的目标是减法。

Backend selection 模式可继续使用现有独立展示，不强行套用 Circuit Debugger 的布局。

---

## 3. 当前步骤与代码进一步合并

保留左侧 Circuit Steps 导航和右侧状态变化。

中间区域以“当前步骤”为中心，不再让完整 QASM 永久占据大量空间。

当前步骤至少显示：

- 第 N / M 步 + step title
- 当前 Gate / measurement 对应的 **当前 QASM 语句**（初始化步骤不显示伪代码）
- “为什么这里需要它？”（Teaching Explainer purpose 或现有 fallback）
- Circuit Diagram / 当前 Gate 高亮
- 上一步 / 下一步 / 自动播放控制

完整 QASM 改为次级入口：

- 默认折叠；
- 用 `查看完整 QASM` / `展开完整代码` 打开；
- 展开后继续保留当前 operation 对应行高亮和自动滚动；
- 初始化步骤展开完整 QASM 时不高亮任何执行语句。

不要引入 Monaco 或新的代码编辑器依赖。

目标不是“隐藏代码”，而是让代码成为当前解释的证据，而不是与解释竞争的第四条主线。

---

## 4. 示例入口改成普通软件开发者能理解的问题

不要把示例按钮的主标题继续写成：

- Bell 态
- GHZ 态
- Bell- / phase

量子术语可以作为 secondary label，但不能成为理解入口的前提。

至少把现有稳定示例包装成 3 个场景卡 / 场景按钮。推荐：

### 示例 A：两个结果为什么总是同步？

底层 prompt 继续使用稳定的 Bell 请求，例如：

`生成一个 Bell 态并测量`

展示文案：

- 普通程序：生成一个随机 bit，再复制结果，也能得到两个相同值；
- 量子版本：这里不是复制经典结果，而是先建立两个量子位之间的纠缠，再分别测量；
- 值得看什么：理解“叠加 → 纠缠 → 测量”如何一步步建立。

注意：不要声称 Bell 电路比普通计算“更快”。

### 示例 B：三个量子位怎样变成一个整体？

底层 prompt 继续使用稳定 GHZ 请求：

`生成一个 3 比特 GHZ 态并测量`

展示文案重点：从两个量子位的关联扩展到三个量子位，观察关联如何逐步传播。

不要包装成不存在的经典性能优势。

### 示例 C：概率没变，量子状态真的没变吗？

底层 prompt 继续使用稳定 phase / Bell- 请求，例如：

`生成一个带相对相位的 Bell- 态，不要求测量`

展示文案重点：经典直觉通常只看概率；量子程序还需要关心相位，相位会影响后续干涉。

量子术语 `Bell / GHZ / Phase` 可以作为卡片角标、小字或进入 Debugger 后的名称，不作为主标题。

---

## 5. 示例进入 Debugger 前提供最轻量的问题背景

用户点击场景示例后，不需要新增独立页面。

可在 request 区域或 Debugger 顶部显示一张非常轻的 Context Card，字段控制在：

- `你正在理解什么？`
- `普通程序怎么做 / 怎么理解？`
- `量子版本有什么不同？`
- `这次重点看什么？`

内容来自前端静态 metadata，不增加 LLM 调用。

用户手动输入任意 prompt 时，不强行生成这张静态背景卡；可以只展示原始目标。

---

## 6. 不要扩大 Scope

本 Task 不做：

- SSE / WebSocket / 真正实时 Agent streaming
- 新的 LLM 调用
- 修改 Teaching Explainer schema
- 修改 L2 objective / `agent_chat`
- 修改 parser / semantic verifier / repair 逻辑
- 真机运行
- Bloch sphere / 复杂 phase visualization
- 概率大规模过滤系统
- autoplay 速度控制
- 移动端专项重构
- Monaco / 代码编辑能力
- L3

---

## 7. 验收重点

至少人工走一遍 Bell、GHZ、phase 三个示例。

重点不是“功能都还在不在”，而是确认第一眼信息顺序是否变成：

1. 我在理解什么问题？
2. 量子版本为什么值得看？
3. 当前执行到哪一步？
4. 为什么需要这一步？
5. 状态发生了什么变化？

同时确认：

- loading 时有清晰过程反馈，但没有伪造实时成功信息；
- 请求完成后主工作区不再持续展示 Agent Trace；
- 左栏主要只承担 Circuit Steps；
- 当前 QASM 语句与 Current Step 同处一个信息块；
- 完整 QASM 默认折叠，展开后高亮仍正确；
- 13C 的初始化、purpose、concept、phase-only 提示不回退；
- Teaching Explainer 降级时仍然可以正常调试；
- Backend selection 不被破坏。

---

## 8. 回归

执行并报告：

- Web build / 现有 Web tests
- Python 全量测试
- Public L2 evaluator
- Bell / GHZ / phase 页面人工验收

不要为了本 Task 改写冻结的 L2 正式路径。

完成后停止，不要继续自行 polish；先等待人工查看页面信息密度与入口体验。
