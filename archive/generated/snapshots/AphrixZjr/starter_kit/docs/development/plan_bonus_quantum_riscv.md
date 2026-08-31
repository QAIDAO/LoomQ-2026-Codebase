# LoomQ Bonus 量子自定义 RISC-V 指令分阶段开发执行计划

## 执行规则

本计划只覆盖一个可验证的最小“汇编—编码—解码—执行”闭环：

```text
基础指令与量子指令混合汇编
→ assembler
→ 32 位 instruction word
→ instruction memory
→ fetch
→ decode
→ execute
```

所有工作按执行块顺序推进，并遵循“实现 → 定向测试 → 回归 → 完成检查 → 阶段提交”的闭环。Bonus 与 L3 隔离：L3 继续使用原版文本 `riscv_emulator.py`；Bonus 可以 fork/扩展模拟器，但不得改变 L3 官方语义测试所导入的类和行为。

本项不描述为完整量子协处理器，不扩展到完整 RV32I、QEMU、真实流水线、操作系统、ABI、链接器、逐门远端调用或跨请求保存量子态。量子执行仍复用项目已有的本地模拟器后端。

## 最小 ISA v1 编码草案

实施前先把下表冻结为独立编码规格文档；后续 assembler、decoder、executor 与测试必须共同引用同一组常量，文档与代码逐项核对。

### 基础指令

只编码闭环实际需要的 RV32I 指令：

| 指令 | 格式 | opcode | funct3 | funct7 | 说明 |
|---|---|---:|---:|---:|---|
| `add` | R | `0110011` | `000` | `0000000` | 寄存器加法 |
| `sub` | R | `0110011` | `000` | `0100000` | 寄存器减法 |
| `addi` | I | `0010011` | `000` | — | 12 位有符号立即数 |
| `beq` | B | `1100011` | `000` | — | PC 相对字节偏移 |
| `bne` | B | `1100011` | `001` | — | PC 相对字节偏移 |
| `lui` | U | `0110111` | — | — | 为大立即数提供高 20 位 |
| `jal x0, offset` | J | `1101111` | — | — | `j` 的真实展开 |

`li rd, imm32` 是 assembler 伪指令：12 位有符号范围内展开为 `addi rd, x0, imm12`，否则按 RV32I 高低位进位规则展开为 `lui` 加可选 `addi`。`j label` 展开为 `jal x0, offset`。instruction memory 中绝不出现 `li` 或 `j`。

### 量子门指令 QGATE

使用 RISC-V 预留 `custom-0` opcode `0001011`（`0x0B`），固定 32 位 Q-type 布局：

```text
31          25 24          20 19          15 14      12 11           7 6          0
+--------------+--------------+--------------+----------+--------------+------------+
| gate_id [6:0]| aux     [4:0]| q1      [4:0]| mode [2:0]| q0      [4:0]| 0001011    |
+--------------+--------------+--------------+----------+--------------+------------+
```

- `q0`：单比特门目标；双/三比特门的第一个量子位。
- `q1`：双/三比特门的第二个量子位；不用时必须为 0。
- `aux`：`ccx` 的第三个量子位；`rz/ry/cu1` 时为保存 Q16.16 有符号弧度参数的经典寄存器 `x0..x31`；其他门必须为 0。
- `mode`：v1 固定为 `000`，其余值保留并由 decoder 拒绝。
- `gate_id`：`h=1`、`x=2`、`s=3`、`sdg=4`、`t=5`、`tdg=6`、`rz=7`、`ry=8`、`cx=9`、`cu1=10`、`swap=11`、`ccx=12`；`0` 和 `13..127` 保留。

Q16.16 参数由 assembler 将汇编中的弧度字面量装入指定经典寄存器，executor 解码后除以 `65536` 交给量子后端。量化范围、舍入方式（round-to-nearest, ties-to-even）和溢出报错必须写入正式规格；不能由 Python 浮点格式偶然决定。

### 量子控制指令 QCTRL

使用 `custom-1` opcode `0101011`（`0x2B`）：

```text
31          25 24          20 19          15 14      12 11           7 6          0
+--------------+--------------+--------------+----------+--------------+------------+
| imm7/reserved| slot    [4:0]| q       [4:0]| op   [2:0]| rd      [4:0]| 0101011    |
+--------------+--------------+--------------+----------+--------------+------------+
```

| `op` | 汇编名 | 字段约束 | v1 语义 |
|---:|---|---|---|
| `000` | `qreset` | 其余字段为 0 | 清空 pending circuit、测量声明和上次结果 |
| `001` | `qmeasure q, slot` | `rd=0, imm7=0` | 把量子位到结果槽的测量声明加入 pending circuit |
| `010` | `qsubmit` | 其余字段为 0 | 一次性执行 pending circuit 并保存结果；未测量或空电路报错 |
| `011` | `qread rd, slot` | `q=0, imm7=0` | 将最近一次提交的该结果槽写入 `rd` |

