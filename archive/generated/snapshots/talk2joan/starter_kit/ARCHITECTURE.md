# LoomQ 架构文档（Architecture）

> 一句话：**adapter.py 是一台"量子方言翻译机"**——人话进去，三家平台的母语出来，
> 每一句翻译都自带验收。

## 1. 总览

```text
                    ┌──────────────────────────────────────────┐
   人话 / QASM ──►  │                adapter.py                │
                    │                                          │
   L1 转译三通道    │   parse ──► rewrite ──► emit ──► driver  │
                    │              (门重写/     (方言别名)  │
                    │               白名单)          │          │
                    │                                        ▼  │
                    │            spinqit ─ pyqpanda ─ braket-worker │
                    │                                        │  │
                    │                                     normalize
                    │                                   (位序统一'001')
                    └──────────────────────────────────────────┘
```

三个 Level 共享同一条 L1 管线，逐层加能力：

| Level | 入口 | 核心机制 |
|---|---|---|
| L1 | `transpile(qasm, target)` / `run(qasm, target, shots)` | 统一管线 + 三平台驱动 |
| L2 | `agent_chat(prompt)` | 分类 → 生成/修复自验闭环 → 确定性兜底 |
| L3 | `compile_hybrid(hybrid_qasm)` | 经典块解析 → RISC-V 代码生成 |
| Web | `webapp.py` + `web/` | 零依赖本地服务，Kitty 桌宠引导 |

## 2. L1：统一转译管线

- **解析**：自研轻量 OpenQASM 解析（不依赖各家 SDK 的解析器）。
- **改写**：白名单内等价展开、方言别名映射（`cx→cnot`、`cu1→cphaseshift`、
  `sdg→si`、`tdg→ti`、`ccx→ccnot`）。
- **发射**：按目标平台输出原生 IR——SpinQ/OpenQASM 2.0、OriginIR 子集、
  Braket/OpenQASM 3。
- **执行**：
  - spinq → 本地 `spinqit` Taurus 模拟器；
  - originq → 本地 `pyqpanda` CPUQVM；
  - braket → 子进程 `_braket_worker.py`（Python 3.12 隔离 antlr 版本冲突），
    stdin/stdout JSON 协议。
- **归一化**：三家计数键统一为"最右字符 = c[0]"小端序（各家大端/小端不一，
  这是隐藏电路失分的最大陷阱，管线内一次解决）。
- **antlr 战争的和平方案**：openqasm3 需要 antlr ≥4.10 而 spinqit 锁 4.9.x。
  解决：主进程用新版；spinqit 导入前经 `_import_spinqit()` 清空 antlr 模块并
  注入 vendored 影子路径（`_vendor/antlr49/antlr4/`）；Braket 干脆走子进程。

## 3. L2：会自验的智能体

```text
prompt ─► 分类器(LLM) ─► generate/repair/backend 三分支
                            │
        ┌───────────────────┼────────────────────┐
        ▼                   ▼                    ▼
   生成/修复             后端推荐            非法门翻译器(查表)
   LLM 写初稿       不让 LLM 背书：      ryy/cz/cy/rx 四种非法门
        │           抽约束靠 LLM，         的白名单等价结构，
        ▼           选后端纯查表            全部矩阵验证后才上线
   自验流水线 ◄──┐   (backend_capabilities.json)
   lint→白名单    │
   →真跑→保真度   │ 失败原因翻成"人话"喂回模型，最多三轮
        │         │
        ├── 通过 ─┘
        ▼
   兜底序列：确定性合成器(bell/ghz/W) → 非法门改写 → 放弃并如实报告
```

设计原则：**LLM 只负责听懂人话和写初稿；一切数学与判定都在确定性代码侧。**
因此评测环境注入任何 OpenAI 兼容模型（含 deepseek-v4-flash）都不影响正确性。

## 4. L3：混合编译器

- 解析：花括号配平提取 `classical { }` 块；递归下降产出 AST
  （赋值 / if-else / 条件 == != / 表达式 + -）。
- 代码生成的寄存器纪律（保证寄存器终态与参考解释器一致）：
  - r1..r9 → x1..x9；测量位 c[k] → x10+k（只读，评测系统预注入）；
  - **目标寄存器当累加器**：`r1 = r2+r3-4` ⇒ `add x1,x2,x3; addi x1,x1,-4`；
  - 自引用赋值先做影子保存（旧值 → x30）再写；
  - 唯一临时是 x31/x30（比较立即数/取负），尾声统一清零。
- 验证：`_test_l3.py` 完整复刻官方判分循环——随机用例 × 穷举测量注入 ×
  参考解释器比对。当前 **2000+ 用例零失败**。

## 5. Web 入口（量子Kitty）

- `webapp.py`：标准库 `http.server` 线程服务，零第三方依赖。
  - `POST /api/chat` → `adapter.agent_chat`
  - `POST /api/run` → `adapter.run`
- `web/`：单页应用，韩系暖色 × robo-advisor 引导流；QASM 自动渲染成
  SVG 电路图（自绘，无库）；结果动画直方图；可拖拽桌宠「量子Kitty」
  在关键节点说话。
- `demo.html`：构建脚本 `_build_standalone.py` 生成的单文件离线演示版，
  双击即玩（file:// 下自动切换内置示例数据）。

## 6. 测试矩阵一览

| 测试 | 规模 | 结果 |
|---|---|---|
| 公开门集 × 3 平台门级探针 | 36 门组合 | 全绿 |
| 公开评测 evaluator.py | 4 case | 4/4 |
| 跨平台一致性（Hellinger） | 2048 shots | 最大极差 < 0.05 |
| 隐藏电路模拟考（独立参考模拟器） | 9 电路 × 3 平台 | 最低保真度 0.9965 |
| L2 变体压测 | 14 题 | 14/14 |
| L3 随机用例穷举注入 | 2000+ 用例 | 0 失败 |
