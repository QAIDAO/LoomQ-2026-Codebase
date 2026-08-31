# 量旋真机：操作卡

空电路 `G-260802-0004` **不计分**。  
已锁定有效平台一：`G-260809-0018`（2 比特核磁 · Bell）。

赛题人工真机分：**最多两个平台 × 5 分**。模拟器不计。  
本源悟空若一直不过审，用 **量旋另一台真机** 当平台二即可（对手普遍这么干）。

## 量旋网页里你会看到的选项（怎么计分）

| 网页名称 | SDK / 常见代号 | 比特 | 能否冲真机分 |
| --- | --- | --- | --- |
| 2 比特核磁量子计算机 | `gemini_vp` | 2 | ✅ 已完成（Bell） |
| 3 比特核磁量子计算机 | `triangulum_vp` | 3 | ✅ **优先作平台二**（GHZ-3） |
| 5 比特核磁量子计算机 | 网页专有（以控制台为准） | 5 | ✅ 可作平台二（需在线） |
| 8 比特超导量子计算机 | `superconductor_vp` | 8 | ✅ 可作平台二（常排队/离线） |
| 全振幅模拟器 | simulator | ≤24 | ❌ **不计真机分** |
| 专属服务 | private | ? | ❌ 勿报（难溯源/非公开赛道资源） |

查在线：打开 https://cloud.spinq.cn → 新建线路 → 看各机器是否可点选/「在线」。  
SDK：`backend.get_platform("triangulum_vp").available()`（需 SSH 云密钥）。

## 平台二推荐：3 比特核磁 · GHZ（路 A 网页）

1. 新建线路 → 选 **3 比特核磁**（不要选全振幅模拟器）  
2. 粘贴（**不要写 `creg` / `measure`**）：

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0],q[1];
cx q[1],q[2];
```

通过标准：线路图出现 **H + 两级 CNOT**；模拟投影主峰约 `000` / `111` 各一半。  
模板：`evidence/files/spinq-ghz3.TODO.qasm`

3. 提交真机 →「运行成功」  
4. 记录任务号（多为 `S-……` 或 `G-……`）、时间、任务页 URL、投影/导出  
5. 存盘：

```text
evidence/files/spinq-ghz3.qasm
evidence/files/spinq-ghz3-result.json
evidence/files/spinq-ghz3-hardware-result.png
```

6. 在 `evidence/README.md` 增加「量旋 · 3 比特核磁」段（与已有 2 比特段并列）。

备选：若 3 比特离线而 **8 比特超导**在线，可仍跑 3 比特 GHZ（`qreg q[3]`），或换小一点的可解释电路；**不要为凑热闹上模拟器**。

## 平台一回顾：2 比特 Bell（已完成可对照）

网页粘贴：

```qasm
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
```

证据：`G-260809-0018` → `evidence/files/spinq-bell.*`

## 路 B：SpinQit 云后端（SSH 密钥）

文档：https://doc.spinq.cn/doc/spinqit/programming/backend/backend.html  

1. 在量旋云绑定 **SSH 公钥**  
2. `starter_kit/.env`：

```bash
LOOMQ_SPINQ_MODE=cloud
LOOMQ_SPINQ_USERNAME=你的用户名
LOOMQ_SPINQ_KEYFILE=/绝对路径/到/私钥
# 平台二举例：
LOOMQ_SPINQ_PLATFORM=triangulum_vp
```

3. Bell（2 比特）：

```bash
PYTHONPATH=starter_kit python starter_kit/tools/run_bell_evidence.py --platform spinq --shots 1024
```

脚本会拒绝本地 simulator 冒充真机（除非 `--allow-simulator` 干跑布局）。

## 本源卡住时还有什么？

| 路径 | 建议 |
| --- | --- |
| 量旋第二台真机（3/5/8） | **立刻可替代本源当第二平台** |
| 本源悟空继续等审 | 过了再补，不挡终局 |
| 全振幅 / 本地模拟 | 只练习，**不写进 HW 证据** |
| 华为云练习机时 | 赛方不认作 SpinQ/Origin 可溯源 job |
| AWS Braket 付费真机 | 理论可报，要账号+钱；LocalSimulator **不要冒充真机分** |

## 无效自检

提交前打开任务页看线路图：必须能看到门（H/CNOT 等），不能是空白线；后端名称不能是模拟器。
