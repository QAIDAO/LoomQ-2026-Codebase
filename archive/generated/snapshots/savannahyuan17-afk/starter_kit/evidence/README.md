# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [ ] L1 真机
- [ ] L2 交互体验
- [x] 工程与产品化
- [ ] 自定义量子 RISC-V Bonus
- [ ] 新手引导与视觉叙事 Bonus

---

## L1 真机

未申报。

---

## L2 交互体验

未申报。

---

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。

```text
干净环境中的构建和启动命令：
  # 0 依赖安装 — 核心模块只使用 Python 标准库
  # Python 3.10+ 即可运行
  cd starter_kit
  python -m starter_kit.evaluator --level declared --target spinq,braket,originq

架构说明：
  starter_kit/ARCHITECTURE.md
  （包含完整模块图、数据流、6 个核心模块的职责与设计理由、5 个关键设计决策）

目标用户和使用场景：
  本项目的目标用户是零量子计算背景的开发者。
  使用场景：
  1. 在 OpenQASM 2.0 电路上做跨平台编译（SpinQ / Braket / OriginQ）
  2. 用自然语言描述量子电路意图 → 自动生成可执行 QASM
  3. 调试有错误的 QASM 代码 → 自动修复
  4. 根据电路特征（qubit 数 / 门数）推荐最优执行后端

完整使用流程：
  1. 克隆仓库：git clone <repo>
  2. 无需安装：cd starter_kit
  3. 运行全量自测：python -m starter_kit.evaluator --level declared --target spinq,braket,originq
  4. 预期输出：8/8 PASS (L1 6个 + L2 1个 + L3 1个公开用例)
  5. 详见 starter_kit/ARCHITECTURE.md 中各模块的独立测试命令
```

工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

---

## 自定义量子 RISC-V Bonus

未申报。

---

## 新手引导与视觉叙事 Bonus

未申报。

---

## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
