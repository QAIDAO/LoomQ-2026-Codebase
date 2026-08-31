"""Per-gate statevector trace generation for explicit debug sessions."""

from __future__ import annotations

from typing import Any, Sequence

from .debug_trace import TraceEvent, TraceRecorder
from .ir import (
    Circuit,
    ClassicalBitRef,
    GateOperation,
    MeasureOperation,
    QubitRef,
)
from .semantic_verifier import simulate_statevector


DEFAULT_MAX_TRACE_QUBITS = 8
STATE_AMPLITUDE_EPSILON = 1e-10

_GATE_DESCRIPTIONS = {
    "h": "H 门：把振幅重新分配到多个基态，使量子位进入叠加。",
    "x": "X 门：交换这个量子位在 |0> 与 |1> 上的振幅。",
    "s": "S 门：增加四分之一圈相位，不直接改变基态测量概率。",
    "sdg": "Sdg 门：减少四分之一圈相位，不直接改变基态测量概率。",
    "t": "T 门：增加八分之一圈相位，不直接改变基态测量概率。",
    "tdg": "Tdg 门：减少八分之一圈相位，不直接改变基态测量概率。",
    "ry": "RY 门：绕 Y 轴旋转，在 |0> 与 |1> 之间重新分配振幅。",
    "rz": "RZ 门：改变相对相位，通常不会立刻改变测量概率。",
    "cx": "CX 门：当控制位为 1 时翻转目标位，因此改变两个量子位之间的关联。",
    "cu1": "CU1 门：当控制位和目标位都为 1 时增加相位。",
    "swap": "SWAP 门：交换两个量子位承载的量子状态。",
    "ccx": "CCX 门：当两个控制位都为 1 时翻转目标位。",
}


def _qubit_count(circuit: Circuit) -> int:
    return sum(register.size for register in circuit.quantum_registers)


def _state_entries(
    statevector: Sequence[complex], qubit_count: int
) -> list[dict[str, Any]]:
    entries = []
    for index, raw_amplitude in enumerate(statevector):
        amplitude = complex(raw_amplitude)
        probability = abs(amplitude) ** 2
        if abs(amplitude) < STATE_AMPLITUDE_EPSILON:
            continue
        entries.append(
            {
                "basis": format(index, "0%db" % qubit_count),
                "real": float(amplitude.real),
                "imag": float(amplitude.imag),
                "probability": float(probability),
            }
        )
    return entries


def _probabilities(state: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"basis": item["basis"], "probability": item["probability"]}
        for item in state
    ]


def _qubit_label(qubit: QubitRef) -> str:
    return "%s[%d]" % (qubit.register, qubit.index)


def _measurement_mappings(
    circuit: Circuit, operation: MeasureOperation
) -> list[dict[str, str]]:
    if isinstance(operation.quantum, QubitRef) and isinstance(
        operation.classical, ClassicalBitRef
    ):
        return [
            {
                "qubit": _qubit_label(operation.quantum),
                "classical_bit": "%s[%d]"
                % (operation.classical.register, operation.classical.index),
            }
        ]

    quantum_register = next(
        register
        for register in circuit.quantum_registers
        if register.name == operation.quantum.register
    )
    return [
        {
            "qubit": "%s[%d]" % (operation.quantum.register, index),
            "classical_bit": "%s[%d]" % (operation.classical.register, index),
        }
        for index in range(quantum_register.size)
    ]


def trace_circuit(
    circuit: Circuit,
    trace_sink: TraceRecorder,
    *,
    max_qubits: int = DEFAULT_MAX_TRACE_QUBITS,
) -> tuple[TraceEvent, ...]:
    """Append deterministic gate and measurement events to a shared recorder."""
    start_seq = len(trace_sink.events)
    qubit_count = _qubit_count(circuit)
    if qubit_count > max_qubits:
        trace_sink.emit(
            layer="circuit",
            stage="statevector_skipped",
            executor="local",
            status="warning",
            summary="电路超过调试上限，已跳过 statevector 可视化。",
            data={"qubit_count": qubit_count, "max_qubits": max_qubits},
        )
        return trace_sink.events[start_seq:]

    prefix_operations: list[GateOperation] = []
    prefix = Circuit(
        openqasm_version=circuit.openqasm_version,
        quantum_registers=circuit.quantum_registers,
        classical_registers=circuit.classical_registers,
        operations=(),
    )
    current_statevector = simulate_statevector(prefix)

    for operation_index, operation in enumerate(circuit.operations):
        if isinstance(operation, GateOperation):
            state_before = _state_entries(current_statevector, qubit_count)
            prefix_operations.append(operation)
            prefix = Circuit(
                openqasm_version=circuit.openqasm_version,
                quantum_registers=circuit.quantum_registers,
                classical_registers=circuit.classical_registers,
                operations=tuple(prefix_operations),
            )
            current_statevector = simulate_statevector(prefix)
            state_after = _state_entries(current_statevector, qubit_count)
            trace_sink.emit(
                layer="circuit",
                stage="gate_step",
                executor="local",
                status="ok",
                summary="已对 %s 执行 %s 门。"
                % (", ".join(map(_qubit_label, operation.qubits)), operation.name.upper()),
                data={
                    "operation_index": operation_index,
                    "gate": operation.name,
                    "qubits": [_qubit_label(qubit) for qubit in operation.qubits],
                    "parameters": list(operation.parameters),
                    "state_before": state_before,
                    "state_after": state_after,
                    "probabilities_after": _probabilities(state_after),
                    "gate_description": _GATE_DESCRIPTIONS.get(
                        operation.name, "该量子门会更新当前量子状态。"
                    ),
                },
            )
        elif isinstance(operation, MeasureOperation):
            state_before = _state_entries(current_statevector, qubit_count)
            trace_sink.emit(
                layer="circuit",
                stage="measurement",
                executor="local",
                status="ok",
                summary="测量把量子位映射到经典位。",
                data={
                    "operation_index": operation_index,
                    "mappings": _measurement_mappings(circuit, operation),
                    "probabilities_before": _probabilities(state_before),
                    "gate_description": (
                        "测量：按当前概率分布把量子信息读成经典 0/1；"
                        "这里不会伪造一次随机结果。"
                    ),
                },
            )
            remaining_gate_count = sum(
                isinstance(remaining, GateOperation)
                for remaining in circuit.operations[operation_index + 1 :]
            )
            if remaining_gate_count:
                trace_sink.emit(
                    layer="circuit",
                    stage="trace_stopped_after_measurement",
                    executor="local",
                    status="warning",
                    summary=(
                        "⚠ 检测到中途测量；测量后状态会按随机结果分支，"
                        "当前调试器停止后续状态追踪。QASM 和 Agent 结果不受影响。"
                    ),
                    data={
                        "measurement_operation_index": operation_index,
                        "remaining_gate_count": remaining_gate_count,
                        "reason": "mid_circuit_measurement",
                    },
                )
                break
    return trace_sink.events[start_seq:]


__all__ = [
    "DEFAULT_MAX_TRACE_QUBITS",
    "STATE_AMPLITUDE_EPSILON",
    "trace_circuit",
]
