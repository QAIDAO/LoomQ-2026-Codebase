# Bonus 实现理由与字段说明

本文专门回答“为何实现该 Bonus”以及每个申报字段如何由代码实现。

## 自定义量子 RISC-V 扩展

- 实现理由：L3 只验证把混合程序降到文本 RV32 控制流，无法表达量子协处理器的机器码边界；量子机器码路径用可编码、可解码、可执行的 custom opcode 补上从经典分支到量子提交与结果回读的最小闭环。它由官方模拟器直接暴露，同时不改变 L3 使用的 `TinyRISCVEmulator` 文本语义。
- 指令编码规格：`docs/loomq_qisa_v1.md` 定义 32 位布局、custom opcode、12 种门、`qsubmit/qread`、Q16.16 参数和保留位约束，使实现可由规格独立复核。
- 模拟器扩展实现：`riscv_emulator.py` 直接定义 assembler、decoder 和 `QuantumRISCVEmulator`；`quantum_riscv.py` 是向后兼容导入层，而不是独立的评分实现。
- 端到端测试：`tests/test_quantum_riscv_e2e.py` 位于正式 `starter_kit/` 归档内，并且只从官方 `riscv_emulator.py` 导入扩展 API。它覆盖 custom opcode 编码/解码、RV32 控制流、Q16.16 参数门、量子提交、测量回读、量子结果驱动经典分支以及 L3 文本语义不变；在 `starter_kit/` 内运行 `python tests/test_quantum_riscv_e2e.py -v`。

## 卓越的新手引导与视觉叙事

- 实现理由：客观 `agent_chat()` 能通过机器判定，却不能单独帮助零基础用户理解一次量子实验；因此增加一个不依赖云账号的可运行工作台，把操作、语境、数学证据和结论边界放进同一流程。
- 零基础首次运行指南：`web/README.md` 与 `web/static/index.html` 的可选八阶段 Bell 引导把首次实验拆成目标、门、测量、预测、验证、运行、解释和探索；用户不进入引导也可使用完整工作台。
- 量子概念解释：`web/app.py` 的指导文案与 `web/static/index.html` 的解释视图分别说明 H、CX、测量、模拟环境和科学边界，避免把叠加简化成普通随机或把相关性冒充纠缠认证。
- 结果可视化：`web/static/app.js` 同时渲染计数柱状图、逐项数据表、shots 摘要和结论边界；这样视觉用户与读屏用户获得等价事实。
- 真机证据叙事：只读 `/api/hardware-evidence` 从仓库内标准摘要同时加载 Bell/GHZ-3 的 Ideal、SpinQ 与 OriginQ 数据，展示 job ID、时间、主峰、理想支撑和泄漏；页面固定说明它是“已归档复盘”，不会连接云平台或创建新任务。
- 错误恢复与无障碍：`web/app.py`、`web/server.py` 和 `web/static/` 实现本地校验、结构性 run/apply 安全门、修复 diff、撤销/重做、revision 冲突保护、可见焦点、live region、减少动态和色觉辅助；`tests/test_l2_web.py` 覆盖这些契约。
