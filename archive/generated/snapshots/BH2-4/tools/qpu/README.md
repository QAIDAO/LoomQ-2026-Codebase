# 真机证据跑批工具（WP3b）

本目录是**开发侧工具**，不属于 `starter_kit/` 评测物；依赖装在本地
`.venv`（Python 3.10）。凭证一律走环境变量，严禁写入仓库。

## 环境准备（已完成）

```bash
cd tools/qpu
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python spinqit pyqpanda pyqpanda3
```

macOS 注意：spinqit wheel 的 rpath 有缺陷，运行时要设
`DYLD_LIBRARY_PATH=.venv/lib/python3.10/site-packages/spinqit`。

## 脚本与适用场景

| 脚本 | 平台通道 | 状态 |
|---|---|---|
| `run_originq3_qpu.py` | 本源量子云（**pyqpanda3 动态后端发现，推荐**） | ✅ 已用它取得 WK_C180_2 真机证据 |
| `run_spinq_qpu.py` | SpinQ 量旋云（spinqit，RSA 公钥认证） | ✅ 已用它取得核磁真机证据 |
| `run_originq_qpu.py` | 本源旧通道（pyqpanda 固定芯片名） | ⚠️ 保留备查；官方 Q&A 确认真机分时段开放，固定芯片名常报"维护中"，**新任务请用 originq3 版** |

## 凭证

| 平台 | 环境变量 | 获取方式 |
|---|---|---|
| SpinQ 量旋云 | `SPINQ_USERNAME`、`SPINQ_KEYFILE` | 量旋云是 RSA 公钥认证：本地 `openssl genrsa` 生成密钥对 → 控制台「SSH 公钥设置」页粘贴**公钥**（`ssh-keygen -y -f 私钥` 提取）→ `SPINQ_KEYFILE` 指向**私钥** pem 文件。本机私钥：`~/.ssh/loomq_spinq.pem` |
| 本源量子云 | `ORIGINQ_TOKEN` | qcloud.originqc.com.cn → 个人中心 → API Key（一串字符） |

建议放进 `tools/qpu/.env`（已 gitignore），跑前 `export $(grep -v '^#' .env | xargs)`。
仓库根 `.gitignore` 另有 `.env`/`*.pem`/`*.key` 全局兜底，密钥任何位置都不入库。

## 跑真机（先小 shots 试水，成功再跑正式档）

```bash
# 本源：动态发现在线真机后端（优先 WK_C180_2 > WK_C180 > PQPUMESH8）
ORIGINQ_TOKEN=xxx .venv/bin/python run_originq3_qpu.py --list
ORIGINQ_TOKEN=xxx .venv/bin/python run_originq3_qpu.py \
  --qasm ../../starter_kit/circuits/bell.qasm --shots 1000

# SpinQ：超导不在线时可换核磁真机（能力表明确核磁属 spinq_cloud_qpu）
DYLD_LIBRARY_PATH=.venv/lib/python3.10/site-packages/spinqit \
SPINQ_USERNAME=xxx SPINQ_KEYFILE=/path/to/key.pem \
.venv/bin/python run_spinq_qpu.py --list
DYLD_LIBRARY_PATH=.venv/lib/python3.10/site-packages/spinqit \
SPINQ_USERNAME=xxx SPINQ_KEYFILE=/path/to/key.pem \
.venv/bin/python run_spinq_qpu.py --qasm ../../starter_kit/circuits/bell.qasm \
  --shots 1000 --platform gemini_vp
```

证据 JSON 自动落到 `starter_kit/evidence/files/{spinq,originq}/`，
包含平台、job_id、UTC 时间戳、shots、提交的电路文本与平台原始结果——
正好覆盖 evidence 模板要求的全部字段。

