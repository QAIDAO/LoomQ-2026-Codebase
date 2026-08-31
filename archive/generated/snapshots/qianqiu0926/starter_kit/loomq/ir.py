"""Typed intermediate representation and strict OpenQASM 2.0 subset parser.

The contest deliberately defines a small source language.  Keeping that language
small and rejecting ambiguous input is safer than trying to repair it silently in
the compiler.  The L2 agent may repair user input before it reaches this parser.
"""

from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Union


GATE_ARITY = {
    "h": 1,
    "x": 1,
    "s": 1,
    "sdg": 1,
    "t": 1,
    "tdg": 1,
    "rz": 1,
    "ry": 1,
    "cx": 2,
    "cu1": 2,
    "swap": 2,
    "ccx": 3,
}
PARAMETER_GATES = {"rz", "ry", "cu1"}


class QASMError(ValueError):
    """Raised when input is outside the published LoomQ QASM subset."""


@dataclass(frozen=True)
class QubitRef:
    register: str
    index: int

    def qasm(self) -> str:
        return f"{self.register}[{self.index}]"


@dataclass(frozen=True)
class Gate:
    name: str
    qubits: tuple[QubitRef, ...]
    parameters: tuple[float, ...] = ()


@dataclass(frozen=True)
class Measure:
    qubit: QubitRef
    cbit: QubitRef


Operation = Union[Gate, Measure]


@dataclass
class Circuit:
    qregs: dict[str, int] = field(default_factory=dict)
    cregs: dict[str, int] = field(default_factory=dict)
    operations: list[Operation] = field(default_factory=list)

    @property
    def total_qubits(self) -> int:
        return sum(self.qregs.values())

    @property
    def total_cbits(self) -> int:
        return sum(self.cregs.values())

    def _offset(self, registers: dict[str, int], name: str) -> int:
        offset = 0
        for current, size in registers.items():
            if current == name:
                return offset
            offset += size
        raise QASMError(f"unknown register: {name}")

    def qubit_index(self, ref: QubitRef) -> int:
        return self._offset(self.qregs, ref.register) + ref.index

    def cbit_index(self, ref: QubitRef) -> int:
        return self._offset(self.cregs, ref.register) + ref.index

    def quantum_instruction_lines(self) -> list[str]:
        lines: list[str] = []
        for operation in self.operations:
            if isinstance(operation, Gate):
                parameter = ""
                if operation.parameters:
                    parameter = "(" + ",".join(format_angle(v) for v in operation.parameters) + ")"
                args = ", ".join(ref.qasm() for ref in operation.qubits)
                lines.append(f"{operation.name}{parameter} {args};")
            else:
                lines.append(f"measure {operation.qubit.qasm()} -> {operation.cbit.qasm()};")
        return lines


