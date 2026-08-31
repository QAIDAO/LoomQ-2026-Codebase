# LoomQ 架构说明（ARCHITECTURE）

> 本文档描述我们在 Starter Kit v1.1.0 之上的全新实现。
> 组织方提供的合同文件(`adapter.py` 契约、`evaluator.py`、`riscv_emulator.py`、
> `target_ir_contract.md`、`l2_policy.json`)保持原样;所有新代码都是重写,
> 未复制参考实现。

## 一、范式映射(应题要求)

| 层 | 指定范式 | 落点 |
|---|---|---|
| L1 转译与执行 | 插件架构 + Asyncio | `plugins/*_plugin.py` 动态发现注册;`runner.py` 用 `asyncio.gather` 并发分发、信号量限流、单后端故障隔离 |
| L2 智能体 | 函数式 + 高阶函数 | `agent_fp.py`:冻结记录(Intent/Verdict/Draft)+ `pipe/retry/rescue` 组合子;生成⇄验证⇄修复闭环是纯函数流水线 |
| L3 混合编译 | 数据类驱动 + 声明式 | `riscv_model.py` 冻结指令数据类(不可变状态机);`hybrid_compiler.py` 表达式折叠 + 每种寻址形态一条声明式规则 |
| 全局 | DI / 配置即代码 | `config.py`(env + YAML 子集)→ `di.py` 组合根 `bootstrap()`;除组合根外无人构造依赖 |

## 二、模块地图

```text
starter_kit/
├── adapter.py            提交契约入口(薄壳,全部依赖来自容器)
├── lexer.py              共享分词器(QASM 与经典块同一套 Token)
├── parser.py             递归下降解析 → 类型化 AST(ir.py)
├── ir.py                 AST 数据类 + lower() 展平为 Circuit
├── gates.py              唯一门事实源:矩阵 / 三方言拼写 / SDK 名 / 分解规则
├── simulator.py          零依赖不可变态矢模拟器(内置引擎)
├── targets.py            三方言发射器(qasm2 / qasm3 / originir)
├── normalize.py          计数归一化(字节序统一为 bit_order=little)
├── plugin_loader.py      BackendPlugin 合同 + 动态发现 *_plugin.py
├── native_support.py     spinqit / pyqpanda / braket 原生路径构建器
├── plugins/              spinq_plugin / originq_plugin / braket_plugin
├── runner.py             asyncio 执行器 + 统一结果 Schema 组装
├── config.py             LOOMQ_* 环境变量 + loomq.yaml 子集 → 冻结配置
├── di.py                 最小 DI 容器 + bootstrap() 组合根
├── agent_fp.py           L2 函数式智能体(意图→草稿→验证→修复→答复)
├── hybrid_compiler.py    L3 编译器 + 参考解释器 + verify_hybrid 全量交叉验证
├── riscv_model.py        RISC-V 指令数据类、纯函数执行器、汇编往返
└── cli.py                零依赖交互控制台(:demo :backend :run …)

tests/                    121 个标准库 unittest(含 60 例随机程序三路交叉验证)
```

## 三、L1 数据流

```text
qasm_str ─▶ parser ─▶ Program ─▶ ir.lower ─▶ Circuit(展平、测量映射)
                                             │
                     ┌───────────────────────┼─────────────────────┐
                     ▼                       ▼                     ▼
              spinq 插件               originq 插件            braket 插件
              dialect=qasm2            dialect=originir        dialect=qasm3
              native: spinqit          native: pyqpanda        native: braket
              fallback: 内置引擎        fallback: 内置引擎       fallback: 内置引擎
                     │                       │                     │
                     └───────── asyncio.gather(并发, 信号量限流) ────┘
                                             │
                              normalize(counts → little-endian clbit 键)
                                             ▼
                       统一 Schema {backend, job_id, shots, counts,
                                    bit_order:"little", timestamp, meta}
```

设计要点:

* **加一个后端 = 加一个文件**:插件导出 `register()` 返回 `BackendPlugin`
  (`target/backend_id/dialect/capabilities/emit/run`),加载器做结构化校验;
  流水线其余部分零改动。
* **诚实降级**:原生 SDK 不可用时自动落回内置引擎,结果里 `engine` 字段如实
  标注 `builtin:statevector`,绝不伪装成真机结果。
* **字节序一次算清**:`normalize.raw_key_to_clbit_key(raw, big_endian,
  measures, n_clbits)` 是唯一换算点——spinq/braket 大端、pyqpanda 小端,
  统一输出最右字符为 `c[0]` 的键。

## 四、L2 函数式智能体

```text
prompt ─▶ extract_intent ─▶ Intent(冻结)
             │  分派(高阶选择器)
             ├─ generate_pipeline: LLM 草稿 ⇄ verify_qasm(模拟在环) ⇄ 修复轮
             ├─ fix_pipeline:     解析诊断 → LLM 修复 ⇄ 验证 → 模板兜底
             └─ select_pipeline:  能力表上的确定性求解器(LLM 只负责措辞)
             ▼
         Draft(qasm, origin, verdict) ─▶ _format_answer
```

* 验证即评分:`verify_qasm` 在内置模拟器上采样并与解析理想分布比对
  Hellinger 保真度(公式与官方 evaluator 完全一致),阈值 0.97。
* 每个请求至少一次有效模型调用(符合 l2_policy);LLM 不可用时离线模板
  引擎仍能完成 GHZ/Bell/W(≤3)/均匀叠加与后端推荐,交互不空转。
