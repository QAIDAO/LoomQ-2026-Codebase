# LoomQ L1 分阶段开发执行计划

## 执行规则

所有工作按下面的执行块顺序推进。每个执行块都必须遵循同一闭环：

1. 完成该块列出的代码或配置修改。
2. 按“新增测试条件”补齐测试。
3. 运行该块要求的定向测试。
4. 运行规定范围的回归测试。
5. 对照“完成检查”确认目标与边界。
6. 仅在全部检查通过后创建阶段性 Git 提交。

不得把未通过测试的工作带入下一执行块；不得在同一提交中混入 L2、L3、UI 或无关文档修改。

执行块 8、9、10 共用的真机任务清单、shots、逻辑门-shots 与重跑采购额度记录在 [`hardware_capacity_L1.md`](hardware_capacity_L1.md)；任何供应商变更都不得减少其中的位序探针或正式证据任务。

## 执行块 1：建立 L1 内部架构与输入模型

### 执行步骤

1. 保持 `adapter.py` 中 `transpile()`、`run()` 和 `SUPPORTED_TARGETS` 的公共签名不变。
2. 新建内部 QASM 解析模块，定义以下结构：
   - 量子寄存器及长度；
   - 经典寄存器及长度；
   - 门操作：门名、参数、量子位列表；
   - 测量操作：量子位到经典位映射；
   - 完整电路对象。
3. 实现 OpenQASM 2.0 最小词法预处理：
   - 去除行注释；
   - 允许任意空白和换行；
   - 识别 `OPENQASM 2.0` 与 `include "qelib1.inc"`；
   - 拆分并定位语句，保留错误所在语句。
4. 实现寄存器声明、门调用和测量语句解析。
5. 实现参数表达式求值，只允许数字、`pi`、括号及 `+ - * /`，禁止使用 `eval()`。
6. 实现输入校验：
   - 门名必须属于 12 门白名单；
   - 门参数个数、量子位个数必须正确；
   - 寄存器和索引必须存在且不越界；
   - 不允许重复声明；
   - 测量两端宽度必须一致；
   - 拒绝条件语句、自定义门和白名单外语法。
7. 为后续 emitter 和 runner 定义内部接口，但本块不接入任何 SDK。

### 新增测试条件

以下任一实现出现时，必须添加对应单元测试：

- 新增一种可接受的 QASM 语法；
- 新增一种参数表达式；
- 新增一条输入校验规则；
- 修复任何解析或校验缺陷；
- 改变内部 IR 字段或测量表示。

本块至少覆盖：

- Bell、GHZ-3 正常解析；
- 12 种门逐一解析；
- 整寄存器和逐位测量；
- 注释、空行和不同逗号空格；
- `pi/2`、`-pi/4`、`2*pi`、括号表达式；
- 未知门、参数数量错误、索引越界、寄存器未声明和测量宽度不一致。

### 回归测试

- 运行全部解析器和 IR 单元测试。
- 运行 `python -m unittest discover -s tests -v`，确认未破坏现有组织方工具测试。
- 本块不运行 SDK 或公开 evaluator 的通过性测试，因为公共接口仍允许处于未完成状态。

### 完成检查

- 目标检查：两个公开 QASM 和全部 12 门均能转换为同一种内部电路表示。
- 边界检查：没有实现目标平台输出、模拟器执行、L2、L3 或真机逻辑。
- 质量检查：错误信息必须包含错误类型及相关语句，不能只抛出无上下文的 `ValueError`。

### 阶段性 Git 提交

全部检查通过后提交：

`Implement validated QASM 2 parser and L1 IR`

提交只包含解析器、IR、相关测试及必要的模块导入调整。

---

## 执行块 2：实现三种目标 IR 转译

### 执行步骤

1. 实现公共 `transpile(qasm_str, target)`：
   - 先解析为统一 IR；
   - 校验 `target`；
   - 调用对应 emitter；
   - 返回非空、确定性的完整目标程序。
2. 实现 SpinQ emitter：
   - 输出完整 OpenQASM 2.0；
   - 保留量子与经典寄存器声明；
   - 输出全部操作和测量；
   - 门名及参数格式符合题面白名单。
