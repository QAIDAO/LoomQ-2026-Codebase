# LoomQ 2026 submission archive

This repository archives all 58 formal LoomQ 2026 submissions. Each entry records the organizer-supplied GitHub HTTPS URL and an exact 40-character commit SHA in `archive/submissions.json`.

## Exactness proof

`archive/generated/snapshots/<contestant_id>/` is the exact root Git tree from the recorded upstream commit. The sync tool grafts that tree object into this repository. It does not copy a checkout, run `git archive`, or rebuild the tree from files.

`archive/generated/commit-objects/<contestant_id>.obj` stores the canonical commit object bytes, including the Git object header. Offline verification proves both conditions for every submission:

```text
sha1(canonical commit object bytes) == manifest commit SHA
commit root tree OID == archived snapshot subtree OID
```

Verification also rejects missing or extra contestant paths and commit records.

## Update and verify the archive

Run these commands from the repository:

```sh
python3 tools/loomq_archive.py sync
python3 tools/loomq_archive.py verify --staged
git commit
python3 tools/loomq_archive.py verify
python3 tools/loomq_archive.py verify --remote
```

`sync` fetches only each exact SHA over HTTPS. It validates all 58 manifest rows before the first fetch. It builds the complete result in isolated bare repositories. After every submission passes, it replaces the generated worktree and stages `archive/submissions.json` with the complete generated archive. A second `sync` with unchanged inputs produces no staged or unstaged diff.

Edit only `archive/submissions.json` to change the roster. The sync tool owns all files under `archive/generated/` and removes stale generated paths.

## Untrusted content and external objects

All submission contents are untrusted. Do not run scripts, builds, package managers, tests, hooks, or discovery tools under `archive/generated/snapshots/`. The archive workflow and CI only read Git objects and file metadata.

The manifest uses the `pointer-only` policy for Git LFS pointers and gitlinks. Git LFS pointer files remain exact pointer blobs. Their external payloads are not part of this archive. Gitlinks retain the submitted commit OID, but nested repository contents are not part of this archive.

The tool preserves executable modes and symlink targets. It rejects paths that cannot be safely materialized, including `.git` components, prefix collisions, and case or Unicode-normalization collisions.

## Contestant code navigation

The table below lists every formal contestant on baseline `998cd4e67b1b29f0f1eb8bafdc155072dfda2980`. The roster is exactly the 58 unique `contestant_id` values in `archive/submissions.json`. There are no extra, missing, empty, or unreadable snapshot directories on this baseline.

Each directory link is a repository-relative path and opens the archived snapshot on GitHub. Stack and entry columns are static identifications (filenames, dependencies, and source features). They do not mean the submission runs, scores, or talks to real hardware.

A separate Chinese static analysis of the same 58 snapshots lives in [`docs/static-analysis-zh.md`](docs/static-analysis-zh.md). README and that report use the same roster, in the same order.

Path note: `infiniteHY` uses `starter-kit/` (hyphen). The other 57 snapshots use `starter_kit/` (underscore). Do not hard-code a single starter directory name.

Excluded / duplicate / empty directories: none on this baseline.

