# Clean V2 Real-Model Validation (DeepSeek V4 Flash)

> 这是参赛者本地的 participant-side robustness validation。它不替代组委会的 hidden/private L2 评测，也不代表官方 L2 满分或任何保证分数。

## 1. 实验边界

- 模型：`deepseek-v4-flash`
- campaign version：`2`
- fixed seed：`20260823`
- 并发：`1`；每个 case 一个 child process，并受 parent hard watchdog 保护
- 预算：最多 `540` recorded API attempts；本次实际 `509`
- 安全边界：无 API health-check、无 QPU、无新硬件、无 tomography submit
- checkpoint：每个 case 完成后原子写入 summary、JSONL records 与 state；正式文件只写入本 V2 路径

## 2. Corpus 与结果

| 类别 | Cases | Pass | Fail |
|---|---:|---:|---:|
| generation | 150 | 149 | 1 |
| repair | 150 | 150 | 0 |
| backend | 120 | 120 | 0 |
| adversarial | 50 | 50 | 0 |
| stability / paraphrase | 30 | 30 | 0 |
| **合计** | **500** | **499** | **1** |

- Pass rate：`99.8%`（499/500）
- First-attempt pass：`490`
- Retry recovered：`9`
- API attempts：`509/540`
- Latency：p50 `7540.309 ms`；p90 `8575.627 ms`；p95 `9313.662 ms`；p99 `14995.280 ms`；max `17956.159 ms`

### 唯一失败

- Case：`v2-generation-130`
- 真实记录：`1` attempt，保留为 FAIL，未重复刷该 case
- 原因：provider transient，异常为 `LoomQ L2 API is unreachable`
- 这不是已确认的 parser、compiler、validator、backend-selection 或 measurement deterministic product failure；没有为追求 500/500 而删除、覆盖或重跑该失败。

## 3. 可审计文件

- Summary：`evidence/files/l2-deepseek-v4-flash-validation-v2-summary.json`
- Per-case JSONL：`evidence/files/l2-deepseek-v4-flash-validation-v2-records.jsonl`
- Atomic state：`evidence/files/l2-deepseek-v4-flash-validation-v2-state.json`
- Harness：`scripts/l2_extended_campaign.py`

V2 的 500 条记录与历史 real-model validation 完全分开。历史 validation 仍为 **101/102**，记录在 `L2_REAL_MODEL_VALIDATION.md` 与 `files/l2-deepseek-v4-flash-stress-summary.json`；历史数据不被 V2 重建或覆盖。

## 4. 复现与声明边界

在本地安全注入 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY`、`LOOMQ_LLM_MODEL=deepseek-v4-flash` 后，从仓库根目录运行：

```powershell
python -X utf8 starter_kit/scripts/l2_extended_campaign.py --production --limit 500 --checkpoint 50 --resume
```

该实验用于说明在给定真实 endpoint、固定 corpus 与受控预算下的链路鲁棒性。它不是 official hidden score，不宣称 guaranteed L2 full marks。所有凭据只存在于调用进程环境，不写入仓库、argv、evidence 或日志。