3. 实现 OriginQ emitter：
   - 输出 `QINIT`、`CREG`；
   - 映射 `cx → CNOT`、`sdg → SDAG`、`tdg → TDAG`、`ccx → TOFFOLI`；
   - 参数门使用契约允许的统一格式；
   - 将所有测量展开为逐位 `MEASURE`。
4. 实现 Braket emitter：
   - 输出 OpenQASM 3.0 和 `stdgates.inc`；
   - 映射 `qreg/creg` 为 `qubit[]/bit[]`；
   - 统一输出 `cnot`；
   - 输出合法的逐位或整寄存器测量赋值。
5. 优先输出目标 IR 原生支持的 12 门；只有验证某目标契约或 SDK不支持时才引入标准门分解。
6. 增加输出稳定性处理：固定声明顺序、参数数值格式、换行和末尾换行。

### 新增测试条件

以下任一情况必须新增或更新 emitter 测试：

- 增加或修改门名映射；
- 改变参数格式或角度表达；
- 改变寄存器、测量或位序输出；
- 引入门分解；
- 修复正式契约或 SDK 解析失败；
- 修改目标 IR 的空白之外的任何内容。

每个平台至少包含：

- Bell 和 GHZ-3 黄金输出测试；
- 12 门完整转译测试；
- 多位寄存器和非连续逐位测量；
- 参数角度正值、负值和组合表达式；
- 不支持的 target 和非法 QASM 错误传播；
- 连续两次转译结果完全一致。

### 回归测试

- 每次修改某个平台 emitter，运行该平台全部 emitter 测试。
- 修改统一 IR、参数格式或测量模型时，运行三个 emitter 的全部测试。
- 引入门分解时，运行全部 12 门转译测试。
- 本块结束时运行完整 `unittest` 套件。
- 对三个输出分别执行语法解析或 SDK 编译检查；此检查不得实际提交云任务。

### 完成检查

- 目标检查：`transpile()` 对三个 target 均返回符合 `target_ir_contract.md` 的完整程序。
- 边界检查：本块不实现采样执行，不生成 counts，不访问云端。
- 契约检查：不得返回注释占位、固定 Bell 电路或与输入无关的输出。
- 架构检查：三种输出必须来自同一 IR，不得维护三套 QASM 输入解析逻辑。

### 阶段性 Git 提交

全部检查通过后提交：

`Add deterministic L1 target IR emitters`

提交只包含 `transpile()`、三个 emitter、契约测试及必要文档说明。

---

## 执行块 3：实现统一结果模型与本地执行框架

### 执行步骤

1. 定义内部执行结果结构，收集原始 counts、后端名、任务标识和元数据。
2. 实现统一 counts 归一化函数：
   - 接受整数、十进制字符串和二进制字符串 key；
   - 按经典寄存器宽度补前导零；
   - 统一为契约要求的 little bit order；
   - 合并归一化后重复的 key；
   - 验证所有值为非负整数；
   - 验证总计数严格等于 `shots`。
3. 实现结果封装函数，生成：
   - `backend`；
   - `job_id`；
   - `shots`；
   - `counts`；
   - `bit_order: "little"`；
   - 当前 UTC ISO-8601 `timestamp`；
   - 可选 `meta`。
4. 实现 `run()` 的公共调度框架：
   - 校验 `shots` 为正整数且不是布尔值；
   - 解析输入并选择目标 runner；
   - 未完成 runner 继续抛出明确异常；
   - 禁止 mock counts 和固定时间戳。
5. 为后端初始化、执行和资源释放定义一致的 runner 生命周期。

### 新增测试条件

必须在以下情况增加测试：

- 支持一种新的 SDK counts 格式；
- 修改 bit order、key 宽度或测量映射；
- 修改结果 schema；
- 增加新的 runner 生命周期或异常转换；
- 修复计数总和、前导零或位序错误。

至少覆盖：

- 整数、十进制和二进制 key；
- 前导零；
- 重复 key 合并；
- 0、负数、布尔值和非整数 shots；
- 空 counts、负计数、计数总和不一致；
- UTC 时间戳格式；
- `meta.is_mock` 不得出现。

### 回归测试

