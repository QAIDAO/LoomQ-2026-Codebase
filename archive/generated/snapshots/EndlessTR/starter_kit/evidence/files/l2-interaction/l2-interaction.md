# L2 交互体验说明与复现指南

本指南针对复现使用QuantumHelper Web Agent，提供了界面启动方法、3个用户体验任务以及页面说明。

## 1. 启动与入口
在终端配置环境变量后运行程序，根据终端反馈进入网页本地链接。以下为具体操作方案。
在仓库根目录运行时：

```powershell
$env:QUANTUMHELPER_ENABLE_LLM="1"
$env:LOOMQ_LLM_BASE_URL="https://组委会提供的兼容接口"
$env:LOOMQ_LLM_API_KEY="由组委会安全注入"
$env:LOOMQ_LLM_MODEL="组委会指定模型"
python starter_kit\quantumhelper_web\server.py
```

以 `starter_kit/` 为当前目录时运行时：

```powershell
python quantumhelper_web\server.py
```

反馈链接出现示例如下所示，请在浏览器中进入链接。
```powershell
QuantumHelper running at http://127.0.0.1:8000
```

入口链接说明（请以终端实际输出为准，当前链接仅为参考）
- 主入口：<http://127.0.0.1:8000/>
- 健康检查：<http://127.0.0.1:8000/api/health>
- 模型配置页：<http://127.0.0.1:8000/config.html>（仅服务器本机可管理）
- `agent.html` 是兼容旧链接的薄入口，最终会回到主工作台。

不要直接双击 HTML。页面依赖同源 API、服务端状态校验和 `starter_kit/adapter.py`。
进入 HTML 主页后，在主页的对话框中输入以下任务并发送即可体验。前端状态模块通过版本化静态资源加载；如果浏览器仍保留旧页面，执行一次强制刷新即可，不需要清除模型配置或修改源码。

## 2. 三个标准用户任务

### 任务 A：自然语言生成

输入：

```text
生成一个 3 比特 GHZ 态并进行全测量
```

应观察到：

1. Current Task。这一部分显示对于任务的理解：目标态GHZ、比特数3 qubits、测量范围全部测量。
2. 线路可视化图表。由真实电路中的operation 数据绘制：一个 H、两个 CX、三个测量，并且下端展示电路工作每一步的解释说明。
3. 线路检查。Agent 返回的 QASM 会再次经过 `adapter.parse_qasm()`，并向三个 L1 目标调用 `adapter.transpile()`；未通过校验的线路不能运行。
4. 电路代码。同时显示标准 OpenQASM 2.0，以及当前“执行目标”所对应的 adapter 代码；切换 SpinQ、OriginQ 或 Braket 时，后端代码会重新校验并按目标语法更新。
5. 推荐运行环境后端。展示了后端名称、特点以及推荐理由。
6. 线路包含测量时，点击本地预览后，结果图表来自 `adapter.run()` 返回的真实 counts 柱状图，并标明模拟器来源与 shots。线路不含测量也属于合法电路，但页面会禁用结果预览并提示“只有测量后才能看到可视化结果”。

### 任务 B：线路修复

输入：

```text
我想制备一个贝尔态，但这段代码报错了，请修复：H q[0]; CX q[0] q[1]
```

应观察到：

1. 系统保留用户声明的 Bell 目标，识别缺失头部、寄存器声明、逗号或分号等可证明问题，显示在左侧对话框区域。
2. 右侧功能界面修复结果先进入“修复建议”，展示对比，不会直接覆盖当前线路。
3. 只有用户点击应用、且 `/api/check` 再次通过后，才以新的修订替换当前线路。
4. 修复失败时保留原输入和上一次有效线路，并给出用户可执行的恢复建议。

### 任务 C：后端选择

输入：

```text
我需要运行一个 15 比特电路，要求零排队并且免费，请选择后端
```

应观察到：

1. 最终后端 ID 只能来自 `backend_capabilities.json`，不由模型自由编造。
2. 页面区分完整匹配、最接近匹配、未满足条件和本地可运行性。
3. 推荐真机与本地模拟预览严格分开；本地 counts 不会伪装成真机结果。

## 3. 多轮一致性与量子问答

推荐追加以下多轮检查：

```text
生成一个 3 比特 GHZ 态并进行全测量
改成 5 比特
为什么这里需要 H？
```

修改任务时 revision、QASM、图示、解释和校验共同更新；解释问题只读当前线路，不创建新 revision。


## 4. 错误恢复与安全边界

- 无模型时仍可导入、检查和本地运行 OpenQASM，也可使用确定性入门线路。
- Prompt、QASM、qubits、operations、shots、并发数和请求频率均有限制。
- API Key 不发送到浏览器，不出现在状态响应和 debug 日志中。
- 配置页保存的模型配置使用请求上下文隔离；并发请求不会通过全局环境变量串用密钥。
- 前端以 request ID、task ID、revision 和 AbortController 阻止迟到响应覆盖新状态。

## 5. 可核验实现与测试

| 证据 | 路径或命令 |
|---|---|
| Web 服务与 API | `starter_kit/quantumhelper_web/server.py` |
| QA 路由与上下文优先级 | `starter_kit/quantumhelper_web/web_agent.py` |
| 单页工作台 | `starter_kit/quantumhelper_web/static/index.html`、`starter_kit/quantumhelper_web/static/app.js`、`starter_kit/quantumhelper_web/static/workspace-state.js` |
| 模型运行时配置 | `starter_kit/quantumhelper_web/runtime_config.py` |
| Web/API 回归 | `python -m pytest starter_kit/test_quantumhelper_web.py starter_kit/test_web_agent.py -q` |
| 状态并发回归 | `node starter_kit/quantumhelper_web/static/workspace-state.test.js` |
| L2 readiness | `python starter_kit/test_l2_readiness.py` |
