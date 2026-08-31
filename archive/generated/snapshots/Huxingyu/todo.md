# LoomQ 100+ 分冲刺清单

截止时间：2026-08-25 12:00（UTC+8）。目标不是堆功能，而是让每一项都能被自动评测或人工证据复核。

## 得分路线

| 模块 | 目标 | 100+ 路线中的作用 |
|---|---:|---|
| L1 通用中间层 | 35/35 | 必须拿满 |
| L1 真机 | 10/10 | 两个平台各 5 分 |
| L2 Agent | 30/30 | 客观 20 分 + 交互 10 分 |
| L3 Hybrid-QASM | 15/15 | 确定性自动评分，必须拿满 |
| 工程与产品化 | 10/10 | 一键运行、架构和目标用户叙事 |
| Bonus | 4-12/12 | 新手引导优先，自定义量子指令视进度完成 |

目标组合：基础 100 + 新手引导 4 = 104。若真机受阻，则必须完成全部 Bonus，理论上限为 102。

## P0：保住有效参赛资格和 L1（8 月 22 日）

- [x] 实现统一 OpenQASM AST、状态向量模拟器、`transpile()` 和 `run()`
- [x] 输出 SpinQ OpenQASM 2、OriginIR、Braket OpenQASM 3
- [x] 公开 Bell/GHZ-3 在三个 target 上通过
- [x] GHZ-5、QFT-4、Grover-3 和 12 门基础回归通过
- [x] 修复所有目标 IR 与 `target_ir_contract.md` 的拼写和语法偏差
- [x] 独立解析三种 `transpile()` 产物并与输入 AST 逐操作比较
- [x] 增加非对称位序、多寄存器、部分测量、重复测量和参数边界测试
- [x] 增加固定种子的随机白名单电路差分测试
- [ ] 在 Python 3.10 干净环境或 Docker 中运行全部测试
- [ ] 创建一次保底最终提交 Issue，并确认获得 `submission:accepted`

验收命令：

```bash
python3 -m unittest discover -s tests -v
cd starter_kit && python3 evaluator.py --level l1 --target spinq,originq,braket
python3 starter_kit/prepare_submission.py --team-id Huxingyu
```

## P0-External：真机证据（立即并行，不阻塞代码）

- [x] 确认 SpinQ Cloud 账号、额度和真机入口可用
- [x] 确认本源量子云账号、API Token、额度和悟空真机入口可用
- [x] 在第一个平台运行 Bell，保存实际 QASM、原始结果、job ID、shots 和时间
- [x] 在第二个平台运行 Bell，保存同样材料
- [x] 将证据放入 `starter_kit/evidence/files/`，不得提交 Token 或 Cookie
- [x] 在 `starter_kit/evidence/README.md` 勾选并填写 L1 真机申报

验收标准：两个 job ID 均可在平台控制台追溯，时间位于赛程内，主导态为 `00`/`11`。

## P1：L3 Hybrid-QASM 满分（8 月 22-23 日）

- [x] 实现 classical 块提取和 tokenizer
- [x] 实现赋值、`+`、`-`、`==`、`!=`、顺序语句和嵌套 `if/else` AST
- [x] 实现 `r1..r9 -> x1..x9`、`c[k] -> x10+k`
- [x] 生成仅含 `li/add/sub/addi/beq/bne/j` 的 RISC-V 汇编
- [x] 确保临时寄存器不覆盖用户寄存器或测量寄存器
- [x] 保序返回量子操作列表
- [x] 用参考解释器穷举所有测量组合
- [x] 增加固定种子的随机经典程序差分测试
- [x] 将 `submission.yaml` 的 `levels.l3` 改为 `true`

验收命令：

```bash
cd starter_kit && python3 evaluator.py --level l3
python3 -m unittest tests.test_l3_compiler -v
```

## P1：L2 客观 20 分（8 月 23 日）

- [x] 从 `LOOMQ_LLM_*` 读取配置并至少完成一次有效模型调用
- [x] 将生成、纠错、后端推荐三类任务写入严格系统提示词
- [x] 生成和纠错结果必须包含可提取的 OpenQASM 2.0
- [x] 用 `parse_qasm()` 校验模型产物，失败时把错误回传并重试
- [x] 对 Bell/GHZ 等明确目标做本地语义自验
- [x] 加载 `backend_capabilities.json`，回复规范 backend ID
- [x] 控制调用次数与总耗时，120 秒内返回当前最优结果
- [x] 使用本地 OpenAI-compatible 假服务覆盖成功、重试、缺环境变量和错误响应
- [x] 使用自备模型服务跑公开 L2 case 和改写 prompt 集
- [x] 将 `submission.yaml` 的 `levels.l2`、`required_for_l2` 改为 `true`

验收命令：

```bash
cd starter_kit && python3 evaluator.py --level l2
python3 -m unittest tests.test_l2_agent -v
```

## P2：L2 交互体验 + 工程产品化（8 月 23-24 日）

- [x] 提供零依赖 CLI，支持自然语言输入、生成/修复/推荐和友好错误提示
- [x] 展示 QASM、执行 counts、概率和 ASCII 可视化
- [x] 准备 3 个零基础现场任务
- [x] 提供一条 setup + run 命令
- [x] 写清架构、模块边界、失败恢复和离线/联网要求
- [x] 回答目标用户：无量子背景开发者如何在 5 分钟内完成第一次量子运行
- [x] 在证据 README 中申报 L2 交互、工程产品化和新手引导

验收标准：干净 Python 3.10 环境按 README 一条命令启动，新用户不读源码也能完成 3 个任务。

## P2：Bonus（8 月 24 日，核心分通过后再做）

### 新手引导与视觉叙事 +4

- [x] 零基础首次运行向导
- [x] Bell/GHZ、shots、counts 的人话解释
- [x] 概率分布可视化
- [x] API、QASM、后端不适配时的恢复建议

### 自定义量子 RISC-V +8

- [x] 设计 custom-0 opcode、funct3、寄存器/量子位字段编码
- [x] 编写指令编码规格文档
- [x] 扩展 `riscv_emulator.py` 支持量子门和测量指令
- [x] 提交 Bell -> 测量 -> 经典分支的端到端测试
- [x] 在证据 README 中填写规格、实现和测试路径

## P0：最终提交（最晚 8 月 25 日 09:00）

- [x] 删除正式评测根目录中的会话记录、临时报告和无关文件
- [x] 检查仓库中没有 API Key、Token、Cookie 或个人数据
- [ ] 运行编译、单测、三个 Level evaluator 和 Docker 构建
- [x] 确认 `submission.yaml` 与真实交付一致
- [x] 填完所有申报项的 `evidence/README.md`
- [ ] 提交并 push，工作区保持干净
- [ ] 运行 `prepare_submission.py` 保存 40 位 SHA
- [ ] 新建最终提交 Issue，不编辑旧 Issue
- [ ] 确认 `submission:accepted`、归档 SHA-256 和 Artifact ID 回执
- [ ] 下载或截图保存最终回执

## 每次提交前的回归门禁

```bash
python3 -m py_compile competition/*.py starter_kit/*.py tests/*.py
python3 -m unittest discover -s tests -v
(cd starter_kit && python3 evaluator.py --level l1 --target spinq,originq,braket)
git status --short
```
