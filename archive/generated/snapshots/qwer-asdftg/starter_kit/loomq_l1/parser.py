"""Parser for the LoomQ contest OpenQASM 2.0 subset."""

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .errors import ExpressionError, QASMParseError, QASMSemanticError
from .expressions import evaluate_expression
from .model import Circuit, Measurement, Operation, Register
from .normalize import MAX_WIDTH


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
PARAMETER_GATES = frozenset({"rz", "ry", "cu1"})


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_ASCII_WHITESPACE_PATTERN = r"[ \t\r\n]"
_HEADER_PATTERN = re.compile(rf"OPENQASM{_ASCII_WHITESPACE_PATTERN}+2\.0")
_INCLUDE_PATTERN = re.compile(
    rf'include{_ASCII_WHITESPACE_PATTERN}+"qelib1\.inc"'
)
_REGISTER_PATTERN = re.compile(
    rf"(?P<kind>qreg|creg){_ASCII_WHITESPACE_PATTERN}+"
    rf"(?P<name>{_IDENTIFIER}){_ASCII_WHITESPACE_PATTERN}*\["
    rf"{_ASCII_WHITESPACE_PATTERN}*(?P<size>[0-9]+)"
    rf"{_ASCII_WHITESPACE_PATTERN}*\]$"
)
_OPERAND_PATTERN = re.compile(
    rf"(?P<name>{_IDENTIFIER})(?:{_ASCII_WHITESPACE_PATTERN}*\["
    rf"{_ASCII_WHITESPACE_PATTERN}*(?P<index>[0-9]+)"
    rf"{_ASCII_WHITESPACE_PATTERN}*\])?$"
)
_GATE_NAME_PATTERN = re.compile(_IDENTIFIER)
_MAX_DECIMAL_LITERAL_LENGTH = 256
_ASCII_WHITESPACE = " \t\r\n"


def _parse_error(message: str, statement: Optional[str] = None) -> QASMParseError:
    if statement is None:
        return QASMParseError(message)
    return QASMParseError(f"{message}: {statement}")


def _semantic_error(message: str, statement: str) -> QASMSemanticError:
    return QASMSemanticError(f"{message}: {statement}")


def _strip_ascii_whitespace(source: str) -> str:
    return source.strip(_ASCII_WHITESPACE)


def _remove_comments(source: str) -> str:
    result: List[str] = []
    index = 0
    while index < len(source):
        if source.startswith("//", index):
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            if index == len(source):
                break
            result.append("\n")
            if source[index] == "\r":
                index += 1
                if index < len(source) and source[index] == "\n":
                    index += 1
            else:
                index += 1
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                raise _parse_error("unterminated block comment")
            result.append(" " + "\n" * source.count("\n", index, end + 2))
            index = end + 2
        else:
            result.append(source[index])
            index += 1
    return "".join(result)


def _split_statements(source: str) -> Tuple[str, ...]:
    without_comments = _remove_comments(source)
    stripped = _strip_ascii_whitespace(without_comments)
    if not stripped:
        raise _parse_error("source is empty")
    if not stripped.endswith(";"):
        raise _parse_error("unterminated final statement")

    statements = tuple(
        _strip_ascii_whitespace(part) for part in without_comments.split(";")[:-1]
    )
    if any(not statement for statement in statements):
        raise _parse_error("empty statement")
    return statements


def _resolve_operand(
    source: str,
    expected_registers: Dict[str, Register],
    other_registers: Dict[str, Register],
    *,
    require_index: bool,
    statement: str,
) -> Tuple[Register, Optional[int]]:
    match = _OPERAND_PATTERN.fullmatch(_strip_ascii_whitespace(source))
    if match is None:
        raise _parse_error("malformed operand", statement)

    name = match.group("name")
    if name in other_registers:
        raise _semantic_error("register has the wrong type", statement)
    register = expected_registers.get(name)
    if register is None:
        raise _semantic_error("unknown register", statement)

    index_source = match.group("index")
    if require_index and index_source is None:
        raise _parse_error("indexed operand required", statement)
    if index_source is None:
        return register, None
    if len(index_source) > _MAX_DECIMAL_LITERAL_LENGTH:
        raise _parse_error("operand index is too long", statement)

    index = int(index_source)
    if index >= register.size:
        raise _semantic_error("register index is out of range", statement)
    return register, index


def _parse_gate(statement: str) -> Tuple[str, Optional[str], Tuple[str, ...]]:
    name_match = _GATE_NAME_PATTERN.match(statement)
    if name_match is None:
        raise _parse_error("malformed statement", statement)

    name = name_match.group(0)
    position = name_match.end()
    parameter_source: Optional[str] = None

    while position < len(statement) and statement[position] in _ASCII_WHITESPACE:
        position += 1

    if position < len(statement) and statement[position] == "(":
        parameter_start = position + 1
        depth = 1
        position += 1
        while position < len(statement) and depth:
            character = statement[position]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            position += 1
        if depth:
            raise _parse_error("unterminated gate parameter", statement)
        parameter_source = statement[parameter_start : position - 1]
        while position < len(statement) and statement[position] in _ASCII_WHITESPACE:
            position += 1
    elif position == name_match.end():
        raise _parse_error("missing separator after gate name or parameter", statement)

    operand_source = _strip_ascii_whitespace(statement[position:])
    if not operand_source:
        raise _parse_error("missing gate operands", statement)

    operands = tuple(_strip_ascii_whitespace(part) for part in operand_source.split(","))
    if any(not operand for operand in operands):
        raise _parse_error("malformed gate operands", statement)
    return name, parameter_source, operands


