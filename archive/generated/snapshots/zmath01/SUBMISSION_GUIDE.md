# LoomQ-2026 最终提交指南

本仓库工作副本已完成全部代码与证据。距正式提交只剩账号相关步骤（需要你自己的 GitHub 账号操作）：

## 1. Fork 并指向你的账号

```bash
# 在 GitHub 网页上 fork https://github.com/QAIDAO/LoomQ-2026 到你的账号
# 然后把本地 origin 改成你的 fork（用户名就是 Team ID）：
git remote set-url origin https://github.com/<YOUR_GITHUB_USERNAME>/LoomQ-2026.git
git add -A
git commit -m "LoomQ submission: L1 transpiler, L2 agent, L3 hybrid compiler, RISC-V bonus"
git push origin main
```

## 2. 本地预检

```bash
python3 starter_kit/prepare_submission.py --team-id <YOUR_GITHUB_USERNAME>
```

通过后会输出 40 位 commit SHA 与提交表单链接。

## 3. 创建最终提交 Issue

在上游仓库 `QAIDAO/LoomQ-2026` 用 "LoomQ 最终提交" Issue Form 创建 Issue，
填写 Team ID（= 你的 GitHub 用户名）、fork 地址和上一步的 commit SHA。
出现 `submission:accepted` 标签 + 归档 SHA-256 回执才算成功。

- 截止：**2026-08-25 12:00 (UTC+8)**，以 Issue `created_at` 为准。
- 更新代码后新建 Issue 重新提交，不要编辑旧 Issue。
- 申报 L1 真机分时在 Issue 的 Hardware evidence 栏填 `starter_kit/evidence/README.md`。

## 4. （可选）L2 本地真实模型自测

正式评测由组委会注入 DeepSeek。本地想跑通真实链路：

```bash
export LOOMQ_LLM_BASE_URL=https://api.deepseek.com
export LOOMQ_LLM_API_KEY=<你的 Key>
export LOOMQ_LLM_MODEL=deepseek-v4-flash
python3 starter_kit/evaluator.py --level l2
```

没有 Key 时可用 `python3 starter_kit/test_l2_plumbing.py` 验证调用链路（stub 服务）。

## 5. （可选）L1 真机分（+10）

注册量旋云（推荐，最易申请）或本源量子云，用 `adapter.transpile(qasm, target)`
的产物在真机任务页提交，把 job ID、原始 result.json、任务页截图按
`starter_kit/evidence/README.md` 的 L1 真机模板填写归档。
