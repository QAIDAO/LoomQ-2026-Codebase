"""Independent admission parser for the exact target subsets we emit.

This is deliberately separate from emission.  It translates already-emitted
contract text back into canonical QASM 2 and sends that through the real QASM
front end, catching malformed or semantically lossy target artifacts before
they leave ``transpile``.
"""

from typing import Any, Dict, List

from ..qasm import parse_and_normalize


def _positive_integer(text: str, label: str) -> int:
    if not text.isdigit() or int(text) <= 0:
        raise ValueError("invalid %s in target artifact" % label)
    return int(text)


def _ref_index(text: str, prefix: str) -> int:
    expected = prefix + "["
    if not text.startswith(expected) or not text.endswith("]"):
        raise ValueError("invalid %s reference in target artifact: %s" % (prefix, text))
    raw = text[len(expected) : -1]
    if not raw.isdigit():
        raise ValueError("invalid %s index in target artifact: %s" % (prefix, text))
    return int(raw)


def _canonical_header(qubits: int, cbits: int) -> List[str]:
    return [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[%d];" % qubits,
        "creg c[%d];" % cbits,
    ]


def _parse_gate_head(head: str) -> tuple[str, str]:
    if "(" not in head:
        return head, ""
    if not head.endswith(")") or head.count("(") != 1:
        raise ValueError("invalid parameterized gate in target artifact: %s" % head)
    name, raw_parameter = head[:-1].split("(", 1)
    if not name or not raw_parameter:
        raise ValueError("invalid parameterized gate in target artifact: %s" % head)
    return name, "(%s)" % raw_parameter


def _parse_braket(artifact: str) -> Any:
    lines = [line.strip() for line in artifact.splitlines() if line.strip()]
    if len(lines) < 4 or lines[0] != "OPENQASM 3.0;" or lines[1] != 'include "stdgates.inc";':
        raise ValueError("Braket artifact must start with the required OpenQASM 3 header")
    qdecl, cdecl = lines[2], lines[3]
    if not qdecl.startswith("qubit[") or not qdecl.endswith("] q;"):
        raise ValueError("invalid Braket qubit declaration")
    if not cdecl.startswith("bit[") or not cdecl.endswith("] c;"):
        raise ValueError("invalid Braket bit declaration")
    qubits = _positive_integer(qdecl[len("qubit[") : -len("] q;")], "qubit count")
    cbits = _positive_integer(cdecl[len("bit[") : -len("] c;")], "classical count")
    qasm = _canonical_header(qubits, cbits)
    names: Dict[str, str] = {"cnot": "cx", "cp": "cu1"}
    for line in lines[4:]:
        if not line.endswith(";"):
            raise ValueError("Braket statement is missing a semicolon")
        statement = line[:-1]
        if " = measure " in statement:
            left, right = statement.split(" = measure ", 1)
            cbit = _ref_index(left.strip(), "c")
            qubit = _ref_index(right.strip(), "q")
            qasm.append("measure q[%d] -> c[%d];" % (qubit, cbit))
            continue
        if " " not in statement:
            raise ValueError("invalid Braket gate statement")
        head, raw_operands = statement.split(" ", 1)
        name, parameter = _parse_gate_head(head)
        name = names.get(name, name)
        qasm.append("%s%s %s;" % (name, parameter, raw_operands))
    return parse_and_normalize("\n".join(qasm))


def _parse_originq(artifact: str) -> Any:
    lines = [line.strip() for line in artifact.splitlines() if line.strip()]
    if len(lines) < 2 or not lines[0].startswith("QINIT ") or not lines[1].startswith("CREG "):
        raise ValueError("OriginIR artifact must start with QINIT and CREG")
    qubits = _positive_integer(lines[0][len("QINIT ") :], "qubit count")
    cbits = _positive_integer(lines[1][len("CREG ") :], "classical count")
    qasm = _canonical_header(qubits, cbits)
    names: Dict[str, str] = {
        "H": "h",
        "X": "x",
        "S": "s",
        "SDAG": "sdg",
        "T": "t",
        "TDAG": "tdg",
        "RY": "ry",
        "RZ": "rz",
        "CNOT": "cx",
        "CU1": "cu1",
        "CR": "cu1",
        "SWAP": "swap",
        "TOFFOLI": "ccx",
        "CCX": "ccx",
    }
    for statement in lines[2:]:
        if statement.startswith("MEASURE "):
            operands = [item.strip() for item in statement[len("MEASURE ") :].split(",")]
            if len(operands) != 2:
                raise ValueError("invalid OriginIR measurement")
            qubit = _ref_index(operands[0], "q")
            cbit = _ref_index(operands[1], "c")
            qasm.append("measure q[%d] -> c[%d];" % (qubit, cbit))
            continue
        if " " not in statement:
            raise ValueError("invalid OriginIR gate statement")
        head, raw_operands = statement.split(" ", 1)
        native_name, parameter = _parse_gate_head(head)
        try:
            name = names[native_name]
        except KeyError as exc:
            raise ValueError("unsupported OriginIR gate: %s" % native_name) from exc
        qasm.append("%s%s %s;" % (name, parameter, raw_operands))
    return parse_and_normalize("\n".join(qasm))


def parse_target_artifact(artifact: str, target: str) -> Any:
    if not isinstance(artifact, str) or not artifact.strip():
        raise ValueError("target artifact must be a non-empty string")
    if target == "spinq":
        return parse_and_normalize(artifact)
    if target == "braket":
        return _parse_braket(artifact)
    if target == "originq":
        return _parse_originq(artifact)
    raise ValueError("unsupported target for round-trip admission: %s" % target)


def admit_target_artifact(source_circuit: Any, artifact: str, target: str) -> str:
    round_tripped = parse_target_artifact(artifact, target)
    if round_tripped != source_circuit:
        raise ValueError("%s target artifact changed normalized circuit semantics" % target)
    return artifact