def _append_measurements(
    statement: str,
    qreg_by_name: Dict[str, Register],
    creg_by_name: Dict[str, Register],
    used_cbits: set[int],
    measurements: List[Measurement],
) -> None:
    parts = statement[len("measure") :].split("->")
    if (
        len(parts) != 2
        or not _strip_ascii_whitespace(parts[0])
        or not _strip_ascii_whitespace(parts[1])
    ):
        raise _parse_error("malformed measurement", statement)

    qreg, qindex = _resolve_operand(
        parts[0], qreg_by_name, creg_by_name, require_index=False, statement=statement
    )
    creg, cindex = _resolve_operand(
        parts[1], creg_by_name, qreg_by_name, require_index=False, statement=statement
    )
    if (qindex is None) != (cindex is None):
        raise _semantic_error("measurement operands must both be bits or registers", statement)
    if qindex is None:
        if qreg.size != creg.size:
            raise _semantic_error("whole-register measurement sizes differ", statement)
        pairs: Iterable[Tuple[int, int]] = (
            (qreg.offset + index, creg.offset + index) for index in range(qreg.size)
        )
    else:
        pairs = ((qreg.offset + qindex, creg.offset + cindex),)

    for qubit, cbit in pairs:
        if cbit in used_cbits:
            raise _semantic_error("duplicate classical measurement destination", statement)
        used_cbits.add(cbit)
        measurements.append(Measurement(qubit, cbit))


def parse_qasm(source: str) -> Circuit:
    """Parse the contest OpenQASM 2.0 subset into an immutable circuit."""
    if type(source) is not str:
        raise _parse_error("source must be a string")
    statements = _split_statements(source)
    if len(statements) < 2:
        raise _parse_error("missing required OpenQASM headers")
    if _HEADER_PATTERN.fullmatch(statements[0]) is None:
        raise _parse_error("expected OPENQASM 2.0 declaration", statements[0])
    if _INCLUDE_PATTERN.fullmatch(statements[1]) is None:
        raise _parse_error("expected include \"qelib1.inc\" declaration", statements[1])

    qregs: List[Register] = []
    cregs: List[Register] = []
    qreg_by_name: Dict[str, Register] = {}
    creg_by_name: Dict[str, Register] = {}
    operations: List[Operation] = []
    measurements: List[Measurement] = []
    used_cbits: set[int] = set()
    next_qoffset = 0
    next_coffset = 0
    executable_seen = False
    measurement_seen = False

    for statement in statements[2:]:
        if statement.startswith("OPENQASM") or statement.startswith("include"):
            raise _parse_error("header or include declaration is misplaced", statement)

        register_match = _REGISTER_PATTERN.fullmatch(statement)
        if register_match is not None:
            if executable_seen:
                raise _parse_error("register declaration after executable statement", statement)
            name = register_match.group("name")
            if name in qreg_by_name or name in creg_by_name:
                raise _semantic_error("duplicate register name", statement)
            size_source = register_match.group("size")
            if len(size_source) > _MAX_DECIMAL_LITERAL_LENGTH:
                raise _parse_error("register size is too long", statement)
            size = int(size_source)
            if size <= 0:
                raise _semantic_error("register size must be positive", statement)
            if size > MAX_WIDTH:
                raise _semantic_error("register size exceeds supported width", statement)
            if register_match.group("kind") == "qreg":
                if next_qoffset + size > MAX_WIDTH:
                    raise _semantic_error("register size exceeds supported width", statement)
                register = Register(name, size, next_qoffset)
                qregs.append(register)
                qreg_by_name[name] = register
                next_qoffset += size
            else:
                if next_coffset + size > MAX_WIDTH:
                    raise _semantic_error("register size exceeds supported width", statement)
                register = Register(name, size, next_coffset)
                cregs.append(register)
                creg_by_name[name] = register
                next_coffset += size
            continue
        if statement.startswith("qreg") or statement.startswith("creg"):
            raise _parse_error("malformed register declaration", statement)

        executable_seen = True
        if statement == "measure" or (
            statement.startswith("measure")
            and len(statement) > len("measure")
            and statement[len("measure")] in _ASCII_WHITESPACE
        ):
            _append_measurements(
                statement, qreg_by_name, creg_by_name, used_cbits, measurements
            )
            measurement_seen = True
            continue

        name, parameter_source, operand_sources = _parse_gate(statement)
        if measurement_seen:
            raise _semantic_error("quantum gate after measurement", statement)
        if name not in GATE_ARITY:
            raise _semantic_error("unknown gate", statement)
        if len(operand_sources) != GATE_ARITY[name]:
            raise _semantic_error("wrong gate arity", statement)
        if (name in PARAMETER_GATES) != (parameter_source is not None):
            raise _semantic_error("invalid gate parameter form", statement)

        qubits = []
        for operand_source in operand_sources:
            register, index = _resolve_operand(
                operand_source,
                qreg_by_name,
                creg_by_name,
                require_index=True,
                statement=statement,
            )
            qubits.append(register.offset + index)
        if len(qubits) > 1 and len(set(qubits)) != len(qubits):
            raise _semantic_error("gate operands must use distinct qubit indices", statement)

        parameter = None
        if parameter_source is not None:
            try:
                parameter = evaluate_expression(parameter_source)
            except ExpressionError as error:
                raise _semantic_error(
                    f"invalid parameter for gate {name} ({parameter_source})", statement
                ) from error
        operations.append(Operation(name, tuple(qubits), parameter))

    if not qregs:
        raise QASMSemanticError("at least one quantum register is required")
    if not cregs:
        raise QASMSemanticError("at least one classical register is required")

    return Circuit(tuple(qregs), tuple(cregs), tuple(operations), tuple(measurements))


__all__ = ["GATE_ARITY", "PARAMETER_GATES", "parse_qasm"]
