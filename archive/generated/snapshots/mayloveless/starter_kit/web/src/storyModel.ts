import type { StateEntry, TraceEvent } from './types'
import { isPhaseOnlyChange, recognizeGroverMechanism } from './viewModel'

export type CuratedScenarioId = 'bell' | 'search' | 'phase'
export type StoryVisualMode = 'wave' | 'probability'

export interface StoryValue {
  basis: string
  magnitude: number | null
  phase: number | null
  probability: number
}

export interface StorySnapshot {
  mode: StoryVisualMode
  values: StoryValue[]
}

export interface ExperimentStoryStage {
  id: string
  number: string
  label: string
  purpose: string
  action: string
  importance: string
  terminology: string | null
  stepIndex: number
  gateIndices: number[]
  before: StorySnapshot
  after: StorySnapshot
}

export interface ExperimentStoryModel {
  scenarioId: CuratedScenarioId
  stages: ExperimentStoryStage[]
}

const EPSILON = 1e-8
const PROBABILITY_TOLERANCE = 0.02

function wrapPhase(value: number): number {
  let phase = value
  while (phase > Math.PI) phase -= Math.PI * 2
  while (phase <= -Math.PI) phase += Math.PI * 2
  return phase
}

function storyValues(value: unknown, probabilityOnly = false): StoryValue[] | null {
  if (!Array.isArray(value)) return null
  const entries = value as StateEntry[]
  if (!entries.length) return null
  const seen = new Set<string>()
  for (const entry of entries) {
    if (typeof entry.basis !== 'string' || seen.has(entry.basis) || !Number.isFinite(entry.probability)) return null
    seen.add(entry.basis)
  }
  if (probabilityOnly) {
    return entries.map((entry) => ({
      basis: entry.basis,
      magnitude: null,
      phase: null,
      probability: entry.probability,
    }))
  }
  const reference = entries.find((entry) => Math.hypot(Number(entry.real ?? 0), Number(entry.imag ?? 0)) > EPSILON)
  if (!reference) return null
  const referencePhase = Math.atan2(Number(reference.imag ?? 0), Number(reference.real ?? 0))
  const values: StoryValue[] = []
  for (const entry of entries) {
    const real = Number(entry.real ?? 0)
    const imag = Number(entry.imag ?? 0)
    if (!Number.isFinite(real) || !Number.isFinite(imag)) return null
    const magnitude = Math.hypot(real, imag)
    values.push({
      basis: entry.basis,
      magnitude,
      phase: magnitude > EPSILON ? wrapPhase(Math.atan2(imag, real) - referencePhase) : 0,
      probability: entry.probability,
    })
  }
  return values
}

function eventBefore(event: TraceEvent): StoryValue[] | null {
  return storyValues(event.data.state_before)
}

function eventAfter(event: TraceEvent): StoryValue[] | null {
  return storyValues(event.data.state_after)
}

function measurementAfter(event: TraceEvent): StoryValue[] | null {
  return storyValues(event.data.probabilities_before, true)
}

function snapshot(values: StoryValue[], mode: StoryVisualMode = 'wave'): StorySnapshot {
  return { mode, values }
}

function gatesBetween(start: number, end: number): number[] {
  return Array.from({ length: Math.max(0, end - start + 1) }, (_, offset) => start + offset)
}

function twoBalancedBranches(values: StoryValue[] | null): values is StoryValue[] {
  return Boolean(values)
    && values!.length === 2
    && values!.every((entry) => Math.abs(entry.probability - 0.5) <= PROBABILITY_TOLERANCE)
}

function hammingDistance(left: string, right: string): number {
  if (left.length !== right.length) return 0
  return [...left].reduce((distance, bit, index) => distance + (bit === right[index] ? 0 : 1), 0)
}

function sameProbabilityDistribution(left: StoryValue[], right: StoryValue[]): boolean {
  const bases = new Set([...left, ...right].map((entry) => entry.basis))
  return [...bases].every((basis) => {
    const before = left.find((entry) => entry.basis === basis)?.probability ?? 0
    const after = right.find((entry) => entry.basis === basis)?.probability ?? 0
    return Math.abs(before - after) <= PROBABILITY_TOLERANCE
  })
}

