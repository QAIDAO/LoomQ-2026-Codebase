# Task 14C：L3 Enable + Merge Gate

## 背景

Task 14A 已完成 L3 Hybrid-QASM Compiler 第一版；Task 14B 已由独立 reviewer 做 adversarial audit，并修复量子参数 canonicalization 的确定性 bug。

当前已知状态：

- 分支：`feat/l3`
- L3 实现已接入 `adapter.compile_hybrid()`；
- Public L3 evaluator 已通过；
- 独立 differential / adversarial / metamorphic 回归已通过；
- `submission.yaml` 仍为 `l3:false`；
- L1/L2 生产语义没有因为 L3 被修改。

本任务不是第三轮算法审计，也不是继续扩展 L3 grammar。

目标只有一个：

> **确认当前 L3 实现可以安全申报，并完成 `l3:true` 的最终启用 gate。**

---

## 第一原则

### 1. 不再重构 L3

除非本任务的最终 regression 暴露明确 correctness regression，否则不要：

- 重写 Lexer / Parser / AST / Codegen；
- 添加 speculative grammar；
- 优化 scratch allocator；
- 猜测性支持 `c[22+]`；
- 修改官方 `riscv_emulator.py`；
- 扩大与 L1/L2 的共享代码。

14B 已经给出 `READY_FOR_L3_ENABLE_REVIEW`，本任务只验证 enable 是否安全。

### 2. L1 / L2 必须保持冻结

允许的生产改动原则上只有：

```text
starter_kit/submission.yaml
```

如果最终测试发现明确 L3 regression，可以对 `starter_kit/loomq/l3/**` 做最小修复；否则不要修改 L3 实现。

严禁修改：

- L1 parser / IR / serializers / runners；
- L2 Prompt / Agent / verifier / backend selection；
- Debug Trace / Web 相关代码。

### 3. 不 commit、不 push、不 merge

本 Task 只准备最终可提交状态并给出 merge recommendation。

完成后等待人工确认。

---

# Part A：确认分支与变更边界

先确认：

```bash
git branch --show-current
git status --short
git log --oneline -6
git diff main...HEAD --stat
```

要求：

- 当前必须是 `feat/l3`；
- 分支不得落后 main；如果 main 已有新提交，停止并报告，不要自行 rebase/merge；
- 检查 `main...HEAD` 的生产代码差异，确认除 adapter 的 `compile_hybrid` 接线、L3 独立模块、L3 tests 外，没有意外修改 L1/L2；
- Task markdown 不属于风险项。

记录当前 HEAD SHA。

---

# Part B：开启 L3 声明

将：

```yaml
levels:
  l1: true
  l2: true
  l3: false
```

改为：

```yaml
levels:
  l1: true
  l2: true
  l3: true
```

除此之外不要修改 `submission.yaml`。

特别确认：

- 不新增 L3 网络需求；
- 不修改 L2 network 配置；
- contract / starter kit version 不变；
- entrypoint 不变。

---

# Part C：最小但完整的 L3 final regression

不要再重复 14B 的 2000-program 大型审计。

至少执行：

## 1. L3 专项测试

按项目现有测试命令运行完整 `test_l3_hybrid.py`。

必须包含并通过此前修复的参数语义回归，例如：

```text
1e-3
1.5e+2
.5
5.
-pi/2
-3*pi/8
```

## 2. Public L3 evaluator

```bash
python starter_kit/evaluator.py --level l3
```

必须 PASS。

## 3. 完整 Python regression

执行项目现有完整测试套件。

重点确认：

- L1/L2 测试结果不比 14B 退化；
- skip 原因仍只是既有可选 SDK / worker 环境；
- 不因为 `l3:true` 引入 import-time side effect。

## 4. 根级契约测试

如果仓库已有根级 contract/tests，继续运行并确认无 regression。

---

# Part D：Docker / 官方运行环境验证

使用仓库现有 Dockerfile 做一次干净构建，确保 L3 在官方 Python 3.10 基线环境内可 import / execute。

至少确认容器内：

```bash
python evaluator.py --level l3
```

或按当前 Docker working directory 的等价命令执行并 PASS。

要求：

- 不为了 L3 新增依赖；
- 不修改 Dockerfile 来迁就本地环境，除非发现真实提交环境 bug；
- L3 不需要网络。

如果完整 Docker regression 因 L2 API 配置而无法执行，不要把它误判为 L3 failure；显式运行 `--level l3`。

---

# Part E：最终静态检查

确认：

```bash
git diff --check
```

通过。

同时人工检查：

1. `adapter.compile_hybrid(hybrid_qasm_str)` 官方签名未变；
2. adapter 只是薄路由到 L3 compiler；
3. `riscv_emulator.py` 没被参赛实现修改；
4. requirements 没因 L3 新增依赖；
5. L3 production code 没有 sample hardcode / mock scoring path；
6. `submission.yaml` 现在且仅现在把 `l3` 改为 `true`；
7. 没有 secrets、临时 report、cache、虚拟环境或本地绝对路径进入 diff。

---

# Part F：Merge readiness

不要执行 merge。

最终基于实际结果给出：

```text
READY_TO_COMMIT_AND_MERGE_L3
```

或：

```text
NOT_READY_TO_COMMIT_AND_MERGE_L3
```

只有以下条件全部满足才可以 READY：

- L3 tests PASS；
- Public L3 evaluator PASS；
- full regression 无新增失败；
- Docker L3 PASS；
- diff boundary 正确；
- `l3:true`；
- 无 secret / dependency / artifact 风险；
- 没有新发现的 correctness blocker。

---

# 交付报告

完成后一次性输出：

## 1. Branch state

- branch
- HEAD SHA
- 相对 main 是否 ahead/behind
- production diff 范围

## 2. Enable change

确认 `submission.yaml` 只修改了 `l3:false -> true`。

## 3. Regression

列出：

- L3 tests：pass/fail/skip
- public L3 evaluator
- full starter-kit tests
- root tests（如存在）
- Docker L3 evaluator
- `git diff --check`

## 4. Final risk check

只报告仍然真实存在的风险，不要重复已经接受的规格歧义作为 blocker。

特别说明：

- `c[22+]` / 极端 scratch pressure 如果没有新的官方证据，不作为本轮 blocker；
- 不因为这些已知边界继续扩 compiler。

## 5. Recommendation

只能输出：

```text
READY_TO_COMMIT_AND_MERGE_L3
```

或

```text
NOT_READY_TO_COMMIT_AND_MERGE_L3
```

如 READY，附上建议 commit message，例如：

```text
feat: enable L3 hybrid compiler
```

---

## 完成限制

完成后不要 commit、不要 push、不要 merge。
