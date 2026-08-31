import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { EXPERIMENT_SCENARIO_IDS, ExperimentsScreen } from './Experiments'
import { SCENARIOS } from './scenarios'

describe('Task 13G experiments screen', () => {
  it('shows only Bell, Grover, and Phase as three distinct formal experiments', () => {
    const markup = renderToStaticMarkup(
      <ExperimentsScreen onNavigate={() => undefined} onSelect={() => undefined} onFreeExplore={() => undefined} />,
    )

    expect(markup.match(/class="experiment-card /g)).toHaveLength(3)
    expect(markup).toContain('两个变量，什么时候不能再分开理解？')
    expect(markup).toContain('搜索一定要逐个检查答案吗？')
    expect(markup).toContain('输出一样，内部状态就一定一样吗？')
    expect(markup).toContain('普通程序里，我们习惯分别理解每个变量；形成纠缠后，更重要的是整个系统的联合状态。')
    expect(markup).toContain('普通程序常用遍历、比较、返回；Grover 用“标记 → 干涉 → 放大 → 测量”改变搜索过程。')
    expect(markup).toContain('当前测量概率相同，不代表量子状态相同；相对相位可能暂时看不出来，却会影响后续干涉和结果。')
    expect(markup).toContain('Bell State · 纠缠与联合状态')
    expect(markup).toContain('Grover Search · 标记与概率放大')
    expect(markup).toContain('Relative Phase · 相位与后续干涉')
    expect(markup).toContain('推荐从这里开始')
    expect(markup).not.toContain('GHZ')
    expect(markup).not.toContain('共享状态')
    expect(markup).not.toContain('共享内存')
    expect(markup).not.toContain('hidden field')
    for (const visual of ['bell-visual', 'grover-visual', 'phase-visual']) {
      expect(markup).toContain(visual)
    }

    for (const [question, bridge, formal] of [
      ['两个变量，什么时候不能再分开理解？', '普通程序里，我们习惯分别理解每个变量', 'Bell State · 纠缠与联合状态'],
      ['搜索一定要逐个检查答案吗？', '普通程序常用遍历、比较、返回', 'Grover Search · 标记与概率放大'],
      ['输出一样，内部状态就一定一样吗？', '当前测量概率相同，不代表量子状态相同', 'Relative Phase · 相位与后续干涉'],
    ]) {
      expect(markup.indexOf(question)).toBeLessThan(markup.indexOf(bridge))
      expect(markup.indexOf(bridge)).toBeLessThan(markup.indexOf(formal))
    }
  })

  it('reuses the existing stable prompts without rewriting them', () => {
    const prompts = EXPERIMENT_SCENARIO_IDS.map(
      (id) => SCENARIOS.find((scenario) => scenario.id === id)?.prompt,
    )

    expect(prompts).toEqual([
      '生成一个 Bell 态并测量',
      '设计一个 2 比特 Grover 搜索电路，搜索目标为 |11>。先创建均匀叠加，再实现标记 |11> 的 Oracle 和扩散算子，最后测量；请使用 OpenQASM 2.0 基础门展开，不定义自定义 gate。',
      '生成一个带相对相位的 Bell- 态，不要求测量',
    ])
  })

  it('keeps the emphasized free exploration entry with the formal experiments', () => {
    const markup = renderToStaticMarkup(
      <ExperimentsScreen onNavigate={() => undefined} onSelect={() => undefined} onFreeExplore={() => undefined} />,
    )

    const freeEntryIndex = markup.indexOf('class="experiments-free"')
    const experimentGridIndex = markup.indexOf('class="experiments-grid"')

    expect(freeEntryIndex).toBeGreaterThan(markup.indexOf('class="experiments-catalog"'))
    expect(freeEntryIndex).toBeLessThan(experimentGridIndex)
    expect(markup.match(/class="experiments-free"/g)).toHaveLength(1)
    expect(markup).toContain('已经有自己的想法？')
    expect(markup).toContain('Explorer 支持直接输入自然语言实验需求')
  })

  it('places a lightweight Why Quantum motivation directly before the formal experiments', () => {
    const markup = renderToStaticMarkup(
      <ExperimentsScreen onNavigate={() => undefined} onSelect={() => undefined} onFreeExplore={() => undefined} />,
    )

    const motivationIndex = markup.indexOf('class="experiments-motivation"')
    const experimentGridIndex = markup.indexOf('class="experiments-grid"')

    expect(markup).toContain('量子计算不是“更快的普通电脑”')
    expect(markup).toContain('它不适合大多数普通程序，却可能在少数特殊问题上提供完全不同的求解方式。')
    expect(markup).toContain('密码学 · 搜索与组合 · 量子系统模拟')
    expect(markup).toContain('先从三个小实验，看看量子计算到底打破了哪些普通程序的直觉。')
    expect(motivationIndex).toBeLessThan(markup.indexOf('class="experiments-free"'))
    expect(motivationIndex).toBeLessThan(experimentGridIndex)
  })
})
