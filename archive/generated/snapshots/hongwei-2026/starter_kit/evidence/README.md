# LoomQ 人工评分证据

证据包是可选的。未申报项留空即可，不影响自动评分。

## 提交前填写

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。

```text
平台名称：SpinQ Cloud（gemini_vp）
平台 job ID：G-260820-0003
运行时间：2026-08-20T03:35:32Z
shots：1024
实际执行的 QASM：starter_kit/evidence/files/spinq-circuit.qasm
平台返回的原始结果：starter_kit/evidence/files/spinq-result.json
任务页截图：无
```

说明：本源悟空在测试时处于维护状态，故本提交仅申报量旋 1 个真机平台。`originq-cloud-sim-result.json` 为云模拟结果，不申报真机分。

## L2 交互体验

```text
启动界面或 CLI 的命令：
  set LOOMQ_LLM_BASE_URL=https://api.deepseek.com
  set LOOMQ_LLM_API_KEY=<评测注入或本地密钥>
  set LOOMQ_LLM_MODEL=deepseek-v4-flash
  python loomq_cli.py --run
  python loomq_web.py
测试入口或页面地址：http://127.0.0.1:8765（loomq_web.py）
适合现场体验的 3 个用户任务：
1. 生成一个 3 比特 GHZ 态并进行全测量
2. 我想制备贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]
3. 我需要运行一个 15 比特电路，且零排队等待，选哪个平台？
截图或演示视频：无
```

## 工程与产品化

```text
干净环境中的构建和启动命令：
  cd starter_kit
  python evaluator.py --json-out report.json
架构说明：starter_kit/PRODUCT.md
目标用户和使用场景：starter_kit/PRODUCT.md
完整使用流程：starter_kit/PRODUCT.md
```

## 自定义量子 RISC-V Bonus

```text
指令编码规格：starter_kit/QUANTUM_RISCV.md
模拟器扩展实现：starter_kit/riscv_emulator.py（TinyRISCVEmulator 的 qinit/qh/qx/qcx/qmeas 与 encode_custom）
端到端测试命令：python test_quantum_riscv.py
```

## 新手引导与视觉叙事 Bonus

```text
零基础首次运行指南：starter_kit/PRODUCT.md；starter_kit/QUANTUM_101.md
量子概念解释：starter_kit/QUANTUM_101.md
结果可视化：starter_kit/loomq_web.py 柱状图；loomq_cli.py JSON counts
错误恢复或无障碍引导：adapter.agent_chat 校验失败自动重试；loomq_cli.py 捕获异常并提示换说法
```
