# Scientific Claims Audit — LoomQ 2026 Current Submission

> 红队审查日期：2026-08-22。本文件逐条审计当前提交中所有与量子实验结果相关的声明，
> 明确每条声明的证据、允许措辞与禁止的过度声明。原则：**数据只支持它能支持的结论**。
> Z-basis 计算基测量不能单独证明 Bell 纠缠；Z-basis GHZ population 不能单独证明 genuine multipartite entanglement。

## 1. 审计方法

全文扫描关键词：`entangle / 纠缠 / GHZ / Bell / fidelity / prove / confirm / 证明 / 证实 / 验证 / 正确 / 真实 / quantum advantage`，
覆盖 README、JUDGE_GUIDE、evidence/*、USER_GUIDE、QUANTUM_101、Web 静态资源（app.js / index.html）。
逐条对照真实硬件数据（job 记录 JSON）判定措辞是否越界。

## 2. 逐条审计表

### 2.1 Bell（canonical，D0C7F490B43D9B04FDF19ABF3DB8B342，legacy QCloud）

| 项 | 内容 |
|---|---|
| 证据 | `originq-hardware-result.normalized.json`：00/11 占主导（Z-basis，shots=1000） |
| 允许措辞 | "strong Z-basis 00/11 correlation consistent with the target Bell circuit" |
| 禁止措辞 | "entanglement proved / 纠缠正确 / 证明了纠缠" |
| 当前状态 | ✅ 合规（evidence/README 明确写"单凭计算基测量不足以证明纠缠，未作此声明"） |

### 2.2 Bell（runtime，2C68A9D3E2F6626B55EEC966DBC3CE2B，WK_C180_2）

| 项 | 内容 |
|---|---|
| 证据 | `originq_runtime_bell-hardware-result.normalized.json`：provider probabilities P(00)=0.4578574、P(11)=0.5419198；逐 shot counts unavailable |
| 允许措辞 | "Z-basis computational-basis correlation；P(00)+P(11)≈1.0；与目标 Bell 电路的计算基相关一致" |
| 禁止措辞 | "证明纠缠 / Bell-state fidelity（未测 X/Y basis，无法计算 F_Φ+）" |
| 当前状态 | ✅ 合规（ORIGINQ_REPRODUCIBILITY.md §边界 明确 classical mixture 也可产生同样 Z-basis marginals） |

### 2.2b Bell 三基纠缠 witness（2026-08-22 新增，X/Y-basis 实验完成后）

| 项 | 内容 |
|---|---|
| 证据 | Z-basis job `2C68A9D3...`（Czz=0.9995545）、X-basis job `CA80432C...`（Cxx=0.9995576）、Y-basis job `5ABEAE90...`（Cyy=−0.9986527）；同一 device `WK_C180_2`、同一物理比特 [49,58]、每 job 请求 shots=1000；API 保存的是 provider probabilities，不是 raw per-shot counts |
| 理论预验证 | 可分离上界 \|Cxx\|+\|Czz\|≤1 与 fidelity 公式已在 22 万个随机可分离态 + 全部 4 个 Bell 态上程序化验证（脚本在硬件提交前运行） |
| 结果 | 点估计：**\|Cxx\|+\|Czz\| = 1.99911**；**F_Φ+ = 0.99944**。由于缺少 raw counts 或文档化的 provider 不确定性模型，不计算 95% 下界，也不据此作统计性 witness/fidelity 结论。 |
| 允许措辞 | "三基 provider probability point estimates 为 \|Cxx\|+\|Czz\|≈1.999、F≈0.999；不构成统计性纠缠证明" |
| 禁止措辞 | "two-setting correlations witness entanglement"、"exceeds separable threshold with 95% confidence"、"完美纠缠 / 无条件纠缠证明" |
| 可复算 | `scripts/compute_bell_witness.py` → `evidence/files/bell-witness-analysis.json`（输入三个 raw JSON 的 provider 概率，复算点估计并明确 `statistical_inference: not_computed`） |

### 2.3 GHZ-3（runtime，B23E5B75D47D124A078F25B1C0083C2A）

| 项 | 内容 |
|---|---|
| 证据 | counts：000=703（0.703）、011=187（0.187）、111=108（0.108），其余≈0 |
| 允许措辞 | "GHZ-3 circuit executed on WK_C180_2；computational-basis distribution returned by real QPU；target-state population affected by hardware noise" |
| 禁止措辞 | "完美 GHZ / 证明三比特纠缠 / genuine multipartite entanglement" |
| 当前状态 | ✅ 合规（文档明确列出 011=0.187 噪声泄漏，未包装） |

### 2.4 Multi（runtime，8575222FE2C04A065B38B9DEE5BA9AEE）

| 项 | 内容 |
|---|---|
| 证据 | provider probabilities P(00)=0.2095924、P(01)=0.277605、P(10)=0.3016603、P(11)=0.2111422 vs reference 均匀 0.25：TVD≈0.08、classical fidelity≈0.993、Hellinger≈0.058 |
| 允许措辞 | "distribution consistent with intended circuit（程序化对比 reference simulator）" |
| 禁止措辞 | 任何纠缠/量子优势推断 |
| 当前状态 | ✅ 合规（`originq_runtime_multi-reference-comparison.json` 保存了可复算的对比数据） |

### 2.5 本地模拟器结果（Web "第一次实验"、L1 reports）

| 项 | 内容 |
|---|---|
| 证据 | 噪声-free 模拟器返回的 counts |
| 允许措辞 | "模拟器结果可以证明程序与目标分布一致（无噪声后端的数学事实）；不支持量子优势/硬件保真度结论" |
| 当前状态 | ✅ 合规（index.html："它不等于量子优势，也不能替代真机噪声证据"） |

### 2.6 后端推荐（L2）

| 项 | 内容 |
|---|---|
| 证据 | 程序化 `select_backends` 对官方 capability 表的确定性匹配 |
| 允许措辞 | "推荐结果满足官方能力表中的显式约束（可程序化复核）；不代表平台实时排队状态" |
| 当前状态 | ✅ 合规（app.js 同句立即声明排队状态边界） |

### 2.7 概念教学（QUANTUM_101.md）

| 项 | 内容 |
|---|---|
| 证据 | 教科书定义 |
| 允许措辞 | "Bell 态（理想数学定义）= 两枚永远同面的硬币"——这是对理想态的定义，不是对测量结果的声明 |
| 当前状态 | ✅ 合规（明确处于"概念"章节，非结果声明） |

## 3. 边界声明（全局）

1. **Simulator ≠ real QPU**：所有模拟器结果从不被描述为真机证据。
2. **Real QPU = 有平台任务 ID 的记录**：组委会可登录复核。
3. **计算基相关 ≠ 纠缠**：Z-basis 单独不能证明纠缠（GHZ-3 与 canonical Bell 仍只作计算基相关声明）。2026-08-22 补充的 X/Y-basis 数据提供三基点估计，但 Runtime API 未导出 raw per-shot counts，且没有可独立验证的 provider 不确定性模型；因此这三个 Bell job 也不使用 witness/fidelity 的统计性措辞。其他电路（GHZ-3、Multi）同样不扩展纠缠声明。
4. **验证/证明 的对象必须明确**：项目中的"程序验证（verifier）"指独立参考模拟器的语义一致性检查，是软件正确性声明，不是物理声明。

## 4. 若补跑 Bell witness 的判定标准（预注册，防 cherry-picking）

- 电路：Bell prep + H(q0),H(q1) 后测量（X-basis）；已有 Z-basis job 作 Czz 来源。
- 公式：Czz = P00+P11−P01−P10（Z 实验）；Cxx 同式（X 实验）。
- 可分离态上界：对任意 separable two-qubit state，|Cxx|+|Czz| ≤ 1（注：单 setting |C|≤1 平凡；两-setting 和的上界 1 来自每个纯积态 |⟨σx⊗σx⟩|+|⟨σz⊗σz⟩| 的最大化分析，数值上可对积态族采样验证）。
- 判定：只有平台导出 raw per-shot counts，或提供可独立验证的方差/mitigation 语义后，才可计算正确的不确定性；且 |Cxx|+|Czz| 的下界仍 > 1 时，才允许写 "two-setting correlations witness entanglement"。否则只记录点估计，禁止重跑刷数据。
- Φ+ fidelity（若做 Y-basis）：F = (1 + Cxx − Cyy + Czz)/4；仅在上述可验证不确定性前提下，才可报告超过可分离阈值。

## 5. 结论

当前提交的全部 judge-facing 声明均未超出数据支持范围。

- 2026-08-22 前：所有纠缠相关表述为否定式边界声明（"未声明证明纠缠"）。
 2026-08-22：按 §4 预注册标准执行了 X/Y-basis 实验。X-basis（Cxx=0.99956）触发 Y-basis；Y-basis（Cyy=−0.99865）完成三关联测量。点估计为 **\|Cxx\|+\|Czz\| = 1.99911**、**F_Φ+ = 0.99944**。复审发现 Runtime API 返回的是 provider probabilities 而非 raw counts；在缺少可验证的不确定性模型时，不能把请求的 1000 shots 直接套入 binomial 下界。因此只报告这三个 job 的点估计，不作统计性 witness 或 fidelity-threshold 声明。

## 6. Final candidate UX diff audit — 2026-08-25

This is a reference-based technical review of the final UX/documentation diff. The attached external science audit was used as a cross-check only; it is not a physical-expert review or endorsement.

The final candidate changed the judge-facing route and release documentation, but did not change the quantum compiler, runners, raw hardware exports, manifests, metadata, checksums, or canonical science numbers. The relevant UX changes are `starter_kit/JUDGE_GUIDE.md`, `starter_kit/README.md`, `starter_kit/USER_GUIDE.md`, `starter_kit/QUANTUM_101.md`, `starter_kit/loomq/web/static/styles.css` comments, and the evidence/checklist files.

Keyword sweep covered `Bell`, `entanglement`, `GHZ`, `tomography`, `fidelity`, `PPT`, `prove`, `量子优势`, `证明`, and `纠缠` across the current judge-facing docs and Web assets:

- Bell / entanglement: the map now directs reviewers from `00/11` correlation to X/Y/Z and tomography; the guide explicitly says Z-basis correlation is not proof of entanglement.
- GHZ: the existing noise-affected computational-basis boundary remains; no new multipartite-entanglement claim was added.
- Tomography / fidelity / PPT: the existing provider-reconstructed point-estimate wording remains bounded; no confidence interval, device-independent certification, loophole-free certification, or quantum-advantage claim was added.
- `prove` / `量子优势`: the final guide preserves the distinction between software verifier correctness, physical evidence, and quantum advantage.
- Backend P0 semantics: `zero_queue` polarity is a routing contract and regression fact, not a physical claim; no scientific evidence is inferred from it.

Conclusion for this diff: no new overclaim was found. The remaining human gate is to review the rendered copy, especially the nearby distinction between the ideal Bell state definition and what one Z-basis run can establish.
