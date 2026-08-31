# 工程与产品化说明

本文专门回答工程与产品化人工评分字段，内容以当前代码和可执行入口为准。

## 可复现交付

- 在 `starter_kit/` 运行 `docker compose up --build`，即可构建统一 Python 3.10 环境并在 `http://127.0.0.1:8765` 启动 L2。
- 同一镜像包含 L1、L2、L3、量子 RISC-V Bonus 及三个 L1 本地 SDK；`GET /api/health` 报告各后端连接状态。
- Dockerfile 默认启动 Web，与 Compose 和健康检查使用相同的 8765 端口。不使用容器时，可安装精确锁定的 `requirements.txt`，再运行 `python web/server.py`。
- evaluator 是独立的显式自测入口：L1/L3 可直接指定 `--level`，L2 必须注入自己的 `LOOMQ_LLM_*` 配置。
- 完整回归命令是 `python -m unittest discover -s tests -v`；专项入口记录在 `README.md` 和 `web/README.md`。
- [`generate_verification_manifest.py`](../../generate_verification_manifest.py) 可在不读取密钥、不调用真实模型或硬件的前提下归档 Git/环境、命令返回码、原始日志与 artifact 哈希；当前可复现边界见 [`verification.md`](verification.md)。

## 目标用户与首次可用场景

目标用户是没有量子物理、QASM 或云端账号经验，却希望第一次完成一个可解释量子实验的人。Web 工作台把目标、电路、QASM、验证、执行位置、计数图和科学结论放在同一页面；Bell 八阶段引导是可选教学层，用户也可直接编辑和运行。评测环境有模型时以 Agent 对话作为唯一引导入口；模型不可用时，当前精确阶段指令可使用明确标注的预置回复和同一本地工具完成流程，内置模拟器不受影响。

它降低门槛的具体方式：

- 用电路图、文本等价描述和 OpenQASM 同步呈现同一状态，兼顾无代码操作与源码学习。
- 在修改前显示验证或 diff，错误时保留最后有效电路，并提供撤销/重做。
- 把理想概率、由理想概率确定性折算的教学计数、图表、数据表和“单一 Z 基测量不能独立认证纠缠”的边界放在一起，避免把教学计数冒充逐 shot 随机样本。
- 明确区分内置模拟器、本地供应商 SDK 与真实硬件，不把离线结果叙述成真机结果。
- 阶段按钮只负责把指令送到 Agent 输入焦点，不直接改变实验；离线回退牺牲自适应解释，以换取单一交互心智和可预测的现场容错。
- 提供键盘焦点、读屏文本、减少动态和色觉辅助主题。
- 响应式检查脚本覆盖 1024 CSS px 与 200% 缩放等价视口；[`browser-responsive-current.json`](../../evidence/files/browser-responsive-current.json) 是 2026-08-11 历史记录，当前源码本地结果见 [`verification.md`](verification.md)。键盘和读屏全流程仍由现场人工验收。

## 完整使用路径

1. 按 `README.md` 用 Compose 启动，或按 `web/README.md` 本地启动。
2. 打开工作台，直接检查/运行默认 QASM，或开启 Bell 引导。
3. 在“验证、解释、运行位置”之间切换；选择可用本地后端并运行。
4. 查看计数图、等价数据表和结论边界；需要时修复 QASM、撤销或继续询问 Agent。
5. 用 `evaluator.py` 和 `unittest` 复核机器契约，再用 `prepare_submission.py` 做最终 fork 预检。
