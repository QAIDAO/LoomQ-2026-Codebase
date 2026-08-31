# 科学与开源依据

本文件只记录直接影响实现的原始论文、官方规范与官方仓库；不把二手博客当作正确性依据。

## 编译器与中间表示

1. [Open Quantum Assembly Language](https://arxiv.org/abs/1707.03429) 定义了 OpenQASM 2 的低深度电路、门、测量与直线程序语义。**采用**：严格解析小子集，不把 QASM 当作可随意替换的字符串。
2. [OpenQASM 3: A broader and deeper quantum assembly language](https://arxiv.org/abs/2104.14722) 扩展了类型、经典控制和时序。**采用**：Braket emitter 输出显式 `qubit/bit` 类型和测量赋值，不假设 QASM 2 文本可直接改版本号。
3. [QIR Alliance Specification](https://github.com/qir-alliance/qir-spec/blob/main/specification/README.md) 明确把量子编译分为语言特定、通用 IR、目标特定三阶段。**采用**：`parser → Circuit IR → emitter`。
4. [t|ket〉: A Retargetable Compiler for NISQ Devices](https://arxiv.org/abs/2003.10611) 展示语言无关、可重定向量子编译器。**采用**：后端只处理目标表示，不重新解释源语言。
5. [Design and architecture of the IBM Quantum Engine Compiler](https://arxiv.org/abs/2408.06469) 使用 MLIR 多层抽象承载不同编译阶段。**采用**：把“用户意图、可移植电路、目标 IR”视为不同层，不混在一个字符串处理中。

## 后端官方实现

1. [SpinQTech/SpinQit](https://github.com/SpinQTech/SpinQit) 提供编译器、Circuit 和模拟器入口。**参考**：SpinQ 目标保持标准 QASM 2，便于平台原生导入。
2. [OriginQ/QPanda-2](https://github.com/OriginQ/QPanda-2) 是本源官方开源框架，并展示 CPUQVM 的纠缠运行路径。**参考**：OriginIR 门名、扁平 qubit/creg 与本地模拟器概念。
3. [Amazon Braket SDK](https://github.com/amazon-braket/amazon-braket-sdk-python) 与 [Amazon Braket organization](https://github.com/amazon-braket) 说明 LocalSimulator 和 OpenQASM 3 payload。**参考**：使用 `stdgates.inc`、`cnot/cp` 与显式测量赋值。
4. [QIR specification Base Profile](https://github.com/qir-alliance/qir-spec/blob/main/specification/profiles/Base_Profile.md) 把“量子指令序列 + 末端测量”定义为最小一致执行能力。**采用**：L1 本地模拟器明确限制 terminal measurement。

## 正确性与测试

1. [Translation Validation](https://doi.org/10.1007/BFb0054170) 提出不证明整个 compiler，而对每次编译结果做检查。**采用**：每次 `run()` 都独立回读目标文本并生成收据。
2. [Proof-Carrying Code](https://doi.org/10.1145/263699.263712) 建立“验证证据后再接受不可信代码”的经典边界。**启发**：运行结果携带可重算的翻译证书；但 LoomQ 收据不等于通用 PCC 形式证明。
3. [CertiQ](https://arxiv.org/abs/1908.08963) 用量子电路 calculus 和自动化条件验证真实编译 pass。**采用**：以语义等价为目标，而不是快照字符串相同。
4. [Giallar](https://arxiv.org/abs/2205.00661) 自动验证编译 pass 保持量子电路语义。**采用**：每个目标 IR 重新解析并检查操作轨迹、全态、测量映射与分布。
5. [Verifying Results of the IBM Qiskit Quantum Circuit Compilation Flow](https://arxiv.org/abs/2009.02376) 针对真实量子编译流做专用等价检查。**采用**：利用当前 emitter 不优化的特性，加入线性成本的规范操作轨迹证明。
6. [Equivalence Checking of Quantum Circuits by Model Counting](https://arxiv.org/abs/2403.18813) 展示通用量子电路等价检查的复杂性与符号方法。**边界**：LoomQ 不声称实现了通用符号判定器；它针对发布的无优化直线 emitter 证明精确轨迹保持。
7. [MorphQ](https://arxiv.org/abs/2206.01111) 用随机程序和量子特有 metamorphic relation 缓解测试 oracle 问题。**采用**：随机白名单电路、逆门关系、相位反例、抵消门反例和三目标往返。

完全形式化验证超出本赛题规模；本实现采用可审计的 translation validation、已知恒等式和随机变形测试组合，并明确记录这个边界。

## 自定义指令与数值契约

1. [RISC-V Unprivileged ISA opcode map](https://docs.riscv.org/reference/isa/unpriv/rv-32-64g.html) 明确说明 `custom-0..3` 会为自定义扩展保留，而 `reserved` opcode 不应占用。**采用**：使用 `custom-0=0x0B`，对未定义 `funct7/funct3` 组合 fail-closed。
2. 参数门不盲目追求“可编码”：量化步长、周期归一化、角度寄存器 ABI 和算子误差界必须一起公布。推导见 [`THEORY.md`](THEORY.md)。

## LLM 生成的可靠性

1. [PICARD](https://arxiv.org/abs/2109.05093) 说明对形式语言做解析约束能显著减少无效生成。**采用**：模型输出必须进入严格 JSON/QASM parser。
2. [Natural Language to Code Translation with Execution](https://arxiv.org/pdf/2204.11454) 说明执行反馈可改进自然语言到代码的候选选择。**采用**：QASM 通过本地状态向量执行验证，而非只检查表面语法。
3. [Self-Refine](https://arxiv.org/abs/2303.17651) 研究有反馈的迭代修正。**采用**：向模型返回具体 parser 诊断，但最多一次，控制成本和时延。
4. [Quantum Circuit Generation via test-time learning with large language models](https://arxiv.org/abs/2602.03466) 把量子电路生成构造成外部模拟器评分的闭环。**采用**：模型提议、本地量子 evaluator 判定；不让模型自己当裁判。

## 新手体验与包容性

1. [WCAG 2.2](https://www.w3.org/TR/WCAG22/) 要求内容可感知、可操作、可理解、稳健。**采用**：语义标签、跳转链接、可见焦点、足够对比、`aria-live`、键盘可达、reduced motion 和移动端无横向滚动。
2. [Inclusive learning for quantum computing](https://arxiv.org/abs/2106.07077) 探讨无需前置知识的量子素养入口。**采用**：先用可操作实验建立直觉，再按需展开原始 IR。
3. [Interactive visualization and simulation for learning quantum physics](https://arxiv.org/abs/2302.06286) 研究新手使用交互模拟时的困难。**采用**：结果图旁直接给概念解释、位序和验证状态，减少界面与解释之间的视线/认知切换。

## “高屋建瓴”原则

LoomQ 的核心不是“让 LLM 写代码”，而是**把概率型生成系统放进确定性语义边界**：自然语言层可开放，IR 层必须类型安全，目标层必须 translation-validated，执行层必须维护归一化与位序不变量，证据层必须可追溯。这是经典编译器正确性、量子程序语义和现代工具型 Agent 三者的交集。
