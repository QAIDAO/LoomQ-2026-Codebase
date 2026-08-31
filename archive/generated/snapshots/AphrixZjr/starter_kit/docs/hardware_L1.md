# L1 真机脚本

真机入口与本地 `adapter.run()` 完全分离；没有凭证时三个本地模拟器照常运行。不要把凭证、私钥、Cookie、完整账户信息或未脱敏响应提交到 Git。

`hardware.env.example` 只是字段清单，脚本不会自动读取它。请在当前 PowerShell 会话中设置相应环境变量；不要复制或重命名该文件来保存真实值。

## 量旋 SpinQ Cloud

参照 `hardware.env.example`，在当前 shell 中设置 `SPINQ_CLOUD_USERNAME` 和仓库外 RSA 私钥的 `SPINQ_CLOUD_KEY_FILE`。这两项足以接入；`SPINQ_CLOUD_HOST` 留空时由 SpinQit 0.2.4 使用服务默认地址，`SPINQ_CLOUD_PLATFORM` 留空时使用三比特真机 `triangulum_vp`。只有服务方明确提供其他路由时才设置可选覆盖值。

先运行不联网、不读取凭证的精确工作量计划；如需查看三个电路的离线提交清单，再运行 `dry-run`：

```powershell
cd starter_kit
python run_spinq_hardware.py plan
python run_spinq_hardware.py dry-run
```

填写环境变量后，先串行提交 Bell 与 `bit_order` 测量映射冒烟任务，默认各 100 shots（每个电路最多 256 shots）：

```powershell
python run_spinq_hardware.py smoke --confirm-submit SPINQ_HARDWARE
```

只有在两个冒烟任务均可查询、counts 与 bit order 正确且 job ID 能在控制台回查后，才运行正式 Bell 与 GHZ-3（各 8192 shots）：

```powershell
python run_spinq_hardware.py formal --confirm-submit SPINQ_HARDWARE
```

任务已返回 job ID 后若本地轮询、结果规范化或证据写入中断，不得重新运行 `smoke`/`formal`。使用原 job ID、电路和 shots 只读恢复，例如：

```powershell
python run_spinq_hardware.py resume --job-id <JOB_ID> --circuit bit_order --shots 100
```

`resume` 不接受提交确认词，也不会调用 `submit_task`。脚本会先运行本地 SpinQ 检查，再调用锁定的 SpinQit 0.2.4 云接口。provider 结果中的 `_shots` 必须是与请求完全相同的正整数，否则脚本拒绝归一化；真机概率随后按确定性最大余数法还原为精确 shots，并按 source QASM 的 `q→c` 测量映射投影到 LoomQ classical bit order。

每个成功任务以独占写入方式在默认目录 `evidence/files/hardware/spinq/` 生成五个互相绑定的文件：`-source.qasm`（含测量的输入）、`-submitted.qasm`（实际送入 SpinQ 编译器、去除测量）、`-request.json`（platform、shots、measured qubits、measurement map 与两份 QASM 哈希）、`-raw.json`（完整脱敏 provider-oriented 结果）和通过公共 schema 的 `-summary.json`。summary 的 `meta` 同时记录 provider/device/SDK、结果类型、归一化方法、测量配置、哈希和 raw 文件名。直接提交时 `timestamp` 是客户端提交 UTC 时间；若随后取得只读 task `createdTime`，正式归档摘要应优先采用该平台创建时间并标明来源。提交证据前仍须人工检查 JSON、时间、shots、主导态和控制台 job ID，并填写 `evidence/README.md`。

现有 `bit_order` 任务能验证归档的 classical permutation 与结果一致，但它制备的 provider 物理态为回文 `101`，不能单独区分 raw key 的整体正向/反向。除非真实提交一个非回文方向探针，否则不得把该任务表述为完整的 provider key 方向证明。本轮也没有归档 `triangulum_vp` 的只读平台能力快照；`simu`、`max_bitnum`、在线机器数和支持门列表仍待有权限时查询，不能自行补写。

