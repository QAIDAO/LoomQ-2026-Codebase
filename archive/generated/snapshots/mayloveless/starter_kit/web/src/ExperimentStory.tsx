import type { CSSProperties } from 'react'
import type { ExperimentStoryModel, ExperimentStoryStage, StorySnapshot, StoryValue } from './storyModel'

function formatStoryPercent(probability: number): string {
  const value = probability * 100
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)}%`
}

function phaseDegrees(value: StoryValue): number {
  return ((value.phase ?? 0) * 180) / Math.PI
}

function effectLabel(
  model: ExperimentStoryModel,
  stage: ExperimentStoryStage,
  value: StoryValue,
  position: 'before' | 'after',
): string | null {
  if (position !== 'after') return null
  if (model.scenarioId === 'search' && stage.id === 'oracle' && value.basis === '11') return '方向翻转'
  if (model.scenarioId === 'search' && stage.id === 'diffusion') {
    if (value.basis === '11') return '建设性增强'
    if (value.basis === '00') return '其他分支部分抵消'
  }
  if (model.scenarioId === 'bell' && stage.id === 'correlate') return '关联分支'
  if (model.scenarioId === 'phase' && stage.id === 'turn' && Math.abs(value.phase ?? 0) > 0.1) return '方向已改变'
  return null
}

type StoryConcept = { name: string; english: string; explanation: string }

function storyConceptFor(model: ExperimentStoryModel, stage: ExperimentStoryStage): StoryConcept | null {
  const key = `${model.scenarioId}:${stage.id}`
  const concepts: Record<string, StoryConcept> = {
    'bell:branch': {
      name: '叠加', english: 'Superposition',
      explanation: '一个确定分支变成多个共同描述当前状态的分支。',
    },
    'bell:correlate': {
      name: '纠缠', english: 'Entanglement',
      explanation: '两个量子位现在必须作为一个联合状态理解，不能再分别描述。',
    },
    'bell:measure': {
      name: '测量', english: 'Measurement',
      explanation: '量子状态被读取为经典结果；重复运行后才能看到关联分布。',
    },
    'search:uniform': {
      name: '叠加', english: 'Superposition',
      explanation: '多个候选分支同时存在，并且此时拥有相同的振幅大小。',
    },
    'search:oracle': {
      name: '相位翻转', english: 'Phase Flip',
      explanation: '振幅大小没有改变，但目标分支与其他分支的方向关系反了。现在测量还看不出优势，后续干涉时才会显现。',
    },
    'search:diffusion': {
      name: '干涉', english: 'Interference',
      explanation: '不同方向的振幅重新组合，让目标分支增强、其他候选部分抵消。',
    },
    'search:measurement': {
      name: '测量', english: 'Measurement',
      explanation: '最终振幅优势在读取时转化成目标结果更高的出现概率。',
    },
    'phase:turn': {
      name: '相对相位', english: 'Relative Phase',
      explanation: '分支大小相同，但彼此的方向关系已经改变；这个差异会影响后续干涉。',
    },
  }
  return concepts[key] ?? null
}

function StorySnapshotView({
  model,
  stage,
  snapshot,
  bases,
  position,
}: {
  model: ExperimentStoryModel
  stage: ExperimentStoryStage
  snapshot: StorySnapshot
  bases: string[]
  position: 'before' | 'after'
}) {
  return (
    <div className={`story-snapshot story-${snapshot.mode}`}>
      {bases.map((basis) => {
        const value = snapshot.values.find((entry) => entry.basis === basis) ?? {
          basis,
          magnitude: snapshot.mode === 'wave' ? 0 : null,
          phase: snapshot.mode === 'wave' ? 0 : null,
          probability: 0,
        }
        const magnitude = value.magnitude ?? Math.sqrt(Math.max(0, value.probability))
        const effect = effectLabel(model, stage, value, position)
        return (
          <div className={`story-branch${value.probability <= 1e-8 ? ' is-quiet' : ''}`} key={basis}>
            <code>|{basis}⟩</code>
            {snapshot.mode === 'probability' ? (
              <div className="story-probability-track" aria-label={`${basis} 的概率 ${formatStoryPercent(value.probability)}`}>
                <i style={{ width: `${Math.min(100, Math.max(0, value.probability * 100))}%` }} />
              </div>
            ) : (
              <div className="story-wave-path" aria-label={`${basis} 的振幅方向 ${Math.round(phaseDegrees(value))} 度`}>
                <i />
                <span
                  className="story-wave"
                  style={{
                    '--story-wave-scale': String(Math.max(0.08, magnitude)),
                    opacity: magnitude <= 1e-8 ? 0 : Math.max(0.35, Math.min(1, magnitude + 0.25)),
                  } as CSSProperties}
                >∿∿∿</span>
                <b style={{ transform: `rotate(${phaseDegrees(value)}deg)` }}>→</b>
              </div>
            )}
            <small>{formatStoryPercent(value.probability)}</small>
            {effect && <em>{effect}</em>}
          </div>
        )
      })}
    </div>
  )
}

export function ExperimentStory({
  model,
  activeStageIndex,
  onSelect,
  onComplete,
}: {
  model: ExperimentStoryModel
  activeStageIndex: number
  onSelect: (stageIndex: number) => void
  onComplete: () => void
}) {
  const safeIndex = Math.min(model.stages.length - 1, Math.max(0, activeStageIndex))
  const stage = model.stages[safeIndex]
  const concept = storyConceptFor(model, stage)
  const bases = [...new Set([...stage.before.values, ...stage.after.values].map((entry) => entry.basis))].sort()

  return (
    <section className={`experiment-story story-${model.scenarioId}`} aria-label={`${model.scenarioId} 实验故事模式`}>
      <nav className="story-stage-nav" aria-label="实验语义阶段">
        {model.stages.map((item, index) => (
          <button
            className={index === safeIndex ? 'active' : ''}
            key={item.id}
            onClick={() => onSelect(index)}
          >
            <span>{item.number}</span>
            <strong>{item.label}</strong>
          </button>
        ))}
      </nav>

      <header className="story-stage-heading">
        <span>当前阶段要做什么</span>
        <h2>{stage.label}</h2>
        <p>{stage.purpose}</p>
      </header>

      <div className="story-visual-key" aria-label="如何理解这张示意图">
        <b aria-hidden="true">!</b>
        <div>
          <strong>如何理解这张示意图</strong>
          <p>路径代表分支 · 波形方向代表相对相位 · 波形强弱代表振幅</p>
          <small>仅用于帮助理解量子状态，不代表真实光子路径。</small>
        </div>
      </div>

      <div className="story-change-frame">
        <section>
          <span>执行前</span>
          <StorySnapshotView model={model} stage={stage} snapshot={stage.before} bases={bases} position="before" />
        </section>
        <div className="story-operation">
          <span>做了什么</span>
          <i>→</i>
          <p>{stage.action}</p>
          <i>→</i>
        </div>
        <section>
          <span>执行后</span>
          <StorySnapshotView model={model} stage={stage} snapshot={stage.after} bases={bases} position="after" />
        </section>
      </div>

      <footer className="story-importance">
        <span>为什么重要</span>
        <strong>{stage.importance}</strong>
        {stage.terminology && <p>{stage.terminology}</p>}
      </footer>
      {concept && (
        <aside className="story-concept">
          <span>💡 当前概念</span>
          <strong>{concept.name} <small>{concept.english}</small></strong>
          <p>{concept.explanation}</p>
        </aside>
      )}
      <nav className="story-footer-navigation" aria-label="切换实验阶段">
        <button onClick={() => onSelect(safeIndex - 1)} disabled={safeIndex === 0}>← 上一阶段</button>
        <span>{safeIndex + 1} / {model.stages.length}</span>
        {safeIndex >= model.stages.length - 1 ? (
          <button className="story-complete-button" onClick={onComplete}>完成这个实验 ✓</button>
        ) : (
          <button onClick={() => onSelect(safeIndex + 1)}>下一阶段 →</button>
        )}
      </nav>
    </section>
  )
}
