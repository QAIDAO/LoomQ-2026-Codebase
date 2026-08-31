# L2 + Bonus 可追踪需求矩阵

| 需求 | 产品位置 | 状态/恢复 | 自动验收 | 证据入口 |
|---|---|---|---|---|
| 八阶段首次 Bell 实验 | `web/static/index.html` 指导卡与阶段轨 | initial → completed；可撤销 | `test_bell_eight_stage_golden_path` | `web/README.md` |
| H/CX/测量三级解释 | 电路区与三级解释折叠区 | 任一步可展开；文本等价 | `test_scientific_boundary_and_local_identity_are_fixed_copy` | `web/static/index.html`、`web/app.py` |
| 图形/QASM 单一 IR | 电路画布和编辑器 | invalid 保留最后有效图形 | `test_invalid_qasm_preserves_last_valid_circuit_and_can_repair` | `web/app.py` |
| revision 防竞态 | 所有电路写操作 | 409 后刷新当前会话恢复 | `test_stale_revision_cannot_overwrite_newer_edit`、HTTP 409 测试 | `web/server.py` |
| 安全修复与撤销 | QASM diff/应用/撤销 | 先预览；应用后重验 | QASM 恢复测试 | `web/README.md` |
| 自然语言 GHZ | 自然语言入口 | 模型不可用用确定性示例 | `test_natural_language_ghz_uses_local_validation` | `web/app.py` |
| 后端推荐与降级 | 证据区运行位置 | 云端不可用不阻断本地 | `test_backend_failure_is_non_blocking` | `backend_capabilities.json` |
| counts 可视化 | 结果柱状图和数据表 | 空/无测量给恢复动作 | 黄金路径与静态契约测试 | `web/static/app.js` |
| 科学结论边界 | 结果边界卡 | 始终与结果同屏 | 科学文案快照测试 | `web/app.py` |
| 键盘/读屏/低动态 | 原生控件、skip link、live region | 非颜色编码、强制低动态 | 静态无障碍契约测试 | `web/static/styles.css` |
| 会话恢复/不可变结果 | sessionStorage + GET session | 刷新恢复；运行快照不随编辑变 | HTTP 恢复与快照测试 | `web/server.py` |

四项 Bonus 均有产品、自动验收和复现入口。浏览器实拍属于补充人工证据，不替代上述确定性测试。
