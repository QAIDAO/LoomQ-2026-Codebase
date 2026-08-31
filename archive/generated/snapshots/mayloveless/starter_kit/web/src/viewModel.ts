import type { StateEntry, TraceEvent } from './types'

const GROVER_BASES = ['00', '01', '10', '11'] as const
const GROVER_TARGET = '11'
const PROBABILITY_TOLERANCE = 0.02
const PHASE_TOLERANCE = 1e-6

export type GroverStageId = 'uniform' | 'oracle' | 'diffusion' | 'measurement'

export interface GroverBasisValue {
  basis: string
  amplitude: number | null
  probability: number
}

export interface GroverStageSnapshot {
  id: GroverStageId
  stepIndex: number
  values: GroverBasisValue[]
}

export interface GroverMechanismModel {
  stages: GroverStageSnapshot[]
}

export const CIRCUIT_STEP_STAGES = new Set(['gate_step', 'measurement'])

export function circuitSteps(events: TraceEvent[]): TraceEvent[] {
  const rawSteps = events.filter(
    (event) => event.layer === 'circuit' && CIRCUIT_STEP_STAGES.has(event.stage),
  )
  const mergedSteps = rawSteps.reduce<TraceEvent[]>((steps, event) => {
    const previous = steps.at(-1)
    if (event.stage !== 'measurement' || previous?.stage !== 'measurement') {
      steps.push(event)
      return steps
    }
    // 模型可能生成逐位 measure；UI 将连续测量合并为一个易理解的读出步骤。
    const previousMappings = Array.isArray(previous.data.mappings)
      ? previous.data.mappings
      : []
    const currentMappings = Array.isArray(event.data.mappings)
      ? event.data.mappings
      : []
    steps[steps.length - 1] = {
      ...previous,
      data: {
        ...previous.data,
        mappings: [...previousMappings, ...currentMappings],
      },
    }
    return steps
  }, [])
  const firstGate = mergedSteps.find((event) => event.stage === 'gate_step')
  const firstAction = mergedSteps[0]
  const initialState = Array.isArray(firstGate?.data.state_before)
    ? firstGate.data.state_before
    : Array.isArray(firstAction?.data.probabilities_before)
      ? firstAction.data.probabilities_before
      : null
  if (!initialState) return mergedSteps
  // 初始化是 Web presentation step，不对应 Gate，也不修改底层 Circuit Trace。
  const initialStep: TraceEvent = {
    seq: 0,
    layer: 'circuit',
    stage: 'initial_state',
    executor: 'local',
    status: 'ok',
    summary: '所有量子位从 |0› 开始。',
    data: {
      presentation_only: true,
      state_after: initialState,
      probabilities_after: initialState.map((entry) => ({
        basis: (entry as StateEntry).basis,
        probability: (entry as StateEntry).probability,
      })),
      gate_description: '所有量子位从 |0› 开始，这是这段程序执行前的起点。',
    },
  }
  return [initialStep, ...mergedSteps]
}

export function circuitWarnings(events: TraceEvent[]): TraceEvent[] {
  return events.filter(
    (event) => event.layer === 'circuit' && event.status === 'warning',
  )
}

export function agentEvents(events: TraceEvent[]): TraceEvent[] {
  return events.filter((event) => event.layer === 'agent')
}

export function extractQasm(events: TraceEvent[]): string {
  const result = [...events]
    .reverse()
    .find((event) => typeof event.data.qasm === 'string')
  return (result?.data.qasm as string | undefined) ?? ''
}

export function stateForStep(event: TraceEvent): StateEntry[] {
  const value =
    event.stage === 'measurement'
      ? event.data.probabilities_before
      : event.data.state_after
  return Array.isArray(value) ? (value as StateEntry[]) : []
}

export function stepTitle(event: TraceEvent): string {
  if (event.stage === 'initial_state') return '初始状态'
  if (event.stage === 'measurement') return '测量'
  const gate = String(event.data.gate ?? '').toUpperCase()
  const qubits = Array.isArray(event.data.qubits)
    ? event.data.qubits.join(', ')
    : ''
  const parameters = Array.isArray(event.data.parameters)
    ? event.data.parameters.join(', ')
    : ''
  return `${gate}${parameters ? `(${parameters})` : ''}${qubits ? ` ${qubits}` : ''}`
}

