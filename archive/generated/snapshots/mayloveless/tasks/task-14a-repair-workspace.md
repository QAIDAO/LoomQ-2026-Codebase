# Task 14A — Repair：真实的检查 / 修复 / 验证工作区

## 背景

Learn、Experiments、Explorer 的主路径已经基本闭合。接下来进入导航中的进阶能力。

优先实现 `04 Repair · 进阶`，因为它直接对应 L2 的核心能力之一：

> 已有 OpenQASM → 说明目标 → 检查 / 修复 → 本地验证

当前 `AdvancedCapabilityScreen` 仍是占位页，但底层 production L2 agent 已经支持 `repair_qasm`，并且已有真实 trace：`intent`、`qasm_candidate`、`parser_validation`、`semantic_verification`、`repair_started`、`repair_candidate`、`agent_result`。

本 Task 的目标不是重新设计 repair agent，而是把**现有真实能力接到 Web**。

---

## 产品定位

Repair 页面回答的是：

> **“我已经有一段量子程序，但它可能有问题。LoomQ 能不能告诉我发生了什么，并给出一个经过验证的修复提案？”**

核心流程：

```text
原始程序
→ 原始输入检查
→ LoomQ 修复提案
→ 本地验证证据
→ 用户确认应用
```

注意安全语义：

> **提案 → 验证 → 用户确认 → 应用**

不能收到响应后自动覆盖用户原始 QASM。

---

## 1. Repair 页面从占位页变成真实工作区

`04 Repair · 进阶` 不再显示“即将接入 Web”。

`05 Backend · 进阶` 本 Task 不改，继续保留占位状态。

Repair 建议保持与 Explorer 当前视觉语言一致，但不需要复制 Explorer 的两栏 Program / Explain。

推荐结构：

```text
04 Repair · 进阶
检查和修复已有量子程序

┌────────────────────┬─────────────────────────────┐
│ ORIGINAL           │ REPAIR RESULT               │
│                    │                             │
│ 你希望它做什么？   │ 原始程序检查                │
│ [目标描述]         │                             │
│                    │ 修复提案                    │
│ OpenQASM           │ [repaired QASM]             │
│ [code textarea]    │                             │
│                    │ 验证结果                    │
│ [检查并修复]       │                             │
│                    │ [应用修复到编辑区]          │
└────────────────────┴─────────────────────────────┘
```

窄屏可以纵向堆叠。

---

## 2. 输入

### A. 用户目标

字段标题：

> **你希望这段程序做什么？**

示例 placeholder：

> 例如：生成 Bell 态并测量两个量子比特

目标必须参与 repair 请求，不能只让模型修语法。

### B. OpenQASM

大号等宽字体 textarea / editor-like textarea。

标题：

> **原始 OpenQASM 2.0**

### C. 示例

提供一个轻量“加载示例”按钮即可，不要自动预填。

示例可以是一个**明确有语法问题的 Bell 程序**，例如漏掉一处分号；目标为“生成 Bell 态并测量”。

示例只用于帮助评委快速体验，不做 scenario 系统。

### D. 提交

按钮：

> **检查并修复**

目标或 QASM 为空时禁用。

---

## 3. 新增专用 `/api/repair`，但必须复用 production agent

不要让前端自己模拟 repair，也不要复制一套 L2 逻辑。

建议在 `debug_web.py` 增加：

```text
POST /api/repair
{
  "goal": "...",
  "qasm": "..."
}
```

### 重要约束

1. **必须调用现有 production `_run_agent` / `build_debug_trace` 路径**；
2. 不修改 `agent_chat(prompt: str) -> str` 的官方签名；
3. 不修改 formal evaluator 路径；
4. 不新增额外 LLM diagnosis call；
5. Repair 页面不需要 Teaching Explainer，因此不要为了 Repair 再调用 `explain_validated_circuit`；
6. 不增加超过现有 L2 pipeline 的模型调用。

建议新增纯 helper，例如：

```python
build_repair_payload(goal: str, qasm: str) -> dict
```

它可以：

1. 对**用户原始 QASM**做一次本地 `validate_qasm(...)` 检查；
2. 捕获 `QASMValidationError.diagnostic`，作为 `input_validation`；
3. 构造明确的 repair prompt；
4. 调用一次 `build_debug_trace(prompt)`；
5. 从真实 agent events / final reply 中返回最终 QASM 和验证证据。

不要因为原始 QASM 本地校验失败就提前停止——语法错误正是 Repair 要处理的输入。

---

## 4. Repair prompt

服务端统一构造，不要把 prompt 模板散落在前端。

语义应明确：

```text
请检查并修复下面的 OpenQASM 2.0 程序。
保持用户明确声明的目标功能和测量语义不变。

用户期望：<goal>

原始程序：
<qasm>
```

