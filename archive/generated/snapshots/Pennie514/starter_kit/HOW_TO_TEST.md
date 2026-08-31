# LoomQ 测试指南（小白版）

> 不用懂量子，跟着做就行。每一条命令后面都写了「你应该看到什么」。
> 全部测试都在本地跑，不需要任何 API Key。

## 0. 先装好依赖（一次性，约 2 分钟）

```bash
cd starter_kit
pip install -r requirements.txt
```

> 如果你用的是本项目自带的虚拟环境（`.venv/`），跳过这步。

## 1. 一键全测（最省事，约 30 秒）

```bash
bash starter_kit/final_check.sh
```

**你应该看到**：`✓ 所有检查通过！` 和每项的 `✓`。如果有 `✗` 把输出发给我。

## 2. 分项测试（想看细节时）

### ① L1 转译与三后端模拟（保真度 ≥ 0.97）

```bash
cd starter_kit
python3 evaluator.py --level l1 --target spinq,originq,braket
```
**看到**：6 行 `[PASS]`，最后一行 `{"passed": 6, "failed": 0, "total": 6}`。

### ② L1 隐藏电路预演（QFT-4 / Grover-3 / 随机电路 × 三后端）

```bash
python3 verify_hidden_circuits.py
```
**看到**：`结果：24 passed, 0 failed`。

### ③ L2 智能体（需要你自己的模型 Key，可选）

```bash
export LOOMQ_LLM_BASE_URL="https://api.deepseek.com"
export LOOMQ_LLM_API_KEY="sk-你的密钥"
export LOOMQ_LLM_MODEL="deepseek-chat"
python3 verify_l2.py
```
**看到**：`结果：9 passed, 0 failed`。没 Key 就跳过这步，不影响其他。

### ④ L3 混合编译（随机用例穷举验证）

```bash
python3 test_hybrid_fuzz.py --cases 100
```
**看到**：`结果：100 passed, 0 failed`。

### ⑤ Bonus 量子 RISC-V 扩展

```bash
python3 test_quantum_riscv.py
```
**看到**：`结果：31 passed, 0 failed`。

### ⑥ 教学引擎（UX 专项奖，Claude 新增）

```bash
python3 test_tutor.py
```
**看到**：`Ran 14 tests ... OK`——每条物理结论（干涉 100% 回 0、Grover 100% 命中等）都被真实运行验证。

## 3. 跑 Web 界面（人工体验评分）

```bash
python3 starter_kit/loomq_web.py
```
浏览器打开 **http://127.0.0.1:8080**：
- 默认进入 **8 章引导课**（预测 → 实验 → 揭示），全程点「下一步」即可，不需要任何配置；
- 第 7 章「上真机」：没配凭证会自动**回放真实芯片存证数据**（本源 180 + 量旋，带 job_id）；
- 顶栏 🧪 进「自由实验室」：跑电路 / 说人话生成 / 修代码 / 选平台 / ⚙️ 配置。

**你应该看到**：每一章右栏有「▶ 运行实验」按钮，点击后出柱状图 + 解读；真机章出真实数据。

## 4. 命令行版

```bash
python3 starter_kit/loomq_cli.py
```
选 4（现成实验）→ 1（量子硬币）→ 回车，能看到 ASCII 柱状图。

## 5. 有问题？

把命令的输出原样贴给队友/我，最快定位。常见情况：
- `ModuleNotFoundError` → 第 0 步没装依赖；
- L2 显示 FAIL → 没配 Key 或 Key 不对（第 ③ 步）；
- 真机按钮报「凭证未配置」→ 正常，零配置用回放，想跑实时去 ⚙️ 配置填凭证。
