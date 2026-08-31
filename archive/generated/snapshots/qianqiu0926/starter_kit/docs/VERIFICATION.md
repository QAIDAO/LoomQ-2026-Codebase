# 验证报告

## 一键复现

```bash
cd starter_kit
python3 verify_submission.py
```

需要本地模型环境时额外运行：

```bash
python3 verify_submission.py --with-l2
```

## 自动化证据

| 层 | 方法 | 样本/覆盖 |
|---|---|---:|
| Parser | 无头文件、未知门、缺逗号、参数注入、重复 qubit 拒绝 | 5 类失败路径 |
| 门语义 | Bell/GHZ、位序、10 组逆门/恒等关系 | 12 门均出现 |
| 三目标转译 | 随机 3–5 qubit、8–28 门；独立回译后轨迹/全态/测量映射/分布证书 | 80 × 3 |
| 翻译对抗反例 | 插入只改相位的 S；插入相互抵消的 X;X | 2 类原有 oracle 盲区均被拒绝 |
| 证明携带执行 | 实际执行独立回读目标，result 携带证书和产物哈希 | 3 目标共用生产 pipeline |
| Schema | 8191 非偶数 shots 的严格配额与字段 | counts 总和精确 |
| Hybrid | 随机负/正常数、嵌套分支、全测量输入；20 cbit scratch 压力 | 80 × 4 = 320 终态 + 1 边界 |
| L2 | 模型调用 mock、真实本地 HTTP endpoint、JSON/不可执行 QASM 修复、敌意约束、任务正/反误分类、最大值防反转、平台排除 | 10 个闭环测试 |
| Quantum RISC-V | 11 opcode 往返、保留编码、Bell、CCX、角度界、参数末态对照 | 100 测量 seed + 数值边界 |
| Web API/资源 | Bell OriginIR 证明携带运行与所有本地素材存在 | 2 项 |

当前 submission-contained suite 共 31 项 `unittest`；其中随机和穷举测试在单项内覆盖上表的多个 seed/分支。

## 浏览器证据

浏览器自动化在桌面和 390×844 移动视口检查：

- 页面非空；无框架错误覆盖层；无 console error；
- 关键 textbox/button/select 均出现在 accessibility tree；
- Bell 运行显示 `|00〉 = 50%`、`|11〉 = 50%`；
- 结果卡显示“目标 IR 已验证执行”与证书摘要，result Schema 可展开并含完整收据；
- 移动端 `scrollWidth == innerWidth`，无横向溢出；
- 静态图标全部从提交目录加载，无 CDN 和第三方字体。

## 统计解释

状态向量给出精确理论概率；counts 使用确定性最大余数配额。该模式没有伪装成真机采样：结果的 `backend` 是规范本地模拟器 ID，`job_id` 前缀是 `loomq-local-`，`meta.engine` 明示 `loomq-statevector-v1`。

公开 evaluator 的 Hellinger Fidelity 阈值为 0.97；精确等价电路在公开 Bell/GHZ case 上达到 1.0（整数配额恰好匹配）。