def strip_comments(source: str) -> str:
    """Remove C/QASM comments without accidentally joining adjacent tokens."""
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def _eval_angle(expression: str) -> float:
    """Evaluate the arithmetic subset used by qelib1 angle parameters."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise QASMError(f"invalid gate parameter: {expression!r}") from exc

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id.lower() == "pi":
            return math.pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
        ):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise QASMError("gate parameter divides by zero")
                return left / right
            return left**right
        raise QASMError(f"unsupported gate parameter expression: {expression!r}")

    value = visit(tree)
    if not math.isfinite(value):
        raise QASMError("gate parameter must be finite")
    return value


def format_angle(value: float) -> str:
    """Stable text form that round-trips through a binary64 parser."""
    if value == 0:
        return "0"
    return format(value, ".17g")


def _split_arguments(text: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    result.append(text[start:].strip())
    if any(not item for item in result):
        raise QASMError(f"invalid argument list: {text!r}")
    return result


def _refs(token: str, registers: dict[str, int], kind: str) -> list[QubitRef]:
    match = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\[\s*(\d+)\s*\])?", token.strip())
    if not match:
        raise QASMError(f"invalid {kind} operand: {token!r}")
    name, raw_index = match.groups()
    if name not in registers:
        raise QASMError(f"undeclared {kind} register: {name}")
    if raw_index is None:
        return [QubitRef(name, index) for index in range(registers[name])]
    index = int(raw_index)
    if index >= registers[name]:
        raise QASMError(f"{kind} index out of range: {name}[{index}]")
    return [QubitRef(name, index)]


def _broadcast(operands: list[list[QubitRef]]) -> Iterable[tuple[QubitRef, ...]]:
    lengths = {len(item) for item in operands}
    if lengths == {1}:
        yield tuple(item[0] for item in operands)
        return
    if len(lengths) != 1:
        raise QASMError("whole-register gate operands must have equal lengths")
    for index in range(lengths.pop()):
        yield tuple(item[index] for item in operands)


def parse_qasm2(source: str) -> Circuit:
    """Parse the exact straight-line OpenQASM 2 subset published by LoomQ."""
    if not isinstance(source, str) or not source.strip():
        raise QASMError("QASM source must be a non-empty string")
    clean = strip_comments(source)
    statements = [item.strip() for item in clean.split(";") if item.strip()]
    if not statements or not re.fullmatch(r"OPENQASM\s+2\.0", statements[0], re.IGNORECASE):
        raise QASMError("source must begin with OPENQASM 2.0;")

    circuit = Circuit()
    for statement in statements[1:]:
        if re.fullmatch(r'include\s+["\']qelib1\.inc["\']', statement, re.IGNORECASE):
            continue
        declaration = re.fullmatch(
            r"(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]",
            statement,
            re.IGNORECASE,
        )
        if declaration:
            kind, name, raw_size = declaration.groups()
            target = circuit.qregs if kind.lower() == "qreg" else circuit.cregs
            if name in circuit.qregs or name in circuit.cregs:
                raise QASMError(f"duplicate register name: {name}")
            size = int(raw_size)
            if size <= 0:
                raise QASMError("register sizes must be positive")
            target[name] = size
            continue

        measurement = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+)", statement, re.IGNORECASE)
        if measurement:
            qrefs = _refs(measurement.group(1), circuit.qregs, "quantum")
            crefs = _refs(measurement.group(2), circuit.cregs, "classical")
            if len(qrefs) != len(crefs):
                raise QASMError("measurement register sizes differ")
            circuit.operations.extend(Measure(q, c) for q, c in zip(qrefs, crefs))
            continue

        gate = re.fullmatch(r"([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s+(.+)", statement)
        if not gate:
            raise QASMError(f"unsupported or malformed statement: {statement!r}")
        raw_name, raw_parameters, raw_operands = gate.groups()
        name = raw_name.lower()
        if name not in GATE_ARITY:
            raise QASMError(f"gate outside LoomQ whitelist: {raw_name}")
        parameters: tuple[float, ...]
        if name in PARAMETER_GATES:
            if raw_parameters is None:
                raise QASMError(f"gate {name} requires one angle parameter")
            parts = _split_arguments(raw_parameters)
            if len(parts) != 1:
                raise QASMError(f"gate {name} requires exactly one angle parameter")
            parameters = (_eval_angle(parts[0]),)
        else:
            if raw_parameters is not None:
                raise QASMError(f"gate {name} takes no parameters")
            parameters = ()
        operand_parts = _split_arguments(raw_operands)
        if len(operand_parts) != GATE_ARITY[name]:
            raise QASMError(f"gate {name} requires {GATE_ARITY[name]} qubit operand(s)")
        operand_refs = [_refs(item, circuit.qregs, "quantum") for item in operand_parts]
        for refs in _broadcast(operand_refs):
            if len(set(refs)) != len(refs):
                raise QASMError(f"gate {name} requires distinct qubits")
            circuit.operations.append(Gate(name, refs, parameters))

    if not circuit.qregs:
        raise QASMError("at least one qreg declaration is required")
    return circuit
