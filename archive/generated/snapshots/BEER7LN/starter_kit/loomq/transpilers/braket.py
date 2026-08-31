"""Public-contract and SDK-runtime OpenQASM 3 renderers for Braket."""

from __future__ import annotations

from ..qasm import GateOperation, MeasureOperation, Program, parse_openqasm2


_PUBLIC_GATE_NAMES = {
    "cx": "cnot",
    "cu1": "cp",
}

_RUNTIME_GATE_NAMES = {
    "sdg": "si",
    "tdg": "ti",
    "cx": "cnot",
    "cu1": "cphaseshift",
    "ccx": "ccnot",
}


def transpile(qasm_str: str) -> str:
    """Return the canonical artifact required by target_ir_contract.md."""

    return serialize_openqasm3(parse_openqasm2(qasm_str))


def transpile_runtime(qasm_str: str) -> str:
    """Return the OpenQASM 3 dialect accepted by the installed Braket SDK."""

    return serialize_openqasm3(parse_openqasm2(qasm_str), runtime=True)


def serialize_openqasm3(program: Program, *, runtime: bool = False) -> str:
    lines = [
        "OPENQASM 3.0;",
        *([] if runtime else ['include "stdgates.inc";']),
        f"qubit[{program.quantum_register.size}] {program.quantum_register.name};",
        f"bit[{program.classical_register.size}] {program.classical_register.name};",
    ]
    gate_names = _RUNTIME_GATE_NAMES if runtime else _PUBLIC_GATE_NAMES
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            gate = gate_names.get(operation.name, operation.name)
            parameter = f"({operation.parameter})" if operation.parameter is not None else ""
            lines.append(f"{gate}{parameter} {', '.join(operation.operands)};")
        else:
            lines.append(_serialize_measurement(operation, program))
    return "\n".join(lines) + "\n"


def _serialize_measurement(operation: MeasureOperation, program: Program) -> str:
    if operation.source == program.quantum_register.name:
        return f"{program.classical_register.name} = measure {program.quantum_register.name};"
    return f"{operation.destination} = measure {operation.source};"
