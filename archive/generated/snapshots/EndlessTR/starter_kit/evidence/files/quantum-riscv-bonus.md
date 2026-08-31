# 量子 RISC-V Bonus：从混合源码到可验证指令流

## 1. 先划清边界

本项目的基础 L3 与 Bonus 共用解析器和经典代码生成器，但输出合同不同。

| 路径 | 入口 | 输出 | 用途 |
|---|---|---|---|
| 基础 L3 | `adapter.compile_hybrid()` | 原序量子操作列表 + 官方轻量模拟器可执行的经典 RISC-V 汇编 | 满足基础 L3 评测合同 |
| RISC-V Bonus | `adapter.compile_hybrid_bonus()` | 原序量子操作列表 + `qinst` 量子指令载体和经典 RISC-V 汇编 | 验证自定义指令的编码、解码与混合控制 |

基础路径不输出 `qinst`，也不要求基础评测器理解自定义 opcode。Bonus 是独立入口，没有改变 `compile_hybrid()` 的行为。`test_base_l3_output_remains_officially_compatible` 对这条边界做了直接断言。

还需明确：当前 `TinyRISCVEmulator` 是轻量指令级模拟器。它执行经典寄存器与控制流语义，并解码、校验、记录量子操作；它**不模拟量子态演化，也不生成测量概率**。记录结果可作为后续量子后端的已验证指令流，而不是量子计算结果。

## 2. 编译流水线

```text
Hybrid-QASM 源码
  -> 输入大小检查、注释清理
  -> 分离量子区与 classical { ... } 块
  -> 量子声明/操作校验 + 经典词法分析
  -> 递归下降解析经典表达式、赋值和 if/else，形成 HybridProgram
  -> 基础 L3：保留量子操作文本 + 生成经典汇编
  -> Bonus：编码量子操作为 qinst + 生成同一份经典汇编
  -> 估算量子指令数与经典最坏路径步数
  -> 输出混合指令流
```

`HybridProgram` 是两条路径的共同中间表示：保存量子操作顺序、经典 AST、经典寄存器规模和量子寄存器规模。因此 Bonus 没有另写一套经典语义。

经典映射保持简单且可检查：混合变量 `r1..r9` 对应 `x1..x9`，测量输入 `c[k]` 对应 `x10+k`；量子指令不写通用寄存器。经典端只使用模拟器既有的 `li`、`add`、`sub`、`addi`、`beq`、`bne` 和 `j` 子集。

## 3. custom-0 编码

扩展规范见 `starter_kit/quantum_riscv_extension.md`。每个量子操作至少占一个 32 位逻辑指令字：

| 位段 | 字段 | 约束 |
|---:|---|---|
| `6:0` | `opcode` | 固定为 RISC-V `custom-0`：`0x0B` |
| `11:7` | `q0` | 第一量子位；测量时为源量子位 |
| `16:12` | `q1` | 第二量子位；测量时为目标 `c[k]` |
| `21:17` | `q2` | 第三量子位 |
| `26:22` | `gate_id` | `1..13`，对应 12 种门及 `measure` |
| `27` | `has_param` | 是否紧随一个 binary32 参数字 |
| `31:28` | `version` | v1 固定为 `1` |

选用 `custom-0` 避免占用标准基础指令编码空间。单、双、三量子位操作统一落入 `q0/q1/q2`；未使用字段必须为零，多量子位门的操作数不得重复。量子位与测量位使用 5 位无符号字段，范围为 `0..31`。

v1 支持 `h`、`x`、`s`、`sdg`、`t`、`tdg`、`rz`、`ry`、`cx`、`swap`、`ccx`、`cu1` 和 `measure`。其中 `rz`、`ry`、`cu1` 带一个 IEEE-754 binary32 参数载荷。编译器只接受由数值、`pi`、括号、一元正负号及 `+ - * / **` 构成的有限表达式，并限制 AST 深度和指数大小；结果经 binary32 舍入，NaN、无穷和溢出均被拒绝。

文本汇编使用轻量载体：

