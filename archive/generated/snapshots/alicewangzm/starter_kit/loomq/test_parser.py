#!/usr/bin/env python3
"""Self-tests for the QASM parser.

Run from the repo root:

    python starter_kit/loomq/test_parser.py

Prints a line per test and a summary. Exit code 0 = all passed, 1 = a failure,
so this also works in CI later. No third-party dependencies (matches the
organiser's stdlib-only baseline).
"""

# When run as a script, this file's own directory is first on sys.path, so a
# plain `from parser import ...` picks up the modules sitting next to it.
from parser import parse_qasm, _parse_reg, _bracket_ints
from testkit import check, check_raises, summary
import math


# --- helper-level tests ------------------------------------------------------

check("_parse_reg qreg", _parse_reg("qreg q[2]"), ("q", 2))
check("_parse_reg creg multi-digit", _parse_reg("creg c[12]"), ("c", 12))
check("_bracket_ints spaced", _bracket_ints("cx q[0], q[1]"), [0, 1])
check("_bracket_ints tight", _bracket_ints("cx q[0],q[1]"), [0, 1])
check("_bracket_ints none", _bracket_ints("measure q -> c"), [])


# --- full-circuit tests ------------------------------------------------------

BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

check(
    "parse bell",
    parse_qasm(BELL),
    {
        "qreg": {"q": 2},
        "creg": {"c": 2},
        "ops": [
            {"gate": "h", "qubits": [0], "params": []},
            {"gate": "cx", "qubits": [0, 1], "params": []},
            {"gate": "measure", "qubits": [0], "clbits": [0]},
            {"gate": "measure", "qubits": [1], "clbits": [1]},
        ],
    },
)

# Single-bit measure form (the other legal spelling of measurement).
SINGLE_MEASURE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q[0] -> c[0];
"""

check(
    "parse single-bit measure",
    parse_qasm(SINGLE_MEASURE)["ops"],
    [
        {"gate": "x", "qubits": [0], "params": []},
        {"gate": "measure", "qubits": [0], "clbits": [0]},
    ],
)

# A gate outside the 12-gate whitelist must fail loudly, not slip through.
UNKNOWN_GATE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
foo q[0];
"""

check_raises("unknown gate raises", lambda: parse_qasm(UNKNOWN_GATE), ValueError)


# --- edge cases --------------------------------------------------------------


def _wrap(body, qsize=3):
    """Wrap a snippet of gate/measure lines in the standard QASM header."""
    return (
        "OPENQASM 2.0;\n"
        'include "qelib1.inc";\n'
        f"qreg q[{qsize}];\n"
        f"creg c[{qsize}];\n"
        f"{body}\n"
    )


# Table-driven: one row per no-parameter gate, checking arity (qubit count).
# Adding a new gate = adding a row, not copy-pasting a whole test.
GATE_ARITY_CASES = [
    ("h q[0];", [{"gate": "h", "qubits": [0], "params": []}]),
    ("s q[0];", [{"gate": "s", "qubits": [0], "params": []}]),
    ("sdg q[1];", [{"gate": "sdg", "qubits": [1], "params": []}]),
    ("tdg q[2];", [{"gate": "tdg", "qubits": [2], "params": []}]),
    ("swap q[0], q[1];", [{"gate": "swap", "qubits": [0, 1], "params": []}]),
    ("ccx q[0], q[1], q[2];", [{"gate": "ccx", "qubits": [0, 1, 2], "params": []}]),
]
for stmt, want_ops in GATE_ARITY_CASES:
    check(f"gate arity: {stmt}", parse_qasm(_wrap(stmt))["ops"], want_ops)

# Boundary: qubit index >= 10 must parse as a whole number, not a single digit.
check(
    "multi-digit qubit index q[10]",
    parse_qasm(_wrap("h q[10];", qsize=12))["ops"],
    [{"gate": "h", "qubits": [10], "params": []}],
)

# Degenerate: a header-only circuit yields no ops rather than erroring.
check("empty circuit (no gates)", parse_qasm(_wrap(""))["ops"], [])

# Format noise: a blank line between statements is ignored, not parsed as a gate.
check(
    "blank line between statements ignored",
    parse_qasm(_wrap("\nh q[0];"))["ops"],
    [{"gate": "h", "qubits": [0], "params": []}],
)

# Whole-register measure must expand to N ops for N > 2 (GHZ3 uses 3).
check(
    "whole-register measure expands to N=3",
    [
        op
        for op in parse_qasm(_wrap("measure q -> c;"))["ops"]
        if op["gate"] == "measure"
    ],
    [
        {"gate": "measure", "qubits": [0], "clbits": [0]},
        {"gate": "measure", "qubits": [1], "clbits": [1]},
        {"gate": "measure", "qubits": [2], "clbits": [2]},
    ],
)

check(
    "comment lines are ignored",
    parse_qasm(_wrap("// prepare\nh q[0]; // trailing\nx q[1];"))["ops"],
    [
        {"gate": "h", "qubits": [0], "params": []},
        {"gate": "x", "qubits": [1], "params": []},
    ],
)

check("parse rz param", parse_qasm(_wrap("rz(pi/2) q[0];"))["ops"],
      [{"gate": "rz", "qubits": [0], "params": [math.pi/2]}])

check("parse rz/cu1 params",
      parse_qasm(_wrap("rz(pi/2) q[0];\ncu1(pi) q[0], q[1];"))["ops"],
      [
          {"gate": "rz",  "qubits": [0],    "params": [math.pi/2]},
          {"gate": "cu1", "qubits": [0, 1], "params": [math.pi]},
      ])

# --- summary -----------------------------------------------------------------

summary()
