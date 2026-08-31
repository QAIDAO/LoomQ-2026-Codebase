# LoomQ 验证报告（Verification Report）

> 提交前在本地（macOS arm64 / Python 3.10.21）对最终提交 commit
> `8da5882` 运行的全部自动化验证。评测环境为固定 Linux 容器，
> 依赖已按 `requirements.txt` 精确锁定。

## 环境

- Python 3.10.21（虚拟环境 `.venv/`）
- spinqit==0.2.4 · pyqpanda==3.8.5 · amazon-braket-sdk==1.99.0

## 1. L1 公开电路（契约自测）— 6/6 通过

```bash
python3 starter_kit/evaluator.py --level l1 --target spinq,originq,braket
# [PASS] l1:bell.qasm:spinq / originq / braket
# [PASS] l1:ghz3.qasm:spinq / originq / braket
# {"passed": 6, "failed": 0, "total": 6}
```

## 2. L1 隐藏电路类型预演（独立 numpy 参考模拟器交叉验证）— 24/24

```bash
python3 starter_kit/verify_hidden_circuits.py
```

| 电路 | 覆盖门 | 后端 |
|---|---|---|
| Bell / GHZ-3（公开） | h, cx | 三后端 ✓ |
| GHZ-5（隐藏集） | h, cx | 三后端 ✓ |
| QFT-4（隐藏集） | h, cu1, swap | 三后端 ✓ |
| Grover-3（隐藏集） | h, x, ccx, cx | 三后端 ✓ |
| Random-Circuit ×3（隐藏集） | 全部 12 门 | 三后端 ✓ |

全部 Hellinger 保真度 ≥ 0.97（8192 shots）。

## 3. L1 转译产物契约校验

- `spinq`：原样 OpenQASM 2.0（qelib1 头在 spinqit 包内解析）✓
- `braket`：OpenQASM 3 方言（cnot/cphaseshift/ccnot/si/ti，无 include），
  已用 braket 官方 `LocalSimulator` 直接解析并模拟通过 ✓
  （`include "stdgates.inc"` 在参考实现中无法解析，故输出采用其原生方言）
- `originq`：OriginIR 规范子集（QINIT/CREG/H/CNOT/CU1/SWAP/TOFFOLI/MEASURE），
  符合 `target_ir_contract.md` 允许门名 ✓

## 4. L3 混合编译随机模糊测试 — 700+ 用例全通过

```bash
python3 starter_kit/test_hybrid_fuzz.py --cases 200 --seed 20260825   # 200/200
python3 starter_kit/test_hybrid_fuzz.py --cases 100 --seed 1          # 100/100
python3 starter_kit/test_hybrid_fuzz.py --cases 100 --seed 42         # 100/100
python3 starter_kit/test_hybrid_fuzz.py --cases 100 --seed 999        # 100/100
python3 starter_kit/test_hybrid_fuzz.py --cases 100 --seed 2026       # 100/100
python3 starter_kit/test_hybrid_fuzz.py --cases 100 --seed 777        # 100/100
```

随机生成（不同分支结构/常量/测量位数/嵌套 if-else/负字面量/左右操作数任意组合），
在官方 `riscv_emulator.py` 上穷举注入全部测量值组合，与独立参考解释器逐组比对
寄存器终态（r1..r9 → x1..x9）100% 一致。

## 5. L2 Agent（本地 mock 端到端验证）

- 生成：`3 比特 GHZ 全测量` → 返回可运行 QASM（qreg q[3]），自验通过 ✓
- 纠错：残缺贝尔态 → 修复为正确电路并自验 ✓
- 纠错自愈：首次给出错误比特数 → 被自验拦截 → 重试后正确（验证闭环）✓
- 选后端：15 比特零排队 → 回复含 `braket_local_simulator` ✓
- 选后端：30 比特免费模拟器 → `originq_local_simulator` ✓
- 选后端：8 比特免费真机 → `spinq_cloud_qpu` ✓
- 选后端：72 比特悟空 → `originq_wukong` ✓
- 120s 时限：模型调用预算 100s，超时收缩，deadline 保护 ✓

正式评分模型为组委会注入的 `deepseek-v4-flash`（temperature=0, thinking 关闭），
`agent_chat` 每次任务至少完成一次有效模型调用。

## 6. Bonus：量子 RISC-V 扩展（LQ-Q）— 31/31

```bash
python3 starter_kit/test_quantum_riscv.py
# 覆盖：官方经典回归、编码往返、Bell、中路测量反馈、参数门、Toffoli/GHZ、测量塌缩
# 结果：31 passed, 0 failed
```

## 7. 官方测试套件

```bash
python3 -m unittest tests.test_l2_contract -v        # OK（4/4）
python3 -m unittest tests.test_submission_tools      # OK
```

## 8. 交互入口

- `python3 starter_kit/loomq_web.py` → http://127.0.0.1:8080（零依赖，实验免配置）
- `python3 starter_kit/loomq_cli.py`（引导式菜单）
- `python3 starter_kit/real_machine.py <平台> --qasm ... --config ...`（真机，需凭证）
