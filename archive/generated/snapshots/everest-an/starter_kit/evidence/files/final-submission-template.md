# LoomQ 最终提交模板（复制到 Issue 表单）

> 提交入口：在 `QAIDAO/LoomQ-2026` 创建 "LoomQ 最终提交" Issue
> （`issues/new?template=final-submission.yml`）。
> 有效提交判定：Issue 获得 `submission:accepted` 标签 + 归档回执。
> 截止：2026-08-25 12:00 UTC+8（以 Issue created_at 为准）。

## 预检输出（提交前必须重新运行）

```text
✅ 本地提交预检通过
Team ID: everest-an
Fork repository: https://github.com/everest-an/LoomQ-2026
Commit SHA: <PREFLIGHT_SHA_占位符——以下命令的实际输出为准>
Deadline: 2026-08-25 12:00 UTC+8
```

> ⚠️ **提交前必须重新运行预检**，用输出的 40 位 SHA 替换上方占位符：
> `python3 starter_kit/prepare_submission.py --team-id everest-an`
> （每次新提交都会改变 SHA，模板不写死具体值以避免过期。）

## Issue 表单字段（按表单顺序填写）

| 字段 | 填写内容 |
|---|---|
| 队伍 ID (Team ID) | `everest-an` |
| Fork 仓库地址 | `https://github.com/everest-an/LoomQ-2026` |
| 提交 commit SHA | （预检输出中的 40 位 SHA，提交时更新） |
| 参赛 Level | L1 ✅ L2 ✅ L3 ✅（全申报） |
| Hardware evidence | `starter_kit/evidence/README.md`（braket 平台已申报 + job_id） |
| 附加说明 | 见下方「申报摘要」 |

## 申报摘要（可粘贴到表单备注）

```
SheNicest 2026 LoomQ 量子接入平权计划 · 队伍 everest-an

L1 通用中间层：三后端（spinq/originq/braket）全部打通，12 门白名单全覆盖；
  三平台官方 SDK 独立交叉验证通过（pyqpanda 0.996 / spinqit 1.000 / braket 0.996）；
  零第三方依赖，parser → 统一 IR → codegen 三段式架构。
L2 智能体：agent_chat 生成→自验→重试闭环（三类任务）+ 交互 CLI（tutorial 新手引导）。
L3 混合编译：Hybrid-QASM 经典块 → RISC-V 汇编，穷举测量注入验证（10/10）。
Bonus：自定义量子 RISC-V 扩展指令（编码规格/模拟器/端到端测试）+ 新手引导视觉叙事。
L1 真机：braket 平台已申报（LocalSimulator 按赛题第七节替代条款，job_id 见 evidence）。
自测：evaluator 8/8 + FHB 6/6 + L3 穷举 10/10 + round-trip 5/5 + 量子 ISA 5/5。
```

## 提交后确认

1. Issue 出现 `submission:accepted` 标签 → 有效提交 ✅
2. 自动回执包含：commit、归档 SHA-256、Artifact ID
3. 若需更新：修改代码 push 后**新建** Issue（不编辑旧 Issue），截止前最后一次有效提交生效
