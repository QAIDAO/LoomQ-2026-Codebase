import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ConceptCard, CuratedWorkspace, CURATED_COMPLETIONS, DEFAULT_RESULT_AUTOPLAY, EmptyWorkspace, ExperimentCompletion, ExplorerScreen, GenericWorkspace, nextCuratedScenarioId, SCENARIOS, ScenarioContext, shouldCelebrateCompletion } from './App'
import { ExperimentStory } from './ExperimentStory'
import type { ExperimentStoryModel } from './storyModel'
import type { StateEntry, TraceEvent } from './types'

describe('Just-in-time concept card', () => {
  it('renders a concept only when both name and explanation exist', () => {
    const markup = renderToStaticMarkup(
      <ConceptCard
        step={{
          operation_index: 0,
          purpose: '准备两条路径。',
          concept: '叠加',
          concept_explanation: '多个基态共同描述当前状态。',
        }}
      />,
    )

    expect(markup).toContain('叠加')
    expect(markup).toContain('多个基态共同描述当前状态')
    expect(renderToStaticMarkup(
      <ConceptCard
        step={{
          operation_index: 1,
          purpose: '继续执行。',
          concept: null,
          concept_explanation: null,
        }}
      />,
    )).toBe('')
  })
})

describe('Task 13D scenario entry', () => {
  it('keeps stable prompts behind developer-friendly scenario titles', () => {
    expect(SCENARIOS.slice(0, 3).map((scenario) => scenario.prompt)).toEqual([
      '生成一个 Bell 态并测量',
      '生成一个 3 比特 GHZ 态并测量',
      '生成一个带相对相位的 Bell- 态，不要求测量',
    ])
    expect(SCENARIOS.slice(0, 3).map((scenario) => scenario.title)).toEqual([
      '两个结果为什么总是同步？',
      '三个量子位怎样变成一个整体？',
      '概率没变，量子状态真的没变吗？',
    ])
  })

  it('renders the lightweight comparison context from static metadata', () => {
    const markup = renderToStaticMarkup(<ScenarioContext scenario={SCENARIOS[0]} />)

    expect(markup).toContain('普通程序怎么理解？')
    expect(markup).toContain('量子版本有什么不同？')
    expect(markup).toContain('这次重点看什么？')
  })
})

describe('Task 13G Explorer entry', () => {
  it('prefills the selected stable prompt without rendering scenario pickers', () => {
    const markup = renderToStaticMarkup(
      <ExplorerScreen initialScenarioId="search" onNavigate={() => undefined} onSelectExperiment={() => undefined} />,
    )

    expect(markup).toContain(
      SCENARIOS.find((scenario) => scenario.id === 'search')!.prompt.replaceAll('>', '&gt;'),
    )
    expect(markup).toContain('aria-current="page"')
    expect(markup).toContain('<strong>自由探索</strong>')
    expect(markup).not.toContain('Experiments · 选择实验')
    expect(markup).not.toContain('Learn · 基础概念')
    expect(markup).not.toContain('场景示例')
    expect(markup).not.toContain('切换示例')
    expect(markup).toContain('Grover 搜索实验已准备好')
    expect(markup).toContain('尚未运行 · 点击上方“运行量子程序”开始')
    expect(markup).not.toContain('class="loading-process"')
    expect(markup).not.toContain('skeleton-line')
  })

  it('opens free exploration with an empty prompt', () => {
    const markup = renderToStaticMarkup(
      <ExplorerScreen initialScenarioId={null} onNavigate={() => undefined} onSelectExperiment={() => undefined} />,
    )

    expect(markup).toMatch(/<textarea[^>]*><\/textarea>/)
    expect(markup).toContain('描述你想探索的量子程序')
    expect(markup).toContain('在上方输入自然语言实验需求')
    expect(markup).not.toContain('class="loading-process"')
    expect(markup).not.toContain('skeleton-line')
  })

  it('shows staged preparation only while Explorer is loading', () => {
    const idleMarkup = renderToStaticMarkup(
      <EmptyWorkspace loading={false} scenario={SCENARIOS[0]} />,
    )
    const loadingMarkup = renderToStaticMarkup(
      <EmptyWorkspace loading scenario={SCENARIOS[0]} />,
    )

    expect(idleMarkup).not.toContain('class="loading-process"')
    expect(idleMarkup).not.toContain('skeleton-line')
    expect(loadingMarkup).toContain('class="loading-process"')
    expect(loadingMarkup).not.toContain('skeleton-line')
    expect(loadingMarkup).toContain('正在准备你的量子实验')
    expect(loadingMarkup).toContain('请求完成后会一次性展示真实结果')
  })
})

