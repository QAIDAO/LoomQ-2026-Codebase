---
mode: autonomous
message: "先看见量子现象如何发生，再认识它的名字"
audience: "零背景第一次学习者"
---

# LoomQ lesson motion storyboard

| Lesson | Conditions | Build | Change | Resolve |
|---|---|---|---|---|
| bit / qubit | X flip; H paths | 单一路径或一个输入节点 | 确定翻转，或分裂为两条有振幅箭头的路径 | 测量只亮起一个出口 |
| shots / counts | deterministic; random | 清空计数器并准备第一个 shot | 每次重新准备、运行、测量，一枚票落入对应票箱 | 两个票箱变成 counts 直方图 |
| Bell | independent; linked | 两枚独立硬币与四个结果槽 | 独立时四槽均可亮；CX 后连线锁定同面结果 | 00/11 主导并强调“随机但相关” |
| phase | 0; π/2; π | H 将一路分成两路 | 一支相位箭头旋转 0/90/180° | 汇合后显示相长、部分干涉或相消 |
| GHZ | Bell-2; GHZ-3 | 第一个 H 建立两条共同分支 | CX 脉冲按顺序传播到第二、第三枚 | 只保留 00/11 或 000/111 |
| noise | Bell evidence; longer GHZ | 理想柱形作为基准 | 门、退相干和读出三类误差沿电路出现 | 真实 01/10 与 job_id 进入证据卡；长电路只解释误差机会增加，不伪造 GHZ 真机数据 |

所有镜头固定 30fps、确定性时间轴，无网络、无运行时随机数。
