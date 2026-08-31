# LoomQ 2026 开发约束

## 项目目标

- 本仓库是 LoomQ 2026 比赛提交仓库。
- 当前优先完成 L1 并取得参赛资格；L2 在 L1 稳定后再开展，L3 当前不在计划范围内。
- 最终评测根目录为 `starter-kit/`。

## 官方文件保护

未经用户明确要求，不得修改：

- `starter-kit/evaluator.py`
- `starter-kit/target_ir_contract.md`
- `starter-kit/circuits/`
- 官方评分规则和提交契约

不得通过修改 evaluator 或测试数据使测试通过。

## L1 架构原则

固定架构：

```text
OpenQASM 2.0
→ Parser
→ 平台无关 Circuit IR
→ Serializer / Backend Adapter
→ Runner
→ 统一结果 Schema
```

- Parser 只负责语法解析和语义校验。
- IR 不包含具体量子平台专属字段。
- Serializer 只负责将 IR 转为目标格式。
- Runner 只负责调用后端和统一执行结果。
- `adapter.py` 只作为官方入口和路由层。
- 不得为 Bell、GHZ 或公开测试用例硬编码转换结果，不得返回 mock counts。
- 不得让不同平台各自重复解析 OpenQASM。

## 技术约束

- 官方运行基准为 Python 3.10；`starter-kit/Dockerfile` 是最终环境基准。
- 优先使用 Python 标准库；新增第三方依赖必须确有必要、写入 `requirements.txt`，并使用精确版本号。
- 使用类型标注；IR 优先使用 `dataclass`；使用自定义异常表达解析和转换错误。
- 测试使用标准库 `unittest`。
- 所有后端结果统一为官方 Schema，counts 位序固定为 `little`。

## 开发规则

每次任务都应：

1. 阅读相关官方文件和项目文档。
2. 检查当前实现，避免重复造轮子。
3. 控制任务范围，不主动扩展至下一阶段。
4. 使用 `apply_patch` 修改文件。
5. 修改后运行相关单元测试。
6. 汇报修改文件、实现内容、测试结果、已知限制和下一步建议。
7. 代码实现需要使用中文补充简单注释

除非用户明确要求，否则不得 commit、push、创建 PR、修改比赛范围、同时实现 L1/L2/L3，或用临时代码和硬编码伪造测试通过。

## 文档优先级

发生冲突时，按以下顺序执行：

1. 官方赛题和提交契约
2. `starter-kit/target_ir_contract.md`
3. `starter-kit/README.md`
4. 根目录 `AGENTS.md`
5. `starter-kit/docs/l1-spec.md`
6. 当前任务提示词