export function isPhaseOnlyChange(event: TraceEvent): boolean {
  if (event.stage !== 'gate_step') return false
  const before = Array.isArray(event.data.state_before)
    ? (event.data.state_before as StateEntry[])
    : []
  const after = Array.isArray(event.data.state_after)
    ? (event.data.state_after as StateEntry[])
    : []
  const bases = [...new Set([...before, ...after].map((entry) => entry.basis))]
  const probabilityChanged = bases.some((basis) => {
    const previous = before.find((entry) => entry.basis === basis)?.probability ?? 0
    const current = after.find((entry) => entry.basis === basis)?.probability ?? 0
    return Math.abs(previous - current) > 1e-9
  })
  const amplitudeChanged = bases.some((basis) => {
    const previous = before.find((entry) => entry.basis === basis)
    const current = after.find((entry) => entry.basis === basis)
    return Math.abs((previous?.real ?? 0) - (current?.real ?? 0)) > 1e-9
      || Math.abs((previous?.imag ?? 0) - (current?.imag ?? 0)) > 1e-9
  })
  return !probabilityChanged && amplitudeChanged
}

function normalizedGroverState(value: unknown): StateEntry[] | null {
  if (!Array.isArray(value)) return null
  const entries = value as StateEntry[]
  const allowed = new Set<string>(GROVER_BASES)
  const seen = new Set<string>()
  for (const entry of entries) {
    if (!allowed.has(entry.basis) || seen.has(entry.basis) || !Number.isFinite(entry.probability)) {
      return null
    }
    seen.add(entry.basis)
  }
  return GROVER_BASES.map((basis) => entries.find((entry) => entry.basis === basis) ?? {
    basis,
    probability: 0,
    real: 0,
    imag: 0,
  })
}

function projectedGroverValues(
  value: unknown,
  preferredReferences: readonly string[],
): GroverBasisValue[] | null {
  const state = normalizedGroverState(value)
  if (!state) return null
  const reference = preferredReferences
    .map((basis) => state.find((entry) => entry.basis === basis))
    .find((entry) => entry && Math.hypot(Number(entry.real ?? 0), Number(entry.imag ?? 0)) > PHASE_TOLERANCE)
  if (!reference) return null
  const referenceReal = Number(reference.real ?? 0)
  const referenceImag = Number(reference.imag ?? 0)
  const referenceMagnitude = Math.hypot(referenceReal, referenceImag)
  const unitReal = referenceReal / referenceMagnitude
  const unitImag = referenceImag / referenceMagnitude
  const values: GroverBasisValue[] = []
  for (const entry of state) {
    const real = Number(entry.real ?? 0)
    const imag = Number(entry.imag ?? 0)
    if (!Number.isFinite(real) || !Number.isFinite(imag)) return null
    const projectedReal = real * unitReal + imag * unitImag
    const projectedImag = imag * unitReal - real * unitImag
    if (Math.abs(projectedImag) > PHASE_TOLERANCE) return null
    values.push({ basis: entry.basis, amplitude: projectedReal, probability: entry.probability })
  }
  return values
}

function uniformValues(event: TraceEvent): GroverBasisValue[] | null {
  if (event.stage !== 'gate_step' || event.status !== 'ok') return null
  const values = projectedGroverValues(event.data.state_after, ['00', '01', '10'])
  if (!values) return null
  const isUniform = values.every(
    (entry) => Math.abs(entry.probability - 0.25) <= PROBABILITY_TOLERANCE
      && entry.amplitude != null
      && entry.amplitude > 0,
  )
  return isUniform ? values : null
}

function oracleValues(event: TraceEvent): GroverBasisValue[] | null {
  if (event.stage !== 'gate_step' || event.status !== 'ok') return null
  const values = projectedGroverValues(event.data.state_after, ['00', '01', '10'])
  if (!values || values.some((entry) => Math.abs(entry.probability - 0.25) > PROBABILITY_TOLERANCE)) {
    return null
  }
  const target = values.find((entry) => entry.basis === GROVER_TARGET)
  const nonTargets = values.filter((entry) => entry.basis !== GROVER_TARGET)
  return target?.amplitude != null
    && target.amplitude < -PHASE_TOLERANCE
    && nonTargets.every((entry) => entry.amplitude != null && entry.amplitude > PHASE_TOLERANCE)
    ? values
    : null
}

