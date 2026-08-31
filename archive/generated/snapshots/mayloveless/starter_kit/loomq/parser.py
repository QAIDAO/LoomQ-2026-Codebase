"""Parser for the LoomQ L1 OpenQASM 2.0 subset."""

import re
from dataclasses import dataclass
from typing import Dict, Iterator, List, Match, Optional, Tuple

from .errors import QASMParseError, QASMSemanticError, UnsupportedGateError
from .expressions import ParameterExpressionError, parse_angle_expression
from .ir import (
    Circuit,
    ClassicalBitRef,
    ClassicalRegister,
    ClassicalRegisterRef,
    GateOperation,
    MeasureOperation,
    Operation,
    QuantumRegister,
    QuantumRegisterRef,
    QubitRef,
)


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_INDEXED_REF_RE = re.compile(
    r"^(?P<name>%s)\s*\[\s*(?P<index>\d+)\s*\]$" % _IDENTIFIER
)
_REGISTER_RE = re.compile(
    r"^(?P<kind>qreg|creg)\s+(?P<name>%s)\s*\[\s*(?P<size>\d+)\s*\]$"
    % _IDENTIFIER,
    re.IGNORECASE,
)
_MEASURE_RE = re.compile(
    r"^measure\s+(?P<quantum>.+?)\s*->\s*(?P<classical>.+)$", re.IGNORECASE
)
_GATE_NAME_RE = re.compile(r"^(?P<name>%s)" % _IDENTIFIER)


@dataclass(frozen=True)
class GateSpec:
    qubit_count: int
    parameter_count: int = 0


# 门规格保持数据驱动，Runner 是否支持某门由各后端单独决定。
SUPPORTED_GATES: Dict[str, GateSpec] = {
    "h": GateSpec(qubit_count=1),
    "x": GateSpec(qubit_count=1),
    "s": GateSpec(qubit_count=1),
    "sdg": GateSpec(qubit_count=1),
    "t": GateSpec(qubit_count=1),
    "tdg": GateSpec(qubit_count=1),
    "ry": GateSpec(qubit_count=1, parameter_count=1),
    "rz": GateSpec(qubit_count=1, parameter_count=1),
    "cx": GateSpec(qubit_count=2),
    "cu1": GateSpec(qubit_count=2, parameter_count=1),
    "swap": GateSpec(qubit_count=2),
    "ccx": GateSpec(qubit_count=3),
}


@dataclass(frozen=True)
class GateStatement:
    name: str
    parameter_text: Optional[str]
    operand_text: str