- 修改归一化逻辑时运行全部结果 schema 和三平台共享测试。
- 修改 `run()` 调度时运行所有 target 路由与异常测试。
- 本块结束时运行完整 `unittest`。
- 使用内存 fake runner 验证完整 `run()` 数据流，不连接真实 SDK。

### 完成检查

- 目标检查：任意合法原始执行结果都能稳定转换为 evaluator 接受的 schema。
- 边界检查：尚未声称任何真实后端可运行；fake runner 只能存在于测试代码。
- 安全检查：不包含凭证字段，不把完整环境变量写入异常或日志。

### 阶段性 Git 提交

全部检查通过后提交：

`Add L1 execution and result normalization framework`

---

## 执行块 4：接入 SpinQ 本地模拟器

### 执行步骤

1. 验证 SpinQit 在 Python 3.10 和项目 Docker 基础镜像中的可安装版本。
2. 将验证通过的版本精确固定到 `requirements.txt`。
3. 实现 SpinQ runner：
   - 使用 SpinQ emitter 生成 OpenQASM 2.0；
   - 通过安全临时文件交给 QASM compiler；
   - 初始化 BasicSimulator；
   - 配置传入的 shots；
   - 执行并读取真实 counts；
   - 无论成功失败都删除临时文件并释放资源。
4. 将原始结果交给共享归一化层。
5. backend 名明确标识为 SpinQ 本地模拟器；本地 job ID 每次执行唯一，不使用 Python 非稳定 `hash()`。
6. 移除或绕开示例中的 mock 返回逻辑，生产路径禁止 SDK 缺失时伪造成功。

### 新增测试条件

- 每次使用新的 SpinQ API、结果字段或编译路径时加入适配测试。
- 发现 SDK 版本差异时加入对应兼容测试；不允许只加 `hasattr` 而没有测试。
- SpinQ 上任何门失败后，修复时必须加入该门的最小复现电路。
- 位序或 counts 格式异常必须加入真实格式样例测试。

### 回归测试

- 每次修改 SpinQ runner，运行 SpinQ runner、共享归一化和 SpinQ emitter 测试。
- 修改公共 IR 或 emitter 后，重新运行 SpinQ Bell、GHZ-3。
- 本块结束时以 8192 shots 运行 Bell、GHZ-3，二者 Fidelity 均须 ≥ 0.97。
- 运行完整 `unittest` 和仅含 SpinQ 的公开 evaluator。

### 完成检查

- 目标检查：SpinQ 本地模拟器真实执行两个公开电路并通过 fidelity 阈值。
- 边界检查：不连接量旋云，不读取真机凭证，不修改其他平台 runner。
- 可复现检查：全新 Docker 构建能安装依赖并执行相同用例。

### 阶段性 Git 提交

全部检查通过后提交：

`Integrate SpinQ local simulator`

---

## 执行块 5：接入 OriginQ 本地模拟器并达到资格线

### 执行步骤

1. 验证 pyQPanda 的 Python 3.10、Linux 和 Docker 兼容版本，并精确固定依赖。
2. 实现 OriginQ runner：
   - 使用统一 IR 和 OriginIR emitter；
   - 通过 pyQPanda CPUQVM 编译并执行；
   - 取得经典寄存器和实际测量结果；
   - 在 `finally` 中释放 QVM；
   - 使用共享归一化层生成公共结果。
3. 明确 pyQPanda 返回 key 的含义和字节序，以单比特确定态及非对称多比特电路验证，不能只用 Bell 判断。
4. 对 SDK 不支持的白名单门，仅在 emitter 层采用已验证分解，保持执行层无额外语义转换。
5. 在同一进程内顺序执行多个电路，验证资源释放及无状态污染。

### 新增测试条件

- OriginIR 门映射、pyQPanda API、bit order 或资源管理发生变化时必须新增测试。
- 任意门需要分解时，必须同时添加：
  - 原门与分解门的语义对比测试；
  - OriginIR 输出测试；
  - OriginQ 实际执行测试。
- 修复崩溃、泄漏或重复运行问题时加入连续执行回归用例。

### 回归测试