* W 态电路为手工推导并经模拟验证的精确构造(RY 分裂 + 开放控制 CRY +
  开放控制 Toffoli);更大规模诚实地返回"暂不支持",绝不输出错误物理。

## 五、L3 声明式编译

规范约定(problem_statement.md):经典寄存器 `r1..r9 ↔ x1..x9`;
测量位 `c[k] → x10+k`;文法 = 整数字面量、r1..r9、`+ - == !=`、if/else。

```text
Hybrid-QASM ─▶ 同一 parser ─▶ classical 块 AST
                                 │
                 _fold 常量折叠('const'|'reg'|op 树)
                                 │
        声明式 lowering 规则表:  const→Li   reg→Add rd rs x0
                                reg±imm→Addi   imm−reg→Li SCRATCH+Sub
                                reg±reg→Add/Sub   if==→Bne 反演
                                 ▼
        指令数据类列表 ─▶ render_program ─▶ RISC-V 汇编文本
```

正确性保障:`verify_hybrid` 对所有测量位注入组合(2^k,k=引用位数),
同时跑**参考解释器**与官方 `TinyRISCVEmulator`,逐寄存器全等比对;
测试套件另加 60 个随机文法程序的同款三路交叉验证。

## 六、真机接入（可选，凭证全走环境变量）

真机凭证与大模型配置采用同一政策：**只从环境变量读取，绝不硬编码、
绝不入库**；`config.describe()` 输出脱敏摘要，`cli :status` 可随时核对。

| 环境变量 | 用途 | 说明 |
|---|---|---|
| `LOOMQ_SPINQ_TOKEN` | 量旋云 / 超导真机 Token | 设置后 spinq 插件具备云端提交能力 |
| `LOOMQ_ORIGINQ_TOKEN` | 本源云 / 悟空 72 比特 Token | 设置后 originq 插件具备云端提交能力 |
| `AWS_ACCESS_KEY_ID` 等 | AWS 标准变量 | Braket 由 boto3 原生读取（本地模拟器无需账号） |
| `LOOMQ_PREFER_REAL_MACHINE` | 置 `1`/`true` 时优先真机 | 需同时配置对应平台凭证 |

行为约定：

* 未设置凭证 → 一律本地路径（SDK 本地模拟器或内置引擎），结果 `engine`
  字段如实标注（`native:pyqpanda` / `builtin:statevector`…）。
* 设置凭证且开启偏好 → 插件调用云端适配器（`run_spinq_cloud` /
  `run_originq_cloud`），返回真实 `job_id`；**任何失败都会如实报错，
  绝不静默降级为模拟结果冒充真机**。
* 正式评测环境默认禁止网络，因此评分链路永远走本地路径；真机分按
  大赛规则以 evidence 材料人工核验。

```bash
# 示例：让智能体把任务发往本源悟空真机
export LOOMQ_ORIGINQ_TOKEN=<你的平台Token>
export LOOMQ_PREFER_REAL_MACHINE=1
python cli.py "生成贝尔态并测量"
```

## 七、Bonus：自定义量子 RISC-V 扩展

三件套齐备（详见 `docs/QUANTUM_RISCV_SPEC.md`）：

1. **编码规格**：custom-0 opcode `0x0B` 的 R 型布局 + funct7 分配表；
2. **扩展实现**：`quantum_riscv.py` 以继承方式扩展官方模拟器（原文件零改动），
   新增 `qh/qx/qz/qrz/qcx/qmeas/qinit` 七条指令、内嵌态矢内核、
   字级 `encode()/decode()` 编解码器；
3. **端到端测试**：`tests/test_quantum_riscv.py`——贝尔/GHZ 关联统计、
   编码往返、测量驱动经典分支、报错路径。

亮点是真正的 hybrid：量子比特编号来自通用寄存器当前值，测量结果立刻
参与 `beq/bne` 分支——一份程序里经典计算决定量子操作、量子测量反馈
经典控制流。

## 八、DI 与配置

* `di.bootstrap(cfg)` 是唯一知道具体模块的组合根:注册
  `config / plugin_registry / llm_transport / runner` 四个懒加载单例;
  `container.scope()` 供测试注入替身而不打补丁。
* 配置来源优先级:显式参数 > 环境变量 > `loomq.yaml` > 默认值。
  LLM 三要素只从 `LOOMQ_LLM_BASE_URL/API_KEY/MODEL` 读取,无任何硬编码;
  密钥永不打印(`config.describe()` 输出脱敏摘要)。

## 九、测试策略

```bash
# 仓库根目录
python -m unittest discover -s tests      # 131 tests, 全部标准库
cd starter_kit && python evaluator.py     # 公开自测 6/6 PASS(l1+l2+l3)
```

覆盖面:12 门语义(精确振幅)、三方言金样与回环解析、字节序矩阵、
统一 Schema 合规(evaluator.validate_schema)、并发聚合与故障隔离、
L2 三任务离线+假传输体(信封格式/修复环/模板兜底)、L3 寻址形态×分支
反转×嵌套×随机模糊、以及官方 RISC-V 模拟器一致性。

## 十、已知的诚实边界

* 本机 Python 3.14 无法安装 cp310-only 的 SDK(spinqit 等),原生路径在
  兼容环境中自动启用,本地验证走内置引擎路径。
* W 态模板覆盖 n≤3;n≥4 时明确告知而非猜测。
* `classical` 块内赋值右侧按文法不支持 `c[k]`(c 位仅用于条件),
  与 problem_statement.md 的迷你文法一致。