仓库已准备但**尚未真机执行**方向探针 `circuits/bit_order_direction.qasm`。它只制备 `q0=1`，并映射 `q0→c2, q1→c0, q2→c1`，LoomQ 预期 classical key 为 `100`；两种相反的 provider qubit-key 方向会给出可区分的 raw 主峰 `100`/`001`。它不进入 `dry-run`、`smoke` 或 `formal` 默认批次。有凭证并明确决定消耗一次任务时，只能通过单任务入口显式提交（最多 256 shots，建议 100）：

```powershell
python run_spinq_hardware.py submit-one --circuit bit_order_direction --shots 100 --confirm-submit SPINQ_HARDWARE
```

若该命令已返回 job ID 后本地流程中断，必须只读恢复而不是再次提交：

```powershell
python run_spinq_hardware.py resume --job-id <JOB_ID> --circuit bit_order_direction --shots 100
```

在真实 job ID、raw 概率和标准摘要全部归档前，文档不会声称方向问题已经由真机解决。

## 本源 OriginQ QCloud

从本源量子云个人账户中心取得 API token，并从当前可用真机列表确认 pyqpanda3 0.4.0 所需的后端名称。参照 `hardware.env.example`，在当前 shell 中设置 `LOOMQ_ORIGINQ_TOKEN` 和 `LOOMQ_ORIGINQ_CHIP_ID`；例如当前悟空 180 后端名为 `WK_C180`。其余字段已有安全默认值，只有服务方明确提供自定义地址时才设置 HTTPS URL；留空时脚本强制使用 `https://pyqanda-admin.qpanda.cn`，不会继承 SDK 的明文 HTTP 默认值。若用 Docker `--env-file` 注入，值不得带外层引号。

例如，可在当前 PowerShell 会话中隐藏输入 token，再填写芯片 ID：

```powershell
$originToken = Read-Host "OriginQ token" -AsSecureString
$env:LOOMQ_ORIGINQ_TOKEN = [System.Net.NetworkCredential]::new("", $originToken).Password
$env:LOOMQ_ORIGINQ_CHIP_ID = Read-Host "OriginQ backend name (for example WK_C180)"
```

离线查看计划和字段：

```powershell
python run_originq_hardware.py plan
```

先串行运行 Bell 与非对称 `bit_order` 冒烟任务，默认各 100 shots（每个电路最多 256 shots）：

```powershell
python run_originq_hardware.py smoke --confirm-submit ORIGINQ_HARDWARE
```

如果一个批次已明确完成部分任务，且控制台和本地证据都确认另一个任务
从未产生 job，可用单任务入口只补交缺失项。例如只补交 100-shot
`bit_order`：

```powershell
python run_originq_hardware.py submit-one --circuit bit_order --shots 100 --confirm-submit ORIGINQ_HARDWARE
```

`submit-one` 强制要求显式电路、显式 shots 和精确确认词；每次调用只运行
一个本地 CPUQVM 预检并最多提交一个任务。`bit_order` 上限为 256 shots，
`bell`/`ghz3` 上限为 8192 shots。若提交结果未知或已经取得 job ID，不得
使用 `submit-one`，应先查控制台并改用下述 `resume`。

确认两个冒烟任务均可在控制台回查且 bit order 正确后，运行正式 Bell 与 GHZ-3（各 8192 shots）：

```powershell
python run_originq_hardware.py formal --confirm-submit ORIGINQ_HARDWARE
```

任务提交后若本地轮询、结果下载或证据写入被中断，不得重新运行
`smoke`/`formal` 代替恢复。保留脚本已打印的 job ID，并用原电路和原
shots 只附着到既有任务，例如：

```powershell
python run_originq_hardware.py resume --job-id <JOB_ID> --circuit bell --shots 100
```

`resume` 不接受 `--confirm-submit`，会先执行同一电路的本地 CPUQVM
预检，然后通过 pyqpanda3 0.4.0 的 `QCloudJob(job_id)` 继续
`status()`/`result()`，不会调用 `backend.run()`。状态或结果查询的短暂
故障最多连续重试三次；超时、失败和中断后仍只能恢复既有 job。若提交
阶段在 job ID 返回前中断，先到本源控制台确认是否已产生任务，再决定
后续操作，不能盲目重跑。

