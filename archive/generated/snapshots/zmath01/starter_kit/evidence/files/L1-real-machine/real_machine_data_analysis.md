## L1 真机 数据分析

状态：
- 量旋（SpinQ）真机证据（bell × 5 + ghz3 × 1）；
- 本源（OriginQ）真机通过控制台跑通 bell (00+11≈97%)；ghz3 (000+111≈85%)；

一键运行：`.venv310/bin/python run_real.py all --circuit circuits/bell.qasm --shots 4096`（量旋/本源/AWS Braket 三平台：注入 SPINQ_CLOUD_USERNAME + SPINQ_CLOUD_KEYFILE / ORIGINQ_API_TOKEN / AWS 凭据即可）

操作手册：`starter_kit/evidence/real_machine_runbook.md`（注册、取密钥、提交、溯源、自查清单）

证据位置：`starer_kit/evidence/files/L1-real-machine`

------

已产出证据：
- spinq (2 比特 / 3 比特 / 8 比特 NMR 量子真机 gemini 等)  
    - spinq_ghz3 : job_id=S-260823-0002  （主峰 111/000 命中）
    - spinq_bell : job_id=G-260823-0011  （主峰 11/00 命中，00+11≈90%）
    - spinq_bell : job_id=G-260823-0012  （主峰 11/00 命中，00+11≈86%，20000 shots）
    - spinq_bell_G-260823-0007/0008/0009_console.json  三个早期任务的控制台溯源（11/00 命中，00+11≈87%）
- originq
    - originq_bell : 本源悟空 180 控制台：00/11 命中，00+11≈97%，1000 shots
    - originq_ghz3 : 本源悟空 180-2 控制台：000/111 命中，000+111≈85%，1000 shots

------

说明：本地脚本修复后产物（raw=spinqit 返回）；`*console.json` 为早期本地脚本 bug 未修复、但官网控制台真实运行成功的任务，其 raw_platform_response 为 SpinQ 官网控制台记录逐字摘录，counts 按概率×4096 推导（与 spinqit 自身做法一致），meta.source=spinq_cloud_console 标注。

本源（OriginQ）记录同源：raw 为 console 任务详情逐字、counts=概率×shots、meta.source=originq_console。

本源（OriginQ）注意：pyqpanda 3.8.5 的 real_chip_type 枚举仅含旧机器（悟源D3/D4/D5+悟空72），该 API 走到的端点全部维护中。

当前在用的真机是超导悟空 180/180-2 + 硅臻启明光量子（不在 pyqpanda 枚举内），需通过控制台 console.originqc.com.cn 提交；提交后保存任务详情 JSON 重建成证据。

说明：真机结果依赖个人平台账号与排队，评测组按 job_id 溯源核验；本仓库不含任何 Token/密钥。
