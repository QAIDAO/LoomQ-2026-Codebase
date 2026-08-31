export type TraceStatus = 'running' | 'ok' | 'warning' | 'error'

export interface TraceEvent {
  seq: number
  layer: 'agent' | 'circuit'
  stage: string
  executor: 'llm' | 'local'
  status: TraceStatus
  summary: string
  data: Record<string, unknown>
}

export interface DebugResponse {
  reply: string
  events: TraceEvent[]
  teaching: TeachingExplanation | null
}

export interface TeachingStep {
  operation_index: number
  purpose: string
  concept: string | null
  concept_explanation: string | null
}

export interface TeachingExplanation {
  circuit_goal: string
  steps: TeachingStep[]
}

export interface StateEntry {
  basis: string
  probability: number
  real?: number
  imag?: number
}

export interface MeasurementMapping {
  qubit: string
  classical_bit: string
}