脚本复用统一 IR 和 OriginIR emitter，通过 pyqpanda3 0.4.0 的 `QCloudService.backend()`、`QCloudOptions` 和 `backend.run()` 提交，再通过 `QCloudJob.status()` 轮询并以 `QCloudJob.result()` 取回结果。每次云提交前会在同一 pyqpanda3 进程中运行 CPUQVM，且不会导入旧 pyQPanda 2.x；真机结果必须同时命中两个预期主导态，且预期支撑概率不得低于 0.5。状态查询发生短暂网络故障时最多连续重试三次，绝不会自动重新提交任务。脚本默认输出目录仍为 `evidence/files/originq/`；本轮已归档证据统一移动至 `evidence/files/hardware/originq/`。后续执行可通过 `--output-dir evidence/files/hardware/originq` 直接写入统一目录，且不会覆盖同名 job。

## AWS Braket QPU 备用路径

本路径只在量旋算力无法及时购买或不可用时作为第二真机平台。AWS 凭证不得写入 `hardware.env`；请使用单独的 named profile，优先使用 AWS IAM Identity Center/临时凭证，并让该 profile 仅能访问选定 QPU 与专用私有 S3 前缀。脚本需要的非秘密字段列在 `hardware.env.example` 的 `LOOMQ_BRAKET_*` 部分。

先在仓库外配置 profile，再在当前 PowerShell 会话填写备案字段。例如：

```powershell
aws configure sso --profile loomq-braket
aws sso login --profile loomq-braket
$env:LOOMQ_BRAKET_AWS_PROFILE = "loomq-braket"
$env:LOOMQ_BRAKET_AWS_REGION = "us-east-1"
$env:LOOMQ_BRAKET_DEVICE_ARN = "arn:aws:braket:us-east-1::device/qpu/provider/device"
$env:LOOMQ_BRAKET_S3_BUCKET = "private-result-bucket"
$env:LOOMQ_BRAKET_S3_PREFIX = "loomq/l1"
```

如需使用本机 `10808` 代理，可在调用前设置标准 SDK 代理变量；Docker 内改用 `host.docker.internal`：

```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:10808"
$env:HTTP_PROXY = "http://127.0.0.1:10808"
```

最小策略模板见 [`aws_braket_iam_policy.template.json`](aws_braket_iam_policy.template.json)：复制到仓库外，将其中的 device ARN、区域、账户号、bucket 和 prefix 占位符全部替换后再交给 AWS IAM 校验/附加，不要在模板本身填入真实账户信息。策略必须按 AWS Service Authorization Reference 的资源类型拆分，不能把所有 Braket 动作都绑定到 device ARN：`braket:GetDevice` 只授权选定的完整 QPU device ARN；`braket:CreateQuantumTask` 同时授权该 device ARN 与当前账户、区域下的 `arn:aws:braket:<region>:<account>:quantum-task/*`；`braket:GetQuantumTask` 只授权上述 `quantum-task/*`。AWS 当前列出的 Braket 条件键不含 `braket:deviceArn`，不要自行添加无效条件；对目标设备的限制由 `CreateQuantumTask` 所需的完整 device ARN 完成。S3 同样拆分：`s3:GetBucketLocation` 与带 `s3:prefix` 条件的 `s3:ListBucket` 绑定 `arn:aws:s3:::<bucket>`；`s3:GetObject` 与 `s3:PutObject` 只绑定 `arn:aws:s3:::<bucket>/loomq/l1/*`（若修改了 `LOOMQ_BRAKET_S3_PREFIX`，同步替换此前缀）。不要给 profile 管理员权限或账户级通配资源，也不要把账户号、profile 文件或 bucket 名归档为公开证据。

先离线查看固定工作量，再执行只读配置检查：

```powershell
python run_braket_hardware.py plan
python run_braket_hardware.py check
```

`check` 只调用设备查询、bucket 区域查询和 S3 前缀只读检查；它会明确报告 `paid_submission_permission_verified=false`，不能证明 `CreateQuantumTask` 或结果写入权限。确认后，依次执行两项 100-shot 冒烟任务与两项 8192-shot 正式任务：

```powershell
python run_braket_hardware.py smoke --confirm-submit AWS_BRAKET_QPU
python run_braket_hardware.py formal --confirm-submit AWS_BRAKET_QPU
```

