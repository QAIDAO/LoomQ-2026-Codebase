#!/usr/bin/env python3
"""Result normalization: backend counts -> unified little-endian clbit schema."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    from .qasm_parser import ParsedCircuit
except ImportError:
    from qasm_parser import ParsedCircuit


def to_clbit_counts(raw: Dict[str, int], nq: int, nc: int,
                    big_endian: bool, measures: List[Tuple[int, int]]) -> Dict[str, int]:
    """Normalize backend counts into little-endian clbit keys (key = c[n-1]..c[0]).

    Each backend returns keys of length nq; character position maps to the qubit
    index (leftmost = q[0]) for big-endian backends, or to q[nq-1-i] for
    little-endian ones (pyqpanda). The circuit's measure q[i] -> c[j] mapping is
    then applied; unmeasured clbits read as 0.
    """
    cl_to_q = {clbit: qubit for qubit, clbit in measures}
    out: Dict[str, int] = {}
    for key, count in raw.items():
        if len(key) != nq:
            raise ValueError("unexpected counts key length %d (nq=%d)" % (len(key), nq))
        value = [int(key[i]) if big_endian else int(key[nq - 1 - i]) for i in range(nq)]
        bits = []
        for j in range(nc):
            qj = cl_to_q.get(j)
            bits.append(str(value[qj]) if qj is not None else "0")
        out["".join(reversed(bits))] = count
    return out


def circuit_depth(pc: ParsedCircuit) -> int:
    """Naive circuit depth: longest dependency chain across qubits."""
    layers = [0] * pc.nq
    for _g, _p, qubits in pc.ops:
        layer = max(layers[q] for q in qubits) + 1
        for q in qubits:
            layers[q] = layer
    return max(layers, default=0)


def result_payload(pc: ParsedCircuit, backend_id: str, shots: int,
                   raw: Dict[str, int], big_endian: bool) -> Dict[str, Any]:
    """Build the unified result schema required by the rules."""
    counts = to_clbit_counts(raw, pc.nq, pc.nc, big_endian, pc.measures)
    seed = (pc.nq, pc.nc, tuple(pc.ops), tuple(pc.measures), backend_id, shots)
    job_id = hashlib.sha1(repr(seed).encode()).hexdigest()[:16]
    return {
        "backend": backend_id,
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {"transpiled_gates": len(pc.ops), "depth": circuit_depth(pc)},
    }