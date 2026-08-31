import { describe, expect, it } from 'vitest'
import type { TraceEvent } from './types'
import {
  circuitSteps,
  executableLineIndex,
  groverMechanismForScenario,
  groverStageForStep,
  isPhaseOnlyChange,
  recognizeGroverMechanism,
} from './viewModel'

function gateEvent(overrides: Partial<TraceEvent['data']> = {}): TraceEvent {
  return {
    seq: 1,
    layer: 'circuit',
    stage: 'gate_step',
    executor: 'local',
    status: 'ok',
    summary: 'gate',
    data: {
      operation_index: 0,
      gate: 'h',
      qubits: ['q[0]'],
      state_before: [{ basis: '0', real: 1, imag: 0, probability: 1 }],
      state_after: [
        { basis: '0', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
        { basis: '1', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
      ],
      ...overrides,
    },
  }
}

describe('Task 13C presentation model', () => {
  it('prepends an initialization step without inventing a QASM operation', () => {
    const steps = circuitSteps([gateEvent()])

    expect(steps.map((step) => step.stage)).toEqual(['initial_state', 'gate_step'])
    expect(steps[0].data.presentation_only).toBe(true)
    expect(steps[0].data.operation_index).toBeUndefined()
    expect(steps[0].data.state_after).toEqual([
      { basis: '0', real: 1, imag: 0, probability: 1 },
    ])
    expect(executableLineIndex('OPENQASM 2.0;\nqreg q[1];\nh q[0];', -1)).toBe(-1)
  })

  it('detects a phase-only change when probability stays equal', () => {
    const phaseEvent = gateEvent({
      gate: 's',
      state_before: [
        { basis: '0', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
        { basis: '1', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
      ],
      state_after: [
        { basis: '0', real: Math.SQRT1_2, imag: 0, probability: 0.5 },
        { basis: '1', real: 0, imag: Math.SQRT1_2, probability: 0.5 },
      ],
    })

    expect(isPhaseOnlyChange(phaseEvent)).toBe(true)
    expect(isPhaseOnlyChange(gateEvent())).toBe(false)
  })
})

const UNIFORM = [
  { basis: '00', real: 0.5, imag: 0, probability: 0.25 },
  { basis: '01', real: 0.5, imag: 0, probability: 0.25 },
  { basis: '10', real: 0.5, imag: 0, probability: 0.25 },
  { basis: '11', real: 0.5, imag: 0, probability: 0.25 },
]

function groverGate(seq: number, operationIndex: number, stateAfter: TraceEvent['data']['state_after']): TraceEvent {
  return gateEvent({ operation_index: operationIndex, state_after: stateAfter, gate: 'x' }) as TraceEvent & { seq: number }
}

function canonicalGroverSteps(globalPhase = 1): TraceEvent[] {
  const phase = (value: number) => value * globalPhase
  const marked = UNIFORM.map((entry) => ({
    ...entry,
    real: phase(entry.basis === '11' ? -0.5 : 0.5),
  }))
  const amplified = [
    { basis: '11', real: phase(1), imag: 0, probability: 1 },
  ]
  return [
    { ...groverGate(2, 4, [{ basis: '00', real: 1, imag: 0, probability: 1 }]), seq: 2 },
    { ...groverGate(8, 11, UNIFORM.map((entry) => ({ ...entry, real: phase(entry.real) }))), seq: 8 },
    { ...groverGate(14, 27, marked), seq: 14 },
    { ...groverGate(21, 43, amplified), seq: 21 },
    {
      seq: 29,
      layer: 'circuit',
      stage: 'measurement',
      executor: 'local',
      status: 'ok',
      summary: 'measurement',
      data: {
        operation_index: 58,
        probabilities_before: [{ basis: '11', probability: 1 }],
        mappings: [],
      },
    },
  ]
}

describe('Task 13N Grover semantic trace recognition', () => {
  it('recognizes all four stages without relying on operation indexes', () => {
    const model = recognizeGroverMechanism(canonicalGroverSteps())

    expect(model?.stages.map((stage) => [stage.id, stage.stepIndex])).toEqual([
      ['uniform', 1],
      ['oracle', 2],
      ['diffusion', 3],
      ['measurement', 4],
    ])
    expect(groverStageForStep(model!, 0).id).toBe('uniform')
    expect(groverStageForStep(model!, 2).id).toBe('oracle')
    expect(groverStageForStep(model!, 3).id).toBe('diffusion')
    expect(groverStageForStep(model!, 4).id).toBe('measurement')
  })

  it('recognizes the Oracle relative phase after a global phase flip', () => {
    const model = recognizeGroverMechanism(canonicalGroverSteps(-1))
    const oracle = model?.stages.find((stage) => stage.id === 'oracle')

    expect(oracle?.values.find((entry) => entry.basis === '11')?.amplitude).toBeLessThan(0)
    expect(oracle?.values.filter((entry) => entry.basis !== '11').every((entry) => (entry.amplitude ?? 0) > 0)).toBe(true)
  })

  it('falls back when any required semantic snapshot is missing', () => {
    expect(recognizeGroverMechanism(canonicalGroverSteps().filter((_, index) => index !== 2))).toBeNull()
    expect(recognizeGroverMechanism(canonicalGroverSteps().filter((_, index) => index !== 3))).toBeNull()
    expect(recognizeGroverMechanism(canonicalGroverSteps().filter((_, index) => index !== 4))).toBeNull()
  })

  it('enables the mechanism only for search and leaves Bell and Phase unchanged', () => {
    const steps = canonicalGroverSteps()

    expect(groverMechanismForScenario('search', steps)).not.toBeNull()
    expect(groverMechanismForScenario('bell', steps)).toBeNull()
    expect(groverMechanismForScenario('phase', steps)).toBeNull()
  })
})