`op=100..111` 保留。v1 使用单次确定性 shot 完成控制流案例；若后续需要多 shots，必须发布新的编码版本或使用明确的新字段，不能偷偷改变 `imm7` 含义。

## 执行块 1：冻结编码规格与模块边界

### 执行步骤

1. 新建独立 ISA 规格文档，完整记录上述位布局、门 ID、保留值、立即数拼接、符号扩展、PC 单位、对齐、Q16.16 和错误行为。
2. 固定模块边界：assembler 接受文本并输出 `list[int]`；instruction memory 只保存无符号 32 位 word；decoder 接受 word 和 PC 并返回结构化指令；executor 不接收 mnemonic 字符串。
3. 定义结构化 decoded instruction，区分基础 R/I/B/U/J、QGATE 和 QCTRL，同时保存已符号扩展的立即数和明确操作数。
4. 规定 PC 为字节地址、每条指令 4 字节、分支/jump 偏移相对当前 PC；拒绝未对齐目标和超范围偏移。
5. 规定经典寄存器为 RV32 无符号 32 位存储，算术按模 `2^32` 回绕，比较 `beq/bne` 按位相等；`x0` 恒为零。
6. 为规格分配版本 `LoomQ-QISA-v1`，编码变更必须先改规格和黄金向量。

### 新增测试条件

- 每一种基础格式和两种 custom opcode 的手工黄金 word；
- 位域边界、符号立即数边界、量子位/slot/寄存器范围；
- 保留 opcode、gate ID、mode、op 和非零保留字段被拒绝；
- PC 偏移和 4 字节对齐；
- 文档表格与代码常量的逐项一致性测试。

### 回归测试

- 运行编码规格黄金向量测试和完整 `unittest`。
- 不改动 L3 的原版模拟器路径。

### 完成检查

- 目标检查：任意合法 word 的每个位都有唯一含义，任意保留组合有明确错误行为。
- 一致性检查：规格不存在“实现自行决定”的关键字段。
- 边界检查：没有 CSR、中断、内存访问、特权态、浮点或完整 RV32I 计划。

### 阶段性 Git 提交

`Specify the LoomQ quantum RISC-V ISA`

---

## 执行块 2：实现两遍 assembler 与机器码装载

### 执行步骤

1. 实现两遍 assembler：第一遍展开伪指令并确定标签地址，第二遍编码 word；标签地址必须基于展开后的真实指令数。
2. 支持基础指令 `add/sub/addi/beq/bne/lui`、真实 `jal x0, label` 及伪指令 `li/j`。
3. 支持 12 个 `qgate` 语法糖和 `qreset/qmeasure/qsubmit/qread`；语法糖只负责字段组装，不进入 executor。
4. 参数门把角度转换为 Q16.16，并显式生成装载参数寄存器的基础机器指令；参数寄存器由汇编语法指定，避免 assembler 隐式破坏活跃寄存器。
5. 对立即数、标签距离、寄存器、量子位、slot、门元数和保留字段执行严格校验。
6. instruction memory 接受 `list[int]` 或等价不可变序列，装载时验证 `0 <= word <= 0xffffffff`，不保留源 mnemonic 供执行旁路使用。

### 新增测试条件

- `li` 的最小/最大 12 位值和需要一条/两条真实指令的 32 位值；
- 前向/后向 `beq/bne/j`，包括伪指令展开改变标签地址；
- 12 个量子门、三个参数门和四个控制指令的黄金 word；
- 未知 mnemonic、错误元数、越界立即数、重复/缺失标签和未对齐跳转；
- 装载后仅有整数 word，不包含 tuple、字符串或源 token。

### 回归测试

- 对每条指令运行手算黄金编码比较。
- 对混合程序检查全部 instruction word 序列和标签目标。
- 运行完整 `unittest` 及 L3 原版模拟器回归。

### 完成检查

- 目标检查：混合汇编可完全转换为 32 位 word 序列。
- 旁路检查：instruction memory 中没有 mnemonic，executor 无法依赖汇编文本。
- 边界检查：assembler 不是完整 GNU assembler，不生成 ELF、重定位或链接产物。

### 阶段性 Git 提交

`Assemble base and quantum instructions to machine code`

---

## 执行块 3：实现统一 fetch 与 decode

### 执行步骤

