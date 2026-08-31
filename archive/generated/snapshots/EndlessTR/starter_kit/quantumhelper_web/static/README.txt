QuantumHelper 页面结构

入口
1. index.html  首页

新手示例
2. example-task.html      理解示例任务
3. example-circuit.html   查看示例线路
4. example-run.html       运行示例
5. example-result.html    示例结果

按场景进入
6. scenario.html?type=search    查找
   scenario.html?type=opt       优化
   scenario.html?type=measure   测量
   scenario.html?type=relation  关联

自己的任务
7. custom-task.html       描述任务
8. custom-plan.html       生成方案
9. custom-circuit.html    确认线路
10. backend.html?source=custom  选择后端
11. custom-run.html       运行任务
12. custom-result.html    任务结果
13. task-adjust.html      任务暂时不适合/需要补充

已有量子线路
14. circuit-import.html       导入 OpenQASM
15. circuit-check.html        检查线路
16. backend.html?source=import 选择后端
17. circuit-run.html          运行线路
18. circuit-result.html       线路结果

说明：
- styles.css 是全站统一设计规范。
- 所有页面都已统一品牌名为 QuantumHelper。
- 页面之间已使用相对链接串联。
- 自定义任务和导入线路流程用 localStorage 在页面间传递原型数据。
- 直接打开 index.html 即可浏览。