```asm
qinst 0x1040000b
qinst 0x19c0000b, 0x3fc90fdb
```

第一项是指令字；第二项只在 `has_param=1` 时存在。若输出为二进制 RISC-V 指令流，规范要求按通常的小端字节序列化逻辑字。当前模拟器消费的是上述文本载体。

## 4. 验证、拒绝与状态安全

安全属性来自两层校验。

编译期由 `QuantumInstructionEncoder` 检查寄存器形态、门白名单、门元数、参数存在性、量子位范围、重复操作数、测量映射和整寄存器测量尺寸。扩展 v1 限定恰有一个名为 `q` 的量子寄存器，规模不超过 32；整寄存器 `measure q -> c` 按索引升序展开，且要求 `q`、`c` 等长。

执行期由 `TinyRISCVEmulator.decode_quantum_instruction()` 再次检查：

- 指令字和参数字均为 32 位无符号整数；
- opcode 为 `0x0B`，版本为 `1`，`gate_id` 已定义；
- `has_param`、载荷数量与门签名一致；
- 未使用字段为零，多量子位门操作数不重复；
- 参数可解码为有限 binary32 数。

单条 `qinst` 采用“先完整解码，后追加记录”的提交顺序。任何校验失败都发生在 `quantum_operations.append(decoded)` 之前，因此该条非法指令不会留下半条记录。这是**单指令原子拒绝**，不是整段程序回滚：若程序先执行了合法量子指令，之后才遇到非法指令，先前合法记录仍然存在。

资源约束同样前置。Bonus 编译器把量子指令数与经典 AST 的最坏路径步数相加，超过模拟器 1000 步上限即拒绝；执行器本身也保留 1000 步保护。`load_program()` 会重置寄存器、程序计数器、标签和量子操作记录；`get_quantum_operations()` 返回深拷贝，调用方不能借修改快照篡改内部状态。

## 5. 模拟器语义

`qinst` 的执行语义是：解码 -> 校验 -> 追加结构化操作 -> `pc + 1`。结构化记录包含原始指令字、门名、量子位；测量另含经典位；参数门另含参数字和 binary32 数值。

量子指令不改变 `x0..x31`。经典条件读取由调用方写入 `x10+k` 的测量位，随后按普通分支语义运行。测试因此可以独立验证两件事：量子指令流被正确恢复；给定测量输入后，经典控制得到确定的寄存器结果。它没有把“记录门”包装成“已模拟量子物理”。

## 6. 可复现证据

规格、实现、测试三者分别位于：

- 编码规范：`starter_kit/quantum_riscv_extension.md`
- 编译实现：`starter_kit/adapter.py` 中的 `QuantumInstructionEncoder`、`HybridCompiler.compile_bonus()` 与 `compile_hybrid_bonus()`
- 解码实现：`starter_kit/riscv_emulator.py` 中的 `decode_quantum_instruction()` 和 `qinst` 执行分支
- 端到端测试：`starter_kit/test_l3_bonus.py`

在仓库根目录执行：

```powershell
python -m unittest starter_kit.test_l3_bonus -v
Push-Location starter_kit
try { python evaluator.py --level l3 } finally { Pop-Location }
```

Bonus 测试覆盖：

- 12 种门与测量的编码/解码往返，含 binary32 参数；
- `measure q -> c` 的逐位展开；
- 三个测量位的全部 8 种输入组合；
- 50 组固定种子经典程序及每组 8 种测量输入；
- 非法量子源码、opcode、版本、门编号、参数标志、载荷数量、保留字段、重复量子位、NaN 参数和越界字；
- 单条非法指令不产生量子操作记录；
- 最大量子位索引 31、状态重置、防御性快照和 1000 步边界；
- 基础 `compile_hybrid()` 不含 `qinst`，Bonus 输出包含 `qinst`。

基础 L3 evaluator 用于确认原合同仍成立；Bonus 测试用于证明扩展链路。评审时应同时核对规范、编译器生成、模拟器解码和端到端断言，不能仅以汇编文本中出现 `qinst` 作为实现成立的依据。