- 每次修改 OriginQ runner，运行 OriginQ runner、OriginQ emitter和共享归一化测试。
- 修改共享 IR、测量或 bit order 后，同时重跑 SpinQ 和 OriginQ。
- 本块结束时两个平台均以 8192 shots 跑 Bell、GHZ-3，全部 Fidelity ≥ 0.97。
- 运行 `python evaluator.py --level l1 --target spinq,originq`。
- 运行完整 `unittest` 和 Docker 内同等测试。

### 完成检查

- 目标检查：同一套中间层在两个本地模拟器通过全部公开 L1 电路，达到评奖资格线。
- 边界检查：此时只声明“公开资格线达成”，不声明隐藏电路或满分线完成。
- 架构检查：SpinQ 与 OriginQ 共享解析、IR、校验、参数求值和结果归一化。

### 阶段性 Git 提交

全部检查通过后提交：

`Integrate OriginQ simulator and complete L1 baseline`

该提交是资格线里程碑，提交后打本地标签建议为 `l1-baseline`；是否推送标签由最终发布流程决定。

---

## 执行块 6：接入 Braket LocalSimulator

### 执行步骤

1. 验证 Amazon Braket SDK 的 Python 3.10 与 Docker 兼容版本并精确锁定。
2. 实现 Braket runner：
   - 使用 Braket emitter 产生 OpenQASM 3.0；
   - 构造 `Program`；
   - 在 `LocalSimulator` 上执行；
   - 提取 measurement counts、任务 ID 和可用元数据；
   - 通过共享归一化层输出。
3. 使用确定态和非对称多比特电路确认 Braket 测量字符串与契约 little bit order 的关系。
4. 确保 LocalSimulator 路径不需要 AWS 凭证、外网或云端队列。
5. 验证容器内三套 SDK 可以共存；如存在二进制依赖冲突，将冲突 runner 隔离为本地子进程，但公共接口和统一 IR 保持不变。

### 新增测试条件

- Braket QASM 3 门名、测量语法、结果字段或位序发生变化时必须新增测试。
- 若引入子进程隔离，必须新增超时、非零退出码、无效 JSON 和子进程清理测试。
- Braket 上任何白名单门失败后，修复必须附最小复现测试。

### 回归测试

- 修改 Braket emitter 或 runner时运行全部 Braket 测试及共享归一化测试。
- 修改共享代码时重跑三个平台。
- 本块结束时三平台分别以 8192 shots 运行 Bell、GHZ-3，全部 Fidelity ≥ 0.97。
- 运行公开 evaluator 的三个 target。
- 执行完整 `unittest`、语法检查和 Docker 测试。

### 完成检查

- 目标检查：三平台本地模拟器全部通过公开用例。
- 边界检查：Braket 只使用 LocalSimulator，不访问 AWS 云设备。
- 环境检查：无任何云凭证时，容器仍能完成三平台公开测试。

### 阶段性 Git 提交

全部检查通过后提交：

`Integrate Braket local simulator`

---

## 执行块 7：完成 12 门语义验证与隐藏集防护

### 执行步骤

1. 为每个白名单门建立最小验证电路；参数门至少覆盖正角、负角、零和非平凡角度。
2. 建立补充电路集：
   - GHZ-5；
   - QFT-4；
   - Grover-3；
   - 至少三组固定私有种子的随机电路；
   - 专门暴露 bit order 的非对称确定态电路；
   - 专门覆盖非连续测量的电路。
3. 建立独立参考模拟路径，计算期望分布；不得用被测 runner 自己产生期望值。
4. 三平台以相同输入、相同 shots 执行，分别与参考分布比较。
5. 对 `swap`、`cu1`、`ccx` 及任何采用分解的门进行原门/分解门差分验证。
6. 检查是否存在按公开文件名、固定 QASM 文本或固定期望分布硬编码的路径并移除。
7. 建立单命令 L1 回归入口，覆盖解析、三个 emitter、三个 runner、公开电路和扩展电路。

### 必须加入测试的情况

从本块开始，满足以下任何条件都必须添加永久回归测试：

