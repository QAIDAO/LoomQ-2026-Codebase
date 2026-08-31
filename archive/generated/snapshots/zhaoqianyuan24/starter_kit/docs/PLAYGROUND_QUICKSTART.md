# LoomQ Playground 快速开始

LoomQ Playground 是一个面向量子计算初学者的网页实验台：用自然语言生成 OpenQASM 电路，也可以直接询问量子概念、当前电路和数学逻辑；然后根据 L2 推荐或用户选择，在本地模拟器、云端服务或已配置的真机上运行和比较测量结果。

## 方式一：Docker（推荐）

已安装并启动 Docker 后，在仓库根目录执行：

```powershell
docker compose -f starter_kit/compose.yaml up --build
```

也可以使用纯 Docker CLI：

```powershell
docker build -f starter_kit/Dockerfile.playground -t loomq-playground:local starter_kit
docker run --rm -p 4173:4173 loomq-playground:local
```

浏览器访问 `http://127.0.0.1:4173/`，再通过右上角“连接 API”填写自己的 OpenAI-compatible API。Key 不会写入镜像或仓库。

如果服务器已经配置完整的 `LOOMQ_LLM_BASE_URL`、`LOOMQ_LLM_API_KEY` 和 `LOOMQ_LLM_MODEL`，也可传入容器：

```powershell
docker run --rm -p 4173:4173 `
  -e LOOMQ_LLM_BASE_URL="https://api.example.com" `
  -e LOOMQ_LLM_API_KEY="填写你自己的 Key" `
  -e LOOMQ_LLM_MODEL="your-model" `
  loomq-playground:local
```

## 方式二：Windows 一键启动

推荐使用 **Python 3.10**。克隆并解压仓库后，直接双击 `starter_kit` 目录中的：

```text
starter_kit\start_playground.bat
```

首次运行会先征求确认，然后自动创建 `starter_kit/.venv` 并安装 `starter_kit/requirements.txt`。安装完成且 `adapter`、`spinqit`、`pyqpanda`、`braket` 全部通过运行预检后，才会启动 Product Service。第二次双击会直接复用已准备好的 `.venv`。

如果没有找到 Python 3.10、用户取消初始化、依赖安装失败或运行预检不通过，启动器会显示具体原因并停止，不会显示虚假的 Ready 状态。

启动成功后，浏览器会自动打开：

```text
http://127.0.0.1:4173/
```

## 方式三：手动 Python

也可以在 Python 3.10 环境中使用仓库内隔离环境手动启动：

```powershell
python -m venv starter_kit\.venv
.\starter_kit\.venv\Scripts\python.exe -m pip install -r .\starter_kit\requirements.txt
.\starter_kit\.venv\Scripts\python.exe .\starter_kit\product_service.py --host 127.0.0.1 --port 4173
```

> 不要直接双击 `starter_kit/frontend/index.html`。静态文件无法连接 Product Service，因此不能生成或运行实验。

## 第一次使用

1. 首次检测到 API 未接入或连接失败时，页面会自动打开 **连接自己的 API** 弹窗；也可以随时点击右上角的 **连接 API**。
2. 填写自己的 OpenAI-compatible API，并点击 **测试连接**。
3. 测试成功后点击 **应用**。
4. 在同一个输入框中选择示例或直接输入自然语言，然后点击 **发送**；赛事任务会优先进入 L2 生成/推荐流程，普通概念和结果问题才进入量子导师问答。
5. 三个赛事基本任务可以直接点击首页的 `L2-1 GHZ 生成`、`L2-2 QASM 修复`、`L2-3 智能选后端`：
   - `生成一个 3 比特 GHZ 态，并对三个量子比特全部测量`；
   - `我想制备一个 Bell 态，但这段 OpenQASM 代码报错了，请修复它……`；
   - `我需要运行一个 15 比特电路，而且零排队等待，请推荐一个满足约束的官方 backend_id……`。
6. 例如“生成一个 Bell 态”会进入 L2 实验生成流程，“什么是量子纠缠？”或“这个实验里发生了什么？”会进入量子导师问答。
7. 生成实验并运行后，可以继续追问“这个 counts 为什么长这样？”；回答会参考当前 QASM、步骤和最新测量结果。
8. 查看 Circuit/QASM，选择后端和 Shots，然后点击 **Run Experiment**。

DeepSeek 示例：

```text
Base URL: https://api.deepseek.com
Model: deepseek-v4-flash
API Key: 填写你自己的 Key
```

API Key 只保存在当前 Product Service 进程的浏览器会话中，不写入项目文件；服务重启后需要重新填写。

## 使用量子问答

量子导师和实验生成共用一个输入框。界面会优先识别明确的解释、概念、数学、代码和“发生了什么”等问题；其余带有“生成、创建、构建、演示”等意图的请求进入实验生成流程。

生成实验后，问答会自动携带当前电路的 QASM、量子门步骤、数学状态说明和最新 counts。回答会区分理论概率与有限 Shots 的统计波动，不把普通问题转换成 QASM。

点击电路中的量子门后，说明卡片会优先展示矩阵或态变换公式，再给出规范的门定义、当前态矢前后变化和 Bloch 球上的局部态轨迹。

## 切换本地后端

生成实验后，在“推荐运行后端”中展开选择器，可切换官方能力表中的后端：

- SpinQ Taurus
- OriginQ CPUQVM
- AWS Braket LocalSimulator

如果已按 [`HARDWARE_QUICKSTART.md`](HARDWARE_QUICKSTART.md) 配置远程凭证，列表也会显示 `spinq_cloud_qpu`、`originq_wukong` 和 `braket_cloud`；选中后仍通过同一个 `Run Experiment` 按钮运行。

切换后电路和 QASM 不变，只有实际执行平台与返回结果改变。

## 常见问题

| 现象 | 处理方法 |
|---|---|
| Product Service 未连接 | 确认 `starter_kit/product_service.py` 正在运行，并访问 `http://127.0.0.1:4173/`，不要打开 `file://` 页面。 |
| API 未配置 | 点击右上角“连接 API”，测试并应用自己的配置。 |
| API Key 无效 | 检查 Key 是否复制完整、是否过期，以及是否有模型调用权限。 |
| Model 不存在或无权限 | 使用服务商实际支持的模型名；DeepSeek 示例为 `deepseek-v4-flash`。 |
| Python 依赖缺失 | 重新双击 `starter_kit/start_playground.bat`，确认首次初始化；启动器会创建或补全 `starter_kit/.venv` 并重新执行严格运行预检。 |
