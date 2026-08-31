# Task 13M — Reframe Experiments around developer intuition

## Goal

Make the three curated experiments feel meaningful to ordinary software developers without inventing fake application scenarios.

The Experiments page should answer:

> 量子计算到底打破了普通程序里的哪些直觉？

Keep the current page structure and visual style. This task is primarily copy / information hierarchy.

## Scope

Only update the curated experiment cards / nearby supporting copy in `02 Experiments`.

Do not redesign the page and do not change experiment behavior.

## Core framing

Do **not** force each experiment into an industry use case.

Instead, describe the contrast between a familiar software-development mental model and what happens in quantum computation.

The three experiments should read as three developer-intuition questions:

### Bell

Primary question:

> 两个变量，什么时候不能再分开理解？

Developer bridge:

> 普通程序里，我们习惯分别理解每个变量；形成纠缠后，更重要的是整个系统的联合状态。

Keep the existing quantum meaning around correlation / entanglement, but avoid saying this is like shared state, synchronization, shared memory, or linked variables. Those analogies are too classical and misleading.

Suggested compact supporting line:

> 从两个独立对象的直觉，切换到“必须整体理解状态”。

Formal / secondary label may use:

> Bell State · 纠缠与联合状态

### Grover

Primary question:

> 搜索一定要逐个检查答案吗？

Developer bridge:

> 普通程序常用遍历、比较、返回；Grover 用“标记 → 干涉 → 放大 → 测量”改变搜索过程。

A compact code-minded hint may use:

> Oracle ≈ `isTarget(x)`

But the card must not imply Oracle directly reveals the answer.

If shown, keep the conceptual sequence accurate:

> 准备候选 → Oracle 标记目标 → 干涉 / Diffusion 放大目标 → 测量

Do not expand this task into the future Grover state-visualization work.

Formal / secondary label may use:

> Grover Search · 标记与概率放大

### Phase

Primary question:

> 输出一样，内部状态就一定一样吗？

Developer bridge:

> 当前测量概率相同，不代表量子状态相同；相对相位可能暂时看不出来，却会影响后续干涉和结果。

Suggested compact supporting line:

> “现在看起来一样”，不代表后续计算会一样。

Do not describe phase as a hidden field, hidden variable, object property, cache, or internal flag. Those can be intuition bridges in discussion but should not become literal product copy.

Formal / secondary label may use:

> Relative Phase · 相位与后续干涉

## Card hierarchy

Prefer this hierarchy on each curated card:

1. Developer-facing question first
2. One short sentence explaining the intuition shift
3. Formal experiment name / quantum concepts as secondary information
4. Existing CTA / behavior unchanged

The user should understand why the experiment is interesting before needing to know the quantum term.

## Page-level copy

Keep the current Task 13L motivation section and its lightweight style.

The transition into the cards can reinforce:

> 先从三个小实验，看看量子计算到底打破了哪些普通程序的直觉。

Use this or a similarly concise sentence if it fits the existing layout better.

Do not add another explanation section.

## Important constraints

- Keep exactly the same three curated experiments: Bell, Grover, Phase.
- Do not add/remove/reorder experiments unless the current implementation already requires it.
- Do not change stable prompts.
- Do not change navigation or free-exploration behavior.
- Do not change Explorer behavior.
- Do not implement the planned Grover Oracle / Diffusion visualization in this task.
- Do not change backend, LLM calls, validation, repair, or correctness logic.
- Do not introduce fake claims about quantum advantage or real-world applicability.
- Do not turn the cards into generic analogy cards; quantum terminology should remain available as secondary context.
- Reuse current typography/colors/layout where possible; no visual redesign is required.

## Acceptance

A software developer with no quantum background should be able to scan the three cards and immediately understand three distinct reasons the experiments are worth opening:

- Bell: sometimes the system cannot be understood as separate variables.
- Grover: search can use a different computational pattern than sequential checking.
- Phase: identical visible probabilities do not imply identical quantum state or future behavior.

After the change, stop for review.
