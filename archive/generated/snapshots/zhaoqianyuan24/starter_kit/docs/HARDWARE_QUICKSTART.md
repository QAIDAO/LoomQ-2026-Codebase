# L2 推荐后端与远程运行

远程后端不是另一套提交入口。L2 返回官方能力表中的 `backend_id` 后，Playground 会把用户选中的同一个 ID 交给 `adapter.run(qasm, backend_id, shots)`：本地模拟器走现有 L1，云端/真机走对应 provider adapter。

## 产品流程

1. 配置下面对应平台的凭证和 SDK。
2. 启动 `starter_kit/product_service.py`，打开 `http://127.0.0.1:4173/`。
3. 在输入框中提出后端约束，例如“我需要 5 比特真实量子硬件，不想付费”。L2 会返回规范后端 ID，例如 `spinq_cloud_qpu` 或 `originq_wukong`。
4. 生成电路后，在“推荐运行后端”中选中该 ID，点击 `Run Experiment`。
5. 页面显示真实 `job_id`、shots、counts 和耗时；申报 L1 真机时，把平台原始结果和任务页面信息放入 `starter_kit/evidence/files/`。

当前产品入口只使用统一的 `/api/run`，不需要另行调用硬件提交脚本。

默认安全策略是：如果选中的远端真机没有完成 SDK、凭证或平台配置，服务不会尝试提交云端任务，而是自动选择已就绪的本地模拟器运行，并在结果中标记 `fallback: true`。如果连本地模拟器依赖也没有，接口会返回 503。需要严格禁止回退时，可设置：

```powershell
$env:LOOMQ_REMOTE_FALLBACK = 'error'
```

## SpinQ Cloud

先安装可选的官方提交器：

```powershell
python -m pip install -r starter_kit/requirements-hardware.txt
```

设置环境变量：

```powershell
$env:PRIVATEKEYPATH = 'C:\path\to\spinq-private-key.pem'
$env:SPINQCLOUDUSERNAME = 'your-spinq-cloud-user'
$env:SPINQCLOUDHOST = 'http://cloud.spinq.cn:6060'
$env:LOOMQ_SPINQ_PLATFORM = '真实 SpinQ Cloud 平台代码'
```

启动 Playground 后，可通过 Product Service 查询平台代码：

```powershell
Invoke-RestMethod http://127.0.0.1:4173/api/spinq-platforms
```

SpinQ 官方 QASM submitter 当前固定使用 `1000 shots`，Playground 选中 `spinq_cloud_qpu` 时会自动固定为 1000。它也要求提交的 QASM 不含 `measure` 行，适配层会在 provider 调用前处理这一点。

## OriginQ 悟空真机

基础 `starter_kit/requirements.txt` 已包含 `pyqpanda`。配置本源云 Token：

```powershell
$env:LOOMQ_ORIGINQ_API_TOKEN = '本源量子云 API Token'
$env:LOOMQ_ORIGINQ_CHIP = 'ORIGIN_72'
$env:LOOMQ_ORIGINQ_TIMEOUT_SECONDS = '3600'
$env:LOOMQ_ORIGINQ_POLL_SECONDS = '2'
```

适配层优先调用异步真机接口并轮询任务状态，返回可追溯的 OriginQ task ID。

## AWS Braket 云端

基础 `starter_kit/requirements.txt` 已包含 Braket SDK。配置设备 ARN、结果 S3 位置和标准 AWS 凭证：

```powershell
$env:AWS_PROFILE = 'default'
$env:LOOMQ_BRAKET_DEVICE_ARN = 'arn:aws:braket:区域:账户:device/qpu/厂商/设备'
$env:LOOMQ_BRAKET_S3_URI = 's3://你的结果桶/loomq-results'
```

也可以分别设置 `LOOMQ_BRAKET_S3_BUCKET` 与 `LOOMQ_BRAKET_S3_PREFIX`。Braket task ARN 会作为统一结果的 `job_id`；云端 QPU 可能排队并产生费用。

## 凭证与证据

凭证只放在进程环境或本机 AWS profile 中，不写进仓库。L2 的推荐依据仍是官方能力表，不会因为当前机器暂时没有凭证而把真机 ID 改成模拟器；界面会显示“未配置或依赖未就绪”，配置完成并重启服务后即可运行。

官方参考：[SpinQ Cloud submitter](https://github.com/SpinQTech/spinqit_mcp_tools)、[OriginQ real-chip tutorial](https://github.com/OriginQ/QPanda-tutorial/blob/master/source/Realchip.rst)、[Amazon Braket task submission](https://docs.aws.amazon.com/braket/latest/developerguide/braket-submit-tasks-to-braket.html)。