- 正式或公开 evaluator 出现一次失败；
- 某 SDK 升级或结果格式变化；
- 新发现一个位序、参数、测量或门分解问题；
- 某电路在一个平台通过、另一个平台失败；
- 发生异常退出、资源未释放、超时或非确定性失败；
- 修改公共 IR、解析器、参数求值或共享归一化；
- 修复依赖、Docker 或平台兼容性问题；
- 真机结果与本地模拟器主导态不一致。

每个缺陷测试必须先能复现失败，再随修复转为通过；不得只扩大宽松阈值掩盖问题。

### 回归测试分级

- **局部回归**：修改单个平台 runner/emitter后，运行该平台全部门和电路。
- **共享回归**：修改解析器、IR、测量或归一化后，运行三平台全部测试。
- **完整回归**：阶段结束、依赖变化、Docker变化或准备提交前，运行：
  - 全部 `unittest`；
  - 三平台公开 evaluator；
  - 12 门测试；
  - 扩展隐藏集模拟；
  - Docker 内完整重复执行。
- 采样测试固定为 8192 shots，Fidelity 必须 ≥ 0.97；确定性语法和 schema 测试不得使用概率容差。

### 完成检查

- 目标检查：三平台全部 12 门、公开电路和补充隐藏集均达阈值。
- 边界检查：测试数据只用于本地防护，不修改组织方 evaluator，不把自建期望值注入提交运行路径。
- 稳定性检查：完整回归连续运行两次均通过，且不存在依赖执行顺序才能通过的测试。

### 阶段性 Git 提交

全部检查通过后提交：

`Harden L1 against hidden circuit evaluation`

该提交不得包含真机凭证、原始私有账户信息或生成的公共 evaluator 报告。

---

## 执行块 8：量旋真机接入与证据归档

### 执行步骤

1. 从环境变量读取量旋凭证、设备标识和必要的服务地址。
2. 在提交前校验凭证存在，但异常中只报告缺失变量名，不输出变量值。
3. 使用与模拟器相同的 SpinQ emitter 和统一 IR 提交真机任务。
4. 先使用 Bell 与非对称 `bit_order` 电路、各 100 shots 完成冒烟测试；确认任务可查询、counts/bit order 可解析、job ID 可在控制台追溯。
5. 冒烟通过后运行正式 Bell 和 GHZ-3、各 8192 shots，保存平台返回的未经伪造的原始结果；默认共 4 个任务、16,584 shots。
6. 将标准化摘要写入 `evidence/README.md`，将脱敏后的原始 JSON 放入 `evidence/files/`。
7. 核验时间戳处于赛程窗口、Top-K 主导态正确、job ID 可回查。
8. 将真机适配与本地 runner 分开配置；无凭证时本地模拟器路径仍正常运行。

### 新增测试条件

- 云 API 请求、轮询、超时、失败状态和结果解析必须使用 fake client 做离线测试。
- 每遇到一种云端任务状态或错误响应，加入状态机测试。
- 真机 counts 格式与本地不同，必须加入脱敏样例测试。
- 真实运行发现主导态异常时，加入对应本地复现电路并执行三平台共享回归。

### 回归测试

- 真机代码修改后运行量旋云客户端离线测试和 SpinQ 本地完整回归。
- 真机执行前运行 SpinQ 对应电路的本地模拟结果。
- 真机执行后重新运行全部无凭证测试，确保云接入没有破坏本地资格线。
- 不在自动化测试中重复提交付费或排队真机任务。

### 完成检查

- 目标检查：至少一份量旋真机证据 schema 完整、主峰正确、任务可追溯。
- 边界检查：凭证和完整账户信息未进入 Git；自动测试不调用真机。
- 回退检查：缺少凭证时只禁用真机入口，不影响 `target="spinq"` 的本地评分路径。

### 阶段性 Git 提交

分两次提交：

1. 真机客户端和离线测试通过后：
   `Add SpinQ hardware execution support`
2. 脱敏证据确认可提交后：
   `Archive SpinQ hardware evidence`

第二个提交前必须运行敏感信息搜索并人工检查暂存区。

---

## 执行块 9：本源真机接入与证据归档

### 执行记录（2026-08-03 已完成）

