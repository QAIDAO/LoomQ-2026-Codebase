# L2 12-case regression record

这是一轮本地可复现回归，不是组委会私有种子正式成绩。运行使用容器内的 `agent_chat`、DeepSeek `deepseek-v4-flash` 和本地 OriginQ CPUQVM 语义验证。

```text
结果：12/12 通过
调用入口：starter_kit/adapter.py -> agent_chat()
验证内容：8 个自然语言生成/修复电路 + 4 个后端推荐
后端推荐验证：官方 backend_capabilities.json
语义验证：Bell、GHZ、X 和修复电路的本地 counts
协议约束：每个 case 最多 3 次模型调用；单 case 超时 120 秒
```

覆盖的 12 个回归 case：

1. 英文 Bell 态生成
2. 中文 GHZ 态生成
3. X 门确定性电路生成
4. 参数门电路生成
5. CCX 错误修复为 GHZ
6. 越界量子比特修复为 Bell 态
7. 错误测量目标修复为 `|1⟩`
8. 不完整 QASM 修复为 Bell 态
9. 28 比特本地、免费、无排队、免账号后端推荐
10. 15 比特无排队后端推荐
11. 5 比特免费配额真机推荐
12. 不可满足的 100 比特本地模拟器请求

Key、请求凭证和完整 API 返回内容不进入仓库。
