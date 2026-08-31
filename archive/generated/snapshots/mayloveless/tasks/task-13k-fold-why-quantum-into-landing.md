# Task 13K — Fold Why Quantum into Learn Landing

## 目标

继续收敛 Learn 的阅读逻辑。

当前独立的「量子计算不是“更快的电脑”」区块内容本身有价值，但作为一个完整 section 插在产品定位和三步教学之间，会打断阅读节奏。

本任务把这部分内容**折回 Learn 首屏产品定位中**，让页面形成一条连续路径：

> LoomQ 是什么 → 为什么开发者值得花几分钟了解 → 30 秒看懂一个量子程序 → Prepare / H / Measure → 最后补术语

本任务只做 Learn 内容结构收敛，不新增功能。

---

## 要做

### 1. 删除独立 Why Quantum section

移除当前完整的：

- `WHY QUANTUM MATTERS`
- `量子计算不是“更快的电脑”`
- 三张密码学 / 搜索组合 / 量子系统模拟卡片

不要再让它作为一个独立的大段内容存在。

同时删除对应失效 CSS / 测试。

### 2. 把核心信息压缩进 Learn 首屏

在现有 LoomQ 产品定位文案之后、首屏 CTA 之前，加入一个轻量 Why-care 提示。

建议语义：

**为什么值得了解？**

> 量子计算不是更快的普通电脑。它只擅长少数特殊问题，但在这些问题上可能非常强。

下面只保留三个简短方向标签 / inline items：

- 密码学
- 搜索 / 组合
- 量子系统模拟

其中密码学可以有一行非常短的补充，例如：

> RSA / ECC 等公钥密码体系正因此推动后量子迁移。

不要再展开 Shor / Grover / 行业背景，不要做成三张知识卡。

### 3. 恢复顺畅 CTA 路径

因为 Why-care 已经在首屏内被用户看到，`30 秒看懂一个量子程序` 可以直接进入当前紧凑三步教学：

- 跳转到 `#learn-quickstart` 或当前三步体验实际 anchor；
- 不再经过一个独立 Why section。

### 4. 保留 13J 已完成的三步体验

以下内容保持不变：

- Prepare → H → Measure 三步结构；
- 什么是量子电路的轻量解释；
- 状态变化作为主角；
- 源码按需查看；
- 当前源码行高亮；
- H 状态变化视觉；
- Measure 一次运行 vs shots；
- NOW NAME THE PARTS recap；
- technical details 默认收起。

---

## 视觉要求

Why-care 在首屏中应该是**辅助认知，不是第二个 Hero**：

- 不新增大面积 section；
- 不做三张卡；
- 不引入更多颜色；
- 可以使用一条细分隔线、轻量 label、inline chips / text items；
- 保持当前深色克制视觉；
- 它的重要性低于 LoomQ 主定位，高于普通 metadata。

用户应该能在首屏 5–10 秒内理解：

1. LoomQ 面向谁；
2. LoomQ 帮我做什么；
3. 为什么量子计算值得开发者花几分钟了解；
4. 下一步从哪里开始。

---

## 不做

本任务不要：

- 修改三步教学交互；
- 修改量子状态可视化；
- 新增 Grover Oracle / Diffusion 教学；
- 修改 Experiments / Explorer；
- 修改 Repair / Backend；
- 修改 stable prompts；
- 修改 parser / verifier / repair / backend selector；
- 修改 Teaching Explainer / Circuit Trace；
- 新增 LLM 调用。

---

## 验收

完成后人工确认：

1. 首屏仍然首先表达 LoomQ 产品定位，而不是量子科普；
2. 用户不用滚过一整块行业知识，就能理解为什么量子计算值得关注；
3. `30 秒看懂一个量子程序` 点击后直接进入三步教学；
4. Learn 阅读路径是否变成连续的一条线，而不是“产品介绍 → PPT 科普 → 教程”；
5. 13J 三步教学没有被改坏；
6. 没有新增无关视觉和功能。

完成后停止，让用户 review。
