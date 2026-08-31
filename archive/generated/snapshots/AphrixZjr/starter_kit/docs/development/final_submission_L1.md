# L1 最终提交信息草稿

> 本文件只准备最终 Issue 所需信息，不是提交回执。Commit SHA 必须在所有验收材料提交并 push 后重新取得。

## 固定信息

- 截止时间：`2026-08-25 12:00 UTC+8`。
- 上游仓库：`QAIDAO/LoomQ-2026`。
- 提交目录：`starter_kit/`。
- 参赛 Levels：仅 L1。
- Hardware evidence：`starter_kit/evidence/README.md`。
- Issue Form：`https://github.com/QAIDAO/LoomQ-2026/issues/new?template=final-submission.yml`。

## 需要最终确认的信息

| 字段 | 草稿值 | 最终检查 |
| --- | --- | --- |
| Team ID | `<GITHUB_USERNAME>`；当前远程提示候选为 `AphrixZjr` | 必须与最终 Issue 作者和 fork 所有者是同一账号。 |
| Fork repository | `https://github.com/<GITHUB_USERNAME>/LoomQ-2026` | 必须公开可读且位于上游 fork network；表单中不能填写代理 URL。 |
| Commit SHA | `<FINAL_40_HEX_SHA>` | 必须在本报告及后续证据提交、push 后重新执行 `git rev-parse HEAD`。 |
| Hardware evidence | `starter_kit/evidence/README.md` | 当前仅申报 OriginQ 一个真机平台，不声称两平台满分。 |

验收报告编写前的工程基线是 `0846d82f2401da47be8a95f0b830cb716f5052b1`。该值仅用于审计追溯，不能作为本文件提交后的最终 SHA。

## Issue Form 填写草稿

```text
标题后缀：<GITHUB_USERNAME> / L1

Team ID:
<GITHUB_USERNAME>

Fork repository:
https://github.com/<GITHUB_USERNAME>/LoomQ-2026

Commit SHA:
<FINAL_40_HEX_SHA>

Levels:
[x] L1
[ ] L2
[ ] L3

Hardware evidence:
starter_kit/evidence/README.md

Declarations:
[x] I agree that this commit is the team's own submission and the team can explain its implementation.
[x] I agree that the organizers may archive, build, execute, and review this commit for competition judging.
[x] I agree that the GitHub Issue creation time is the authoritative submission time.
```

三项声明必须由最终提交账号本人确认。若 Team ID 确认为 `AphrixZjr`，把两个 `<GITHUB_USERNAME>` 一并替换为该值。

## 最终提交前命令

当前 `origin` 是代理包装 URL，`prepare_submission.py` 会拒绝。保留直接 GitHub URL，同时单独让 HTTPS 传输使用本机 10808 代理：

```powershell
git remote set-url origin https://github.com/<GITHUB_USERNAME>/LoomQ-2026.git
git config --local http.https://github.com.proxy http://127.0.0.1:10808
git remote get-url origin
git push origin main
git rev-parse HEAD
python starter_kit/prepare_submission.py --team-id <GITHUB_USERNAME>
```

`git remote get-url origin` 必须显示直接的 `https://github.com/...`，而不是 `gh-proxy.com/...`。如果直连可用，可不设置仓库级代理；若 10808 不是 HTTP 代理，应按实际代理协议调整，不能把代理包装地址填入 Issue。

预检通过后再打开 Issue Form。成功提交必须同时看到：

1. `submission:accepted` 标签；
2. GitHub Actions bot 的归档回执；
3. 回执中的 commit 与 Issue 填写值一致；
4. 回执包含 Archive SHA-256 和 Artifact ID。

代码或证据更新后不能编辑旧 Issue 来替换 SHA，必须重新创建 Issue；截止前最后一次通过校验的提交生效。
