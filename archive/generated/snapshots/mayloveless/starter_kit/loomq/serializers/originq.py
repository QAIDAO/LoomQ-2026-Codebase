"""Serialize platform-independent Circuit IR as OriginQ OriginIR."""

import math
from typing import Dict, List, Tuple

from ..ir import (
    Circuit,
    GateOperation,
    MeasureOperation,
    QubitRef,
    QuantumRegisterRef,
)
from ..measurements import (
    classical_bit_count,
    measurement_mapping,
    quantum_bit_indices,
)


# OriginIR 门名和 IR 参数、量子位数量保持数据驱动的一致映射。
_GATE_SPECS: Dict[str, Tuple[str, int, int]] = {
    "h": ("H", 1, 0),
    "x": ("X", 1, 0),
    "s": ("S", 1, 0),
    "sdg": ("SDAG", 1, 0),
    "t": ("T", 1, 0),
    "tdg": ("TDAG", 1, 0),
    "ry": ("RY", 1, 1),
    "rz": ("RZ", 1, 1),
    "cx": ("CNOT", 2, 0),
    "cu1": ("CU1", 2, 1),
    "swap": ("SWAP", 2, 0),
    "ccx": ("TOFFOLI", 3, 0),
}

_INVERSE_PHASE_ANGLES = {"sdg": -math.pi / 2, "tdg": -math.pi / 4}


def _measurement_count(operation: MeasureOperation) -> int:
    """Return the number of flattened pairs emitted for one measurement."""
    if isinstance(operation.quantum, QubitRef):
        return 1
    if isinstance(operation.quantum, QuantumRegisterRef):
        # Parser 已保证整寄存器测量的量子、经典寄存器宽度相同。
        return 0
    raise ValueError("invalid measurement quantum reference in Circuit IR")


def serialize_originq(circuit: Circuit, *, execution_mode: bool = False) -> str:
    """Return a complete OriginIR program with globally flattened bit indices.

    public 与 execution mode 都使用合同允许且 pyQPanda 3.8.5 可解析的写法；
    保留 ``execution_mode`` 参数以兼容 Runner 的现有调用契约。
    """
    qubit_indices = quantum_bit_indices(circuit)
    mappings = iter(measurement_mapping(circuit))
    lines: List[str] = [
        "QINIT %d" % len(qubit_indices),
        "CREG %d" % classical_bit_count(circuit),
    ]

    for operation in circuit.operations:
        if isinstance(operation, GateOperation):
            try:
                origin_name, expected_qubits, expected_parameters = _GATE_SPECS[
                    operation.name
                ]
            except KeyError as exc:
                raise ValueError(
                    "unsupported OriginIR gate %r" % operation.name
                ) from exc
            if len(operation.qubits) != expected_qubits:
                raise ValueError(
                    "OriginIR gate %r expects %d qubits, got %d"
                    % (operation.name, expected_qubits, len(operation.qubits))
                )
            if len(operation.parameters) != expected_parameters:
                raise ValueError(
                    "OriginIR gate %r expects %d parameters, got %d"
                    % (
                        operation.name,
                        expected_parameters,
                        len(operation.parameters),
                    )
                )
            operands = ", ".join(
                "q[%d]" % qubit_indices[qubit] for qubit in operation.qubits
            )
            parameter_values = ", ".join(
                format(value, ".17g") for value in operation.parameters
            )
            if operation.name in _INVERSE_PHASE_ANGLES:
                # SDK 不识别 SDAG/TDAG；等价 RZ 仅相差不可观测的全局相位。
                angle = format(_INVERSE_PHASE_ANGLES[operation.name], ".17g")
                lines.append("RZ %s,(%s)" % (operands, angle))
            elif operation.parameters:
                # 合同接受后置参数，且 CU1 的 OriginIR 等价门名可使用 CR。
                sdk_name = "CR" if operation.name == "cu1" else origin_name
                lines.append("%s %s,(%s)" % (sdk_name, operands, parameter_values))
            else:
                parameters = "(%s)" % parameter_values if parameter_values else ""
                lines.append("%s%s %s" % (origin_name, parameters, operands))
        elif isinstance(operation, MeasureOperation):
            pair_count = _measurement_count(operation)
            if pair_count:
                pairs = [next(mappings)]
            else:
                # 共享映射已按寄存器内部索引展开并保持操作出现顺序。
                quantum_register = operation.quantum.register
                register_size = next(
                    register.size
                    for register in circuit.quantum_registers
                    if register.name == quantum_register
                )
                pairs = [next(mappings) for _ in range(register_size)]
            lines.extend(
                "MEASURE q[%d], c[%d]" % (quantum_index, classical_index)
                for quantum_index, classical_index in pairs
            )
        else:
            raise TypeError("unsupported operation in Circuit IR: %r" % (operation,))

    return "\n".join(lines) + "\n"