- API token 与 `WK_C180` 后端通过只读配置/可用性检查；token 未写入镜像、日志、证据或 Git。
- 冒烟 Bell、`bit_order` 与正式 Bell、GHZ-3 共 4 个真机任务全部完成，合计 16,584 shots；非对称位序探针 100/100 为 LoomQ 约定下的 `011`。
- 四个 job ID、平台原始开始时间、QASM、OriginIR、脱敏原始响应和标准摘要已归档到 `starter_kit/evidence/`；正式 Bell 预期支撑率 1.0，GHZ-3 为 0.9974365234375。
- 首个 Bell 在旧 SDK 本地轮询失败后按既有 job ID 恢复，没有重复提交；当前依赖固定为 `pyqpanda3==0.4.0`。
- 代码兼容性修复、单任务安全补交入口和证据分别提交为 `f212904`、`24980d3`、`3457ec3`。

### 执行步骤

1. 从环境变量读取本源云凭证、设备与服务配置。
2. 复用 OriginIR emitter 和统一 IR，不为真机重新实现转译。
3. 实现提交、轮询、超时、失败状态处理和结果下载；中断后可按既有 job ID 恢复，恢复路径不得再次提交。
4. 先以 Bell 与非对称 `bit_order` 电路各 100 shots 冒烟，再正式运行 Bell 与 GHZ-3；默认共 4 个任务、16,584 shots。
5. 归一化 counts 并核对 bit order 与本地主导态。
6. 保存脱敏原始 JSON和标准化摘要。
7. 在控制台核验 job ID 和赛程时间戳。
8. 确认本源证据符合 `evidence/README.md` 要求；第二平台证据由执行块 8 或执行块 10 补齐。

### 新增测试条件

与量旋真机相同；此外，任何 OriginIR 真机兼容性修复都必须同时加入 OriginQ 本地执行回归，防止为真机破坏模拟器语义。

### 回归测试

- 运行本源云客户端全部离线测试。
- 运行 OriginQ 本地全部门和扩展电路。
- 修改共享 emitter 时，重新运行三平台完整回归。
- 真机证据归档后运行无凭证 Docker 测试。

### 完成检查

- 目标检查：本源至少一份有效、可回溯、主峰命中的真机证据。
- 边界检查：仓库内只包含允许提交的脱敏证据。
- 满分条件检查：第二平台真机证据在执行块 8 或执行块 10 完成后统一核验。

### 阶段性 Git 提交

分两次提交：

1. `Add OriginQ hardware execution support`
2. `Archive OriginQ hardware evidence`

证据提交前再次检查暂存文件，不得提交 `.env`、token、cookie、账号 ID 或控制台会话数据。

---

## 执行块 10：AWS Braket QPU 备用接入与证据归档

当量旋真机算力在赛程窗口内无法购买或不可用时，本块作为第二真机平台的备用路径；客户端和离线测试无论是否启用备用路径都应预先完成，但不得仅凭离线测试宣称真机证据完成。

### 预建记录（2026-08-03）

- named profile/区域/QPU ARN/S3 前缀字段、最小 IAM 策略模板和 `plan`/`check`/`smoke`/`formal`/`submit-one`/`retry-prepared`/`resume` 脚本已预建。
- 离线 fake-client、Braket LocalSimulator、凭证脱敏、私有恢复收据隔离、位序和半写回滚均有测试；没有读取 AWS 凭证或发起真实 AWS 请求。
- 尚未填写真实 AWS profile、QPU ARN、账户或 bucket，也未提交 AWS QPU 任务；本块当前只完成备用代码阶段，条件证据阶段仍待实际启用。

### 执行步骤

