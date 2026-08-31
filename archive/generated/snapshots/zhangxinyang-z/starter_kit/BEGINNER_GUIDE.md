# LoomQ 零基础首次运行指南

LoomQ 面向没有量子计算背景、希望通过自然语言生成或理解量子电路的学习者。

## 30 秒首次运行

在仓库根目录设置组委会或自己的 OpenAI-compatible 模型配置：

```bash
export LOOMQ_LLM_BASE_URL="https://你的模型服务地址"
export LOOMQ_LLM_API_KEY="你的密钥"
export LOOMQ_LLM_MODEL="你的模型名"
```

然后运行：

```bash
python -m starter_kit.chat "生成一个 3 比特 GHZ 态并进行全测量"
```

CLI 会展示解释、完整 QASM，以及本地理想测量结果柱状图。柱状图是帮助理解的本地模拟预览，不代表真机运行结果。

## 三个可直接使用的问题

```text
生成一个 3 比特 GHZ 态并进行全测量
修复这个贝尔态代码：H q[0]; CX q[0] q[1]
我需要运行一个 15 比特电路且零排队等待，推荐哪个后端？
```

## 三个概念

- **Qubit（量子比特）**：量子程序处理的信息单位。
- **Bell/GHZ 态**：多个量子比特形成关联结果的常用演示电路；测量后会出现少数几个主导结果。
- **测量**：把量子状态转换成普通的 0/1 结果。CLI 的柱状图用每个结果的概率帮助理解测量。

更多门和 OpenQASM 基础见 `starter_kit/QUANTUM_101.md`。

## 常见问题与恢复

| 看到的问题 | 怎么处理 |
|---|---|
| 缺少 `LOOMQ_LLM_*` 环境变量 | 按“30 秒首次运行”配置三个变量后重试。不要把密钥写入代码或提交到 Git。 |
| 模型服务不可访问或 HTTP 错误 | 检查网络、接口地址、模型名和账号额度后重试。 |
| 回复没有 QASM 或本地预览失败 | 让 Agent“只返回完整 OpenQASM 2.0 程序”，或说明你希望生成的目标态。 |
| 不知道怎样提问 | 从上面的三个示例复制一个，再根据自己的比特数或目标修改。 |

## 提交前自检

```bash
python -m starter_kit.evaluator --level all --target spinq,originq,braket
```
