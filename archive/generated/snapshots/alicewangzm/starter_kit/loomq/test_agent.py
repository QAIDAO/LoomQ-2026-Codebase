#!/usr/bin/env python3
"""Self-tests for the L2 agent's deterministic helpers.

The LLM call needs a live key, so these cover only the parts that don't: pulling
QASM out of a reply (_extract_qasm) and validating it structurally
(_validate_qasm). Run from the repo root:

    python starter_kit/loomq/test_agent.py
"""

from agent import _extract_qasm, _validate_qasm
from testkit import check, summary

# --- _extract_qasm -----------------------------------------------------------

FENCED = 'Here you go:\n```qasm\nOPENQASM 2.0;\nqreg q[1];\n```\ndone'
check("extract from ```qasm block", _extract_qasm(FENCED).startswith("OPENQASM 2.0;"), True)
check(
    "extract from bare ``` block",
    _extract_qasm("```\nOPENQASM 2.0;\nx\n```").startswith("OPENQASM"),
    True,
)
check(
    "extract without fences",
    _extract_qasm("sure: OPENQASM 2.0; qreg q[1];").startswith("OPENQASM"),
    True,
)
check("extract returns None for prose", _extract_qasm("Use braket_local_simulator."), None)

# --- _validate_qasm ----------------------------------------------------------

GOOD = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
    "h q[0];\ncx q[0],q[1];\nmeasure q -> c;"
)
check("valid circuit passes", _validate_qasm(GOOD), None)
check(
    "bad gate is flagged",
    "unsupported gate" in _validate_qasm(GOOD.replace("h q[0];", "foo q[0];")),
    True,
)
check(
    "out-of-range qubit is flagged",
    "out of range" in _validate_qasm(GOOD.replace("h q[0];", "h q[9];")),
    True,
)

summary()