describe('Task 13O curated experiment story frame', () => {
  const model: ExperimentStoryModel = {
    scenarioId: 'search',
    stages: [
      {
        id: 'oracle',
        number: '02',
        label: '翻转目标方向',
        purpose: '对每个候选执行同一个判断。',
        action: '目标分支的振幅方向被翻过来；Oracle ≈ isTarget(x)，但不会直接返回答案。',
        importance: '概率还没有变大，方向差异会留给后续干涉使用。',
        terminology: '这也叫相位翻转。',
        stepIndex: 2,
        gateIndices: [1, 2],
        before: { mode: 'wave', values: [
          { basis: '00', magnitude: 0.5, phase: 0, probability: 0.25 },
          { basis: '11', magnitude: 0.5, phase: 0, probability: 0.25 },
        ] },
        after: { mode: 'wave', values: [
          { basis: '00', magnitude: 0.5, phase: 0, probability: 0.25 },
          { basis: '11', magnitude: 0.5, phase: Math.PI, probability: 0.25 },
        ] },
      },
    ],
  }

  it('keeps a completed request stopped until the user advances it', () => {
    expect(DEFAULT_RESULT_AUTOPLAY).toBe(false)
  })

  it('renders the five-part frame and explains Oracle as a direction flip first', () => {
    const markup = renderToStaticMarkup(
      <ExperimentStory model={model} activeStageIndex={0} onSelect={() => undefined} onComplete={() => undefined} />,
    )

    expect(markup).toContain('当前阶段要做什么')
    expect(markup).toContain('执行前')
    expect(markup).toContain('做了什么')
    expect(markup).toContain('执行后')
    expect(markup).toContain('为什么重要')
    expect(markup).toContain('振幅方向被翻过来')
    expect(markup).toContain('不会直接返回答案')
    expect(markup).toContain('方向翻转')
    expect(markup).toContain('不代表真实光子')
    expect(markup).toContain('当前概念')
    expect(markup).toContain('相位翻转')
    expect(markup).toContain('Phase Flip')
    expect(markup).toContain('上一阶段')
    expect(markup).toContain('完成这个实验 ✓')
  })

  it('renders the curated two-column Program and Story layout with range highlights', () => {
    const steps: TraceEvent[] = [
      {
        seq: 0, layer: 'circuit', stage: 'initial_state', executor: 'local', status: 'ok', summary: '初始状态',
        data: { state_after: [{ basis: '00', probability: 1 }] },
      },
      {
        seq: 1, layer: 'circuit', stage: 'gate_step', executor: 'local', status: 'ok', summary: 'H',
        data: { operation_index: 0, gate: 'h', qubits: ['q[0]'], state_before: [], state_after: [] },
      },
      {
        seq: 2, layer: 'circuit', stage: 'gate_step', executor: 'local', status: 'ok', summary: 'Z',
        data: { operation_index: 1, gate: 'z', qubits: ['q[0]'], state_before: [], state_after: [] },
      },
    ]
    const markup = renderToStaticMarkup(
      <CuratedWorkspace
        story={model}
        steps={steps}
        qasm={'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\nz q[0];'}
        circuitGoal="搜索目标 |11⟩"
        activeStoryStage={0}
        activeStep={2}
        qasmOpen
        guideOpen
        completed={false}
        celebrating={false}
        onSelectStoryStage={() => undefined}
        onSelectStep={() => undefined}
        onQasmOpenChange={() => undefined}
        onDismissGuide={() => undefined}
        onOpenGuide={() => undefined}
        onComplete={() => undefined}
        onReturnToStory={() => undefined}
        onContinue={() => undefined}
        onBackToExperiments={() => undefined}
      />,
    )

    expect(markup).toContain('data-layout="curated-two-column"')
    expect(markup).toContain('PROGRAM')
    expect(markup).toContain('STORY')
    expect(markup).toContain('class="circuit-diagram"')
    expect(markup).toMatch(/<details[^>]*curated-qasm[^>]*open=""/)
    expect(markup.match(/stage-highlighted/g)?.length).toBeGreaterThanOrEqual(4)
    expect(markup).not.toContain('CIRCUIT STEPS')
    expect(markup).not.toContain('自动回放')
    expect(markup).not.toContain('查看这一阶段对应的 Gate')
    expect(markup).toContain('先看右边：一次只解释一个阶段')
  })
})