function bellStory(steps: TraceEvent[]): ExperimentStoryModel | null {
  const initialIndex = steps.findIndex((event) => event.stage === 'initial_state' && event.status === 'ok')
  if (initialIndex < 0) return null
  const initial = eventAfter(steps[initialIndex])
  if (!initial || initial.length !== 1 || initial[0].probability < 1 - PROBABILITY_TOLERANCE) return null

  let branchIndex = -1
  let branches: StoryValue[] | null = null
  for (let index = initialIndex + 1; index < steps.length; index += 1) {
    const candidate = eventAfter(steps[index])
    if (steps[index].status === 'ok' && twoBalancedBranches(candidate)) {
      branchIndex = index
      branches = candidate
      break
    }
  }
  if (!branches || branchIndex < 0) return null

  let correlationIndex = -1
  let correlated: StoryValue[] | null = null
  for (let index = branchIndex + 1; index < steps.length; index += 1) {
    const candidate = eventAfter(steps[index])
    if (
      steps[index].status === 'ok'
      && twoBalancedBranches(candidate)
      && hammingDistance(candidate[0].basis, candidate[1].basis) === 2
      && candidate.some((entry) => !branches!.some((branch) => branch.basis === entry.basis))
    ) {
      correlationIndex = index
      correlated = candidate
      break
    }
  }
  if (!correlated || correlationIndex < 0) return null
  const measurementIndex = steps.findIndex(
    (event, index) => index > correlationIndex && event.stage === 'measurement' && event.status === 'ok',
  )
  if (measurementIndex < 0) return null
  const measured = measurementAfter(steps[measurementIndex])
  if (!measured || !sameProbabilityDistribution(correlated, measured)) return null

  return {
    scenarioId: 'bell',
    stages: [
      {
        id: 'start', number: '01', label: '起点', stepIndex: initialIndex,
        purpose: '先确认两个量子位从同一个确定状态开始。',
        action: '准备真实电路的初始量子状态。',
        importance: '这个确定的起点让后面的分支与关联变化有清楚的参照。',
        terminology: '当前只有一个基态分支。',
        gateIndices: [], before: snapshot(initial), after: snapshot(initial),
      },
      {
        id: 'branch', number: '02', label: '分出两个分支', stepIndex: branchIndex,
        purpose: '让程序不再只保留一个确定分支。',
        action: '第一个量子位发生变化，真实状态中出现两个等强分支。',
        importance: '程序现在同时保留两种量子可能性，为建立关联做准备。',
        terminology: '两个分支共同描述状态，这叫叠加。',
        gateIndices: gatesBetween(initialIndex + 1, branchIndex), before: snapshot(initial), after: snapshot(branches),
      },
      {
        id: 'correlate', number: '03', label: '建立关联', stepIndex: correlationIndex,
        purpose: '让第二个量子位跟随第一个量子位所在的分支发生变化。',
        action: 'CX 按第一个量子位的分支条件改变第二个量子位。',
        importance: `变化后只留下 ${correlated.map((entry) => `|${entry.basis}⟩`).join(' 与 ')} 这两个成对关联的分支。`,
        terminology: '现在必须整体理解两个量子位的联合状态，这叫纠缠。',
        gateIndices: gatesBetween(branchIndex + 1, correlationIndex), before: snapshot(branches), after: snapshot(correlated),
      },
      {
        id: 'measure', number: '04', label: '测量', stepIndex: measurementIndex,
        purpose: '把联合量子状态读成普通程序可以接收的经典结果。',
        action: '最后才按真实概率分布测量两个量子位。',
        importance: '单次只得到一组结果；重复运行后才能在统计中看到关联模式。',
        terminology: '当前 Trace 没有伪造 shots 次数或单次随机结果。',
        gateIndices: [measurementIndex], before: snapshot(correlated), after: snapshot(measured, 'probability'),
      },
    ],
  }
}

function groverValues(values: { basis: string; amplitude: number | null; probability: number }[]): StoryValue[] {
  return values.map((entry) => ({
    basis: entry.basis,
    magnitude: entry.amplitude == null ? null : Math.abs(entry.amplitude),
    phase: entry.amplitude == null ? null : entry.amplitude < 0 ? Math.PI : 0,
    probability: entry.probability,
  }))
}

function groverStory(steps: TraceEvent[]): ExperimentStoryModel | null {
  const mechanism = recognizeGroverMechanism(steps)
  if (!mechanism) return null
  const [uniform, oracle, diffusion, measurement] = mechanism.stages
  const uniformAfter = groverValues(uniform.values)
  const oracleAfter = groverValues(oracle.values)
  const diffusionAfter = groverValues(diffusion.values)
  const measurementAfterValues = groverValues(measurement.values)
  const firstGateIndex = steps.findIndex((event) => event.stage === 'gate_step')
  const uniformBefore = firstGateIndex >= 0 ? eventBefore(steps[firstGateIndex]) : null
  if (!uniformBefore) return null

  return {
    scenarioId: 'search',
    stages: [
      {
        id: 'uniform', number: '01', label: '准备候选', stepIndex: uniform.stepIndex,
        purpose: '先让 4 个候选拥有同样的机会。',
        action: '量子门把振幅均匀分配到四个候选分支。',
        importance: '四个候选现在一样强，还没有偏向任何答案。',
        terminology: '这种四个候选等强的状态叫均匀叠加。',
        gateIndices: gatesBetween(firstGateIndex, uniform.stepIndex), before: snapshot(uniformBefore), after: snapshot(uniformAfter),
      },
      {
        id: 'oracle', number: '02', label: '翻转目标方向', stepIndex: oracle.stepIndex,
        purpose: '对每个候选执行同一个“是不是目标”的判断。',
        action: '符合条件的 |11⟩ 振幅方向被翻过来；Oracle ≈ isTarget(x)，但不会直接返回答案。',
        importance: '目标已经留下可供后续干涉利用的差异，但此时 |11⟩ 的测量概率还没有变大。',
        terminology: '振幅方向翻转也叫相位翻转 / 相位标记。',
        gateIndices: gatesBetween(uniform.stepIndex + 1, oracle.stepIndex), before: snapshot(uniformAfter), after: snapshot(oracleAfter),
      },
      {
        id: 'diffusion', number: '03', label: '干涉并放大', stepIndex: diffusion.stepIndex,
        purpose: '让四个振幅重新相互作用，把方向差异变成强弱差异。',
        action: 'Diffusion / 干涉增强目标分支，同时削弱其他候选分支。',
        importance: '|11⟩ 获得振幅优势，因此最后被测到的概率更高。',
        terminology: '数学上可以理解为围绕平均振幅做反射。',
        gateIndices: gatesBetween(oracle.stepIndex + 1, diffusion.stepIndex), before: snapshot(oracleAfter), after: snapshot(diffusionAfter),
      },
      {
        id: 'measurement', number: '04', label: '测量', stepIndex: measurement.stepIndex,
        purpose: '把最终的振幅优势转换成经典程序可读取的结果概率。',
        action: '最后才按真实测量前分布读取量子状态。',
        importance: '|11⟩ 现在更容易出现；页面不会伪造一次随机测量结果。',
        terminology: null,
        gateIndices: [measurement.stepIndex], before: snapshot(diffusionAfter), after: snapshot(measurementAfterValues, 'probability'),
      },
    ],
  }
}

