# LoomQ 人工评分证据

## 申报项目

- [ ] L1 真机（未伪造；需补入赛程内真实平台 job）
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

当前提交只提供三个规范本地模拟器路径，所有本地 job ID 均明确以 `loomq-local-` 开头。本节不申报真机分。取得真实平台回执后，应补齐平台、job ID、带时区运行时间、shots、实际 QASM、原始结果和可选截图；不得把本地或 mock 结果放入本节。

## L2 交互体验

```text
启动界面或 CLI 的命令：cd starter_kit && python3 -m loomq serve
测试入口或页面地址：http://127.0.0.1:8765
用于交互体验评测的 3 个用户任务：
1. “生成一个 3 比特 GHZ 态并进行全测量”，观察两个 50% 主峰并展开目标 IR。
2. “我想制备贝尔态，但代码 H q[0]; CX q[0] q[1] 报错了，请修复”，确认意图保持且 QASM 可运行。
3. “15 比特、零排队、免费且无需账号，推荐哪个后端？”，确认回复包含官方规范后端 ID。
截图或演示视频：无；工作人员可直接运行上述入口，代码优先于静态截图。
```

界面有 skip link、label、`aria-live`、键盘焦点、reduced-motion、窄屏布局和不依赖颜色的文本数值。模型失败时显示可恢复说明；直接 QASM 运行不需要 API Key。

## 工程与产品化

```text
干净环境中的构建和启动命令：python3 verify_submission.py；或 docker build -t loomq . && docker run --rm loomq
架构说明：docs/ARCHITECTURE.md
目标用户和使用场景：跨界创作者、教师/学习者、键盘/窄屏/辅助技术用户的第一次可验证量子实验
完整使用流程：README.md 的“60 秒开始”和“使用智能体”
```

科学与开源依据见 `docs/RESEARCH.md`；验证矩阵与样本量见 `docs/VERIFICATION.md`。

## 自定义量子 RISC-V Bonus

```text
指令编码规格：docs/QUANTUM_RISCV_SPEC.md
模拟器扩展实现：riscv_emulator.py；编解码器 loomq/quantum_riscv.py
端到端测试命令：python3 -m unittest tests.test_quantum_riscv -v
```

三项齐全：32 位 `custom-0` 两 profile 规格、`.word` 解码/量子执行、QASM→编码→Bell/CCX/参数门测试。实现覆盖 8 种离散指令与 `QRY/QRZ/QCU1`，后三者有 0.5 μrad 角度量化界和端到端态距离检查。

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：README.md “60 秒开始”；python3 -m loomq demo
量子概念解释：Web 结果区“纠缠 ≈ 两枚永远同面的硬币”；README.md
结果可视化：loomq/web_assets/app.js 的概率柱状图 + 文本百分比/counts
错误恢复或无障碍引导：loomq/web.py 的 recovery；index.html skip-link/ARIA；app.css focus/reduced-motion/mobile
```