describe('Task 13R curated experiment completion', () => {
  const snapshot = { mode: 'wave' as const, values: [
    { basis: '0', magnitude: 1, phase: 0, probability: 1 },
  ] }

  function completionMarkup(scenarioId: 'bell' | 'search' | 'phase', celebrating = false) {
    return renderToStaticMarkup(
      <ExperimentCompletion
        scenarioId={scenarioId}
        celebrating={celebrating}
        onReturnToStory={() => undefined}
        onContinue={() => undefined}
        onBackToExperiments={() => undefined}
      />,
    )
  }

  it('uses the required Bell completion summary and Grover recommendation', () => {
    const markup = completionMarkup('bell')
    expect(markup).toContain('✓ 你已经完成 Bell 实验')
    expect(markup).toContain('叠加 → 建立关联 → 测量')
    expect(markup).toContain('需要整体描述的联合状态')
    expect(markup).toContain('继续看 Grover 搜索 →')
    expect(markup).toContain('你学到了什么？')
    expect(markup).toContain('两个量子位的读出彼此关联')
    expect(markup).toContain('纠缠：多个量子位需要作为一个整体状态来理解。')
  })

  it('uses the required Grover completion summary and Phase recommendation', () => {
    const markup = completionMarkup('search')
    expect(markup).toContain('✓ 你已经完成 Grover 搜索实验')
    expect(markup).toContain('准备候选 → 翻转目标方向 → 干涉增强 → 测量')
    expect(markup).toContain('通过干涉把它变成测量优势')
    expect(markup).toContain('继续看相位实验 →')
  })

  it('uses the required Phase completion summary and free exploration recommendation', () => {
    const markup = completionMarkup('phase')
    expect(markup).toContain('✓ 你已经完成相位实验')
    expect(markup).toContain('概率相同 → 改变方向关系 → 后续行为可能不同')
    expect(markup).toContain('相对相位会影响之后的干涉')
    expect(markup).toContain('开始自由探索 →')
  })

  it('keeps the recommendation order Bell to Grover to Phase to free explore', () => {
    expect(nextCuratedScenarioId('bell')).toBe('search')
    expect(nextCuratedScenarioId('search')).toBe('phase')
    expect(nextCuratedScenarioId('phase')).toBeNull()
  })

  it('resolves every recommendation through the existing stable scenario prompts', () => {
    const search = SCENARIOS.find((scenario) => scenario.id === CURATED_COMPLETIONS.bell.nextScenarioId)
    const phase = SCENARIOS.find((scenario) => scenario.id === CURATED_COMPLETIONS.search.nextScenarioId)
    expect(search?.prompt).toBe('设计一个 2 比特 Grover 搜索电路，搜索目标为 |11>。先创建均匀叠加，再实现标记 |11> 的 Oracle 和扩散算子，最后测量；请使用 OpenQASM 2.0 基础门展开，不定义自定义 gate。')
    expect(phase?.prompt).toBe('生成一个带相对相位的 Bell- 态，不要求测量')
  })

  it('provides follow-up routes to modify, explore, inspect implementation, and return', () => {
    const markup = completionMarkup('bell')
    expect(markup).toContain('返回实验列表')
    expect(markup).toContain('修改当前实验 / 参数')
    expect(markup).toContain('自由探索（Agent）')
    expect(markup).toContain('查看程序实现（Advanced）')
  })

  it('renders the one-shot decoration only while celebration is active', () => {
    expect(completionMarkup('bell', true)).toContain('class="completion-confetti" aria-hidden="true"')
    expect(completionMarkup('bell', false)).not.toContain('class="completion-confetti"')
  })

  it('skips celebration animation when reduced motion is preferred', () => {
    expect(shouldCelebrateCompletion(true)).toBe(false)
    expect(shouldCelebrateCompletion(false)).toBe(true)
  })

  it('keeps the normal next-stage action before the final stage', () => {
    const stage = {
      id: 'start', number: '01', label: '起点', purpose: '准备状态。', action: '初始化。',
      importance: '建立起点。', terminology: null, stepIndex: 0, gateIndices: [0],
      before: snapshot, after: snapshot,
    }
    const model: ExperimentStoryModel = {
      scenarioId: 'bell',
      stages: [stage, { ...stage, id: 'measure', number: '02', label: '测量' }],
    }
    const markup = renderToStaticMarkup(
      <ExperimentStory model={model} activeStageIndex={0} onSelect={() => undefined} onComplete={() => undefined} />,
    )
    expect(markup).toContain('下一阶段 →')
    expect(markup).not.toContain('完成这个实验 ✓')
  })

  it('keeps Program and QASM visible when the right column enters completion', () => {
    const model: ExperimentStoryModel = {
      scenarioId: 'bell',
      stages: [{
        id: 'start', number: '01', label: '起点', purpose: '准备状态。', action: '初始化。',
        importance: '建立起点。', terminology: null, stepIndex: 0, gateIndices: [0],
        before: snapshot, after: snapshot,
      }],
    }
    const markup = renderToStaticMarkup(
      <CuratedWorkspace
        story={model}
        steps={[{
          seq: 0, layer: 'circuit', stage: 'initial_state', executor: 'local', status: 'ok', summary: '初始状态',
          data: { state_after: [{ basis: '0', probability: 1 }] },
        }]}
        qasm={'OPENQASM 2.0;\nqreg q[1];'}
        circuitGoal="Bell 实验"
        activeStoryStage={0}
        activeStep={0}
        qasmOpen
        guideOpen={false}
        completed
        celebrating={false}
        onSelectStoryStage={() => undefined}
        onSelectStep={() => undefined}
        onQasmOpenChange={() => undefined}
        onDismissGuide={() => undefined}
        onOpenGuide={() => undefined}
        onComplete={() => undefined}
        onReturnToStory={() => undefined}
        onContinue={() => undefined}
        onBackToExperiments={() => undefined}
      />,
    )
    expect(markup).toContain('PROGRAM')
    expect(markup).toContain('OpenQASM · 收起代码')
    expect(markup).toContain('✓ 你已经完成 Bell 实验')
    expect(markup).not.toContain('当前阶段要做什么')
  })

  it('opens the recommended experiment in ready state without a result workspace', () => {
    const markup = renderToStaticMarkup(
      <ExplorerScreen initialScenarioId="search" onNavigate={() => undefined} onSelectExperiment={() => undefined} />,
    )
    expect(markup).toContain('Grover 搜索实验已准备好')
    expect(markup).toContain(SCENARIOS.find((scenario) => scenario.id === 'search')!.prompt.replaceAll('>', '&gt;'))
    expect(markup).not.toContain('result-workspace')
    expect(markup).not.toContain('experiment-completion')
  })

  it('opens the final free exploration entry with no inherited prompt or completion', () => {
    const markup = renderToStaticMarkup(
      <ExplorerScreen initialScenarioId={null} onNavigate={() => undefined} onSelectExperiment={() => undefined} />,
    )
    expect(markup).toMatch(/<textarea[^>]*><\/textarea>/)
    expect(markup).not.toContain('experiment-completion')
    expect(markup).not.toContain('继续看 Grover 搜索')
  })
})

