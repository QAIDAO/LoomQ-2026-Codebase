# L1 真机接入操作手册（Runbook）

> 本手册说明如何用 `run_real.py` 产出**可溯源的真机证据**。
> 真机证据要求：平台原始 `result.json` + 可溯源的 `job_id` + 赛程内 `timestamp`。
> **绝不伪造**：脚本没有 Mock 回退，缺凭据或 SDK 时会直接失败。

## 0. 通用流程

```bash
cd starter_kit
# 1) 注入凭据（只进环境变量，绝不写进仓库）
export SPINQ_CLOUD_USERNAME=<量旋云用户名>     # 量旋：账号 + RSA 私钥文件（非 token）
export SPINQ_CLOUD_KEYFILE=/path/to/your/rsa_private.key
export ORIGINQ_API_TOKEN=<本源量子云 API Token> # 本源
export AWS_ACCESS_KEY_ID=...                  # AWS Braket（如用云端）
export AWS_SECRET_ACCESS_KEY=...
# 2) 安装平台 SDK（必须 Python 3.10：spinqit 只提供 cp310 wheel；torch 用 CPU 索引避免 nvidia 轮子损坏问题）
uv python install 3.10 && uv venv --python 3.10 .venv310
uv pip install --python .venv310 pyqpanda amazon-braket-sdk
uv pip install --python .venv310 --no-deps spinqit && uv pip install --python .venv310 'numpy<2' autograd psutil retworkx 'antlr4-python3-runtime==4.9.2' python-constraint 'pycryptodome==3.11.0' 'autoray==0.6.1' 'noisyopt==0.2.2' scikit-learn 'python-igraph==0.9.10'
uv pip install --python .venv310 torch --index-url https://download.pytorch.org/whl/cpu
# （Braket 包名是 amazon-braket-sdk，无 -python 后缀；spinqit 在 3.11/3.12 无可用 wheel）
# 3) 提交电路（自动转译 → 提交 → 保存原始结果 → 校验主峰）
.venv310/bin/python run_real.py all --circuit circuits/bell.qasm --shots 4096
```

产出文件：`starter_kit/evidence/files/L1-real-machine/<platform>_<circuit>_<时间戳>.json`，
内含 `raw_platform_response`（平台原始返回）与 `normalized_result`（统一 Schema + 主峰校验）。

## 1. 量旋云 (SpinQ Cloud)

