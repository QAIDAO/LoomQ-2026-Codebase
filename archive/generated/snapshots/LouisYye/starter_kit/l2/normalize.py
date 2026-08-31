from __future__ import annotations

import re

from qiskit import qasm2, transpile

try:
    from ..parser import parse_qasm
except ImportError:
    from parser import parse_qasm


BASIS = ["h", "x", "s", "sdg", "t", "tdg", "ry", "rz", "cx", "swap", "ccx"]

FENCED = re.compile(r"```[A-Za-z0-9_+-]*\s*(.*?)```", re.DOTALL)
QASM_START = re.compile(r"OPENQASM\s+2\.0\s*;", re.IGNORECASE)


def clean(qasm_str: str) -> str:
    """Strip Markdown fences and prose the model may wrap around a program.

    Models routinely return a fenced block inside the JSON `qasm` field; without
    this the parser fails on a backtick and the whole attempt is wasted.
    """
    text = qasm_str.strip()
    if "```" in text:
        blocks = [
            block.strip()
            for block in FENCED.findall(text)
            if QASM_START.search(block)
        ]
        text = blocks[0] if blocks else text.replace("```", "")
        text = text.strip()
    match = QASM_START.search(text)
    if match:
        text = text[match.start() :]
    return text.strip()


def normalize(qasm_str: str):
    """Return (program text, parsed Circuit) using only the LoomQ gate subset."""
    source = clean(qasm_str)
    try:
        return source, parse_qasm(source)
    except Exception:
        circuit = qasm2.loads(
            source, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS
        )
        normalized = transpile(circuit, basis_gates=BASIS, optimization_level=0)
        text = qasm2.dumps(normalized)
        return text.strip(), parse_qasm(text)
