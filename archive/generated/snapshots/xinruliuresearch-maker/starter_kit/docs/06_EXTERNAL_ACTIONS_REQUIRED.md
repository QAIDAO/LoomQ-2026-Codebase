# 06 · 需要外部或人工完成的动作

本文只列代码不能自行代办、需要账号/外部环境/GitHub 状态或权利确认的事项。已完成的本地实现不在此重复。

## 优先动作表

| 优先级 | 动作 | 所需权限/环境 | 当前事实 |
|---:|---|---|---|
| 0 | 对最终 HEAD 核对官方预检 | 稳定 GitHub 网络 | 已在一个已 push 的干净 HEAD 上完整通过；任何新 commit 必须重跑 |
| 0 | 创建最终上游 Issue 并核对回执 | GitHub 账号 `xinruliuresearch-maker` | Issue 未创建，无 accepted 回执 |
| 1 | 在正式 OpenAI-compatible/DeepSeek 注入环境复测 L2 | 组委会或凭证持有人 | 本地真实 HTTP stub 1/1；正式端点未验证 |
| 1 | 申请 SpinQ/OriginQ 真实 QPU 权限并运行 `--record` | 平台账号、额度、条款接受 | 只有 23/23 dry-run/契约测试；无 job |
| 1 | 在 Python 3.10 Linux/Docker 干净环境冷构建 | 有 Docker 的主机/CI | 当前主机无 Docker，未 build/run |
| 2 | 确认 SCI-Pegasus/Pegasus 权利与许可 | 原项目权利人 | 未获得权威 LICENSE；继续 clean-room |

## A. 标准 Git 仓库与最终提交

标准 clone 已位于 `<standard-clone>/`。以下步骤已经完成：

1. 正式差异已迁入 clone，并排除 `.codex_reference/`、缓存、凭证、临时 workspace、虚拟环境和非必要大文件；
2. Python 3.10.11 的 119/119、公开 evaluator、随机差分与发布审计均已在 clone 中完成；
3. `main` 已 commit 并 push 到 `https://github.com/xinruliuresearch-maker/LoomQ-2026`，远端页面已核验更新；
4. 本文不写死会随发布状态变化的最终提交 SHA。

官方预检已经从 fork 根在一个已 push 的干净 HEAD 上完整通过：

```bash
python starter_kit/prepare_submission.py --team-id xinruliuresearch-maker
```

预检会绑定运行时的完整 HEAD；任何后续 commit 都会使该结果过期。剩余动作：

1. 对 Final Submission Issue 将引用的最终 HEAD 重跑同一官方预检并确认通过；
2. 由 `xinruliuresearch-maker` 在上游 `QAIDAO/LoomQ-2026` 创建“LoomQ 最终提交”Issue；
3. 核对 `submission:accepted` 标签、commit、归档 SHA-256 与 Artifact ID。

只有第 3 步成功才可写“提交成功”。已完成的 fork push 和预检都不能代替 Issue 与接收回执。

## B. L2 正式模型环境

实现只从环境读取：

- `LOOMQ_LLM_BASE_URL`
- `LOOMQ_LLM_API_KEY`
- `LOOMQ_LLM_MODEL`
- `LOOMQ_LLM_TIMEOUT_SECONDS`

本地标准库 HTTP stub 已实际接收请求并通过公开 L2 1/1，也验证了有界调用、超时、429、空/畸形 JSON 和 secret 不泄露。这不能替代正式 `deepseek-v4-flash` 验证。

外部验收需在隔离 shell 临时设置真实变量，运行 L2 tests/evaluator，确认每个 case 至少一次有效请求且总预算满足合同。不要把 Authorization、Key 或模型完整敏感请求写入命令记录、`.env`、日志、截图或 Evidence；完成后清除临时环境。

## C. 真实硬件

运行器、官方来源审计和证据契约见 `docs/hardware/`。两种模式不可混淆：

- `--dry-run` 不读凭证、不联网、不写 evidence、不生成 job ID；
- `--record` 才能提交，且必须证明后端是 QPU、等待完整结果并原子写入证据。

每个平台至少需要：实际 QASM、去敏提交记录、厂商原始响应、规范化结果、metadata（平台/QPU/job ID/shots/带时区时间/commit）。截图只能辅助，不能替代 job 与 raw result。

外部负责人需完成：

1. 获取 SpinQ/OriginQ 账号、真实 QPU 访问权与额度；
2. 在隔离 Python 3.10 环境按各自 runbook 安装/审查可选厂商 SDK；
3. 从环境提供凭证，明确选择 QPU 而非 simulator；
4. 执行 `--record`，在平台控制台核对 job；
5. 审查 timestamp、shots、counts、QASM、commit 与 secrets；
6. 只有材料完整后才勾 `evidence/README.md` 的 L1 真机。

当前没有有效 job ID、原始 QPU 结果或截图；不得生成占位 job。

## D. Linux/Docker

Dockerfile 已提供，但当前 Windows 主机没有可用 Docker 可执行文件。需要在有 Docker 的干净环境执行：

```bash
cd starter_kit
docker build --no-cache -t loomq-pegasus .
docker run --rm loomq-pegasus
docker run --rm -p 127.0.0.1:8000:8000 loomq-pegasus \
  python -m loomq.ui.server --host 0.0.0.0 --port 8000 --workspace /tmp/loomq-runs
```

记录宿主、Docker 版本、镜像 digest、构建时间、默认 CMD 结果和 UI health。完成前只能写“Dockerfile 已提供，未验证”，不能写“容器一键运行已通过”。

## E. 许可与来源确认

SCI-Pegasus 附件和本次 LoomQ fork 根均未观察到可授权其全部内容的权威 LICENSE。需要权利人确认所有权、比赛提交/公开 fork/修改/再分发范围、NOTICE 与第三方素材。

获得书面依据前：

- 不复制 SCI-Pegasus TypeScript、React、CSS、SVG、Prompt、图片或品牌资产；
- 不宣称它是 MIT、Apache、BSD、GPL 或其他许可证；
- 只保留抽象架构启发并独立 Python clean-room 重写；
- 不添加会错误覆盖官方或参考材料的根 LICENSE。

## F. 截止与回执

官方截止为 **2026-08-25 12:00 UTC+8**，以 GitHub Issue `created_at` 为准。若截止前更新代码，需按规则创建新的提交 Issue；本地测试全绿、预检通过或 Issue 已创建都不等于 accepted。必须保留自动回执作为最终状态依据。
