"""Emit backend-native circuit text from the LoomQ IR (the inverse of parse_qasm)."""

import math

# OriginIR mappings, verified against pyqpanda's parser.
# Non-parameter gates that map straight to an OriginIR mnemonic.
_ORIGINIR_DIRECT = {
    "h": "H",
    "x": "X",
    "s": "S",
    "t": "T",
    "cx": "CNOT",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}
# sdg/tdg have no OriginIR mnemonic (SDAG/TDAG don't exist), so emit them as an
# RZ rotation. RZ(theta) equals the phase gate up to a global phase, which never
# changes measurement counts -- so this is exact for our purposes.
_ORIGINIR_AS_RZ = {"sdg": -math.pi / 2, "tdg": -math.pi / 4}
# Parameter gates. OriginIR wants the angle AFTER the qubits: `RZ q[0], (theta)`
# (front-paren `RZ(theta) q[0]` is rejected by pyqpanda). cu1 is spelled CR.
_ORIGINIR_PARAM = {"rz": "RZ", "ry": "RY", "cu1": "CR"}


def emit_spinq(ir):
    """Emit OpenQASM 2.0 for the SpinQ target from the IR."""
    lines = []

    # 1. Header (always the same two lines)
    lines.append("OPENQASM 2.0;")
    lines.append('include "qelib1.inc";')

    # 2. Register declarations   <-- YOUR SLICE 1
    for name, size in ir["qreg"].items():
        lines.append(f"qreg {name}[{size}];")
    for name, size in ir["creg"].items():
        lines.append(f"creg {name}[{size}];")

    # 3. Ops -> one line each     (slice 2, next)
    for op in ir["ops"]:
        if op["gate"] == "measure":
            qname = list(ir["qreg"])[0]
            cname = list(ir["creg"])[0]
            line = f"measure {qname}[{op['qubits'][0]}] -> {cname}[{op['clbits'][0]}];"
        else: 
            qname = list(ir["qreg"])[0]                                  # "q"
            qubits_str = ", ".join(f"{qname}[{i}]" for i in op['qubits'])  # <-- handles 1, 2, OR 3 qubits
            param_str  = f"({op['params'][0]})" if op["params"] else ""    # <-- handles param OR no param
            line = f"{op['gate']}{param_str} {qubits_str};"
        
        lines.append(line)

    # 4. Join into one string
    return "\n".join(lines) + "\n"


def emit_originir(ir):
    """Emit OriginIR text for the OriginQ target from the IR.

    OriginIR differs from QASM: registers are `QINIT N` / `CREG N`, gates use
    upper-case mnemonics (cx -> CNOT, ccx -> TOFFOLI, cu1 -> CR, ...), a
    parameter follows the qubits as `RZ q[0], (theta)`, and measurement is
    `MEASURE q[i], c[j]`. sdg/tdg are emitted as equivalent RZ rotations.
    """
    lines = []

    # Registers: QINIT <n qubits>, CREG <n classical bits>.
    for _name, size in ir["qreg"].items():
        lines.append(f"QINIT {size}")
    for _name, size in ir["creg"].items():
        lines.append(f"CREG {size}")

    qname = list(ir["qreg"])[0]
    cname = list(ir["creg"])[0]
    for op in ir["ops"]:
        lines.append(_originir_op(op, qname, cname))

    return "\n".join(lines) + "\n"


def _originir_op(op, qname, cname):
    """Render one IR op as a single OriginIR statement."""
    gate = op["gate"]
    if gate == "measure":
        return f"MEASURE {qname}[{op['qubits'][0]}], {cname}[{op['clbits'][0]}]"

    qubits_str = ", ".join(f"{qname}[{i}]" for i in op["qubits"])
    if gate in _ORIGINIR_DIRECT:
        return f"{_ORIGINIR_DIRECT[gate]} {qubits_str}"
    if gate in _ORIGINIR_AS_RZ:
        return f"RZ {qubits_str}, ({_ORIGINIR_AS_RZ[gate]})"
    if gate in _ORIGINIR_PARAM:
        return f"{_ORIGINIR_PARAM[gate]} {qubits_str}, ({op['params'][0]})"
    raise ValueError(f"no OriginIR mapping for gate {gate!r}")