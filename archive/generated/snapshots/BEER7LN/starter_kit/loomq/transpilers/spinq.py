"""SpinQ target implementation for the public L1 contract."""

from __future__ import annotations

from dataclasses import replace

from ..qasm import GateOperation, Program, parse_openqasm2, serialize_openqasm2
from ..simulator import _parameter_value


def transpile(qasm_str: str) -> str:
    """Validate and canonicalize OpenQASM 2.0 for the SpinQ QASM target."""

    return serialize_openqasm2(parse_openqasm2(qasm_str))


def transpile_runtime(qasm_str: str) -> str:
    """Render exact-decimal parameters for the installed SpinQ compiler."""

    return serialize_runtime(parse_openqasm2(qasm_str))


def serialize_runtime(program: Program) -> str:
    """Render one already-validated Program for SpinQ compiler execution."""

    operations = tuple(
        replace(
            operation,
            parameter=_fixed_decimal(_parameter_value(operation.parameter)),
        )
        if isinstance(operation, GateOperation) and operation.parameter is not None
        else operation
        for operation in program.operations
    )
    return serialize_openqasm2(replace(program, operations=operations))


def _fixed_decimal(value: float) -> str:
    rendered = format(value, ".17f").rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered
