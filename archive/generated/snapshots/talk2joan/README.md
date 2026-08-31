# 量子Kitty · LoomQ

> 一只趴在富士山顶的低像素橘猫，陪你把人话变成量子魔法。
>
> Team `talk2joan` · SheNicest 2026 夏季黑客松

[🎮 在线试玩](https://talk2joan.github.io/cola-pages/quantum-kitty/play.html) ·
[🏠 展示页](https://talk2joan.github.io/cola-pages/quantum-kitty/) ·
双击 `starter_kit/demo.html` 同样可玩（直连大模型）

---

## 我是谁

我是一位做咨询的跨界艺术家。
报名这个比赛的时候：没学过量子力学，没有工程学位，没写过一行转译器。

## 我为什么做这个

赛题说，每一个量子云平台都在筑起自己的"黑话高墙"。我对此没有类比可打——
因为我就站在墙外。

周六早晨，我从"什么是叠加态"开始学起；周六深夜，三平台的统一转译器已经在跑
隐藏电路模拟考。这个过程本身，就是这个产品最好的用户测试：

- 每一个让我卡壳的报错，后来都变成了 Kitty 的"人话报错层"；
- 每一个我看不懂的术语，后来都变成了魔法隐喻（测量 = 掷量子骰子，保真度 = 像不像）；
- 每一个我希望"要是有人直接告诉我就好了"的瞬间，后来都变成了产品里的引导。

一个普通的艺术家加一位 AI 搭档，一个周末，从零到指挥真实的量子计算机。
**这就是普惠的证明，而不只是普惠的口号。**

---

## L1 统一转译：一门人话，三家云都听得懂

你输入人话或者一段 OpenQASM，LoomQ 解析意图、生成电路，然后适配三家量子云：
**量旋云 / 本源悟空 / AWS Braket**。

它的主要特点：

- 36 种量子门 × 三家平台，门级探针全部通过；跨平台位序自动归一化；
- 隐藏电路模拟考最低保真度 0.9965；
- 不合法的门不会硬报错，而是查表改写成白名单里的等价结构，每种改写都先做矩阵验证。

关于真机，要诚实说明一件事：**本源悟空从 8 月 22 日起一直在检修**，
整个周末我每 15 分钟查询一次，始终没有开放。所以我换到另一个平台——
在**量旋云的两台不同架构的真机上完成了贝尔态实测**
（gemini_vp 两比特核磁 / triangulum_vp 三比特核磁，主峰命中理想分布，
job_id 可溯源，原始返回完整存档于 [starter_kit/evidence/README.md](starter_kit/evidence/README.md)）。
两台独立架构交叉验证，统一管线对多真机的适配能力是实证过的。
若悟空在截止前恢复，我会补交第二平台证据。

---

## L2 学习网页：小学生也能上手

这是我最想请大家亲手试一试的部分：**[点开就能玩](https://talk2joan.github.io/cola-pages/quantum-kitty/play.html)**，零配置——在线版直接连着真实的大模型，电路试跑则是页面内置的真实量子模拟，不是录好的假数据。

它有 AI agent 的基本功能——说人话生成电路、帮你把写坏的代码修好、按比特数和预算
推荐后端、用费曼式比喻解释概念（讲完还会抛一个引导问题，不堆公式）。

在这些之上，我加了三层让学习真正发生的东西：

- **知识卡**：翻面自测的复习卡片，记不住的卡会再回来找你；
- **量子试炼**：六关小游戏，亲手把 H 门和 CX 门拼成贝尔态、拼出 GHZ 三胞胎，
  有星星评级和经验值；
- **桌宠**：一只可以拖着走的像素小猫，会眨眼，会在你发呆的时候搭话。

---

## 为什么叫量子Kitty

因为全宇宙最有名的量子梗就是薛定谔的猫——**不打开盒子，谁也不知道里面发生了什么；
但打开的方式可以很友好。**

量子Kitty 是这个项目的 IP 形象：一只低像素风格的橘粉色小猫。开场动画里它躺在
富士山顶，进入页面后它就住在右下角。它不用物理术语吓人——别人说
"波函数坍缩成测量结果"，它说"骰子落地啦 ✨"。

---

## L3 混合编译：寄存器纪律编译器

`compile_hybrid` 把带经典控制流的混合程序编译成官方 `riscv_emulator` 可执行的
量子 RISC-V 程序。特点是纪律：寄存器使用全程追踪、测量注入穷举所有分支，
2000+ 随机用例进官方判分循环零失败。

另外还做了两个 Bonus：自定义量子 RISC-V 指令扩展（规格 + 模拟器 + 端到端测试 8/8），
以及一份 30 分钟零基础上手手册 [QUANTUM_101.md](starter_kit/QUANTUM_101.md)。

---

## 给评审的快速入口

| 看什么 | 在哪 |
|---|---|
| L1 转译器 | [starter_kit/adapter.py](starter_kit/adapter.py)，验证：`python evaluator.py --level l1` |
| L2 学习网页 | [starter_kit/webapp.py](starter_kit/webapp.py)；或直接[在线试玩](https://talk2joan.github.io/cola-pages/quantum-kitty/play.html) |
| L3 编译器 | [adapter.py · compile_hybrid](starter_kit/adapter.py)，验证：`python evaluator.py --level l3` |
| 真机证据 | [starter_kit/evidence/README.md](starter_kit/evidence/README.md) |
| 设计决策 | [starter_kit/ARCHITECTURE.md](starter_kit/ARCHITECTURE.md) |
| RISC-V | [规格](starter_kit/quantum_riscv_spec.md) · [模拟器](starter_kit/riscv_quantum_emulator.py) · [测试](starter_kit/test_quantum_riscv.py) |

以上命令均在 `starter_kit/` 目录下执行；公开自测：`python evaluator.py --level declared`。

## 快速开始

```bash
pip install -r starter_kit/requirements.txt
cd starter_kit
python evaluator.py --level declared   # 公开自测（L2 项需 LLM 环境变量，详见 starter_kit/README.md）
python webapp.py                       # 量子Kitty 网页版 http://127.0.0.1:8765
```
