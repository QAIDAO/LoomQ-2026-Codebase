"""Public-contract and PyQPanda-runtime OriginIR renderers."""

from __future__ import annotations

import re

from ..qasm import GateOperation, MeasureOperation, Program, parse_openqasm2


_PUBLIC_GATE_NAMES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "rz": "RZ",
    "ry": "RY",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}

_RUNTIME_GATE_NAMES = {
    **_PUBLIC_GATE_NAMES,
    "sdg": "S",
    "tdg": "T",
    "cu1": "CR",
}


def transpile(qasm_str: str) -> str:
    return serialize_originir(parse_openqasm2(qasm_str))


def transpile_runtime(qasm_str: str) -> str:
    """Return the OriginIR dialect accepted by the installed PyQPanda SDK."""

    return serialize_originir(parse_openqasm2(qasm_str), runtime=True)


def serialize_originir(program: Program, *, runtime: bool = False) -> str:
    lines = [f"QINIT {program.quantum_register.size}", f"CREG {program.classical_register.size}"]
    gate_names = _RUNTIME_GATE_NAMES if runtime else _PUBLIC_GATE_NAMES
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            gate = gate_names[operation.name]
            operands = [_quantum_operand(operand, program) for operand in operation.operands]
            if runtime and operation.name in {"sdg", "tdg"}:
                lines.extend(("DAGGER", f"{gate} {', '.join(operands)}", "ENDDAGGER"))
            elif operation.parameter is None:
                lines.append(f"{gate} {', '.join(operands)}")
            elif not runtime:
                lines.append(f"{gate}({operation.parameter}) {', '.join(operands)}")
            else:
                lines.append(
                    f"{gate} {', '.join(operands)},({_origin_parameter(operation.parameter)})"
                )
        else:
            lines.extend(_measure_lines(operation, program))
    return "\n".join(lines) + "\n"


def _measure_lines(operation: MeasureOperation, program: Program) -> list[str]:
    if operation.source == program.quantum_register.name:
        return [
            f"MEASURE q[{index}], c[{index}]"
            for index in range(program.quantum_register.size)
        ]
    source = _quantum_operand(operation.source, program)
    destination = operation.destination.replace(program.classical_register.name + "[", "c[")
    return [f"MEASURE {source}, {destination}"]


def _quantum_operand(operand: str, program: Program) -> str:
    return operand.replace(program.quantum_register.name + "[", "q[")


def _origin_parameter(expression: str) -> str:
    """Render OpenQASM's lowercase pi token in OriginIR's required spelling."""

    return re.sub(r"\bpi\b", "PI", expression)
