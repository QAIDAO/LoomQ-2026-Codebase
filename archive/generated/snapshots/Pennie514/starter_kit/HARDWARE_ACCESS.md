# LoomQ 真机接入与 API 申请指南（HARDWARE ACCESS）

本文件回答两个问题：

1. **如何申请各平台的 API / 凭证**（量旋云、本源量子云、AWS Braket）；
2. **如何配合我们写好的真机代码提交你自己的输入**（自定义输入）。

> 真机接入是 L1 的加分阶梯（每平台主峰命中 +5，至多 2 个平台 +10 分），
> **不是评奖资格闸门**。全部代码已经写好并做了本地模拟自验，你只需：
> 注册账号 → 拿到凭证 → 设置环境变量 → 运行一行命令。

---

## 0. 快速总览

| 平台 | 凭证 | 环境变量 | 真机 | 建议 |
|---|---|---|---|---|
| 量旋云 | 用户名 + RSA 私钥文件 | `SPINQ_CLOUD_USERNAME`, `SPINQ_CLOUD_KEYFILE` | 超导真机（8 比特） | ⭐ 最推荐第一个打通 |
| 本源悟空 | API Token | `ORIGINQ_API_TOKEN` | 悟空 72 比特超导 | 免费机时 60 秒，任务在控制台可查 |
| AWS Braket | AWS 凭证（可选） | 标准 AWS 凭证链 | SV1 云端模拟器 / IonQ 等 QPU | 允许以本地模拟器替代，非必须 |

统一运行方式（以量旋为例）：

```bash
cd <你的 fork 根目录>
export SPINQ_CLOUD_USERNAME="你的量旋云用户名"
export SPINQ_CLOUD_KEYFILE="/path/to/你的私钥文件"

python3 starter_kit/real_machine.py spinq_cloud \
    --qasm starter_kit/circuits/bell.qasm \
    --shots 8192 \
    --config starter_kit/evidence/config_spinq_cloud.json \
    --out starter_kit/evidence/files/spinq_cloud_result.json
```

程序会自动：
- 先在**本地无噪声模拟器**上跑一遍同一电路做语义自验（打印理想主峰）；
- 提交真机任务，轮询结果；
- 输出**统一 Schema 的 result.json**（含可溯源 `job_id`/`task_code`、时间戳、counts）到
  `starter_kit/evidence/files/`，并额外保存平台原始返回。

---

## 1. 量旋云（SpinQ Cloud）—— 推荐首个真机

### 1.1 申请步骤

1. 打开 https://cloud.spinq.cn ，注册账号（手机号/邮箱均可）。
2. 在平台 **个人中心 / 账号设置** 中，**添加你的 SSH 公钥**（平台的登录凭证是
   「用户名 + SSH 密钥对」）。需要先在本地生成密钥对：
   ```bash
   ssh-keygen -t rsa -b 2048 -f ~/.ssh/spinq_cloud
   # 生成 ~/.ssh/spinq_cloud（私钥）与 ~/.ssh/spinq_cloud.pub（公钥）
   ```
   把 `spinq_cloud.pub` 的内容粘贴到量旋云后台。
3. 平台文档：https://cloud.spinq.cn/#/docs ；建议先在控制台跑一次官方示例，确认账号可用。
4. 平台代码：`superconductor_vp`（量旋云文档标注的超导真机平台，8 比特）。
   另有 `gemini_vp`（2 比特核磁）、`triangulum_vp`（3 比特），可用于先行练手。
   > 本队实际提交的量旋证据跑在 `gemini_vp` 上（提交时账号未取得 `superconductor_vp`
   > 可用额度），其平台性质与计分方式见 `evidence/README.md` 的"平台性质如实说明"，
   > 本队不作自我认定。
   > 运行 `python3 starter_kit/real_machine.py spinq_cloud --qasm ...` 时程序会
   > 打印当前账号可用的全部平台代码，直接照抄进 `--config` 的 `platform_code` 即可。

### 1.2 运行（自定义输入）

```bash
export SPINQ_CLOUD_USERNAME="你的用户名"
export SPINQ_CLOUD_KEYFILE="$HOME/.ssh/spinq_cloud"   # 私钥文件路径

python3 starter_kit/real_machine.py spinq_cloud \
    --qasm starter_kit/circuits/bell.qasm \
    --shots 8192 \
    --config starter_kit/evidence/config_spinq_cloud.json \
    --out starter_kit/evidence/files/spinq_cloud_result.json
```

`--config` 里可以自定义（`starter_kit/evidence/config_spinq_cloud.json` 已备好模板）：

```json
{
  "platform": "spinq_cloud",
  "backend": "spinq_cloud_qpu",
  "platform_code": "superconductor_vp",
  "shots": 8192,
  "task_name": "LoomQ-2026-Bell",
  "task_desc": "Bell state on SpinQ superconducting real chip",
  "host": "http://cloud.spinq.cn:6060",
  "timeout_seconds": 3600
}
```

- `platform_code`：从程序打印的平台列表里选（真机选 `superconductor_vp`）；
- `shots`：采样次数；
- `task_name` / `task_desc`：任务名与描述（会显示在量旋云控制台）；
- `measure_qubits`（可选）：只想测量部分比特时填 `[0, 1, ...]`。

**溯源**：`result.json` 里的 `job_id` 就是量旋云的 `task_code`，登录
https://cloud.spinq.cn 的任务列表即可查到同一任务。