四个任务合计 16,584 shots。所有选定电路会先通过 Braket LocalSimulator；云端任务严格串行提交，异常或本地超时不会自动重提或取消付费任务。脚本在每次付费调用前独占保存带 `clientToken` 的 prepared receipt，并在 AWS 返回后立即保存包含原 `clientToken`、安全 task ID、电路、shots 与程序哈希，但不含完整 ARN 或账户号的 submitted receipt。两类私有收据固定写入 `starter_kit/.hardware-private/braket/`，该目录同时被 Git 与 Docker 构建上下文忽略；`--output-dir` 只控制脱敏公开证据，不能把私有收据重定向到公开目录。

批次中断时不得直接重跑 `smoke` 或 `formal`。若 AWS 控制台和私有 receipt 都能明确证明某个任务从未创建，可用新 token 只补交这一项：

```powershell
python run_braket_hardware.py submit-one --circuit bit_order --shots 100 --confirm-submit AWS_BRAKET_QPU
```

`submit-one` 强制一次只运行一个显式电路，并限制 `bit_order` 不超过 256 shots、Bell/GHZ-3 不超过 8192 shots。若付费 API 调用结果不明，绝不能用 `submit-one`，否则新 token 可能创建重复计费任务；此时应复用同一个 schema v2 prepared receipt 的幂等 token：

```powershell
python run_braket_hardware.py retry-prepared --prepared-receipt <PREPARED_RECEIPT_BASENAME> --circuit bit_order --shots 100 --confirm-submit AWS_BRAKET_QPU
```

`retry-prepared` 只接受固定私有目录内的 receipt 文件名，并校验 provider、状态、电路、shots、QASM 哈希以及绑定原 named profile、区域和完整 `CreateQuantumTask` 参数的请求指纹；校验通过后只调用一次 `CreateQuantumTask`，复用原 `clientToken`。旧 schema v1 receipt 缺少这一完整请求指纹，会被关闭失败且不能安全升级：若控制台无法证明任务未创建，应先联系 AWS 支持，不得自动重试；只有明确未创建时才可改用 `submit-one`。

若本地轮询中断，从 `starter_kit/.hardware-private/braket/` 中的对应 receipt 读取 `clientToken`，并在 AWS 控制台用 task ID 取得完整 task ARN。为避免把带账户号的 ARN写入 PowerShell 历史，可通过交互变量传入：

```powershell
$taskArn = Read-Host "Existing Braket task ARN"
$clientToken = Read-Host "Original clientToken"
python run_braket_hardware.py resume --task-arn $taskArn --client-token $clientToken --circuit bell --shots 100
```

`resume` 不接受提交确认词，也不会调用 `CreateQuantumTask`；`--shots` 必须填写原任务的 shots（冒烟通常为 100，正式任务为 8192）。不得重新运行 `smoke`/`formal` 来代替恢复。脱敏结果默认写入 `evidence/files/braket/`；即使使用自定义 `--output-dir`，私有 receipt 仍只写入固定忽略目录。归档前需在 AWS 控制台以 task ID 人工核对。脚本拒绝 `AWS_ENDPOINT_URL*` 自定义端点并要求 SDK 使用 AWS 官方服务端点；代理仍通过标准 `HTTP_PROXY`/`HTTPS_PROXY` 工作。

三条真机路径的精确任务数、shots 与供应商询价口径见开发期材料 [`development/hardware_capacity_L1.md`](development/hardware_capacity_L1.md)；该预算不作为验收证据。

## 官方配置依据

- 本源量子：[pyqpanda3 量子云服务](https://qcloud.originqc.com.cn/document/qpanda-3/cn/d2/d42/tutorial_qcloud_service.html)
- 量旋科技：[量旋云与本地 SpinQit 提交说明](https://www.spinq.cn/products-services/cloud)
- AWS：[named profile](https://docs.aws.amazon.com/braket/latest/developerguide/braket-using-boto3-profiles.html)、[OpenQASM 3 Boto3 提交](https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm-create-submit-task.html)、[按 ARN 恢复任务](https://docs.aws.amazon.com/braket/latest/developerguide/braket-monitor-tasks-sdk.html)、[Braket 动作与资源类型](https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbraket.html)、[限制设备访问](https://docs.aws.amazon.com/braket/latest/developerguide/restrict-access.html)
