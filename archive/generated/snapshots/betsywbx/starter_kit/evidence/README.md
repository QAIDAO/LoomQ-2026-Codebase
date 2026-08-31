# LoomQ 人工评分证据

这份文件是人工评分材料的统一入口。请直接编辑它，只填写要申报的项目。截图、原始结果或图表统一放在 `starter_kit/evidence/files/`，也可以引用 `starter_kit/` 中已有的代码和文档。

证据包是可选的。没有申报某项人工分时，留空即可，不影响自动评分。

## 提交前填写

把要申报项目的方框改成 `[x]`，并填写对应内容：

- [x] L1 真机
- [x] L2 交互体验
- [x] 工程与产品化
- [x] 自定义量子 RISC-V Bonus
- [x] 新手引导与视觉叙事 Bonus

## L1 真机

每个有效真机平台计 5 分，最多两个平台。模拟器不计真机分。每个平台复制并填写一次下面的信息：

### SpinQ
**平台名称**：量旋云<br>
**平台 job ID**：S-260820-0010<br>
**运行时间**：2026-08-20T06:47:33.235567Z<br>
**shots**：8192<br>
**实际执行的 QASM**：[files/spinq-circuit.qasm](./files/spinq-circuit.qasm)<br>
**平台返回的原始结果**：[files/spinq-S-260820-0010_raw.json](./files/spinq-S-260820-0010_raw.json)<br>
**任务页截图**：[files/spinq-screenshot.png](./files/spinq-screenshot.png)<br>

### OriginQ
**平台名称**：本源量子<br>
**平台 job ID**：959CD11FB04417BF96280FCA8AEE7D5E<br>
**运行时间**：2026-08-21T01:12:40.984267Z<br>
**shots**：8192<br>
**实际执行的 QASM**：[files/originq-circuit.qasm](./files/originq-circuit.qasm)<br>
**平台返回的原始结果**：[files/originq_959CD11FB04417BF96280FCA8AEE7D5E_raw.json](./files/originq_959CD11FB04417BF96280FCA8AEE7D5E_raw.json)<br>
**任务页截图**：[files/originq-screenshot.png](./files/originq-screenshot.png)<br>

#### 非对称电路测试结果：
**平台名称**：本源量子<br>
**平台 job ID**: EA3F5364AE4741D0DD9B19F918E3F78D<br>
**shots**: 200<br>
**实际执行的 QASM**：[files/originq-asymmetrical-circuit.qasm](./files/originq-asymmetrical-circuit.qasm)<br>
**平台返回的原始结果**：[files/originq_EA3F5364AE4741D0DD9B19F918E3F78D_raw.json](./files/originq_EA3F5364AE4741D0DD9B19F918E3F78D_raw.json)<br>
**任务页截图**：[files/originq-asymmetrical-screenshot.png](./files/originq-asymmetrical-screenshot.png)<br>

工作人员会核对 job ID、运行时间、电路、shots 和原始结果。截图只能辅助说明，不能代替 job ID 和原始结果。

## L2 交互体验

```text
启动界面或 CLI 的命令：先按 `LOOMQ_README.md`「快速上手」完成 `setup.sh` 和环境变量配置，再运行 `python3 app.py`
测试入口或页面地址：`http://127.0.0.1:5000`（本地启动后浏览器打开）
适合现场体验的 3 个用户任务：
1. 帮我生成一个3比特GHZ态的电路
2. 我想跑一个15比特的电路，不想排队，用哪个后端？
3. 我想跑一个100比特的电路，用哪个后端？
```

## 工程与产品化

已有内容可以直接引用主 README 或其他项目文档，不必复制到本目录。<br><br>
查看[LOOMQ_README.md](../LOOMQ_README.md)<br><br>
工作人员会按最终 commit 实际构建和启动，并检查文档与代码是否一致、产品是否真的降低了量子计算的使用门槛。

## 自定义量子 RISC-V Bonus

以下三项必须齐全且测试通过，才获得 8 分：

**指令编码规格**：[../bonus/qxor_isa_spec.md](./../bonus/qxor_isa_spec.md)<br>
**模拟器扩展实现**：[../bonus/riscv_emulator_ext.py](./../bonus/riscv_emulator_ext.py)<br>
**端到端测试命令**：[../bonus/demo_qxor_e2e.py](./../bonus/demo_qxor_e2e.py)<br>

## 新手引导与视觉叙事 Bonus

请填写已有材料的路径，不要求为评分另写一套文档：<br><br>

**零基础首次运行指南**：<br>
按[LOOMQ_README.md](../LOOMQ_README.md)指示，打开浏览器访问网页入口，无需安装任何软件、无需注册账号、无需了解任何量子计算或编程知识。页面顶部提供三个可点击的示例问题（生成电路 / 选后端-有解 / 选后端-无解场景），新用户可以直接点击体验，也可以直接用中文描述自己的需求。整个交互过程与市面上任何聊天软件一致，没有额外学习成本。<br><br>

**错误恢复或无障碍引导**：<br>
`agent_chat` 内置自验证重试闭环：模型生成的电路会先在本地跑一遍验证正确性，跑不通会自动把报错信息喂回模型重新生成（最多2次重试），用户全程不会看到内部报错细节，拿到的始终是能跑通的结果或诚实的失败说明。界面提供的示例问题按钮，帮助不知道"该问什么"的用户直接上手，降低了"面对空白输入框不知道从哪开始"的常见新手门槛。<br><br>


## 提交规则

- 所有材料都要在截止前进入最终提交的 commit，工作人员不接受截止后补交。
- 外部视频可以用稳定只读链接，源码、原始结果和复现命令应保存在仓库中。
- 整个 fork commit 的归档包不得超过 100 MiB。
- 不要提交 API Key、Token、Cookie、个人身份信息或平台账户隐私。
- 如申报 L1 真机分，在最终提交 Issue 的 `Hardware evidence` 中填写 `starter_kit/evidence/README.md`。
