# 远程评委核验清单

截止：**2026-08-25 12:00 UTC+8**。正式提交以截止前最后一次 `submission:accepted` Issue 为准。

## 提交入口

- Fork：https://github.com/jessicaruan6688-byte/LoomQ-2026-Jessica
- 证据总入口：`starter_kit/evidence/README.md`
- Demo 一键启动：仓库根目录 `./start_demo.sh` → http://127.0.0.1:8765/

## 5 分钟复现（不烧真机）

```bash
./start_demo.sh
# 浏览器打开：
#   http://127.0.0.1:8765/
#   http://127.0.0.1:8765/?demo=ghz3
#   http://127.0.0.1:8765/?demo=repair
#   http://127.0.0.1:8765/?demo=backend
```

| 步骤 | 命令 / URL | 期望现象 |
|---|---|---|
| 启动 | `./start_demo.sh` | 服务监听 `:8765`，无需 LLM 密钥即可看真机回放 |
| 首页 | `/` | Bell 归档柱状图主峰 **00/11**；job `G-260809-0018`；lede 提及本源双云 |
| GHZ | `?demo=ghz3` | 主峰 **000/111**；job `S-260810-0001` |
| 修电路 | `?demo=repair` | OpenQASM 语法说明 + Bell 对照（Agent 需 `LOOMQ_LLM_*`） |
| 选后端 | `?demo=backend` | 15 比特零排队能力表，不排队、不烧机时 |

## 双云真机核验

| 平台 | Job | 远程怎么核 |
|---|---|---|
| 量旋 Bell | `G-260809-0018` | https://cloud.spinq.cn/circuitDesign/taskResult/61210 · `evidence/files/spinq-bell-*` |
| 量旋 GHZ | `S-260810-0001` | https://cloud.spinq.cn/circuitDesign/taskResult/61216 · `evidence/files/spinq-ghz3-*` |
| 本源 Bell | `724E511297B861472AA2441F90F3D5E6` | 打开 `originq-bell-result.json`（counts 00/11）与 `originq-bell-rest-detail.json`（`taskState=3`，chipId=180，物理比特 `[157,166]`） |

## 本源适配三点（工程）

1. **chipId=180**：`WK_C180` 必须映射到 180；误用退役 72 会假性「维护中」。
2. **不要 `set_configure(72,72)`**：会清掉 `init_qvm` 状态。
3. **SDK 轮询失败 ≠ 任务失败**：先存 job id，用 REST `getTaskDetail` / 控制台取结果；禁止因超时重交。

## 产品一句话

给会写软件、但不想同时学 SpinQ / OriginIR / Braket 三套方言的人——先看可溯源真机主峰，再用自然语言改电路。

## 机时冻结

- `.env`：`LOOMQ_ORIGINQ_MODE=local`、`LOOMQ_SPINQ_MODE=local`
- 不要再跑 `try_originq_bell.sh`