1. 从环境变量读取显式 AWS named profile、区域、QPU ARN、私有 S3 bucket 和结果前缀；凭证只保存在 AWS profile 中，不写入仓库环境文件。
2. 使用 Boto3 低层 Braket/S3 API，并复用通过 LocalSimulator 预检的无 `include` OpenQASM 3 emitter，避免旧版高层 SDK 的云设备能力解析差异。
3. `plan` 模式保持完全离线；`check` 模式只执行 `GetDevice`、`GetBucketLocation` 和 S3 前缀只读检查，不创建任务或对象，且明确不得把只读通过表述为已验证付费提交权限。
4. 任何 QPU 提交必须显式提供 `--confirm-submit AWS_BRAKET_QPU`，并在提交前校验设备为同区域、在线、支持所需操作且 shots 在设备限制内。
5. 冒烟任务严格串行执行 Bell 与 `bit_order`，各 100 shots；两者的 LocalSimulator 预检必须在首个付费任务前全部通过。
6. 冒烟通过后严格串行正式执行 Bell 与 GHZ-3，各 8192 shots；默认备案总量为 4 个 QPU 任务、16,584 shots。
7. 实现 `CREATED`、`QUEUED`、`RUNNING`、`CANCELLING`、`COMPLETED`、`FAILED`、`CANCELLED` 状态机、总超时和未知状态关闭失败；超时只停止本地等待，不自动取消或重复付费任务。
8. 付费调用前在固定私有状态目录独占保存 `clientToken` 恢复收据，收到 ARN 后立即保存原 token、安全 task ID、电路、shots 与程序哈希，但不保存完整 ARN 或账户号；`--output-dir` 只能重定向脱敏公开证据，不能重定向私有收据。批次中断后，只有在控制台和收据都明确证明任务未创建时才可用 `submit-one` 以新 token 补交一个显式任务；付费调用结果不明时只能用 `retry-prepared` 校验 schema v2 收据及绑定 profile、区域和完整创建参数的请求指纹，并复用原 token 幂等重试一次。旧 schema v1 收据不得自动升级或重试。提供 `resume` 入口按原 ARN/token/circuit/shots 继续查询，恢复路径绝不调用 `CreateQuantumTask`，固定状态目录必须同时排除于 Git 与 Docker 构建上下文。
9. 下载 S3 `results.json` 后先保存脱敏 payload 与哈希，再核验 task ID、device、shots、task schema、measured qubits 和 bit order；以独占写入保存 QASM 2、实际 QASM 3、脱敏原始 JSON 和标准化摘要，部分写入失败时回滚本地文件。
10. 在 AWS 控制台以 task ID 核验设备与赛程时间戳，并在证据提交前检查账户号、bucket、profile、访问密钥和请求元数据均已脱敏。

### 新增测试条件

- named profile、区域/QPU ARN、bucket、前缀、shots 和占位值校验使用纯离线单元测试。
- `GetDevice`、只读 S3 检查、创建任务、轮询、按 ARN 恢复、下载、超时、失败、未知状态和结果解析全部使用 fake client；自动测试不得连接 AWS。
- 使用非对称确定态 `bit_order.qasm` 验证 Braket `measuredQubits` 到 LoomQ little bit order 的映射。
- 验证确认文字在创建 AWS 客户端前失败、所有本地预检先于首次提交、恢复不触发提交、task ID 不被账户号脱敏规则误改、证据文件不可覆盖且敏感字段不会出现在异常或 JSON 中。
- 验证 `submit-one` 每次只提交一个受 shots 上限约束的任务；`retry-prepared` 拒绝目录逃逸、符号链接、超大/重复键/旧 schema 收据和任意请求指纹差异，复用原 token，且只接受完全一致的既有 submitted receipt。

### 回归测试

- 运行 AWS Braket 硬件客户端全部离线测试和 Braket LocalSimulator 回归。
- 修改共享 emitter 时重新运行三平台公开 evaluator 与门/扩展电路回归。
- 真实任务完成后重新运行无凭证测试，确保备用接入不改变本地资格线。
- CI、普通单元测试和 Docker 回归不传 AWS profile，也不提交或轮询真实任务。

### 完成检查

- 备用代码检查：显式 named profile、只读检查、确认门、状态机、超时、脱敏和独占证据均有离线测试。
- 条件证据检查：仅在量旋不可用且 AWS QPU 实际运行完成后，将有效、可回溯、主峰命中的 Braket 证据作为第二平台证据。
- 满分条件检查：本源加上量旋或 AWS Braket 二者之一，构成两平台真机证据；不得将 AWS LocalSimulator 计作真机。

### 阶段性 Git 提交

分两次提交，第二次仅在实际启用备用路径时执行：

1. `Add AWS Braket QPU fallback execution support`
2. `Archive AWS Braket QPU fallback evidence`