describe('Task 13Q generic two-column Explorer', () => {
  const steps: TraceEvent[] = [
    {
      seq: 0, layer: 'circuit', stage: 'initial_state', executor: 'local', status: 'ok', summary: '初始状态',
      data: { state_after: [{ basis: '0', real: 1, imag: 0, probability: 1 }] },
    },
    {
      seq: 1, layer: 'circuit', stage: 'gate_step', executor: 'local', status: 'ok', summary: '执行 H',
      data: {
        operation_index: 0, gate: 'h', qubits: ['q[0]'], gate_description: 'H 让状态形成两个等概率分支。',
        state_before: [{ basis: '0', real: 1, imag: 0, probability: 1 }],
        state_after: [
          { basis: '0', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
          { basis: '1', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
        ],
      },
    },
  ]

  it('keeps the full Generic step explanation inside the shared two-column shell', () => {
    const markup = renderToStaticMarkup(
      <GenericWorkspace
        steps={steps}
        warnings={[]}
        qasm={'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];'}
        circuitGoal="观察一个自定义 H 电路"
        activeStep={1}
        qasmOpen
        autoPlaying={false}
        currentState={steps[1].data.state_after as StateEntry[]}
        currentPurpose="建立两个等概率分支，供后续操作使用。"
        teachingStep={{
          operation_index: 0,
          purpose: '建立两个等概率分支。',
          concept: '叠加',
          concept_explanation: '多个基态共同描述当前量子状态。',
        }}
        hasTeaching
        onSelectStep={() => undefined}
        onQasmOpenChange={() => undefined}
        onToggleAutoPlayback={() => undefined}
      />,
    )

    expect(markup).toContain('data-layout="generic-two-column"')
    expect(markup).not.toContain('class="generic-step-strip"')
    expect(markup).toContain('class="circuit-diagram"')
    expect(markup).toMatch(/<details[^>]*curated-qasm[^>]*open=""/)
    expect(markup).toContain('当前 Gate / Step')
    expect(markup).toContain('建立两个等概率分支，供后续操作使用。')
    expect(markup).toContain('发生了什么？')
    expect(markup).toContain('当前概念')
    expect(markup).toContain('多个基态共同描述当前量子状态')
    expect(markup).toContain('展开技术细节')
    expect(markup).toContain('← 上一步')
    expect(markup).toContain('下一步 →')
    expect(markup).toContain('↺ 重播')
    expect(markup).not.toContain('Ⅱ 暂停')
    expect(markup).toContain('stage-highlighted active')
    expect(markup).not.toContain('CIRCUIT STEPS')
    expect(markup).not.toContain('data-layout="curated-two-column"')
    expect(markup).not.toContain('experiment-completion')
  })
})
