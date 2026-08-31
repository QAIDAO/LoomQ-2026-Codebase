import { FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import type {
  DebugResponse,
  MeasurementMapping,
  StateEntry,
  TeachingStep,
  TraceEvent,
} from './types'
import {
  agentEvents,
  circuitSteps,
  circuitWarnings,
  executableLineIndex,
  extractQasm,
  latestBackendIds,
  isPhaseOnlyChange,
  stateForStep,
  stepTitle,
} from './viewModel'
import { ExperimentStory } from './ExperimentStory'
import { buildExperimentStory, type CuratedScenarioId, type ExperimentStoryModel } from './storyModel'
import { LearnScreen } from './Learn'
import { ExperimentsScreen } from './Experiments'
import { AdvancedCapabilityScreen } from './AdvancedCapability'
import { GlobalNavigation, type AppScreen } from './Navigation'
import { RecoveryGuidance } from './RecoveryGuidance'
import { SCENARIOS, type Scenario } from './scenarios'

export { SCENARIOS } from './scenarios'

const LOADING_STAGES = [
  '理解需求',
  '生成并校验程序',
  '准备可视化解释',
]

export const DEFAULT_RESULT_AUTOPLAY = false
const CURATED_GUIDE_STORAGE_KEY = 'loomq.curated-story-guide-dismissed'

type CuratedCompletionCopy = {
  title: string
  recap: string
  summary: string
  takeaway: {
    phenomenon: string
    concept: string
    importance: string
  }
  nextIntro: string
  nextLabel: string
  nextScenarioId: CuratedScenarioId | null
}

export const CURATED_COMPLETIONS: Record<CuratedScenarioId, CuratedCompletionCopy> = {
  bell: {
    title: '✓ 你已经完成 Bell 实验',
    recap: '叠加 → 建立关联 → 测量',
    summary: '你看到两个量子位不再只能分别理解，而会形成一个需要整体描述的联合状态。',
    takeaway: {
      phenomenon: '两个量子位的读出彼此关联，而不是各自独立地给出结果。',
      concept: '纠缠：多个量子位需要作为一个整体状态来理解。',
      importance: '这种整体关联是量子计算能表达普通独立 bit 难以表达关系的基础。',
    },
    nextIntro: '接下来看看：这种量子状态变化怎样真正参与一次算法。',
    nextLabel: '继续看 Grover 搜索 →',
    nextScenarioId: 'search',
  },
  search: {
    title: '✓ 你已经完成 Grover 搜索实验',
    recap: '准备候选 → 翻转目标方向 → 干涉增强 → 测量',
    summary: '你看到量子搜索不是逐项返回答案，而是先留下方向差异，再通过干涉把它变成测量优势。',
    takeaway: {
      phenomenon: '目标分支没有被直接“找出”，而是在后续步骤中变得更容易被测量到。',
      concept: '干涉：不同分支的方向关系会相互增强或抵消。',
      importance: '它说明量子算法的优势来自安排状态如何组合，而不只是同时尝试更多候选。',
    },
    nextIntro: '刚才真正起作用的关键之一，是“相位”。接下来单独看看它。',
    nextLabel: '继续看相位实验 →',
    nextScenarioId: 'phase',
  },
  phase: {
    title: '✓ 你已经完成相位实验',
    recap: '概率相同 → 改变方向关系 → 后续行为可能不同',
    summary: '你看到“当前测量概率一样”并不等于“量子状态一样”，相对相位会影响之后的干涉。',
    takeaway: {
      phenomenon: '两个状态当前的测量概率相同，但它们在之后的操作中会表现不同。',
      concept: '相对相位：分支之间的方向关系是量子状态的一部分。',
      importance: '它提醒你不要只看概率；相位决定了后续能否形成有用的干涉。',
    },
    nextIntro: '三个正式实验已经看完，现在可以自己描述一个量子程序。',
    nextLabel: '开始自由探索 →',
    nextScenarioId: null,
  },
}

export function nextCuratedScenarioId(scenarioId: CuratedScenarioId): CuratedScenarioId | null {
  return CURATED_COMPLETIONS[scenarioId].nextScenarioId
}

export function shouldCelebrateCompletion(prefersReducedMotion: boolean): boolean {
  return !prefersReducedMotion
}

function shouldShowCuratedGuide(): boolean {
  if (typeof window === 'undefined') return true
  try {
    return window.localStorage.getItem(CURATED_GUIDE_STORAGE_KEY) !== '1'
  } catch {
    return true
  }
}

const AGENT_LABELS: Record<string, string> = {
  intent: '理解需求',
  qasm_candidate: '生成电路',
  target_spec: '提取目标态',
  parser_validation: '本地校验',
  semantic_verification: '语义验证',
  repair_started: '自动修复',
  repair_candidate: '生成修复电路',
  backend_constraints: '提取后端约束',
  backend_selected: '筛选可用后端',
  agent_result: '完成验证',
}

function formatPercent(probability: number): string {
  const value = probability * 100
  return `${value >= 10 ? value.toFixed(1) : value.toFixed(2)}%`
}

function statusIcon(event: TraceEvent): string {
  if (event.status === 'error') return '×'
  if (event.status === 'warning' || event.stage === 'repair_started') return '!'
  if (event.status === 'running') return '…'
  return '✓'
}

function ProbabilityRows({ entries }: { entries: StateEntry[] }) {
  if (!entries.length) {
    return <p className="muted empty-copy">当前步骤没有可展示的概率。</p>
  }
  return (
    <div className="probability-list">
      {entries.map((entry) => (
        <div className="probability-row" key={entry.basis}>
          <code className="basis">|{entry.basis}›</code>
          <div className="probability-track" aria-hidden="true">
            <div
              className="probability-fill"
              style={{ width: `${Math.min(100, Math.max(0, entry.probability * 100))}%` }}
            />
          </div>
          <span className="probability-value">{formatPercent(entry.probability)}</span>
        </div>
      ))}
    </div>
  )
}

function ProbabilityComparison({ event }: { event: TraceEvent }) {
  const after = stateForStep(event)
  const before = Array.isArray(event.data.state_before)
    ? (event.data.state_before as StateEntry[])
    : []
  const allBasis = [...new Set([...before, ...after].map((entry) => entry.basis))]
  const changes = allBasis.flatMap((basis) => {
    const previous = before.find((entry) => entry.basis === basis)?.probability ?? 0
    const current = after.find((entry) => entry.basis === basis)?.probability ?? 0
    return Math.abs(previous - current) > 0.0001
      ? [{ basis, previous, current }]
      : []
  })

  if (event.stage === 'initial_state') {
    return (
      <div className="initial-probability">
        <span className="comparison-label">程序执行前</span>
        <ProbabilityRows entries={after} />
      </div>
    )
  }

  if (event.stage === 'measurement') {
    return (
      <>
        <ProbabilityRows entries={after} />
        <p className="measurement-probability-note">测量读取这个概率分布；这里不伪造一次随机坍缩结果。</p>
      </>
    )
  }

  return (
    <div className="probability-comparison">
      <div className="probability-state before-state">
        <span className="comparison-label">执行前</span>
        <ProbabilityRows entries={before} />
      </div>
      <span className="comparison-arrow">→</span>
      <div className="probability-state after-state">
        <span className="comparison-label">执行后</span>
        <ProbabilityRows entries={after} />
      </div>
      <div className="probability-changes">
        <span>本步变化</span>
        {changes.length ? changes.map((change) => (
          <code key={change.basis}>
            |{change.basis}› {formatPercent(change.previous)} → {formatPercent(change.current)}
          </code>
        )) : <code>{isPhaseOnlyChange(event) ? '概率未变 · 相位已变化' : '状态概率没有变化'}</code>}
      </div>
    </div>
  )
}

function eventQubits(event: TraceEvent): string[] {
  if (Array.isArray(event.data.qubits)) return event.data.qubits as string[]
  if (Array.isArray(event.data.mappings)) {
    return (event.data.mappings as MeasurementMapping[]).map((item) => item.qubit)
  }
  return []
}

export function CircuitDiagram({
  steps,
  activeStep,
  highlightedSteps = [],
  onSelect,
}: {
  steps: TraceEvent[]
  activeStep: number
  highlightedSteps?: number[]
  onSelect: (index: number) => void
}) {
  const qubits = [...new Set(steps.flatMap(eventQubits))]
  const scrollRef = useRef<HTMLDivElement>(null)
  const activeOperationRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const container = scrollRef.current
    const target = activeOperationRef.current
    if (!container || !target) return
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const nextLeft = container.scrollLeft
      + targetRect.left
      - containerRect.left
      - (container.clientWidth - targetRect.width) / 2
      + 24
    // 自动将当前 Gate 移到可视区域中央，用户无需寻找横向滚动条。
    container.scrollTo({ left: Math.max(0, nextLeft), behavior: 'smooth' })
  }, [activeStep, steps.length])

  if (!qubits.length) return null

  return (
    <div className="circuit-diagram">
      <div className="circuit-diagram-heading">
        <span>电路回放</span>
        <small>点击 Gate 跳转</small>
      </div>
      <div className="circuit-scroll" ref={scrollRef}>
        <div className="circuit-labels">
          {qubits.map((qubit) => <code key={qubit}>{qubit}</code>)}
        </div>
        <div className="circuit-operations">
          {steps.map((step, stepIndex) => {
            const involved = eventQubits(step)
            const involvedRows = involved.map((qubit) => qubits.indexOf(qubit)).filter((index) => index >= 0)
            const firstRow = Math.min(...involvedRows)
            const lastRow = Math.max(...involvedRows)
            const gate = String(step.data.gate ?? '').toUpperCase()
            const inStoryStage = highlightedSteps.includes(stepIndex)
            return (
              <button
                className={`circuit-operation${inStoryStage ? ' stage-highlighted' : ''}${stepIndex === activeStep ? ' active' : ''}`}
                key={step.seq}
                ref={stepIndex === activeStep ? activeOperationRef : undefined}
                onClick={() => onSelect(stepIndex)}
                aria-label={`跳转到第 ${stepIndex + 1} 步 ${stepTitle(step)}`}
              >
                {involvedRows.length > 1 && (
                  <i
                    className="gate-connector"
                    style={{ top: `${firstRow * 34 + 17}px`, height: `${(lastRow - firstRow) * 34}px` }}
                  />
                )}
                {qubits.map((qubit, rowIndex) => {
                  const operandIndex = involved.indexOf(qubit)
                  let marker = ''
                  let markerClass = 'gate-box'
                  if (step.stage === 'measurement' && operandIndex >= 0) marker = '测'
                  else if (gate === 'CX' && operandIndex === 0) {
                    marker = '●'
                    markerClass = 'control-dot'
                  } else if (gate === 'CX' && operandIndex === 1) {
                    marker = '⊕'
                    markerClass = 'target-plus'
                  } else if (gate === 'CCX' && operandIndex >= 0 && operandIndex < 2) {
                    marker = '●'
                    markerClass = 'control-dot'
                  } else if (gate === 'CCX' && operandIndex === 2) {
                    marker = '⊕'
                    markerClass = 'target-plus'
                  } else if (gate === 'SWAP' && operandIndex >= 0) {
                    marker = '×'
                    markerClass = 'swap-mark'
                  } else if (operandIndex >= 0) marker = gate || 'G'
                  return (
                    <span className="circuit-wire" key={`${step.seq}-${qubit}`}>
                      {marker && <b className={markerClass}>{marker}</b>}
                      {rowIndex === 0 && <em>{stepIndex + 1}</em>}
                    </span>
                  )
                })}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function TechnicalDetails({ event, state }: { event: TraceEvent; state: StateEntry[] }) {
  const stateBefore = Array.isArray(event.data.state_before)
    ? (event.data.state_before as StateEntry[])
    : []
  const allBasis = [...new Set([...stateBefore, ...state].map((entry) => entry.basis))]

  function amplitude(entry?: StateEntry): string {
    const real = Number(entry?.real ?? 0)
    const imag = Number(entry?.imag ?? 0)
    return `${real >= 0 ? '+' : ''}${real.toFixed(6)}${imag >= 0 ? '+' : ''}${imag.toFixed(6)}i`
  }

  return (
    <details className="technical-details">
      <summary>
        <span>展开技术细节</span>
        <small>{event.stage === 'gate_step' ? `${allBasis.length} 个活跃基态` : '测量事件信息'}</small>
      </summary>
      <div className="detail-content">
        <div className="detail-grid">
          <div className="detail-meta">
            <span>执行器</span>
            <code>LOCAL STATEVECTOR</code>
          </div>
          <div className="detail-meta">
            <span>Operation index</span>
            <code>{String(event.data.operation_index ?? '—')}</code>
          </div>
          <div className="detail-meta">
            <span>事件类型</span>
            <code>{event.stage.toUpperCase()}</code>
          </div>
          <div className="detail-meta">
            <span>状态</span>
            <code>{event.status.toUpperCase()}</code>
          </div>
        </div>
        {event.stage === 'gate_step' && (
          <div className="gate-metadata">
            <div><span>Gate</span><code>{String(event.data.gate ?? '').toUpperCase()}</code></div>
            <div><span>Qubits</span><code>{Array.isArray(event.data.qubits) ? event.data.qubits.join(', ') : '—'}</code></div>
            <div><span>Parameters</span><code>{Array.isArray(event.data.parameters) && event.data.parameters.length ? event.data.parameters.join(', ') : 'none'}</code></div>
          </div>
        )}
        {event.stage === 'gate_step' && (
          <>
            <div className="state-delta">
              <span className="detail-label">PROBABILITY CHANGE</span>
              <div className="delta-header"><span>基态</span><span>执行前</span><span>执行后</span><span>变化</span></div>
              {allBasis.map((basis) => {
                const before = stateBefore.find((entry) => entry.basis === basis)?.probability ?? 0
                const after = state.find((entry) => entry.basis === basis)?.probability ?? 0
                const delta = after - before
                return (
                  <div className="delta-row" key={basis}>
                    <code>|{basis}›</code>
                    <code>{formatPercent(before)}</code>
                    <code>{formatPercent(after)}</code>
                    <code className={delta > 0 ? 'delta-up' : delta < 0 ? 'delta-down' : ''}>
                      {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
                    </code>
                  </div>
                )
              })}
            </div>
            <div className="amplitude-comparison">
              <div className="amplitudes">
                <span className="detail-label">COMPLEX AMPLITUDE · 执行前</span>
                {allBasis.map((basis) => (
                  <div className="amplitude-row" key={basis}>
                    <code>|{basis}›</code>
                    <code>{amplitude(stateBefore.find((entry) => entry.basis === basis))}</code>
                  </div>
                ))}
              </div>
              <div className="amplitudes amplitudes-after">
                <span className="detail-label">COMPLEX AMPLITUDE · 执行后</span>
                {allBasis.map((basis) => (
                  <div className="amplitude-row" key={basis}>
                    <code>|{basis}›</code>
                    <code>{amplitude(state.find((entry) => entry.basis === basis))}</code>
                  </div>
                ))}
              </div>
            </div>
            <p className="phase-note">概率只反映测量可能性；复振幅中的正负号和虚部保留了相对相位。</p>
          </>
        )}
        {event.stage === 'measurement' && (
          <div className="measurement-detail">
            <span className="detail-label">MEASUREMENT SEMANTICS</span>
            <p>{event.summary}</p>
            {(event.data.mappings as MeasurementMapping[] | undefined)?.map((mapping) => (
              <div className="amplitude-row" key={`${mapping.qubit}-${mapping.classical_bit}`}>
                <code>{mapping.qubit}</code>
                <code>→ {mapping.classical_bit}</code>
              </div>
            ))}
            <p className="phase-note">这里展示测量前的确定性概率分布，不伪造单次随机测量结果。</p>
          </div>
        )}
      </div>
    </details>
  )
}

export function ConceptCard({ step }: { step?: TeachingStep }) {
  if (!step?.concept || !step.concept_explanation) return null
  return (
    <div className="concept-card">
      <span>💡 当前概念</span>
      <strong>{step.concept}</strong>
      <p>{step.concept_explanation}</p>
    </div>
  )
}

function StateDetailContent({
  current,
  currentState,
  phaseOnly,
  teachingStep,
  hasTeaching,
}: {
  current: TraceEvent
  currentState: StateEntry[]
  phaseOnly: boolean
  teachingStep?: TeachingStep
  hasTeaching: boolean
}) {
  return (
    <>
      <div className="state-change-copy">
        <span>发生了什么？</span>
        <p>{String(current.data.gate_description ?? current.summary)}</p>
      </div>
      <div className="probability-section">
        <div className="subheading">
          <div><h3>{current.stage === 'measurement' ? '测量前概率' : '概率分布'}</h3><p>每个基态在测量时出现的可能性</p></div>
          <span>{currentState.length} STATES</span>
        </div>
        <ProbabilityComparison event={current} />
      </div>
      {phaseOnly && (
        <div className="phase-only-alert">
          <strong>概率没有变化，但相位发生了变化。</strong>
          <p>相位不会总是立刻体现在测量概率里，但会影响后续干涉。</p>
        </div>
      )}
      <ConceptCard step={teachingStep} />
      {current.stage === 'measurement' && (
        <div className="measurement-card">
          <span className="detail-label">QUANTUM → CLASSICAL</span>
          {(current.data.mappings as MeasurementMapping[] | undefined)?.map((mapping) => (
            <div className="mapping-row" key={`${mapping.qubit}-${mapping.classical_bit}`}>
              <code>{mapping.qubit}</code><span>→</span><code>{mapping.classical_bit}</code>
            </div>
          ))}
        </div>
      )}
      {current.stage !== 'initial_state' && (
        <>
          <TechnicalDetails event={current} state={currentState} />
          {hasTeaching && (
            <p className="teaching-disclaimer">教学解释由模型根据已验证电路生成，不参与正确性判断。</p>
          )}
        </>
      )}
    </>
  )
}

function SidebarProcess({ events }: { events: TraceEvent[] }) {
  return (
    <details className="sidebar-process" open>
      <summary>
        <span>生成与验证过程</span>
        <em>已完成</em>
      </summary>
      <div className="sidebar-process-list">
        {events.map((event) => (
          <div className={`process-row status-${event.status}`} key={event.seq}>
            <span className="summary-icon">{statusIcon(event)}</span>
            <div>
              <strong>{AGENT_LABELS[event.stage] ?? event.stage}</strong>
              <small>{event.executor === 'llm' ? '模型' : '本地'}</small>
              {typeof event.data.fidelity === 'number' && (
                <code>F {event.data.fidelity.toFixed(3)}</code>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  )
}

function BackendResult({ events, reply }: { events: TraceEvent[]; reply: string }) {
  const ids = latestBackendIds(events)
  const constraintEvent = events.find((event) => event.stage === 'backend_constraints')
  return (
    <section className="backend-result panel">
      <div className="panel-heading">
        <span className="eyebrow">BACKEND SELECTION</span>
        <h2>本地能力表筛选结果</h2>
        <p>模型只负责提取约束；canonical backend ID 由 LoomQ 在本地决定。</p>
      </div>
      <div className="backend-body">
        <div className="constraint-card">
          <span>模型提取的约束</span>
          <div className="constraint-chips">
            {constraintEvent?.data.min_qubits != null && (
              <code>至少 {String(constraintEvent.data.min_qubits)} qubits</code>
            )}
            {constraintEvent?.data.require_no_queue === true && <code>零排队</code>}
            {constraintEvent?.data.require_qpu === true && <code>真实量子硬件</code>}
            {constraintEvent?.data.cost_policy !== 'unspecified' &&
              constraintEvent?.data.cost_policy != null && (
                <code>{String(constraintEvent.data.cost_policy)}</code>
              )}
          </div>
        </div>
        <div className="backend-list">
          {ids.length ? ids.map((id) => (
            <div className="backend-row" key={id}>
              <span className="backend-status">✓</span>
              <code>{id}</code>
              <span>满足全部约束</span>
            </div>
          )) : <p className="warning-callout">当前没有同时满足全部约束的后端。</p>}
        </div>
        <p className="backend-reply">{reply}</p>
      </div>
    </section>
  )
}

export function ScenarioContext({ scenario }: { scenario: Scenario }) {
  return (
    <section className="scenario-context" aria-label="示例背景">
      <div className="context-heading">
        <span>你正在理解什么？</span>
        <strong>{scenario.title}</strong>
        <em>{scenario.tag}</em>
      </div>
      <div className="context-item">
        <span>普通程序怎么理解？</span>
        <p>{scenario.ordinary}</p>
      </div>
      <div className="context-item">
        <span>量子版本有什么不同？</span>
        <p>{scenario.quantum}</p>
      </div>
      <div className="context-item focus-item">
        <span>这次重点看什么？</span>
        <p>{scenario.focus}</p>
      </div>
    </section>
  )
}

export function LoadingProcess() {
  return (
    <div className="loading-process" aria-label="LoomQ 正在准备量子程序">
      <div className="loading-process-heading">
        <span className="loading-orbit" aria-hidden="true">⌁</span>
        <div>
          <h2>正在准备你的量子实验</h2>
          <p>LoomQ 正在把自然语言需求变成一个经过验证、可以逐步解释的量子程序。</p>
        </div>
      </div>
      <ol>
        {LOADING_STAGES.map((stage) => (
          <li key={stage}>
            <i aria-hidden="true" />
            <span>{stage}</span>
          </li>
        ))}
      </ol>
      <small>请求完成后会一次性展示真实结果。</small>
    </div>
  )
}

export function EmptyWorkspace({ loading = false, scenario }: { loading?: boolean; scenario?: Scenario }) {
  if (loading) {
    return (
      <div className="workspace empty-workspace loading-workspace">
        <div className="empty-main panel"><LoadingProcess /></div>
      </div>
    )
  }

  return (
    <div className="workspace idle-workspace">
      <div className="empty-main panel">
        {scenario ? (
          <>
            <div className="idle-status ready">
              <span>{scenario.tag} · READY</span>
              <h2>{scenario.id === 'bell' ? 'Bell 实验已准备好' : scenario.id === 'search' ? 'Grover 搜索实验已准备好' : scenario.id === 'phase' ? '相位实验已准备好' : '实验已准备好'}</h2>
              <p>LoomQ 会先生成并验证量子程序，再带你逐步查看状态变化。</p>
              <strong>尚未运行 · 点击上方“运行量子程序”开始</strong>
            </div>
          </>
        ) : (
          <div className="idle-status free">
            <div className="empty-icon">⌁</div>
            <h2>描述你想探索的量子程序</h2>
            <p>例如：让两个量子比特形成 Bell 态并测量。</p>
            <strong>在上方输入自然语言实验需求，再点击“运行量子程序”。</strong>
          </div>
        )}
      </div>
    </div>
  )
}

export function ProgramPanel({
  steps,
  qasm,
  circuitGoal,
  activeStep,
  highlightedSteps,
  qasmOpen,
  warnings = [],
  onSelectStep,
  onQasmOpenChange,
}: {
  steps: TraceEvent[]
  qasm: string
  circuitGoal: string
  activeStep: number
  highlightedSteps: number[]
  qasmOpen: boolean
  warnings?: TraceEvent[]
  onSelectStep: (index: number) => void
  onQasmOpenChange: (open: boolean) => void
}) {
  const activeLine = steps[activeStep]
    ? executableLineIndex(qasm, Number(steps[activeStep].data.operation_index ?? -1))
    : -1
  const highlightedLines = new Set(highlightedSteps.flatMap((stepIndex) => {
    const step = steps[stepIndex]
    if (!step) return []
    const line = executableLineIndex(qasm, Number(step.data.operation_index ?? -1))
    return line >= 0 ? [line] : []
  }))
  const firstHighlightedLine = highlightedLines.size ? Math.min(...highlightedLines) : -1
  const codeViewRef = useRef<HTMLDivElement>(null)
  const firstHighlightedLineRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = codeViewRef.current
    const target = firstHighlightedLineRef.current
    if (!qasmOpen || !container || !target) return
    // 等面板完成本轮布局，再依据代码行在滚动容器中的真实位置定位。
    const frame = window.requestAnimationFrame(() => {
      const containerRect = container.getBoundingClientRect()
      const targetRect = target.getBoundingClientRect()
      const nextTop = container.scrollTop
        + targetRect.top
        - containerRect.top
        - (container.clientHeight - targetRect.height) / 2
      // 立即落到当前高亮范围，避免 smooth scroll 在快速切换阶段时被下一次滚动取消。
      container.scrollTo({ top: Math.max(0, nextTop), behavior: 'auto' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [activeStep, firstHighlightedLine, qasmOpen])

  return (
    <section className="curated-program program-panel panel" aria-label="Program · Circuit 与 QASM">
      <header className="curated-program-heading">
        <div><span>PROGRAM</span><strong>电路与源码</strong></div>
        <p><i>✓</i> 已生成并通过 LoomQ 验证</p>
      </header>
      <div className="curated-program-goal"><span>实验目标</span><p>{circuitGoal}</p></div>
      {warnings.map((warning) => (
        <div className="generic-program-warning" key={warning.seq}>
          <span>!</span><p>{warning.stage === 'statevector_skipped'
            ? '电路规模较大，当前不展开 statevector；生成与验证结果仍然有效。'
            : warning.summary}</p>
        </div>
      ))}
      <CircuitDiagram
        steps={steps}
        activeStep={activeStep}
        highlightedSteps={highlightedSteps}
        onSelect={onSelectStep}
      />
      <details
        className="qasm-disclosure curated-qasm"
        open={qasmOpen}
        onToggle={(event) => onQasmOpenChange(event.currentTarget.open)}
      >
        <summary>
          <span><b className="qasm-icon">Q</b>{qasmOpen ? 'OpenQASM · 收起代码' : 'OpenQASM · 展开代码'}</span>
          <small>{highlightedSteps.length > 1 ? '当前阶段范围已标出' : '当前步骤已标出'}</small>
        </summary>
        <div className="code-view" ref={codeViewRef} role="region" aria-label="完整 OpenQASM 程序">
          {qasm.split('\n').map((line, index) => {
            const inHighlightedRange = highlightedLines.has(index)
            const isActive = index === activeLine
            return (
              <div
                className={`code-line${inHighlightedRange ? ' stage-highlighted' : ''}${isActive ? ' highlighted' : ''}`}
                key={`${index}-${line}`}
                ref={index === firstHighlightedLine ? firstHighlightedLineRef : undefined}
              >
                <span className="line-number">{index + 1}</span>
                <code>{line || ' '}</code>
                {isActive && <span className="execution-marker">▶</span>}
              </div>
            )
          })}
        </div>
      </details>
      </section>
  )
}

export function ExperimentCompletion({
  scenarioId,
  celebrating,
  onReturnToStory,
  onModifyExperiment = () => undefined,
  onFreeExplore = () => undefined,
  onContinue,
  onBackToExperiments,
}: {
  scenarioId: CuratedScenarioId
  celebrating: boolean
  onReturnToStory: () => void
  onModifyExperiment?: () => void
  onFreeExplore?: () => void
  onContinue: () => void
  onBackToExperiments: () => void
}) {
  const completion = CURATED_COMPLETIONS[scenarioId]

  return (
    <section className="experiment-completion" aria-live="polite">
      {celebrating && (
        <div className="completion-confetti" aria-hidden="true">
          {Array.from({ length: 12 }, (_, index) => <i key={index} />)}
        </div>
      )}
      <div className="completion-check" aria-hidden="true">✓</div>
      <p className="completion-kicker">EXPERIMENT COMPLETE</p>
      <h2>{completion.title}</h2>
      <p className="completion-recap">{completion.recap}</p>
      <p className="completion-summary">{completion.summary}</p>
      <section className="completion-takeaway" aria-labelledby="completion-takeaway-heading">
        <header><span>TAKEAWAY</span><h3 id="completion-takeaway-heading">你学到了什么？</h3></header>
        <dl>
          <div><dt>观察到的现象</dt><dd>{completion.takeaway.phenomenon}</dd></div>
          <div><dt>对应量子概念</dt><dd>{completion.takeaway.concept}</dd></div>
          <div><dt>为什么重要</dt><dd>{completion.takeaway.importance}</dd></div>
        </dl>
      </section>
      <div className="completion-next">
        <p>{completion.nextIntro}</p>
        <button className="completion-primary" onClick={onContinue}>{completion.nextLabel}</button>
      </div>
      <nav className="completion-actions" aria-label="实验完成后的操作">
        <button onClick={onModifyExperiment}>修改当前实验 / 参数</button>
        <button onClick={onFreeExplore}>自由探索（Agent）</button>
        <button onClick={onReturnToStory}>查看程序实现（Advanced）</button>
        <button onClick={onBackToExperiments}>返回实验列表</button>
      </nav>
    </section>
  )
}

export function CuratedWorkspace({
  story,
  steps,
  qasm,
  circuitGoal,
  activeStoryStage,
  activeStep,
  qasmOpen,
  guideOpen,
  completed,
  celebrating,
  onSelectStoryStage,
  onSelectStep,
  onQasmOpenChange,
  onDismissGuide,
  onOpenGuide,
  onComplete,
  onReturnToStory,
  onModifyExperiment,
  onFreeExplore,
  onContinue,
  onBackToExperiments,
}: {
  story: ExperimentStoryModel
  steps: TraceEvent[]
  qasm: string
  circuitGoal: string
  activeStoryStage: number
  activeStep: number
  qasmOpen: boolean
  guideOpen: boolean
  completed: boolean
  celebrating: boolean
  onSelectStoryStage: (index: number) => void
  onSelectStep: (index: number) => void
  onQasmOpenChange: (open: boolean) => void
  onDismissGuide: () => void
  onOpenGuide: () => void
  onComplete: () => void
  onReturnToStory: () => void
  onModifyExperiment?: () => void
  onFreeExplore?: () => void
  onContinue: () => void
  onBackToExperiments: () => void
}) {
  const stage = story.stages[Math.min(story.stages.length - 1, Math.max(0, activeStoryStage))]

  return (
    <section className="workspace result-workspace two-column-workspace curated-workspace" data-layout="curated-two-column">
      <ProgramPanel
        steps={steps}
        qasm={qasm}
        circuitGoal={circuitGoal}
        activeStep={activeStep}
        highlightedSteps={stage.gateIndices}
        qasmOpen={qasmOpen}
        onSelectStep={onSelectStep}
        onQasmOpenChange={onQasmOpenChange}
      />

      <section className="curated-story-panel panel" aria-label="Story · 实验解释">
        <header className="curated-story-heading">
          <div><span>{completed ? 'COMPLETE' : 'STORY'}</span><strong>{completed ? '实验完成' : '理解这段程序'}</strong></div>
          {!completed && <button onClick={onOpenGuide}>如何阅读这个页面？</button>}
        </header>
        {!completed && guideOpen && (
          <aside className="curated-guide" aria-label="Story Mode 新手引导">
            <ol>
              <li><b>1</b><span>先看右边：一次只解释一个阶段</span></li>
              <li><b>2</b><span>看懂后点“下一阶段”继续</span></li>
              <li><b>3</b><span>想看实现时，左边 Circuit 与 QASM 会同步标出当前阶段</span></li>
            </ol>
            <button onClick={onDismissGuide}>知道了</button>
          </aside>
        )}
        {completed ? (
          <ExperimentCompletion
            scenarioId={story.scenarioId}
            celebrating={celebrating}
            onReturnToStory={onReturnToStory}
            onModifyExperiment={onModifyExperiment}
            onFreeExplore={onFreeExplore}
            onContinue={onContinue}
            onBackToExperiments={onBackToExperiments}
          />
        ) : (
          <ExperimentStory
            model={story}
            activeStageIndex={activeStoryStage}
            onSelect={onSelectStoryStage}
            onComplete={onComplete}
          />
        )}
      </section>
    </section>
  )
}

export function GenericWorkspace({
  steps,
  warnings,
  qasm,
  circuitGoal,
  activeStep,
  qasmOpen,
  autoPlaying,
  currentState,
  currentPurpose,
  teachingStep,
  hasTeaching,
  onSelectStep,
  onQasmOpenChange,
  onToggleAutoPlayback,
}: {
  steps: TraceEvent[]
  warnings: TraceEvent[]
  qasm: string
  circuitGoal: string
  activeStep: number
  qasmOpen: boolean
  autoPlaying: boolean
  currentState: StateEntry[]
  currentPurpose: string
  teachingStep?: TeachingStep
  hasTeaching: boolean
  onSelectStep: (index: number) => void
  onQasmOpenChange: (open: boolean) => void
  onToggleAutoPlayback: () => void
}) {
  const current = steps[activeStep]
  if (!current) {
    return (
      <section className="workspace result-workspace generic-workspace" data-layout="generic-two-column">
        <div className="panel-empty panel">没有可展示的电路步骤。</div>
      </section>
    )
  }
  const activeLine = executableLineIndex(qasm, Number(current.data.operation_index ?? -1))
  const currentStatement = activeLine >= 0 ? qasm.split('\n')[activeLine]?.trim() ?? '' : ''
  const phaseOnly = isPhaseOnlyChange(current)

  return (
    <section className="workspace result-workspace two-column-workspace generic-workspace" data-layout="generic-two-column">
      <ProgramPanel
        steps={steps}
        qasm={qasm}
        circuitGoal={circuitGoal}
        activeStep={activeStep}
        highlightedSteps={[activeStep]}
        qasmOpen={qasmOpen}
        warnings={warnings}
        onSelectStep={onSelectStep}
        onQasmOpenChange={onQasmOpenChange}
      />

      <section className="generic-explain-panel panel" aria-label="Explain · 当前步骤解释">
        <header className="curated-story-heading generic-explain-heading">
          <div><span>EXPLAIN</span><strong>理解当前步骤</strong></div>
          <small>{activeStep + 1} / {steps.length}</small>
        </header>
        <article className="generic-current-step">
          <span>当前 Gate / Step</span>
          <h2>{stepTitle(current)}</h2>
          {current.stage !== 'initial_state' && currentStatement && <code>{currentStatement}</code>}
          <div>
            <strong>为什么这里需要它？</strong>
            <p>{currentPurpose}</p>
          </div>
        </article>
        <div className="generic-state-content">
          <StateDetailContent
            current={current}
            currentState={currentState}
            phaseOnly={phaseOnly}
            teachingStep={teachingStep}
            hasTeaching={hasTeaching}
          />
        </div>
        <nav className="generic-footer-navigation" aria-label="逐步查看电路">
          <button
            onClick={() => onSelectStep(Math.max(0, activeStep - 1))}
            disabled={activeStep === 0}
          >← 上一步</button>
          <button
            className={`generic-auto-play${autoPlaying ? ' playing' : ''}`}
            onClick={onToggleAutoPlayback}
          >{autoPlaying ? 'Ⅱ 暂停' : activeStep >= steps.length - 1 ? '↺ 重播' : '▶ 自动'}</button>
          <button
            onClick={() => onSelectStep(Math.min(steps.length - 1, activeStep + 1))}
            disabled={activeStep >= steps.length - 1}
          >下一步 →</button>
        </nav>
      </section>
    </section>
  )
}

export function ExplorerScreen({
  initialScenarioId,
  onNavigate,
  onSelectExperiment,
}: {
  initialScenarioId: string | null
  onNavigate: (screen: AppScreen) => void
  onSelectExperiment: (scenarioId: CuratedScenarioId | null) => void
}) {
  const initialScenario = SCENARIOS.find((scenario) => scenario.id === initialScenarioId)
  const [prompt, setPrompt] = useState(initialScenario?.prompt ?? '')
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(initialScenario?.id ?? null)
  const [result, setResult] = useState<DebugResponse | null>(null)
  const [activeStep, setActiveStep] = useState(0)
  const [activeStoryStage, setActiveStoryStage] = useState(0)
  const [autoPlaying, setAutoPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resultPrompt, setResultPrompt] = useState('')
  const [qasmOpen, setQasmOpen] = useState(true)
  const [curatedQasmOpen, setCuratedQasmOpen] = useState(true)
  const [curatedGuideOpen, setCuratedGuideOpen] = useState(shouldShowCuratedGuide)
  const [storyCompleted, setStoryCompleted] = useState(false)
  const [celebrating, setCelebrating] = useState(false)
  const promptInputRef = useRef<HTMLTextAreaElement>(null)

  const steps = useMemo(() => circuitSteps(result?.events ?? []), [result])
  const warnings = useMemo(() => circuitWarnings(result?.events ?? []), [result])
  const agents = useMemo(() => agentEvents(result?.events ?? []), [result])
  const qasm = useMemo(() => extractQasm(result?.events ?? []), [result])
  const current = steps[activeStep]
  const currentState = current ? stateForStep(current) : []
  const backendMode = result != null && steps.length === 0 && agents.some(
    (event) => event.stage === 'backend_selected',
  )
  const selectedScenario = SCENARIOS.find((scenario) => scenario.id === selectedScenarioId)
  const experimentStory = useMemo(
    () => buildExperimentStory(selectedScenarioId, steps),
    [selectedScenarioId, steps],
  )
  const currentStoryStage = experimentStory?.stages[activeStoryStage] ?? null

  useEffect(() => {
    if (!experimentStory) return
    // 正式实验完成后停在第一个可解释阶段，不自动逐 Gate 播放。
    setActiveStoryStage(0)
    setActiveStep(experimentStory.stages[0].stepIndex)
    setAutoPlaying(false)
    setStoryCompleted(false)
    setCelebrating(false)
  }, [experimentStory])

  useEffect(() => {
    if (!celebrating) return
    // 礼花只播放一次并在 800ms 后退出，不参与任何实验状态计算。
    const timer = window.setTimeout(() => setCelebrating(false), 800)
    return () => window.clearTimeout(timer)
  }, [celebrating])

  useEffect(() => {
    if (!autoPlaying || steps.length < 2) return
    if (activeStep >= steps.length - 1) {
      setAutoPlaying(false)
      return
    }
    // Trace 已完整返回；这里仅用慢速定时器自动回放现有步骤。
    const timer = window.setTimeout(() => {
      setActiveStep((step) => Math.min(steps.length - 1, step + 1))
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [activeStep, autoPlaying, steps.length])

  async function runDebug(event?: FormEvent) {
    event?.preventDefault()
    const requestPrompt = prompt.trim()
    if (!requestPrompt || loading) return
    // 新请求必须先退出上一轮会话，失败时也不能继续展示旧电路的结果。
    setResult(null)
    setResultPrompt('')
    setActiveStep(0)
    setActiveStoryStage(0)
    setAutoPlaying(false)
    setQasmOpen(true)
    setCuratedQasmOpen(true)
    setStoryCompleted(false)
    setCelebrating(false)
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/debug', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: requestPrompt }),
      })
      const payload = (await response.json()) as DebugResponse & { error?: string }
      if (!response.ok) throw new Error(payload.error)
      setResult(payload)
      setResultPrompt(requestPrompt)
      setActiveStep(0)
      setActiveStoryStage(0)
      setAutoPlaying(DEFAULT_RESULT_AUTOPLAY)
    } catch {
      setError('这次运行没有完成，请检查模型配置后重试。')
    } finally {
      setLoading(false)
    }
  }

  function keyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      void runDebug()
    }
  }

  function modifyExplorerInput() {
    setError('')
    promptInputRef.current?.focus()
  }

  function selectStep(index: number) {
    setAutoPlaying(false)
    setActiveStep(index)
  }

  function dismissCuratedGuide() {
    setCuratedGuideOpen(false)
    if (typeof window === 'undefined') return
    try {
      // 只保存纯 UI 引导状态，不记录实验数据或用户输入。
      window.localStorage.setItem(CURATED_GUIDE_STORAGE_KEY, '1')
    } catch {
      // 存储不可用时仍允许本次会话正常关闭引导。
    }
  }

  function selectStoryStage(index: number) {
    if (!experimentStory) return
    const nextIndex = Math.min(experimentStory.stages.length - 1, Math.max(0, index))
    setAutoPlaying(false)
    setActiveStoryStage(nextIndex)
    setActiveStep(experimentStory.stages[nextIndex].stepIndex)
  }

  function completeStory() {
    if (!experimentStory) return
    setStoryCompleted(true)
    const reduceMotion = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    setCelebrating(shouldCelebrateCompletion(Boolean(reduceMotion)))
  }

  function continueExperiment() {
    if (!experimentStory) return
    // 场景切换交给 App 重新挂载 Explorer，确保旧结果与步骤不会残留。
    onSelectExperiment(nextCuratedScenarioId(experimentStory.scenarioId))
  }

  function modifyCurrentExperiment() {
    // 回到已有输入区保留当前目标，用户可以直接改写描述后重新运行。
    setResult(null)
    setResultPrompt('')
    setActiveStep(0)
    setActiveStoryStage(0)
    setAutoPlaying(false)
    setStoryCompleted(false)
    setCelebrating(false)
    promptInputRef.current?.focus()
  }

  function startFreeExplore() {
    modifyCurrentExperiment()
    setSelectedScenarioId(null)
    setPrompt('')
  }

  function toggleAutoPlayback() {
    if (autoPlaying) {
      setAutoPlaying(false)
      return
    }
    if (activeStep >= steps.length - 1) setActiveStep(0)
    setAutoPlaying(true)
  }

  const teachingStep = current && typeof current.data.operation_index === 'number'
    ? result?.teaching?.steps.find(
      (step) => step.operation_index === current.data.operation_index,
    )
    : undefined
  const currentPurpose = current?.stage === 'initial_state'
    ? '先确认程序的共同起点，后续每个 Gate 的变化都会与这个初始状态比较。'
    : teachingStep?.purpose ?? String(current?.data.gate_description ?? current?.summary ?? '')
  const circuitGoal = result?.teaching?.circuit_goal || resultPrompt

  return (
    <main className="app-shell">
      <GlobalNavigation current="explorer" onNavigate={onNavigate} />
      <header className="topbar">
        <div className="brand-copy">
          <div><strong>Quantum Explorer</strong><em>MVP</em></div>
          <p>像阅读代码一样，理解量子程序每一步如何改变状态</p>
        </div>
        <div className={`connection ${loading ? 'loading' : ''}`}>
          <i /> {loading ? '正在生成并验证量子程序…' : 'LOCAL EXPLORATION'}
        </div>
      </header>

      <section className={`request-section ${result ? 'result-mode' : loading ? 'loading-mode' : ''}`}>
        <form className="prompt-form" onSubmit={runDebug}>
          <span className="prompt-glyph">›_</span>
          <textarea
            aria-label="描述你想探索的量子程序"
            ref={promptInputRef}
            value={prompt}
            onChange={(event) => {
              setPrompt(event.target.value)
              setSelectedScenarioId(null)
            }}
            onKeyDown={keyDown}
            rows={1}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !prompt.trim()}>
            <span>{loading ? '运行中' : '运行量子程序'}</span>
            {!loading && <kbd>⌘ ↵</kbd>}
          </button>
        </form>
        {error && (
          <RecoveryGuidance
            title="这次量子程序没有准备完成"
            whatHappened="LoomQ 没有得到可以安全展示的实验结果。"
            possibleReason="模型服务暂时不可用、网络连接中断，或本地验证环境尚未准备好。"
            nextStep="可以直接重试；若仍未完成，请修改实验描述后再运行。"
            onRetry={() => void runDebug()}
            onModify={modifyExplorerInput}
            retryLabel="重试运行"
            modifyLabel="修改实验描述"
          />
        )}
      </section>

      {!result && <EmptyWorkspace loading={loading} scenario={selectedScenario} />}

      {result && backendMode && (
        <div className="backend-layout">
          <aside className="sidebar panel">
            <SidebarProcess events={agents} />
          </aside>
          <BackendResult events={agents} reply={result.reply} />
        </div>
      )}

      {result && !backendMode && experimentStory && currentStoryStage && current && (
        <CuratedWorkspace
          story={experimentStory}
          steps={steps}
          qasm={qasm}
          circuitGoal={circuitGoal}
          activeStoryStage={activeStoryStage}
          activeStep={activeStep}
          qasmOpen={curatedQasmOpen}
          guideOpen={curatedGuideOpen}
          completed={storyCompleted}
          celebrating={celebrating}
          onSelectStoryStage={selectStoryStage}
          onSelectStep={selectStep}
          onQasmOpenChange={setCuratedQasmOpen}
          onDismissGuide={dismissCuratedGuide}
          onOpenGuide={() => setCuratedGuideOpen(true)}
          onComplete={completeStory}
          onReturnToStory={() => {
            setStoryCompleted(false)
            setCelebrating(false)
            setCuratedQasmOpen(true)
          }}
          onModifyExperiment={modifyCurrentExperiment}
          onFreeExplore={startFreeExplore}
          onContinue={continueExperiment}
          onBackToExperiments={() => onNavigate('experiments')}
        />
      )}

      {result && !backendMode && (!experimentStory || !currentStoryStage || !current) && (
        <GenericWorkspace
          steps={steps}
          warnings={warnings}
          qasm={qasm}
          circuitGoal={circuitGoal}
          activeStep={activeStep}
          qasmOpen={qasmOpen}
          autoPlaying={autoPlaying}
          currentState={currentState}
          currentPurpose={currentPurpose}
          teachingStep={teachingStep}
          hasTeaching={Boolean(result.teaching)}
          onSelectStep={selectStep}
          onQasmOpenChange={setQasmOpen}
          onToggleAutoPlayback={toggleAutoPlayback}
        />
      )}
    </main>
  )
}

function App() {
  const [screen, setScreen] = useState<AppScreen>('learn')
  const [selectedExperimentId, setSelectedExperimentId] = useState<string | null>(null)

  function navigate(nextScreen: AppScreen) {
    setScreen(nextScreen)
  }

  // 页面选择只传递稳定 prompt，不会自动运行或触发后端请求。
  if (screen === 'learn') {
    return <LearnScreen onStart={() => navigate('experiments')} onNavigate={navigate} />
  }
  if (screen === 'experiments') {
    return (
      <ExperimentsScreen
        onNavigate={navigate}
        onSelect={(scenario) => {
          setSelectedExperimentId(scenario.id)
          navigate('explorer')
        }}
        onFreeExplore={() => {
          setSelectedExperimentId(null)
          navigate('explorer')
        }}
      />
    )
  }
  if (screen === 'repair' || screen === 'backend') {
    return <AdvancedCapabilityScreen kind={screen} onNavigate={navigate} />
  }
  return (
    <ExplorerScreen
      key={`explorer-${selectedExperimentId ?? 'free'}`}
      initialScenarioId={selectedExperimentId}
      onNavigate={navigate}
      onSelectExperiment={(scenarioId) => {
        setSelectedExperimentId(scenarioId)
        setScreen('explorer')
      }}
    />
  )
}

export default App