证据提交前必须再次执行敏感信息搜索并人工检查暂存区，不得提交 AWS profile、访问密钥、账户号、私有 bucket 或控制台会话数据。

---

## L1 阶段性验收记录（2026-08-03）

- 执行块 1–7 的统一工程闭环通过阶段验收；执行块 9 的 OriginQ 单平台真机证据完整、可追溯。
- 执行块 8 的 SpinQ 客户端已完成，但算力购买仍待服务方回复；执行块 10 的 AWS 客户端与安全恢复已完成，但注册受阻，二者均没有真机完成记录。
- 当前可以按 L1 工程成果和 OriginQ 一个平台真机证据参赛提交；不得宣称两平台真机、AWS/SpinQ 真机或 45 分满分完成。
- 执行块 11 保持未完成；它在第二平台证据到位后继续作为满分版冻结门禁。即使第二平台赛前仍不可用，也可在执行最终提交预检后按当前成果提交。
- 旧阶段验收报告已删除；当前验证结论见 [`../acceptance/verification.md`](../acceptance/verification.md)。开发期 Issue 字段草稿见 [`final_submission_L1.md`](final_submission_L1.md)，不得作为最终回执。

---

## 执行块 11：发布前冻结与最终验收

### 执行步骤

1. 冻结解析器、IR、门映射、bit order 和 counts 归一化；冻结后只接受阻断提交的问题修复。
2. 检查 `submission.yaml`：
   - `l1: true`；
   - `l2: false`；
   - `l3: false`；
   - `required_for_l1: false`。
3. 检查 `requirements.txt` 中所有第三方包均使用精确版本。
4. 更新 README，只记录实际可运行命令、支持后端、环境变量名称和已知限制。
5. 从干净构建上下文构建 Docker 镜像。
6. 在无凭证环境运行三个本地模拟器完整测试。
7. 执行最终检查：
   - `python -m unittest discover -s tests -v`
   - CI 等价语法检查
   - 三平台 L1 evaluator
   - 12 门与扩展电路回归
   - Docker 内完整回归
   - `prepare_submission.py`
8. 审查 Git diff、未跟踪文件、生成报告和敏感信息。
9. 仅保留应提交的源码、测试、文档和脱敏真机证据。

### 发布前缺陷处理规则

- 解析、IR、测量、bit order 或归一化修复：必须运行三平台完整回归。
- 单平台 SDK 调用修复：运行该平台全部回归，再运行三平台公开 evaluator。
- Docker 或依赖修改：必须重新构建干净镜像并运行容器内完整回归。
- 文档修改：验证命令可复制执行；纯文字修改无需概率电路回归。
- 证据修改：重新执行 schema、敏感信息和 job ID 可追溯检查。
- 任何修复都必须先添加或确认已有失败复现测试，禁止无测试的最后一分钟代码修补。

### 完成检查

- 目标检查：三平台公开及扩展电路全部达标，本源与量旋/AWS Braket 二选一组成的两平台真机证据有效。
- 边界检查：L2/L3 仍为未实现状态，没有 UI、Agent 或混合编译内容混入。
- 提交检查：工作树只包含预期文件，没有 evaluator 报告、凭证或临时产物。
- 可复现检查：干净 Docker 环境不依赖本机缓存、云账号或未声明文件。

### 阶段性 Git 提交

1. 若最终验收只涉及文档和配置：
   `Finalize L1 submission documentation`
2. 若发现并修复阻断缺陷：
   - 先单独提交缺陷与回归测试：`Fix <specific L1 failure>`
   - 再提交发布元数据：`Finalize L1 submission`
3. 最终提交完成后不再 squash 不同性质的阶段提交，以保留可审计的开发里程碑。

## Git 提交通用门禁

任何阶段性提交都必须满足：

- 暂存区只包含当前执行块的改动；
- 相关定向测试全部通过；
- 该块要求的回归测试全部通过；
- 没有凭证、报告、缓存、临时 QASM 或 SDK 生成文件；
- 提交主题简短、祈使式、单一职责；
- 若测试因外部真机不可用而未执行，只能提交离线客户端代码，不能提交“真机完成”或证据里程碑。
