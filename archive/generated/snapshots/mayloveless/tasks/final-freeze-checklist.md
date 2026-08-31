
# Final Freeze Checklist

目标：

在提交前冻结 LoomQ 最终版本。

原则：

- 不新增功能；
- 不重构架构；
- 不修改评分相关逻辑；
- 任何失败只做最小修复。

---

# Phase 1: Repository Cleanup

## Git 状态

确认：

- 所有需要保留的代码已经 commit；
- 不存在未追踪临时文件；
- 不存在本地实验修改。

执行：

```bash
git status
````

目标：

```
working tree clean
```

---

## Audit 文件整理

检查新增：

* L1 audit
* L2 audit
* L3 audit
* Backend preflight
* Resource audit

确认：

保留：

* 可复现脚本；
* 测试；
* 必要文档。

删除：

* 临时 JSON 输出；
* 本地生成文件；
* 包含敏感信息的文件。

---

# Phase 2: Full Test Verification

运行：

```bash
python -m unittest discover -s starter_kit/tests -v
```

记录：

* PASS
* SKIP
* FAIL

失败必须停止。

---

# Phase 3: Docker Clean Build

禁止：

* bind mount
* 本地未提交代码

流程：

```bash
git rev-parse HEAD
git status
```

确认：

* SHA 固定
* dirty=false

然后：

```bash
docker build --no-cache -t loomq-final .
```

---

# Phase 4: Docker Runtime Verification

在 clean image 中运行：

## L1

* native audit
* evaluator

## L2

* objective audit
* backend selection

## L3

* differential
* resource boundary

记录：

* SHA
* image tag
* execution time
* PASS/FAIL

---

# Phase 5: Evidence Freeze

生成最终记录：

包含：

* commit SHA
* clean status
* Docker image build result
* L1 result
* L2 result
* L3 result
* backend snapshot hash

禁止：

* 修改代码后继续使用旧报告。

---

# Phase 6: Submission Review

人工检查：

## Product

第一次打开：

* 是否知道目标用户？
* 是否知道为什么量子值得了解？
* 是否知道下一步点哪里？

## Demo flow

推荐：

1. Hero
2. Learn
3. Experiment
4. Explorer
5. Repair
6. Backend

## Final rule

完成 freeze 后：

禁止：

* 改 compiler
* 改 agent prompt
* 改 evaluator
* 改 IR

除非发现提交 blocker。

