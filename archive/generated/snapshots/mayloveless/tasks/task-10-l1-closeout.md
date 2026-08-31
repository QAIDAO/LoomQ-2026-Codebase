# Task 10：L1 收口、复现说明与提交预检

## 目标

将当前三后端 L1 实现整理为可复现、可审查、可提交的稳定候选版本。

当前功能已经完成：

- 统一 OpenQASM 2.0 Parser 与平台无关 Circuit IR；
- SpinQ、OriginQ、Braket 三种目标 IR；
- SpinQ Basic Simulator、OriginQ CPUQVM、Braket LocalSimulator；
- 官方 12 门、参数表达式、测量映射与统一结果 Schema；
- 三后端公开 evaluator 6/6；
- 隐藏风格组合电路回归。

本任务只做 L1 收口，不开始 L2，不接真机，不做大规模重构。

## 范围

### 1. 审核提交配置

检查 `starter-kit/submission.yaml`：

- `contract_version`、`starter_kit_version` 与仓库当前版本一致；
- 只声明 `l1: true`；
- Python 版本为 3.10；
- L1 不要求网络；
- 不添加无关字段，不修改上游契约结构。

若当前内容已经正确，不要为了产生 diff 而修改。

### 2. 更新 L1 设计规格的当前状态

更新 `starter-kit/docs/l1-spec.md`，使其准确反映现状：

- 架构图包含 SpinQ、OriginQ、Braket 三个 Serializer 与 Runner；
- OriginQ 不再写成“后续”；
- 说明三个 SDK 的环境边界：
  - 主 Python 环境：Braket；
  - SpinQ 独立 Worker；
  - OriginQ 独立 Worker；
- 说明公开 `transpile()` 与私有 SDK execution mode 的区别；
- 将已完成项和暂不包含项写清楚；
- 不把计划文档扩写成冗长教程。

### 3. 新增 L1 复现手册

新增 `starter-kit/docs/l1-runbook.md`，至少包含：

1. 一段简短架构说明；
2. 三后端和依赖版本；
3. 推荐的 Docker 复现方式；
4. 本地开发环境的可选搭建方式；
5. 公开 evaluator、全量测试、OriginQ 专项和隐藏风格测试命令；
6. `LOOMQ_SPINQ_PYTHON`、`LOOMQ_ORIGINQ_PYTHON` 的含义；
7. 已知限制：
   - 仅支持末尾测量；
   - pyQPanda 3.8.5 已验证环境为 Python 3.10/x86_64；
   - SpinQit 传递依赖较大，干净构建较慢；
   - 当前只接本地模拟器，不含真机。

推荐命令应能直接复制执行，例如：

```bash
cd starter-kit
docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
docker run --rm loomq-l1 python -m unittest discover -s tests -v
```

不得在文档里写入本机绝对路径。

### 4. 固化 L1 公开报告

在干净 Docker 镜像中执行三后端公开 evaluator，将最终 JSON 报告保存为：

```text
starter-kit/evidence/files/l1-public-report.json
```

要求：

- target 为 `spinq,originq,braket`；
- 报告中 6 项全部通过；
- 不手工伪造或编辑运行结果；
- 不保存临时镜像 ID、宿主机路径或无关日志。

### 5. 填写工程与产品化证据

更新 `starter-kit/evidence/README.md`：

- 只勾选当前确实可以申报的“工程与产品化”；
- 不勾选 L1 真机、L2、RISC-V 或尚未完成的 Bonus；
- 填写：
  - 干净构建与启动命令；
  - 架构说明路径；
  - 目标用户与使用场景；
  - 完整复现流程路径；
  - 公开报告路径。

描述必须基于当前真实实现，不夸大为真机或完整零基础产品。

### 6. 提交预检

使用 GitHub 用户名 `mayloveless` 执行：

```bash
python starter-kit/prepare_submission.py --team-id mayloveless
```

本步骤只做预检：

- 不创建最终提交 Issue；
- 不上传归档；
- 不修改 Git 历史；
- 如果脚本生成临时归档或输出文件，确认是否应忽略，不要盲目提交。

同时检查：

- 仓库不存在 API Key、Token、Cookie；
- 没有提交 `.venv*`、缓存、Docker 产物；
- 最终跟踪文件总量满足 100 MiB 限制；
- 文档中没有开发者本机绝对路径。

### 7. 最终回归

至少执行：

```bash
cd starter-kit

docker build --no-cache -t loomq-l1 .
docker run --rm loomq-l1
docker run --rm loomq-l1 python -m unittest discover -s tests -v
docker run --rm loomq-l1 python -m unittest tests.test_originq_runner tests.test_originq_worker tests.test_originq_serializer -v
docker run --rm loomq-l1 python -m unittest tests.test_l1_hidden_like -v
```

## 修改边界

允许修改或新增：

- `starter-kit/docs/l1-spec.md`
- `starter-kit/docs/l1-runbook.md`
- `starter-kit/evidence/README.md`
- `starter-kit/evidence/files/l1-public-report.json`
- 必要时 `.gitignore` / `.dockerignore` 中与预检产物相关的最小规则

除非收口测试发现真实阻断缺陷，否则不要修改 Parser、IR、Serializer、Runner 或 evaluator。

不要：

- 开始 L2、L3 或真机接入；
- 为缩短镜像构建时间大改依赖结构；
- 提交虚拟环境、镜像导出、压缩归档或大体积日志；
- commit 或 push。

## 验收标准

- L1 设计规格与当前三后端实现一致；
- 有一份可复制执行的 L1 runbook；
- 工程证据填写真实、克制；
- 干净 Docker 三后端公开 evaluator 6/6；
- 全量测试无失败、无跳过；
- `prepare_submission.py --team-id mayloveless` 预检通过，或明确列出非代码阻断原因；
- 未引入生产逻辑改动；
- 未 commit、未 push。

## 完成后汇报

只需汇报：

1. 文档和证据修改清单；
2. 三后端 evaluator 结果；
3. 全量及专项测试结果；
4. 提交预检结果；
5. 仓库大小、秘密扫描和绝对路径检查结果；
6. 是否发现必须在进入 L2 前修复的 L1 问题。