1. fetch 用字节 PC 从 instruction memory 读取 32 位 word，检查对齐和范围。
2. decoder 先按低 7 位 opcode 分类，再按 `funct3/funct7/gate_id/op/mode` 解码；基础与量子指令走同一入口。
3. 按 RV32I 布局重组 I/B/U/J 立即数并正确符号扩展；R 型用 `funct7` 区分 `add/sub`。
4. QGATE decoder 根据 gate ID 校验元数和 `aux` 角色；QCTRL decoder 校验所有未使用字段为零。
5. decoder 返回不可变或受控的结构化指令；executor 不再解析寄存器字符串、标签或原始汇编行。
6. 对非法 opcode、非法 funct 组合、保留字段和截断 word fail closed。

### 新增测试条件

- 所有基础和量子黄金 word 可恢复正确类型、操作数和立即数；
- 正负分支偏移、J 型拆分立即数和 U/I 组合；
- 12 门逐一恢复正确量子位及参数寄存器；
- 单 bit 翻转导致字段变化或明确拒绝；
- 非法 word 不会退回 mnemonic 或默认指令路径。

### 回归测试

- 对所有 assembler 黄金向量执行 encode → decode 比较。
- 另用手写 word 测 decoder，避免测试只证明 encoder/decoder 犯同一种错误。
- 运行完整 `unittest` 和 L3 回归。

### 完成检查

- 目标检查：基础与 custom 指令统一从机器码解码为结构化指令。
- 独立性检查：存在不依赖 assembler 的 decoder 黄金测试。
- 旁路检查：decoder/executor API 不接受字符串 mnemonic。

### 阶段性 Git 提交

`Decode LoomQ RISC-V instruction words`

---

## 执行块 4：实现基础机器指令 executor

### 执行步骤

1. 扩展或 fork `riscv_emulator.py`，保留原版 `TinyRISCVEmulator` 供 L3 使用，并为 Bonus 提供独立机器码执行类或入口。
2. 实现统一循环：fetch word → decode → execute → 更新 PC；最大步数保护继续生效。
3. 实现 `add/sub/addi/lui/beq/bne/jal` 的 RV32 行为、`x0` 保护、模 `2^32` 回绕和 PC 相对控制流。
4. executor 只按 decoded instruction 类型分派，禁止查看汇编源、标签、mnemonic 或 assembler 内部对象。
5. 明确异常携带 PC、word 和错误类型，但不把源码文本作为执行依据。

### 新增测试条件

- 原模拟器示例的等价机器码程序终态；
- 算术回绕、负立即数、`x0` 写保护；
- taken/not-taken 的 `beq/bne` 和前后向跳转；
- 最大步数、未对齐 PC、越界 fetch 和非法 word；
- monkeypatch/构造测试证明执行路径调用 decoder 且不接收 mnemonic。

### 回归测试

- 运行基础机器码 executor 全部测试。
- 对 assembler 产生的混合前置经典代码进行端到端执行。
- 运行原版 L3 evaluator，确认文本模拟器行为未改变。

### 完成检查

- 目标检查：基础程序只靠 32 位 word 可正确完成控制流。
- 隔离检查：Bonus 的 RV32 回绕语义没有渗入 L3 的文本整数语义。
- 边界检查：没有 load/store、系统调用、CSR、流水线或 OS 支持。

### 阶段性 Git 提交

`Execute the minimal machine-coded RISC-V subset`

---

## 执行块 5：接入 pending circuit 与现有量子后端

### 执行步骤

1. 为 Bonus executor 增加明确的量子状态：pending gates、pending measurements、last result 和 backend adapter；程序开始时均为空。
2. QGATE 只把解码后的逻辑门追加到 pending circuit，不逐门调用后端；保持门顺序和量子位顺序。
3. `qmeasure` 只记录量子位到 slot 的映射；拒绝重复 slot、越界量子位及提交后的非法追加状态。
4. `qsubmit` 将完整 pending circuit 一次性交给项目已有本地模拟器后端，保存单次结果并结束该 pending circuit；不调用远端真机，不跨提交保存量子态。
5. `qread` 只能读取最近一次成功提交的 slot，并把 0/1 写回经典 `rd`；提交前读取、未知 slot 或后端失败必须报错。
6. `qreset` 明确丢弃 pending、measurement 和 last result，使下一电路从干净状态开始。
7. 用窄 backend protocol 和 fake/spy backend 测试门序列；生产 adapter 复用已有模拟器能力，不复制量子模拟算法。

### 新增测试条件

- 12 门均以正确参数和量子位顺序进入 pending circuit；
- 参数寄存器 Q16.16 解码为预期弧度；
- 门入队时 backend 未被调用，只有 `qsubmit` 调用一次；
- `qmeasure → qsubmit → qread` 将 0/1 写回寄存器；
- 多 slot、重复 slot、空提交、提交前读取、二次提交和 `qreset` 生命周期；
- 后端异常不产生伪造结果，也不留下可被误读的半完成状态。

### 回归测试

- 用 spy backend 验证精确门序列和调用次数。
- 用现有本地量子模拟器运行确定性 `x`、Bell 和多测量位电路。
- 运行基础机器码、L3、L1 和完整 `unittest` 回归。