function changedRelativePhase(before: StoryValue[], after: StoryValue[]): boolean {
  return before.some((entry) => {
    const next = after.find((candidate) => candidate.basis === entry.basis)
    return next?.phase != null && entry.phase != null && Math.abs(wrapPhase(next.phase - entry.phase)) > 0.1
  })
}

function phaseStory(steps: TraceEvent[]): ExperimentStoryModel | null {
  const phaseIndex = steps.findIndex((event) => {
    if (!isPhaseOnlyChange(event) || event.status !== 'ok') return false
    const before = eventBefore(event)
    const after = eventAfter(event)
    return twoBalancedBranches(before)
      && twoBalancedBranches(after)
      && sameProbabilityDistribution(before, after)
      && changedRelativePhase(before, after)
  })
  if (phaseIndex < 0) return null
  const phaseBefore = eventBefore(steps[phaseIndex])
  const phaseAfter = eventAfter(steps[phaseIndex])
  if (!phaseBefore || !phaseAfter) return null

  let branchIndex = -1
  for (let index = 0; index < phaseIndex; index += 1) {
    const candidate = eventAfter(steps[index])
    if (twoBalancedBranches(candidate) && sameProbabilityDistribution(candidate, phaseBefore)) branchIndex = index
  }
  if (branchIndex < 0) return null
  const branchBefore = eventBefore(steps[branchIndex]) ?? phaseBefore
  const firstGateIndex = steps.findIndex((event) => event.stage === 'gate_step')
  if (firstGateIndex < 0) return null

  return {
    scenarioId: 'phase',
    stages: [
      {
        id: 'branches', number: '01', label: '形成两个分支', stepIndex: branchIndex,
        purpose: '先准备两个大小相同、方向关系清楚的量子分支。',
        action: '真实电路建立两个等概率分支。',
        importance: '这给后面的方向变化提供了可比较的起点。',
        terminology: '分支的大小对应振幅大小。',
        gateIndices: gatesBetween(firstGateIndex, branchIndex), before: snapshot(branchBefore), after: snapshot(phaseBefore),
      },
      {
        id: 'turn', number: '02', label: '改变分支方向', stepIndex: phaseIndex,
        purpose: '只改变分支之间的方向关系，不改变它们的大小。',
        action: '当前量子门改变其中一个分支相对于另一个分支的方向。',
        importance: '两个分支的测量概率仍一样，但量子状态已经不同。',
        terminology: '这个方向关系叫相对相位，它会影响以后再次干涉时的结果。',
        gateIndices: [phaseIndex], before: snapshot(phaseBefore), after: snapshot(phaseAfter),
      },
      {
        id: 'probability', number: '03', label: '概率仍一样', stepIndex: phaseIndex,
        purpose: '把改变后的状态暂时只按测量概率观察。',
        action: '没有执行额外 Gate；这里只把同一真实状态切换为概率视角。',
        importance: '现在看起来一样，不代表后续计算会一样。',
        terminology: '如果后续重新干涉，相对相位才会进一步转化成可见的概率差异。',
        gateIndices: [], before: snapshot(phaseBefore, 'probability'), after: snapshot(phaseAfter, 'probability'),
      },
    ],
  }
}

// 正式实验只有在真实 Trace 足以支撑完整故事时才进入 Story Mode。
export function buildExperimentStory(
  scenarioId: string | null,
  steps: TraceEvent[],
): ExperimentStoryModel | null {
  if (scenarioId === 'bell') return bellStory(steps)
  if (scenarioId === 'search') return groverStory(steps)
  if (scenarioId === 'phase') return phaseStory(steps)
  return null
}
