# Final Release Optimization Plan

> Release 阶段优化清单。
>
> 本文用于从 robustness follow-up 候选中筛选最终值得执行的项目。
>
> 原则：
>
> - 优先保护已经通过验证的 L1 / L2 / L3 路径；
> - 只处理真实评分风险、提交风险或高收益体验问题；
> - 没有失败证据不修改稳定 production 逻辑；
> - 避免 release 阶段引入大范围重构。

---

## P1 - Recommended

## 1. L3 Resource Boundary Audit

### Goal

补充 L3 在资源边界上的验证，不修改 compiler 语义。

### Scope

- execution step 数量统计；
- 生成 assembly 规模统计；
- nested if / else 压力测试；
- 多 measurement / classical feedback 路径。

### Acceptance

- audit 记录最大 execution step；
- 测试集保持安全余量；
- 不出现 RecursionError 或异常编译时间增长；
- 与现有 differential validation 保持一致。

---

## 2. Backend Capability Snapshot Preflight

### Goal

在最终提交前确认 backend capability 数据仍与 selector 使用的事实源一致。

### Scope

增加 release preflight 检查：

- capability version；
- 文件 hash / 内容变化；
- selector hidden-like 回归。

### Constraints

- 不增加运行时网络依赖；
- 不在 production runtime 中拒绝合法输入；
- 发现变化后人工审阅语义差异。

---

## 3. Hero "Why Quantum" Minimal Copy

### Goal

提升第一次打开页面时的定位理解。

### Scope

只调整 Hero 文案，不重构首页。

需要回答：

- 给谁使用；
- 为什么量子计算值得了解；
- LoomQ 如何帮助开发者开始探索。

### Constraints

- 不新增大型 section；
- 不替代 Learn / Experiments 页面职责；
- 不扩展为量子产业科普页。

---

## P2 - Optional

## 4. Explorer Execution Parameter Explanation

### Goal

降低第一次运行实验时对执行参数的困惑。

### Possible Content

轻量说明：

- backend 为什么选择；
- shots 的意义；
- measured bits 如何读取；
- ideal probability 与 finite sample 的区别。

### Constraints

- 默认不占主视图；
- 不新增教学流程；
- 复用已有 execution 数据。

---

## Won't Do Before Submission

以下项目暂不执行：

### OpenQASM Whole Register Expansion

原因：

- 当前 L1 已通过充分验证；
- 修改 Parser / IR / Serializer 风险高于收益。

### L2 Error Taxonomy

原因：

- 主要改善诊断体验；
- 不直接影响当前评分正确率。

### Compiler / Prompt Architecture Refactor

原因：

- release 阶段避免结构性变化；
- 保持已验证路径稳定。

### New Language Features

原因：

- 不因理论完整性扩大支持范围；
- 优先满足当前正式契约。

---

## Final Freeze Checklist

提交前：

1. 完成必要优化；
2. 清理未提交修改；
3. 确认 `git status` clean；
4. clean checkout 验证；
5. Docker clean build；
6. 重跑关键 audit；
7. 生成最终 submission evidence。