### 完成检查

- 目标检查：解码后的门构成一个 pending circuit，显式提交后由现有模拟器一次执行。
- 结果检查：读取指令可把真实模拟结果写回经典寄存器。
- 边界检查：没有逐门远程调用、真机账号依赖或跨请求量子态假设。

### 阶段性 Git 提交

`Execute quantum custom instructions on the local backend`

---

## 执行块 6：建立混合程序端到端闭环测试

### 执行步骤

1. 编写至少一个完整程序：`qreset → x/h/cx 等量子操作 → qmeasure → qsubmit → qread → beq/bne → 经典赋值`。
2. 对该程序逐层断言：
   - assembler 输出的每个 word 与规格一致；
   - instruction memory 只含 32 位整数；
   - decoder 恢复正确指令类型和操作数；
   - spy backend 收到正确门序列和测量布局；
   - 结果写回指定寄存器；
   - 后续经典分支依据该寄存器选择正确路径。
3. 完整案例优先使用确定性量子结果，避免随机采样造成脆弱测试；另设统计或可注入 RNG 的测试覆盖非确定性后端适配。
4. 增加一个含基础算术、前后跳转、参数门和多量子位的混合程序，防止闭环只对单一演示成立。
5. 测试不得调用 assembler 后直接把源 mnemonic 传给 executor；可在执行前丢弃源文本以验证机器码自足性。
6. 输出失败诊断时记录 PC、word、decoded instruction、经典寄存器和量子生命周期状态。

### 新增测试条件

- 必选“量子操作 → 测量 → 经典条件分支”案例；
- taken 与 not-taken 两条分支均有确定性案例；
- word 黄金值、decoder 字段、backend 门序列和最终寄存器四层断言；
- 伪指令展开后标签仍正确；
- 非法量子指令 word 在调用 backend 前被拒绝。

### 回归测试

- 单命令运行 Bonus 编码、assembler、decoder、executor、backend 和端到端测试。
- 运行 `python -m unittest discover -s tests -v`、L3 官方模拟器测试及 L1 回归。
- 在 Docker 干净环境运行同一闭环，确保无云凭证和网络也能通过。

### 完成检查

- 目标检查：测试从汇编文本开始，只通过机器码 fetch/decode 到达经典和量子执行结果。
- 证据检查：规格文档、模拟器扩展和可运行端到端测试三者齐备。
- 旁路检查：不存在按原始 mnemonic 直接执行量子门的隐藏路径。

### 阶段性 Git 提交

`Verify the quantum ISA end to end`

---

## 执行块 7：文档对账与 Bonus 发布验收

### 执行步骤

1. 逐字段对账 ISA 规格、编码常量、assembler、decoder、executor 和测试向量；任何不一致都按阻断缺陷处理。
2. README 只声明最小闭环、12 门、四条量子控制指令、基础子集和本地后端，不使用“完整协处理器”“完整 RISC-V”或“真机逐门控制”等表述。
3. 在 Bonus 证据区引用：
   - ISA 规格文档；
   - fork/扩展模拟器入口；
   - 端到端测试路径和一条可复制命令；
   - 实际测试摘要。
4. 从干净 Docker 构建运行完整测试，并执行 `prepare_submission.py`。
5. 审查 diff、未跟踪文件、生成二进制/报告、缓存和敏感信息；只归档源码、测试与必要文档。

### 发布前缺陷处理规则

- 位布局或门 ID 修改：先升级规格/版本，再更新全部黄金 word、assembler、decoder 和 executor 测试。
- 基础指令修复：重跑所有控制流与混合端到端程序。
- 量子生命周期修复：重跑 12 门、错误路径、reset 和多电路测试。
- 后端 adapter 修复：重跑 spy backend 与真实本地模拟器测试。
- 每个缺陷必须先有最小失败复现，不做无测试的发布前补丁。

### 完成检查

- 目标检查：编码规格、扩展实现和端到端测试均可在干净环境复现。
- L3 隔离检查：原版 `TinyRISCVEmulator` 仍通过官方文本汇编测试。
- 声明检查：Bonus 被准确描述为最小 ISA 编码—解码—执行闭环。

### 阶段性 Git 提交

`Finalize the LoomQ quantum ISA bonus`

## Git 提交通用门禁

任何阶段性提交都必须满足：

- 暂存区只包含当前执行块的改动；
- ISA 文档和实现不存在未解释差异；
- 定向测试、完整回归及 L3 隔离测试全部通过；
- executor 只接收 instruction word 或 decoded instruction；
- 不含云凭证、远端任务、缓存、生成报告或临时二进制；
- 不把最小演示宣传为完整 RISC-V、量子协处理器、QEMU 或真实硬件控制能力。