def _split_top_level_commas(
    text: str, *, line: int, statement: str
) -> List[str]:
    if not text.strip():
        return []
    items: List[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise QASMParseError(
                    "unbalanced parentheses in gate parameters",
                    line=line,
                    statement=statement,
                )
        elif character == "," and depth == 0:
            items.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        raise QASMParseError(
            "unbalanced parentheses in gate parameters",
            line=line,
            statement=statement,
        )
    items.append(text[start:].strip())
    return items


def _split_gate_statement(statement: str, line: int) -> Optional[GateStatement]:
    name_match = _GATE_NAME_RE.match(statement)
    if name_match is None:
        return None
    name = name_match.group("name")
    cursor = name_match.end()
    name_end = cursor
    while cursor < len(statement) and statement[cursor].isspace():
        cursor += 1

    parameter_text: Optional[str] = None
    if cursor < len(statement) and statement[cursor] == "(":
        start = cursor + 1
        depth = 1
        cursor += 1
        while cursor < len(statement) and depth:
            if statement[cursor] == "(":
                depth += 1
            elif statement[cursor] == ")":
                depth -= 1
            cursor += 1
        if depth:
            raise QASMParseError(
                "unbalanced parentheses in gate parameters",
                line=line,
                statement=statement,
            )
        parameter_text = statement[start : cursor - 1]
        if cursor >= len(statement) or not statement[cursor].isspace():
            raise QASMParseError(
                "expected qubit operands after gate parameters",
                line=line,
                statement=statement,
            )
    elif cursor == name_end:
        raise QASMParseError(
            "expected qubit operands after gate name",
            line=line,
            statement=statement,
        )
    operand_text = statement[cursor:].strip()
    if not operand_text:
        raise QASMParseError(
            "expected qubit operands after gate name",
            line=line,
            statement=statement,
        )
    return GateStatement(
        name=name,
        parameter_text=parameter_text,
        operand_text=operand_text,
    )


def _statements(source: str) -> Iterator[Tuple[str, int]]:
    without_comments = re.sub(r"//[^\n]*", "", source)
    buffer: List[str] = []
    line = 1
    statement_line: Optional[int] = None

    for character in without_comments:
        if statement_line is None and not character.isspace():
            statement_line = line
        if character == ";":
            statement = "".join(buffer).strip()
            if statement:
                yield statement, statement_line if statement_line is not None else line
            buffer = []
            statement_line = None
        else:
            buffer.append(character)
        if character == "\n":
            line += 1

    remainder = "".join(buffer).strip()
    if remainder:
        raise QASMParseError(
            "statement is missing a terminating semicolon",
            line=statement_line,
            statement=remainder,
        )


def _require_match(
    pattern: re.Pattern[str], statement: str, line: int, message: str
) -> Match[str]:
    match = pattern.fullmatch(statement)
    if match is None:
        raise QASMParseError(message, line=line, statement=statement)
    return match


def _parse_qubit(
    text: str,
    quantum_registers: Dict[str, QuantumRegister],
    *,
    line: int,
    statement: str,
) -> QubitRef:
    match = _require_match(
        _INDEXED_REF_RE, text.strip(), line, "expected an indexed qubit reference"
    )
    name = match.group("name")
    index = int(match.group("index"))
    register = quantum_registers.get(name)
    if register is None:
        raise QASMSemanticError(
            "quantum register '%s' is not declared" % name,
            line=line,
            statement=statement,
        )
    if index >= register.size:
        raise QASMSemanticError(
            "qubit index %d is out of range for register '%s[%d]'"
            % (index, name, register.size),
            line=line,
            statement=statement,
        )
    return QubitRef(register=name, index=index)


def _parse_classical_bit(
    text: str,
    classical_registers: Dict[str, ClassicalRegister],
    *,
    line: int,
    statement: str,
) -> ClassicalBitRef:
    match = _require_match(
        _INDEXED_REF_RE, text.strip(), line, "expected an indexed classical bit reference"
    )
    name = match.group("name")
    index = int(match.group("index"))
    register = classical_registers.get(name)
    if register is None:
        raise QASMSemanticError(
            "classical register '%s' is not declared" % name,
            line=line,
            statement=statement,
        )
    if index >= register.size:
        raise QASMSemanticError(
            "classical bit index %d is out of range for register '%s[%d]'"
            % (index, name, register.size),
            line=line,
            statement=statement,
        )
    return ClassicalBitRef(register=name, index=index)


def _parse_measurement(
    match: Match[str],
    quantum_registers: Dict[str, QuantumRegister],
    classical_registers: Dict[str, ClassicalRegister],
    *,
    line: int,
    statement: str,
) -> MeasureOperation:
    quantum_text = match.group("quantum").strip()
    classical_text = match.group("classical").strip()
    quantum_indexed = _INDEXED_REF_RE.fullmatch(quantum_text) is not None
    classical_indexed = _INDEXED_REF_RE.fullmatch(classical_text) is not None

    if quantum_indexed != classical_indexed:
        raise QASMSemanticError(
            "measurement must map one qubit to one bit or one register to one register",
            line=line,
            statement=statement,
        )

    if quantum_indexed:
        return MeasureOperation(
            quantum=_parse_qubit(
                quantum_text,
                quantum_registers,
                line=line,
                statement=statement,
            ),
            classical=_parse_classical_bit(
                classical_text,
                classical_registers,
                line=line,
                statement=statement,
            ),
        )

    if re.fullmatch(_IDENTIFIER, quantum_text) is None:
        raise QASMParseError(
            "invalid quantum register reference", line=line, statement=statement
        )
    if re.fullmatch(_IDENTIFIER, classical_text) is None:
        raise QASMParseError(
            "invalid classical register reference", line=line, statement=statement
        )
    quantum_register = quantum_registers.get(quantum_text)
    classical_register = classical_registers.get(classical_text)
    if quantum_register is None:
        raise QASMSemanticError(
            "quantum register '%s' is not declared" % quantum_text,
            line=line,
            statement=statement,
        )
    if classical_register is None:
        raise QASMSemanticError(
            "classical register '%s' is not declared" % classical_text,
            line=line,
            statement=statement,
        )
    if quantum_register.size != classical_register.size:
        raise QASMSemanticError(
            "register measurement size mismatch: '%s' has %d qubits but '%s' has %d bits"
            % (
                quantum_text,
                quantum_register.size,
                classical_text,
                classical_register.size,
            ),
            line=line,
            statement=statement,
        )
    return MeasureOperation(
        quantum=QuantumRegisterRef(register=quantum_text),
        classical=ClassicalRegisterRef(register=classical_text),
    )


def _parse_gate(
    gate: GateStatement,
    quantum_registers: Dict[str, QuantumRegister],
    *,
    line: int,
    statement: str,
) -> GateOperation:
    name = gate.name.lower()
    spec = SUPPORTED_GATES.get(name)
    if spec is None:
        raise UnsupportedGateError(
            "unsupported quantum gate '%s'" % name, line=line, statement=statement
        )

    parameter_text = gate.parameter_text
    parameters: Tuple[float, ...] = ()
    if parameter_text is not None:
        raw_parameters = _split_top_level_commas(
            parameter_text, line=line, statement=statement
        )
        try:
            parameters = tuple(
                parse_angle_expression(value) for value in raw_parameters
            )
        except ParameterExpressionError as exc:
            raise QASMParseError(
                "invalid parameter expression: %s" % exc,
                line=line,
                statement=statement,
            ) from exc
    if len(parameters) != spec.parameter_count:
        raise QASMParseError(
            "gate '%s' expects %d parameter(s), got %d"
            % (name, spec.parameter_count, len(parameters)),
            line=line,
            statement=statement,
        )

    operands = [operand.strip() for operand in gate.operand_text.split(",")]
    if len(operands) != spec.qubit_count or any(not value for value in operands):
        raise QASMParseError(
            "gate '%s' expects %d qubit operand(s), got %d"
            % (name, spec.qubit_count, len(operands)),
            line=line,
            statement=statement,
        )
    qubits = tuple(
        _parse_qubit(
            operand, quantum_registers, line=line, statement=statement
        )
        for operand in operands
    )
    return GateOperation(name=name, qubits=qubits, parameters=parameters)


def parse_qasm(source: str) -> Circuit:
    """Parse the supported OpenQASM 2.0 subset into a platform-neutral IR."""
    if not isinstance(source, str):
        raise TypeError("OpenQASM source must be a string")

    version: Optional[str] = None
    quantum_registers: Dict[str, QuantumRegister] = {}
    classical_registers: Dict[str, ClassicalRegister] = {}
    operations: List[Operation] = []

    for position, (statement, line) in enumerate(_statements(source)):
        version_match = re.fullmatch(
            r"OPENQASM\s+([0-9]+(?:\.[0-9]+)?)", statement, re.IGNORECASE
        )
        if version_match is not None:
            if position != 0:
                raise QASMParseError(
                    "OPENQASM declaration must be the first statement",
                    line=line,
                    statement=statement,
                )
            if version is not None:
                raise QASMParseError(
                    "duplicate OPENQASM declaration", line=line, statement=statement
                )
            version = version_match.group(1)
            if version != "2.0":
                raise QASMParseError(
                    "only OPENQASM 2.0 is supported", line=line, statement=statement
                )
            continue

        if version is None:
            raise QASMParseError(
                "OPENQASM 2.0 declaration must be the first statement",
                line=line,
                statement=statement,
            )

        include_match = re.fullmatch(
            r'include\s+"([^"]+)"', statement, re.IGNORECASE
        )
        if include_match is not None:
            if include_match.group(1) != "qelib1.inc":
                raise QASMParseError(
                    "unsupported include '%s'" % include_match.group(1),
                    line=line,
                    statement=statement,
                )
            continue

        register_match = _REGISTER_RE.fullmatch(statement)
        if register_match is not None:
            name = register_match.group("name")
            size = int(register_match.group("size"))
            if size <= 0:
                raise QASMSemanticError(
                    "register '%s' must have a positive size" % name,
                    line=line,
                    statement=statement,
                )
            if name in quantum_registers or name in classical_registers:
                raise QASMSemanticError(
                    "register '%s' is already declared" % name,
                    line=line,
                    statement=statement,
                )
            if register_match.group("kind").lower() == "qreg":
                quantum_registers[name] = QuantumRegister(name=name, size=size)
            else:
                classical_registers[name] = ClassicalRegister(name=name, size=size)
            continue

        measure_match = _MEASURE_RE.fullmatch(statement)
        if measure_match is not None:
            operations.append(
                _parse_measurement(
                    measure_match,
                    quantum_registers,
                    classical_registers,
                    line=line,
                    statement=statement,
                )
            )
            continue


        gate_statement = _split_gate_statement(statement, line)
        if gate_statement is not None:
            operations.append(
                _parse_gate(
                    gate_statement,
                    quantum_registers,
                    line=line,
                    statement=statement,
                )
            )
            continue

        raise QASMParseError(
            "unsupported or malformed statement", line=line, statement=statement
        )

    if version is None:
        raise QASMParseError("missing OPENQASM 2.0 declaration")

    return Circuit(
        openqasm_version=version,
        quantum_registers=tuple(quantum_registers.values()),
        classical_registers=tuple(classical_registers.values()),
        operations=tuple(operations),
    )
