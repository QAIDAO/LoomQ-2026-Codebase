import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import App from './App'
import { LearnScreen } from './Learn'

const plainText = (markup: string) => markup.replace(/<[^>]*>/g, '')

describe('Task 13J compact three-step Learn experience', () => {
  it('positions why quantum, who LoomQ serves, and how it helps before the compact experience', () => {
    const markup = renderToStaticMarkup(<App />)
    const text = plainText(markup)

    expect(text).toContain('从熟悉的编程方式开始理解量子计算')
    expect(text).toContain('一种面向特定问题的新计算方式')
    expect(text).toContain('LoomQ 帮助开发者从熟悉的编程方式出发')
    expect(text).toContain('探索、生成并验证量子程序')
    expect(text).toContain('YOUR INTENT用户描述目标')
    expect(text).toContain('QUANTUM PROGRAM生成并验证量子程序')
    expect(text).toContain('EXECUTION TRACE探索程序如何执行')
    expect(text).toContain('RESULT理解测量结果')
    expect(text).not.toContain('找到合适的运行平台')
    expect(text).not.toContain('量子计算是更快的普通电脑')
    expect(text).not.toContain('解决所有问题')
    expect(text).not.toContain('量子计算并不适合大多数程序')
    expect(text).not.toContain('密码学 · 搜索与组合 · 量子系统模拟')
    expect(markup).toContain('href="#learn-quickstart"')
    expect(markup).not.toContain('class="learn-why"')
    expect(text).not.toContain('WHY QUANTUM MATTERS')
    expect(text).toContain('跟着一个量子比特，看懂量子程序怎么运行')
    expect(text).toContain('01Prepare准备 |0⟩')
    expect(text).toContain('02H产生叠加')
    expect(text).toContain('03Measure读取结果')
    expect(markup.match(/role="tab"/g)).toHaveLength(3)
    expect(markup).not.toContain('class="learn-code-window"')
    expect(markup).not.toContain('class="learn-program-step')
  })

  it('explains circuit once and keeps source as hidden evidence by default', () => {
    const markup = renderToStaticMarkup(<LearnScreen onStart={() => undefined} onNavigate={() => undefined} />)
    const text = plainText(markup)

    expect(text).toContain('什么是量子电路（Quantum Circuit）？')
    expect(text).toContain('按顺序执行的一组量子操作')
    expect(text.indexOf('什么是量子电路（Quantum Circuit）？')).toBeLessThan(text.indexOf('01Prepare准备 |0⟩'))
    expect(markup).toContain('aria-expanded="false"')
    expect(markup).toContain('id="learn-qasm-source"')
    expect(markup).toContain('hidden=""')
    expect(markup).toContain('qreg q[1];')
    expect(markup).toContain('h q[0];')
    expect(markup).toContain('measure q[0] -&gt; c[0];')
    expect(markup).toContain('class="is-highlighted"><em>03</em><code>qreg q[1];</code>')
  })

  it('keeps state change primary and retains measurement semantics in the implementation', () => {
    const markup = renderToStaticMarkup(<LearnScreen onStart={() => undefined} onNavigate={() => undefined} />)
    const text = plainText(markup)

    expect(markup).toContain('class="learn-compact-visual"')
    expect(markup).toContain('class="learn-compact-probability"')
    expect(text).toContain('当前量子状态 · 确定')
    expect(text).toContain('|0⟩100%')
    expect(text).toContain('你刚刚已经读完了第一个量子电路')
    for (const term of ['量子比特', '量子状态', '量子门', '量子电路', '测量']) {
      expect(markup).toContain(`<strong>${term}</strong>`)
    }
  })

  it('uses static term emphasis without restoring glossary or old teaching DOM', () => {
    const markup = renderToStaticMarkup(<LearnScreen onStart={() => undefined} onNavigate={() => undefined} />)

    expect(markup).toContain('class="quantum-term"')
    expect(markup).not.toContain('class="learn-concept-label"')
    expect(markup).not.toContain('class="quantum-concept-name"')
    expect(markup).not.toContain('quantum-concept-marker')
    expect(markup).not.toContain('term-trigger')
    expect(markup).not.toContain('term-popover')
  })

  it('keeps the technical explanation collapsed by default', () => {
    const markup = renderToStaticMarkup(<LearnScreen onStart={() => undefined} onNavigate={() => undefined} />)

    expect(markup).toContain('想看更技术一点？')
    expect(markup).toContain('<details class="learn-technical">')
    expect(markup).not.toContain('<details class="learn-technical" open="">')
  })

  it('keeps real hardware as an optional Learn-completion entry', () => {
    const markup = renderToStaticMarkup(<LearnScreen onStart={() => undefined} onNavigate={() => undefined} />)
    const text = plainText(markup)

    expect(text).toContain('🚀 体验真实量子计算')
    expect(text).toContain('选择一个量子实验')
    expect(markup).not.toContain('REAL HARDWARE · OPTIONAL EXPERIENCE')
  })
})