function amplifiedValues(event: TraceEvent): GroverBasisValue[] | null {
  if (event.stage !== 'gate_step' || event.status !== 'ok') return null
  const values = projectedGroverValues(event.data.state_after, ['11', '00', '01', '10'])
  if (!values) return null
  const target = values.find((entry) => entry.basis === GROVER_TARGET)
  const largestOther = Math.max(...values.filter((entry) => entry.basis !== GROVER_TARGET).map((entry) => entry.probability))
  return target && target.probability >= 0.5 && target.probability - largestOther >= 0.2
    ? values
    : null
}

function measurementValues(event: TraceEvent): GroverBasisValue[] | null {
  if (event.stage !== 'measurement' || event.status !== 'ok') return null
  const state = normalizedGroverState(event.data.probabilities_before)
  if (!state) return null
  const target = state.find((entry) => entry.basis === GROVER_TARGET)
  const largestOther = Math.max(...state.filter((entry) => entry.basis !== GROVER_TARGET).map((entry) => entry.probability))
  if (!target || target.probability < 0.5 || target.probability - largestOther < 0.2) return null
  return state.map((entry) => ({ basis: entry.basis, amplitude: null, probability: entry.probability }))
}

function sameProbabilities(left: GroverBasisValue[], right: GroverBasisValue[]): boolean {
  return GROVER_BASES.every((basis) => {
    const a = left.find((entry) => entry.basis === basis)?.probability ?? 0
    const b = right.find((entry) => entry.basis === basis)?.probability ?? 0
    return Math.abs(a - b) <= PROBABILITY_TOLERANCE
  })
}

// 只从真实 trace 的状态语义识别阶段；任一关键快照缺失时安全回退。
export function recognizeGroverMechanism(steps: TraceEvent[]): GroverMechanismModel | null {
  const uniformIndex = steps.findIndex((event) => uniformValues(event) != null)
  if (uniformIndex < 0) return null
  const oracleOffset = steps.slice(uniformIndex + 1).findIndex((event) => oracleValues(event) != null)
  if (oracleOffset < 0) return null
  const oracleIndex = uniformIndex + 1 + oracleOffset
  const measurementOffset = steps.slice(oracleIndex + 1).findIndex((event) => measurementValues(event) != null)
  if (measurementOffset < 0) return null
  const measurementIndex = oracleIndex + 1 + measurementOffset
  const measurement = measurementValues(steps[measurementIndex])
  if (!measurement) return null

  let diffusionIndex = -1
  let diffusion: GroverBasisValue[] | null = null
  for (let index = oracleIndex + 1; index < measurementIndex; index += 1) {
    const candidate = amplifiedValues(steps[index])
    if (candidate && sameProbabilities(candidate, measurement)) {
      diffusionIndex = index
      diffusion = candidate
    }
  }
  const uniform = uniformValues(steps[uniformIndex])
  const oracle = oracleValues(steps[oracleIndex])
  if (!uniform || !oracle || !diffusion || diffusionIndex < 0) return null

  return {
    stages: [
      { id: 'uniform', stepIndex: uniformIndex, values: uniform },
      { id: 'oracle', stepIndex: oracleIndex, values: oracle },
      { id: 'diffusion', stepIndex: diffusionIndex, values: diffusion },
      { id: 'measurement', stepIndex: measurementIndex, values: measurement },
    ],
  }
}

export function groverMechanismForScenario(
  scenarioId: string | null,
  steps: TraceEvent[],
): GroverMechanismModel | null {
  return scenarioId === 'search' ? recognizeGroverMechanism(steps) : null
}

export function groverStageForStep(model: GroverMechanismModel, stepIndex: number): GroverStageSnapshot {
  const [uniform, oracle, diffusion, measurement] = model.stages
  if (stepIndex <= uniform.stepIndex) return uniform
  if (stepIndex <= oracle.stepIndex) return oracle
  if (stepIndex <= diffusion.stepIndex) return diffusion
  return measurement
}

export function executableLineIndex(qasm: string, operationIndex: number): number {
  const lines = qasm.split('\n')
  let currentOperation = -1
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim()
    const isOperation =
      line.length > 0 &&
      !line.startsWith('//') &&
      !/^OPENQASM\b/i.test(line) &&
      !/^include\b/i.test(line) &&
      !/^(qreg|creg)\b/i.test(line)
    if (isOperation) {
      currentOperation += 1
      if (currentOperation === operationIndex) return index
    }
  }
  return -1
}

export function latestBackendIds(events: TraceEvent[]): string[] {
  const selected = [...events]
    .reverse()
    .find((event) => event.stage === 'backend_selected')
  return Array.isArray(selected?.data.backend_ids)
    ? (selected.data.backend_ids as string[])
    : []
}
