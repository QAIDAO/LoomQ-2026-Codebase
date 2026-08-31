"""Gate signatures shared by normalization and serialization."""

from __future__ import annotations


# name: (parameter count, qubit count)
GATE_SIGNATURES = {
    "h": (0, 1),
    "x": (0, 1),
    "s": (0, 1),
    "sdg": (0, 1),
    "t": (0, 1),
    "tdg": (0, 1),
    "rz": (1, 1),
    "ry": (1, 1),
    "cx": (0, 2),
    "cu1": (1, 2),
    "swap": (0, 2),
    "ccx": (0, 3),
}


__all__ = ["GATE_SIGNATURES"]