---

## 2. 本源量子云（Origin Quantum）—— 悟空真机

### 2.1 申请步骤

1. 打开本源量子云平台 https://qcloud.originqc.com.cn/zh ，点击右上角 **登录/注册**
   （手机号或邮箱注册，海外用户用邮箱）。
2. 登录后进入 **个人中心 → 账号设置**，找到并复制你的 **API Token**
   （pyqpanda 文档称之为 `api_token`；这就是访问云服务的身份凭证）。
   > 参考官方指引：
   > [本源悟空超导量子计算机如何访问和使用？](https://qcloud.originqc.com.cn/zh/blogdetail/how-to-use-wukong-233)
   > [真实芯片计算服务文档](https://qcloud.originqc.com.cn/document/qpanda-doc-cn/Realchip.html)
3. 新注册用户有约 **60 秒免费机时**，足够跑几次 Bell/GHZ 证据任务；
   可在「个人中心 → 资源用量」查看剩余机时。
4. 真机芯片：**悟空 72 比特超导真机**，`chip_id = 72`（代码默认值，无需改动）。

### 2.2 运行（自定义输入）

```bash
export ORIGINQ_API_TOKEN="你的 API Token"

python3 starter_kit/real_machine.py originq_wukong \
    --qasm starter_kit/circuits/bell.qasm \
    --shots 8192 \
    --config starter_kit/evidence/config_originq_wukong.json \
    --out starter_kit/evidence/files/originq_wukong_result.json
```

`--config` 模板（`starter_kit/evidence/config_originq_wukong.json`）：

```json
{
  "platform": "originq_wukong",
  "backend": "originq_wukong",
  "shots": 8192,
  "chip_id": 72,
  "is_amend": true,
  "is_mapping": true,
  "is_optimization": true,
  "task_name": "LoomQ-2026-Bell",
  "timeout_seconds": 3600
}
```

- `chip_id`：悟空 72 比特 = `72`（保持默认即可）；
- `is_amend` / `is_mapping` / `is_optimization`：纠错、映射与优化开关，默认全开；
- 程序使用**异步提交**（`async_real_chip_measure` 返回 `task_id`）并轮询，
  `job_id` 即该 `task_id`。

**溯源**：登录 https://qcloud.originqc.com.cn/zh → **工作台**，按 `task_id` 查询
任务状态与原始结果。

> **小贴士**：真机对线路深度敏感。证据电路建议用 Bell（2 比特）与 GHZ-3（3 比特），
> 主峰命中率最高。真机只核对主峰，噪声不影响得分。

---

## 3. AWS Braket（可选）

赛题允许 **AWS Braket 用本地模拟器替代付费云端**（`braket_local_simulator`，
无需 AWS 账号）。若想拿云端证据：

1. 注册 AWS 账号 → IAM 创建用户并附加 `AmazonBraketFullAccess` 策略；
2. 配置凭证（任选其一）：
   ```bash
   aws configure                        # ~/.aws/credentials
   # 或环境变量
   export AWS_ACCESS_KEY_ID="..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_DEFAULT_REGION="us-west-1"
   ```
3. 运行：
   ```bash
   python3 starter_kit/real_machine.py braket_cloud \
       --qasm starter_kit/circuits/bell.qasm \
       --shots 8192 \
       --config starter_kit/evidence/config_braket_cloud.json
   ```
   模板默认用 **SV1 托管模拟器**（`arn:aws:braket:::device/quantum-simulator/amazon/sv1`）；
   想上真机 QPU（如 IonQ Aria）就把 `device_arn` 换成对应 ARN：
   ```python
   from braket.devices import Devices
   print([d for d in Devices if "QPU" in d.name])
   ```

---

## 4. 完成后：填证据

跑完真机后：

1. 确认 `starter_kit/evidence/files/` 下有各平台的 `*_result.json`
   （含真实 `job_id`、`timestamp`、counts 主峰）；
2. 把 `starter_kit/evidence/README.md` 中 **「L1 真机」** 的方框改为 `[x]`，
   并按模板填写平台、job ID、运行时间、shots、实际执行的 QASM 与结果文件路径；
3. 按赛题官方提交流程（fork → push → 提交 Issue）完成提交。

> ⚠️ 不要提交任何 API Key / Token / 私钥文件到仓库。凭证只放本机环境变量。
> `.gitignore` 已排除常见凭证文件名；若自定义了路径，请再次确认没有入库。

---

## 5. L2 本地调试：DeepSeek API（可选，自备）

正式 L2 评分由组委会统一注入 DeepSeek 模型服务，**赛前不提供**。想本地验证
`agent_chat`（Web / CLI 的「生成」「纠错」「选平台」）时，可自备 Key：

1. 注册 DeepSeek 开放平台：https://platform.deepseek.com
2. 充值少量额度（几块钱即可）→ 「API Keys」→ 创建 Key（`sk-...`）
3. 配置环境变量后启动 Web / CLI：
   ```bash
   export LOOMQ_LLM_BASE_URL="https://api.deepseek.com"
   export LOOMQ_LLM_API_KEY="sk-你的密钥"
   export LOOMQ_LLM_MODEL="deepseek-v4-flash"
   python3 starter_kit/loomq_web.py
   ```
4. 不配 Key 也没关系：Web「现成实验」、CLI 菜单 4/5、L1/L3 全部本地可用。
