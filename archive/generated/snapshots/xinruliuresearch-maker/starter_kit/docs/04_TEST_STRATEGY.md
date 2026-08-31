# 04 · 测试策略与当前结果

## 1. 证据规则

任何结果都必须写清 Python 版本、命令/入口、seed 或测试规模以及证据边界。必须区分：

- syntax 与功能；
- 公开自测与隐藏/正式评分；
- 本地 HTTP stub 与正式 DeepSeek；
- 参考模拟器、hardware dry-run 与真实 QPU；
- 静态 Dockerfile 审阅与实际冷构建。

## 2. 历史基线

修改前在 Python 3.10.11 的结果：默认 evaluator 0/4、三目标 L1 0/6、L3 0/1，L2 因缺少外部模型配置未取得结果，`compileall` 通过。`baseline-report.json` 保存默认 0/4，只是历史基线，不代表当前状态。

## 3. 当前已执行结果

验证解释器：Python 3.10.11 正式解释器。

| 检查 | 当前结果 | 证据/说明 |
|---|---:|---|
| Python 源文件 syntax | 78/78 | 逐文件编译检查；不单独代表功能 |
| `unittest` 全量 | 119/119 | 所有 `tests/test_*.py` |
| 公开 L1 三 target | 6/6 | `evidence/files/l1-public-report.json` |
| QASM 随机 round-trip | 100 seeds × 3 | 三目标独立回读与语义比较 |
| 公开 L2 | 1/1 | `evidence/files/l2-public-report.json`；本地真实 HTTP stub |
| 公开 L3 | 1/1 | `evidence/files/l3-public-report.json` |
| Hybrid 随机差分 | 500 programs × 8 assignments | 参考 AST 解释器与编译路径终态一致 |
| UI tests | 9/9 | workspace、原子 manifest、真实 loopback HTTP、可视化、本地指南与错误/安全路径 |
| 浏览器 QA | desktop + 390px，0 console errors | `evidence/files/ui/browser-qa.json`、3 张截图 |
| 量子 RISC-V | 17/17 | 编解码、模拟器、随机差分、demo |
| Hardware preparation | 23/23 | dry-run 与证据契约；未联网、未生成 job |

所有 `evidence/files/l*-public-report.json` 都带有“Public self-check only”声明。本表不声称隐藏用例或正式得分通过。

## 4. 分层覆盖

### 4.1 L1

- lexer/parser：注释、空白、单行/多行、多寄存器、广播、测量映射、非法字符与位置；
- expression：`pi`、科学计数法、括号、正负号、四则运算、除零和非有限值拒绝；
- semantic：12 门 arity/参数、寄存器类型、索引、测量宽度、重复声明；
- serializer：AST round-trip、稳定格式、精度与负角；
- target：SpinQ QASM 2、OriginIR、Braket QASM 3 的独立子集解析与规范语义比较；
- runtime：12 门矩阵、测量、little-endian、固定宽度 key、shots 守恒、schema 与 mock 拒绝；
- property：100 个固定 seed 结构化随机电路，每个电路检查 3 target。

### 4.2 L2

- 生成：Bell、GHZ-n、均匀叠加、纠缠链、计算基态与中英文变体；
- 修复：fence、缺声明/标点、有效但语义错误候选、目标优先；
- 推荐：比特数、真机/模拟器、费用、队列、账号组合；
- 协议：本地 socket 实际接收 OpenAI-compatible 请求；模型名、temperature、stream、thinking 和 timeout 合同；
- 失败：缺环境、畸形/空 JSON、429、超时、最多两次调用、secret 不泄露、prompt injection。

本地 stub 只替代模型服务响应，不替代 QASM parser/runtime，也不作为正式 DeepSeek 或私有准确率证据。

### 4.3 L3

- tokens/AST/parser：赋值、左结合 `+/-`、`==/!=`、嵌套 `if/else`、负常数和错误位置；
- allocator/compiler：固定寄存器映射、临时寄存器避让、唯一 label、官方 allowlist 指令；
- semantics：量子序列顺序、经典块前后操作、官方 TinyRISCV 终态；
- differential：500 个随机程序，对每个程序穷举 8 种测量赋值，100% 比较解释器与编译路径。

### 4.4 UI、Bonus 与硬件准备

- UI：静态资源/CSP、loopback 绑定、真实 HTTP、三方言 artifact、counts、错误定位、repair、Hybrid、路径穿越、secret redaction、原子 manifest；
- 浏览器：1440×900 真实运行、390×844 响应式布局、console error 与横向溢出检查；
- Bonus：固定机器码、编码/解码/反汇编、随机字段和量子电路差分、经典兼容、Bell/Toffoli、错误边界；
- Hardware：dry-run 不读凭证/不联网/不写证据，record 前置检查，响应 schema、QPU 标识、job/time/counts、secret redaction、全有或全无原子证据。

Hardware 23/23 只证明准备层安全，不证明厂商 SDK 可安装、账号可用或 QPU 已执行。

## 5. 推荐复跑命令

在 `starter_kit/` 用 Python 3.10：

```bash
python scripts/run_all_checks.py
python -m unittest discover -s tests -p "test_*.py" -v
python evaluator.py --level l1 --target spinq,originq,braket --json-out evidence/files/l1-public-report.json
python scripts/run_l2_stub_evaluator.py
python evaluator.py --level l3 --json-out evidence/files/l3-public-report.json
python scripts/run_random_differential_tests.py
python -m loomq.bonus.demo
```

UI：

```bash
python -m loomq.ui.server
```

访问 `http://127.0.0.1:8765`。浏览器证据位于 `evidence/files/ui/`。

硬件 dry-run 复现见 `docs/hardware/README.md`。不要在没有真实账号/QPU 权限时使用 `--record`，不要把测试值或占位 ID 写入 Evidence。

## 6. 尚未完成与外部验证

- 正式组委会 `deepseek-v4-flash` 环境和私有 L2 cases；
- 隐藏 L1/L3 evaluator 与官方人工评分；
- SpinQ/OriginQ 真实 QPU job 和厂商原始结果；
- Python 3.10 Linux / Docker `--no-cache` 构建与默认 CMD；
- Final Submission Issue 将引用的最终 HEAD 对应的官方 `prepare_submission.py` 核对；预检已在一个已 push 的干净 HEAD 上完整通过，任何新 commit 必须重跑；
- Final Submission Issue、`submission:accepted` 标签、归档 SHA-256 与 Artifact ID 回执。

当前主机没有可用 Docker 可执行文件，因此 Dockerfile 只能做静态审查，不能写“已验证”。

## 7. 当前发布余项

标准 clone 迁移、119/119、UI/browser smoke、secret/tracked-file 审计以及 `main` commit/push 已完成，远端页面已核验。剩余顺序是：

1. 对 Final Submission Issue 将引用的最终 HEAD 重跑 `python starter_kit/prepare_submission.py --team-id xinruliuresearch-maker` 并确认通过；
2. 创建 Final Submission Issue；
3. 核对 `submission:accepted`、归档 SHA-256 与 Artifact ID 回执；
4. 若有 Docker 环境，补做冷构建与容器默认命令验证。

Issue 获得 `submission:accepted` 回执前，状态仍为“未完成赛事提交”。