| # | Contestant | Snapshot | Static stack | Static entry candidates |
|---:|---|---|---|---|
| 1 | `infiniteHY` | [archive/generated/snapshots/infiniteHY/](archive/generated/snapshots/infiniteHY/) | Python, quantum SDK | `starter-kit/agent.py`; baseline `starter-kit/{adapter.py,evaluator.py}` |
| 2 | `savannahyuan17-afk` | [archive/generated/snapshots/savannahyuan17-afk/](archive/generated/snapshots/savannahyuan17-afk/) | Python, quantum SDK | `starter_kit/agent.py` |
| 3 | `cycyotw` | [archive/generated/snapshots/cycyotw/](archive/generated/snapshots/cycyotw/) | Python, Shell, quantum SDK | `loomq.sh`; `starter_kit/loomq/agent.py` |
| 4 | `everest-an` | [archive/generated/snapshots/everest-an/](archive/generated/snapshots/everest-an/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 5 | `Muhongfan` | [archive/generated/snapshots/Muhongfan/](archive/generated/snapshots/Muhongfan/) | Python, quantum SDK | `starter_kit/l2_agent.py`; `starter_kit/runner.py` |
| 6 | `WilderNoTrack` | [archive/generated/snapshots/WilderNoTrack/](archive/generated/snapshots/WilderNoTrack/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/cli.py`; `starter_kit/loomq/web/server.py` |
| 7 | `AphrixZjr` | [archive/generated/snapshots/AphrixZjr/](archive/generated/snapshots/AphrixZjr/) | Python, HTML/JS, quantum SDK | `starter_kit/web/server.py`; `starter_kit/web/static/index.html` |
| 8 | `lyl2222` | [archive/generated/snapshots/lyl2222/](archive/generated/snapshots/lyl2222/) | Python, HTML/JS, quantum SDK | `starter_kit/web_app.py`; `starter_kit/loomq/agent.py` |
| 9 | `Jimmy658` | [archive/generated/snapshots/Jimmy658/](archive/generated/snapshots/Jimmy658/) | Python, quantum SDK | `starter_kit/l2_agent.py` |
| 10 | `tale03` | [archive/generated/snapshots/tale03/](archive/generated/snapshots/tale03/) | Python, Flask, HTML, quantum SDK | `starter_kit/app.py` |
| 11 | `AzureWynn` | [archive/generated/snapshots/AzureWynn/](archive/generated/snapshots/AzureWynn/) | Python, Shell, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 12 | `hongwei-2026` | [archive/generated/snapshots/hongwei-2026/](archive/generated/snapshots/hongwei-2026/) | Python, quantum SDK | `starter_kit/loomq_agent.py` |
| 13 | `zhangxinyang-z` | [archive/generated/snapshots/zhangxinyang-z/](archive/generated/snapshots/zhangxinyang-z/) | Python, quantum SDK | `starter_kit/chat.py` |
| 14 | `xinruliuresearch-maker` | [archive/generated/snapshots/xinruliuresearch-maker/](archive/generated/snapshots/xinruliuresearch-maker/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/ui/server.py`; `starter_kit/loomq/bonus/demo.py` |
| 15 | `EndlessTR` | [archive/generated/snapshots/EndlessTR/](archive/generated/snapshots/EndlessTR/) | Python, HTML/JS, quantum SDK | `starter_kit/quantumhelper_web/server.py` |
| 16 | `2IKK12` | [archive/generated/snapshots/2IKK12/](archive/generated/snapshots/2IKK12/) | Python, HTML/JS, quantum SDK | `starter_kit/web_app.py`; `starter_kit/loomq_agent.py` |
| 17 | `mayloveless` | [archive/generated/snapshots/mayloveless/](archive/generated/snapshots/mayloveless/) | Python, React/TypeScript, quantum SDK | `starter_kit/web/src/main.tsx`; `starter_kit/loomq/l2_agent.py` |
| 18 | `0Dionysus0` | [archive/generated/snapshots/0Dionysus0/](archive/generated/snapshots/0Dionysus0/) | Python, HTML/JS, quantum SDK | `starter_kit/web_chat.py`; `starter_kit/loomq_l2/cli.py` |
| 19 | `Huxingyu` | [archive/generated/snapshots/Huxingyu/](archive/generated/snapshots/Huxingyu/) | Python, quantum SDK | `starter_kit/loomq_cli.py` |
| 20 | `haiyun919` | [archive/generated/snapshots/haiyun919/](archive/generated/snapshots/haiyun919/) | Python, quantum SDK | `starter_kit/evaluator.py`; backends in `starter_kit/backends/` |
| 21 | `arw131072` | [archive/generated/snapshots/arw131072/](archive/generated/snapshots/arw131072/) | Python, Flask, quantum SDK | `starter_kit/l2_web_flask.py` |
| 22 | `yiyuanrvk77` | [archive/generated/snapshots/yiyuanrvk77/](archive/generated/snapshots/yiyuanrvk77/) | Python, HTML/CSS, quantum SDK | `starter_kit/agent.py`; `starter_kit/visualizations/index.html` |
| 23 | `UokyI` | [archive/generated/snapshots/UokyI/](archive/generated/snapshots/UokyI/) | Python, quantum SDK | `starter_kit/run_wukong.py` |
| 24 | `orange-city` | [archive/generated/snapshots/orange-city/](archive/generated/snapshots/orange-city/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/agent.py` |
| 25 | `noh1204` | [archive/generated/snapshots/noh1204/](archive/generated/snapshots/noh1204/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 26 | `BEER7LN` | [archive/generated/snapshots/BEER7LN/](archive/generated/snapshots/BEER7LN/) | Python, HTML/JS, Node/Remotion/WebGL, quantum SDK | `start.ps1`; `starter_kit/web/index.html` |
| 27 | `zhangsiyue343-hub` | [archive/generated/snapshots/zhangsiyue343-hub/](archive/generated/snapshots/zhangsiyue343-hub/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/runner.py` |
| 28 | `elenawia` | [archive/generated/snapshots/elenawia/](archive/generated/snapshots/elenawia/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/web/server.py` |
| 29 | `talk2joan` | [archive/generated/snapshots/talk2joan/](archive/generated/snapshots/talk2joan/) | Python, HTML/JS, quantum SDK | `starter_kit/webapp.py` |
| 30 | `33ClayLesley` | [archive/generated/snapshots/33ClayLesley/](archive/generated/snapshots/33ClayLesley/) | Python, Streamlit, quantum SDK | `starter_kit/web/app.py` |
| 31 | `alicewangzm` | [archive/generated/snapshots/alicewangzm/](archive/generated/snapshots/alicewangzm/) | Python, HTML, quantum SDK | `starter_kit/loomq/webapp.py`; `starter_kit/loomq/agent.py` |
| 32 | `qianqiu0926` | [archive/generated/snapshots/qianqiu0926/](archive/generated/snapshots/qianqiu0926/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/cli.py`; `starter_kit/loomq/agent.py` |
| 33 | `Yolanlanlanda` | [archive/generated/snapshots/Yolanlanlanda/](archive/generated/snapshots/Yolanlanlanda/) | Python, quantum SDK | `starter_kit/interactive.py` |
| 34 | `Andante397` | [archive/generated/snapshots/Andante397/](archive/generated/snapshots/Andante397/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 35 | `iiixiscientia` | [archive/generated/snapshots/iiixiscientia/](archive/generated/snapshots/iiixiscientia/) | Python, quantum SDK | `starter_kit/web_app.py`; `starter_kit/src/agent/agent.py` |
| 36 | `LinXuan2576` | [archive/generated/snapshots/LinXuan2576/](archive/generated/snapshots/LinXuan2576/) | Python, quantum SDK | `starter_kit/cli.py`; `starter_kit/l2_agent.py` |
| 37 | `CloverLiu03` | [archive/generated/snapshots/CloverLiu03/](archive/generated/snapshots/CloverLiu03/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 38 | `arwenlinzhaoqing` | [archive/generated/snapshots/arwenlinzhaoqing/](archive/generated/snapshots/arwenlinzhaoqing/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 39 | `softeight` | [archive/generated/snapshots/softeight/](archive/generated/snapshots/softeight/) | Python, quantum SDK | `starter_kit/evaluator.py` |
| 40 | `zhaoqianyuan24` | [archive/generated/snapshots/zhaoqianyuan24/](archive/generated/snapshots/zhaoqianyuan24/) | Python, HTML/JS, quantum SDK | `starter_kit/l2/agent.py`; `starter_kit/frontend/index.html` |
| 41 | `jessicaruan6688-byte` | [archive/generated/snapshots/jessicaruan6688-byte/](archive/generated/snapshots/jessicaruan6688-byte/) | Python, HTML/JS, Shell, quantum SDK | `start_demo.sh`; `starter_kit/web/server.py` |
| 42 | `wronps` | [archive/generated/snapshots/wronps/](archive/generated/snapshots/wronps/) | Python, HTML, quantum SDK | `starter_kit/tools/run_hardware.py`; `starter_kit/tools/web/index.html` |
| 43 | `lil4notfound` | [archive/generated/snapshots/lil4notfound/](archive/generated/snapshots/lil4notfound/) | Python, HTML/JS, quantum SDK | `starter_kit/run_local.py`; `starter_kit/loomq_app/server.py` |
| 44 | `xueerlin20-stack` | [archive/generated/snapshots/xueerlin20-stack/](archive/generated/snapshots/xueerlin20-stack/) | Python, HTML/JS, quantum SDK | `starter_kit/run_l2.py`; `starter_kit/web_app.py` |
| 45 | `qwer-asdftg` | [archive/generated/snapshots/qwer-asdftg/](archive/generated/snapshots/qwer-asdftg/) | Python, PowerShell, quantum SDK | `starter_kit/l2_cli.py` |
| 46 | `LouisYye` | [archive/generated/snapshots/LouisYye/](archive/generated/snapshots/LouisYye/) | Python, quantum SDK | `starter_kit/l2_cli.py`; `starter_kit/l2_agent.py` |
| 47 | `betsywbx` | [archive/generated/snapshots/betsywbx/](archive/generated/snapshots/betsywbx/) | Python, Flask, HTML, quantum SDK | `starter_kit/app.py` |
| 48 | `zmath01` | [archive/generated/snapshots/zmath01/](archive/generated/snapshots/zmath01/) | Python, HTML, Shell, quantum SDK | `run.sh`; `starter_kit/webui/index.html` |
| 49 | `BH2-4` | [archive/generated/snapshots/BH2-4/](archive/generated/snapshots/BH2-4/) | Python, quantum SDK | `starter_kit/chat.py` |
| 50 | `Duanice` | [archive/generated/snapshots/Duanice/](archive/generated/snapshots/Duanice/) | Python, HTML, Shell, quantum SDK | `starter_kit/run_demo.sh`; `starter_kit/agent/server.py` |
| 51 | `danjituya` | [archive/generated/snapshots/danjituya/](archive/generated/snapshots/danjituya/) | Python, Flask, quantum SDK | `starter_kit/cli.py`; `starter_kit/webapp.py` |
| 52 | `WayneYu1212` | [archive/generated/snapshots/WayneYu1212/](archive/generated/snapshots/WayneYu1212/) | Python, HTML/JS, Shell/PowerShell, quantum SDK | `starter_kit/loomq/web/server.py` |
| 53 | `HpIahtcthocw` | [archive/generated/snapshots/HpIahtcthocw/](archive/generated/snapshots/HpIahtcthocw/) | Python, Flask/FastAPI, HTML/JS, quantum SDK | `start.sh`; `starter_kit/loomq/cli.py` |
| 54 | `casccjy67` | [archive/generated/snapshots/casccjy67/](archive/generated/snapshots/casccjy67/) | Python, setuptools, quantum SDK | `starter_kit/agent/chat.py`; baseline `starter_kit/evaluator.py` |
| 55 | `Pennie514` | [archive/generated/snapshots/Pennie514/](archive/generated/snapshots/Pennie514/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq_web.py`; `starter_kit/loomq_cli.py` |
| 56 | `JunkaiWang-TheoPhy` | [archive/generated/snapshots/JunkaiWang-TheoPhy/](archive/generated/snapshots/JunkaiWang-TheoPhy/) | Python, HTML/JS, quantum SDK | `starter_kit/loomq/agent.py`; `starter_kit/web/index.html` |
| 57 | `PHTPSN` | [archive/generated/snapshots/PHTPSN/](archive/generated/snapshots/PHTPSN/) | Python, HTML/JS, PowerShell, quantum SDK | `starter_kit/loomq_l2/agent.py`; `starter_kit/loomq_l2/ui/index.html` |
| 58 | `3dmove` | [archive/generated/snapshots/3dmove/](archive/generated/snapshots/3dmove/) | Python, quantum SDK | `starter_kit/evaluator.py` |
