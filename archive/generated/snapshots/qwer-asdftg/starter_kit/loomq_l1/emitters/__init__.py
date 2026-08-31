"""Deterministic emitters for LoomQ L1 provider IR formats."""

import math
import re

from ..errors import QASMSemanticError, UnsupportedTargetError
from ..model import Circuit, Measurement, Operation, Register
from ..parser import GATE_ARITY, PARAMETER_GATES


_REGISTER_NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_VALIDATION_TOKEN = object()


def _invalid(message: str) -> None:
    raise QASMSemanticError(f"invalid circuit IR for emission: {message}")


def _validate_registers(registers: object, kind: str) -> tuple[int, set[str]]:
    if not isinstance(registers, tuple):
        _invalid(f"{kind} registers must be a tuple")
    if not registers:
        _invalid(f"at least one {kind} register is required")

    width = 0
    names = set()
    for register in registers:
        if not isinstance(register, Register):
            _invalid(f"{kind} registers must contain Register values")
        if type(register.name) is not str or _REGISTER_NAME_PATTERN.fullmatch(register.name) is None:
            _invalid(f"{kind} register has an invalid name")
        if register.name in names:
            _invalid(f"duplicate {kind} register name")
        if type(register.size) is not int or register.size <= 0:
            _invalid(f"{kind} register has an invalid size")
        if type(register.offset) is not int or register.offset != width:
            _invalid(f"{kind} register offsets must be contiguous")
        names.add(register.name)
        width += register.size
    return width, names


def _validate_circuit(circuit: object) -> Circuit:
    if not isinstance(circuit, Circuit):
        _invalid("expected a Circuit")
    if not isinstance(circuit.operations, tuple):
        _invalid("operations must be a tuple")
    if not isinstance(circuit.measurements, tuple):
        _invalid("measurements must be a tuple")

    num_qubits, quantum_names = _validate_registers(circuit.qregs, "quantum")
    num_clbits, classical_names = _validate_registers(circuit.cregs, "classical")
    if quantum_names & classical_names:
        _invalid("quantum and classical registers must have unique names")

    for operation in circuit.operations:
        if not isinstance(operation, Operation):
            _invalid("operations must contain Operation values")
        if not isinstance(operation.name, str) or operation.name not in GATE_ARITY:
            _invalid("unsupported operation")
        if not isinstance(operation.qubits, tuple):
            _invalid(f"operation {operation.name} qubits must be a tuple")
        if len(operation.qubits) != GATE_ARITY[operation.name]:
            _invalid(f"operation {operation.name} has wrong arity")
        if any(type(index) is not int or not 0 <= index < num_qubits for index in operation.qubits):
            _invalid(f"operation {operation.name} has an invalid qubit index")
        if len(operation.qubits) > 1 and len(set(operation.qubits)) != len(operation.qubits):
            _invalid(f"operation {operation.name} must use distinct qubit indices")

        needs_parameter = operation.name in PARAMETER_GATES
        if needs_parameter != (operation.parameter is not None):
            _invalid(f"operation {operation.name} has an invalid parameter form")
        if needs_parameter:
            if type(operation.parameter) not in (int, float):
                _invalid(f"operation {operation.name} has an invalid parameter type")
            try:
                parameter_is_finite = math.isfinite(operation.parameter)
            except (OverflowError, TypeError, ValueError):
                parameter_is_finite = False
            if not parameter_is_finite:
                _invalid(f"operation {operation.name} has a non-finite parameter")

    used_cbits = set()
    for measurement in circuit.measurements:
        if not isinstance(measurement, Measurement):
            _invalid("measurements must contain Measurement values")
        if type(measurement.qubit) is not int or not 0 <= measurement.qubit < num_qubits:
            _invalid("measurement has an invalid qubit index")
        if type(measurement.cbit) is not int or not 0 <= measurement.cbit < num_clbits:
            _invalid("measurement has an invalid classical index")
        if measurement.cbit in used_cbits:
            _invalid("duplicate classical measurement destination")
        used_cbits.add(measurement.cbit)
    return circuit


def _format_parameter(value: float) -> str:
    return format(value, ".17g")


from .braket import emit_braket
from .originq import emit_originq
from .spinq import emit_spinq


_EMITTERS = {
    "spinq": emit_spinq,
    "originq": emit_originq,
    "braket": emit_braket,
}


def emit(circuit: Circuit, target: str) -> str:
    """Emit validated *circuit* as deterministic textual IR for *target*."""
    if not isinstance(target, str) or target not in _EMITTERS:
        raise UnsupportedTargetError(f"unsupported target: {target!r}")
    validated_circuit = _validate_circuit(circuit)
    return _EMITTERS[target](validated_circuit, _validation_token=_VALIDATION_TOKEN)


__all__ = ["emit", "emit_braket", "emit_originq", "emit_spinq"]
