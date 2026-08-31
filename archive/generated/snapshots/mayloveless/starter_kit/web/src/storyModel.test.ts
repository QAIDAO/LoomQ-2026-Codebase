import { describe, expect, it } from 'vitest'
import { buildExperimentStory } from './storyModel'
import type { StateEntry, TraceEvent } from './types'
import { circuitSteps } from './viewModel'

function gate(
  seq: number,
  gateName: string,
  before: StateEntry[],
  after: StateEntry[],
): TraceEvent {
  return {
    seq,
    layer: 'circuit',
    stage: 'gate_step',
    executor: 'local',
    status: 'ok',
    summary: gateName,
    data: {
      operation_index: seq * 3,
      gate: gateName,
      qubits: ['q[0]'],
      state_before: before,
      state_after: after,
    },
  }
}

function measurement(seq: number, probabilities: StateEntry[]): TraceEvent {
  return {
    seq,
    layer: 'circuit',
    stage: 'measurement',
    executor: 'local',
    status: 'ok',
    summary: 'measurement',
    data: {
      operation_index: seq * 3,
      probabilities_before: probabilities.map(({ basis, probability }) => ({ basis, probability })),
      mappings: [],
    },
  }
}

const ZERO = [{ basis: '00', real: 1, imag: 0, probability: 1 }]
const SPLIT = [
  { basis: '00', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
  { basis: '10', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
]
const BELL_PLUS = [
  { basis: '00', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
  { basis: '11', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
]
const BELL_MINUS = [
  { basis: '00', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
  { basis: '11', real: -Math.SQRT1_2, imag: 0, probability: 0.5 },
]

function bellSteps(): TraceEvent[] {
  return circuitSteps([
    gate(2, 'h', ZERO, SPLIT),
    gate(9, 'cx', SPLIT, BELL_PLUS),
    measurement(15, BELL_PLUS),
  ])
}

function phaseSteps(): TraceEvent[] {
  return circuitSteps([
    gate(2, 'h', ZERO, SPLIT),
    gate(9, 'cx', SPLIT, BELL_PLUS),
    gate(17, 'z', BELL_PLUS, BELL_MINUS),
  ])
}

describe('Task 13O curated experiment story recognition', () => {
  it('builds Bell as start, branch, correlation, and measurement from trace states', () => {
    const story = buildExperimentStory('bell', bellSteps())

    expect(story?.stages.map((stage) => stage.id)).toEqual(['start', 'branch', 'correlate', 'measure'])
    expect(story?.stages[1].after.values.map((entry) => entry.basis)).toEqual(['00', '10'])
    expect(story?.stages[2].after.values.map((entry) => entry.basis)).toEqual(['00', '11'])
    expect(story?.stages[3].after.mode).toBe('probability')
  })

  it('builds Phase from a real phase-only change without changing probabilities', () => {
    const story = buildExperimentStory('phase', phaseSteps())

    expect(story?.stages.map((stage) => stage.id)).toEqual(['branches', 'turn', 'probability'])
    const turn = story?.stages[1]
    expect(turn?.before.values.map((entry) => entry.probability)).toEqual([0.5, 0.5])
    expect(turn?.after.values.map((entry) => entry.probability)).toEqual([0.5, 0.5])
    expect(Math.abs(turn?.after.values.find((entry) => entry.basis === '11')?.phase ?? 0)).toBeCloseTo(Math.PI)
  })

  it('keeps free exploration and incomplete curated traces on the generic fallback', () => {
    expect(buildExperimentStory(null, bellSteps())).toBeNull()
    expect(buildExperimentStory('ghz', bellSteps())).toBeNull()
    expect(buildExperimentStory('bell', bellSteps().slice(0, -1))).toBeNull()
    expect(buildExperimentStory('phase', phaseSteps().slice(0, -1))).toBeNull()
  })
})