不要在 prompt 中替用户添加未声明的目标态或测量要求。

模型应通过现有 SYSTEM_PROMPT 识别为 `repair_qasm`。

---

## 5. 原始程序检查

这一块只展示**真实可证明的信息**。

如果原始 QASM 本地语法 / 结构检查失败：

```text
原始程序没有通过本地检查
<真实 diagnostic>
```

如果原始 QASM 本地检查通过：

```text
原始程序语法可解析
LoomQ 会继续根据你描述的目标检查并生成修复提案。
```

不要在这里只因为语法通过就写“程序正确”。

不要伪造“发现 3 个问题”之类的问题数量。

---

## 6. 修复提案

从真实最终 `agent_result.qasm`（或同等可靠来源）取得修复后的完整 OpenQASM。

标题：

> **LoomQ 的修复提案**

显示完整代码，默认可读，不要藏到很深的 disclosure。

可以在旁边显示 agent reply 中的简短 explanation，但：

- 不要让 explanation 覆盖本地验证结论；
- 不要把模型解释当成 correctness evidence。

如果最终没有可靠 QASM，就不要渲染假的 repair result。

---

## 7. 验证结果

验证区必须只依据真实 trace。

至少识别：

### parser_validation

真实 `status=ok` 时才显示：

> ✓ OpenQASM 语法与结构校验通过

真实 `status=error` 时显示失败，不可显示绿色通过。

### semantic_verification

如果真实存在成功事件：

> ✓ 目标语义验证通过

若有真实 fidelity，可以展示，例如：

> Fidelity 0.998 · threshold 0.970

如果 semantic verification 没有发生 / 不支持：

> 未进行确定性纯态语义验证

不要把“没有事件”写成“已验证”。

### agent_result

只用于说明最终候选已通过 production pipeline。

注意：`agent_result.data.repaired` 表示 pipeline 是否触发了**额外的一次 bounded repair**，它不等于“用户的 repair 请求有没有被执行”。

因此不要根据 `repaired=false` 写“无需修复”。

---

## 8. 应用修复

默认状态：原始输入 textarea **保持不变**。

结果区提供主按钮：

> **应用修复到编辑区**

用户点击后才：

- 把 repaired QASM 写入左侧 QASM textarea；
- 显示轻量状态 `已应用到编辑区`；
- 不自动再次发请求；
- 不清除当前 repair evidence，方便对照。

可以另提供：

> 重新检查

但不需要做复杂历史版本。

本 Task 暂不做“在 Explorer 中打开修复结果”；后续需要时再串联。

---

## 9. Loading / Error

请求是非流式返回。

Loading 文案保持诚实，例如：

> **正在检查并准备修复提案**
>
> LoomQ 会先理解目标，再让修复后的程序经过本地验证。

不要做假的逐阶段实时完成动画。

错误时：

> 这次检查没有完成，请检查模型配置后重试。

不要暴露 traceback、API key、文件路径或原始模型响应。

---

## 10. 不做

- 不改 Backend 页面；
- 不改 Explorer；
- 不改 Learn / Experiments；
- 不改 stable prompts；
- 不改 L2 SYSTEM_PROMPT，除非现有 repair 输入确实无法被识别，并且必须先说明原因；
- 不改 semantic verifier；
- 不改 one bounded repair 限制；
- 不增加新的 LLM call；
- 不做代码编辑器依赖；
- 不做多文件 QASM；
- 不做 repair 历史版本；
- 不做自动应用。

---

## 11. 测试要求

至少覆盖：

1. Repair 页面不再显示“即将接入 Web”；
2. Backend 页面仍保持占位；
3. `/api/repair` 缺少 goal / qasm 时返回安全 400；
4. 原始 QASM 语法错误时，`input_validation` 返回真实失败信息，但仍调用 repair agent；
5. 原始 QASM 语法通过时，不错误宣称语义正确；
6. Repair payload 不调用 Teaching Explainer；
7. 最终 repaired QASM 来自真实 agent result；
8. parser / semantic UI 状态严格由真实 trace 决定；
9. 点击“应用修复到编辑区”之前原始 textarea 不变；
10. Generic / Curated Explorer 行为不受影响；
11. formal `agent_chat` 签名与 evaluator 路径不变。

如果仓库现有测试命令可运行，可以执行；不要为了本 Task 修改无关失败项。

---

## 完成标准

第一次打开 Repair 的开发者可以独立完成：

```text
粘贴一段已有 QASM
→ 说明它本来应该做什么
→ 看懂原始输入哪里至少存在可证明的问题
→ 得到 LoomQ 的修复提案
→ 看到真实本地验证证据
→ 自己决定是否应用修复
```

完成后停止，等待 review。