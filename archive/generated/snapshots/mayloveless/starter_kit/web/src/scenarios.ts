export type Scenario = {
  id: string
  tag: string
  title: string
  prompt: string
  ordinary: string
  quantum: string
  focus: string
}

// 稳定 prompt 集中维护；Experiments 与 Explorer 只引用，不复制或改写。
export const SCENARIOS: Scenario[] = [
  {
    id: 'bell',
    tag: 'BELL',
    title: '两个结果为什么总是同步？',
    prompt: '生成一个 Bell 态并测量',
    ordinary: '生成一个随机 bit，再复制它，也能得到两个相同值。',
    quantum: '不复制经典结果，而是先建立两个量子位的纠缠，再分别测量。',
    focus: '观察“叠加 → 纠缠 → 测量”如何一步步建立。',
  },
  {
    id: 'ghz',
    tag: 'GHZ',
    title: '三个量子位怎样变成一个整体？',
    prompt: '生成一个 3 比特 GHZ 态并测量',
    ordinary: '普通程序可以复制同一个值，让三个变量保持一致。',
    quantum: '量子电路把两个量子位的关联继续传播到第三个量子位。',
    focus: '观察关联怎样从两个量子位逐步扩展到三个。',
  },
  {
    id: 'phase',
    tag: 'PHASE',
    title: '概率没变，量子状态真的没变吗？',
    prompt: '生成一个带相对相位的 Bell- 态，不要求测量',
    ordinary: '经典直觉通常只比较每个结果出现的概率。',
    quantum: '量子状态还包含相位；相位不一定立即改变概率，却会影响后续干涉。',
    focus: '留意概率不变时，复振幅的相位如何发生变化。',
  },
  {
    id: 'search',
    tag: 'SEARCH',
    title: '怎样让目标答案更容易被找到？',
    prompt: '设计一个 2 比特 Grover 搜索电路，搜索目标为 |11>。先创建均匀叠加，再实现标记 |11> 的 Oracle 和扩散算子，最后测量；请使用 OpenQASM 2.0 基础门展开，不定义自定义 gate。',
    ordinary: '普通搜索通常逐项检查候选，直到找到符合条件的答案。',
    quantum: '量子版本先组合多个候选，再用干涉改变它们被测到的机会。',
    focus: '观察叠加、条件操作和测量如何组成一次搜索尝试。',
  },
]
