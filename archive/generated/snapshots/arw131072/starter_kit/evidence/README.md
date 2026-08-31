\# LoomQ · 量子接入平权计划



> 让不懂“黑话”的人，也能指挥最前沿的算力



\## 🚀 一键复现



在干净的 Linux/macOS/Windows 环境（Python 3.10）中，按以下步骤即可从零运行本项目：



```bash

\# 1. 克隆仓库（或解压压缩包）

git clone https://github.com/arw131072/LoomQ-2026.git

cd LoomQ-2026



\# 2. 创建 Conda 环境（推荐，也可用 venv）

conda create -n loomq python=3.10 -y

conda activate loomq



\# 3. 一键安装所有依赖

pip install -r requirements.txt



\# 4. 一键启动 L2 Web 界面（体验核心功能）

python l2_web_flask.py  (starter_kit/l2_web_flask.py)

打开浏览器访问 http://127.0.0.1:5000，即可看到用户友好的图形界面。输入“生成一个贝尔态”，几秒内即可获得量子电路代码、测量结果柱状图和物理解释。



如果只验证 L1/L3，可直接运行公开评估器：python evaluator.py --level l1 --json-out report.json



📸 界面预览

starter_kit/evidence/img1.png
starter_kit/evidence/img2.png
starter_kit/evidence/img3.png
starter_kit/evidence/img4.png


（截图展示界面样式，新手引导，用户选择后端，用户输入“生成一个贝尔态”后，页面会显示 QASM 代码、Counts 柱状图、后端信息和物理解释。）



🧩 功能概览

L1 通用中间层

支持三个后端：量旋 SpinQ、本源 OriginQ、AWS Braket



统一输入 OpenQASM 2.0，输出标准化 JSON（含 counts、bit\_order 等）



已通过公开评估器（Bell 和 GHZ-3）保真度测试



L2 自然语言智能体

基于 DeepSeek API，将自然语言转译成 QASM 代码



支持意图生成、代码纠错、智能选后端



自带自验证闭环：生成的电路自动用 L1 模拟器验证，失败则重试



提供 Web 图形界面，零基础用户可自主操作



L3 混合编译

解析 Hybrid-QASM，分离量子操作和经典控制流



生成 RISC-V 汇编（支持 li, addi, beq, bne, j 等指令）



已通过 riscv\_emulator.py 模拟器验证



真机证据

已成功在 量旋 Gemini VP 真实量子硬件上运行，并保存证据在 starter\_kit/evidence/gemini\_vp/。