1. 注册 [SpinQ Cloud](https://cloud.spinq.cn)（真机免费额度，需实名）。
2. SpinQ Cloud 使用**账号 + RSA 私钥**签名认证（spinqit 0.2.4 的 `SpinQCloudBackend(username, keyfile, host)`）；
   在控制台"API 密钥/SSH Key"处配置与私钥配对的**公钥**，私钥路径设为 `SPINQ_CLOUD_KEYFILE`。
3. **API 主机默认是 `http://cloud.spinq.cn:6060`**（不是 https://cloud.spinq.cn —— 打错端点会返回
   `Incorrect checksum`）；如你有专属 host 用 `SPINQ_CLOUD_HOST` 覆盖。
4. `.venv310/bin/python run_real.py spinq --circuit circuits/bell.qasm --shots 4096`
5. 提交后任务进入平台队列（分钟级）；`execute()` 内部轮询到完成并返回结果。
6. 溯源：登录 cloud.spinq.cn → 左侧菜单 **"我的实验"** → 任务列表（URL `https://cloud.spinq.cn/circuitDesign/getTaskList`），
   筛选"来源 = SpinQit"即可看到 `G-xxxxxxxx` 任务；点击实验编号看结果页，截图作为溯源佐证。
   （SSH 公钥管理在"账号中心 → SSH公钥设置"。）
7. 可选：`SPINQ_PLATFORM_CODE` 指定平台码（如 `gemini_vp`/`triangulum_vp`/`superconductor_vp`）；
   默认自动选择比特数够用的第一个真机平台。

> **测量语义**：SpinQ Cloud 不接受显式 `measure` 门（报
> `SpinQ Cloud currently does not support explicit invocation of measure gates`），
> 它会在电路末尾**自动测量全部比特**。`run_real.py` 已自动剥离 measure 行，
> 因此结果 counts 覆盖全部比特——请用**全比特测量**的电路（bell/ghz3/ghz5/qft4）；
> 部分测量电路（如 grover3 含 ancilla）观测键会长于本地期望，主峰校验需人工复核。

> 说明：`SpinQRunner.submit` 已按 spinqit 0.2.4 实测 API 编写（`get_compiler("qasm")` 编译 +
> `SpinQCloudBackend(username, keyfile, host)` + `execute(ir, config)`）。
> 若你使用的 spinqit 版本 API 有出入（官方文档 [doc.spinq.cn](https://doc.spinq.cn/doc/spinqit/index.html)），
> 只需调整该函数内云提交的几行，其余流程（转译、保存、校验）不变。

**排障：报 `Incorrect checksum` 的两类原因**
1. **私钥格式/加密**（最常见）：`~/.ssh/id_rsa` 是带密码的 OpenSSH 格式（`BEGIN OPENSSH PRIVATE KEY`），
   pycryptodome 无法解析 → **本地**抛 `ValueError: Incorrect checksum`（不是服务器返回）。
   解决：生成一把专用无密码 PEM 私钥，公钥上传 SpinQ Cloud 后重跑：
   ```bash
   ssh-keygen -m PEM -t rsa -b 2048 -N "" -f ~/.ssh/spinq_cloud_key
   cat ~/.ssh/spinq_cloud_key.pub   # 复制到 SpinQ Cloud 控制台
   export SPINQ_CLOUD_KEYFILE=$HOME/.ssh/spinq_cloud_key
   ```
2. **端点错误**：API 主机必须是 `http://cloud.spinq.cn:6060`（`SPINQ_CLOUD_HOST` 覆盖默认值）。

## 2. 本源悟空 (OriginQ Wukong)

1. 注册 [本源量子云控制台](https://console.originqc.com.cn/zh)（旧版 qcloud.originqc.com.cn 仍可登录，
   但已停用计算服务），**当前在用的真机是 悟空 180 / 180-2（超导）+ 硅臻·启明光量子**——这些
   机型**不在 pyqpanda 3.8.5 的 `real_chip_type` 枚举里**（该枚举只含旧的悟源 D3/D4/D5+悟空 72），
   所以 `run_real.py originq` 走 `async_real_chip_measure` 只会打维护中的旧端点，**真机必须通过控制台提交**。
2. 控制台提交流程：登录 → 图形化编程 / 在线编程 → 粘贴 QASM（直接用 `circuits/bell.qasm` 文本）→
   选 "本源悟空 180"（推荐，超导 180 比特）→ 提交；几分钟内出结果。Bell 在 悟空 180 上 1000 shots
   实测 00+11 ≈ 97%（近乎完美）。
3. 拿到 `taskId` 后，在控制台任务详情页可直接看到结果概率。**保存任务详情 JSON**
   （浏览器开发者工具 Network 找任务详情的响应，或在详情页右键查看 JSON），
   然后用 `reconstruct_evidence.py`（`/tmp/reconstruct_evidence.py`，或依样手写）按
   `key/value` 重建为证据 JSON，raw 写原始详情、counts = value × shots、meta.source = originq_console。
4. 溯源：`taskId` 在控制台 "计算任务" 列表可查；评测组按 task_id 复核。
5. **可选项**：升级到支持新机型的 pyqpanda（≥ 4.0？）后，`run_real.py` 即可直连；目前的限制是
   第三方 SDK 版本问题，不是平台问题。

> 说明：`OriginQRunner.submit` 已按 pyqpanda 3.8.5 实测 API 编写：用 **QCloud 机器本身**做
> `convert_originir_str_to_qprog` 转换（若用独立 CPUQVM 会产生悬垂指针段错误），再
> `init_qvm(user_token)` + `set_qcloud_url` + `async_real_chip_measure` + `query_task_state_result` 轮询。

## 3. AWS Braket

1. 配置 AWS 凭据（`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`）与默认区域
   （`AWS_DEFAULT_REGION=us-east-1` 等）。
2. `python3 run_real.py braket --circuit circuits/bell.qasm --shots 4096`
3. 默认使用 SV1 托管模拟器（`arn:aws:braket:::device/quantum-simulator/amazon/sv1`）；
   若要用真机 QPU，设置 `BRAKET_DEVICE_ARN` 指向具体设备 ARN。
4. 溯源：`job_id`（task ARN）在 AWS Braket 控制台可查。

> 注意：Braket 云端按任务计费；若仅需模拟器证据，官方允许用免费的
> `braket.local_simulator.LocalSimulator`，但本地模拟器**不算真机分**——
> 真机分只认云端 QPU 的原始返回。

## 4. 校验规则（与评测一致）

`run_real.py` 会用本地无噪声模拟器推导理想主导态（概率 > 25% 的态，如 Bell 的
`00, 11`），再检查平台返回的 Top-K 是否包含这些态（真机允许噪声，只查主峰命中）。
校验结果写入 `normalized_result.meta.dominant_state_check`。

## 5. 提交前自查清单

- [ ] `evidence/files/L1-real-machine/` 下每个平台至少一份原始 result.json
- [ ] 每个文件内含 `job_id`，且已在对应平台控制台手动复核可溯源
- [ ] `timestamp` 在赛程窗口（2026-08-01 ~ 2026-08-25 12:00 UTC+8）内
- [ ] 运行 `python3 check_secrets.py --history`，确认无任何 Token/Key 入库
- [ ] `evidence/README.md` 的 L1 部分已填写平台、job ID、结果文件路径
