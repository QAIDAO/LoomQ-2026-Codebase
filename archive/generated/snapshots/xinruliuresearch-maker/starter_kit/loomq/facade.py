"""Stateless L1 facade used by the official adapter."""

import hashlib
from typing import Any, Dict

from .errors import InputValidationError
from .qasm import parse_and_normalize
from .runtime import admit_result, get_provider
from .targets.registry import validate_target


MAX_QASM_BYTES = 256_000


def _validate_qasm(qasm_str: str) -> str:
    if not isinstance(qasm_str, str):
        raise InputValidationError("qasm_str must be a string")
    if not qasm_str.strip():
        raise InputValidationError("qasm_str must not be empty")
    if len(qasm_str.encode("utf-8")) > MAX_QASM_BYTES:
        raise InputValidationError("qasm_str exceeds the 256000-byte safety limit")
    return qasm_str


def transpile(qasm_str: str, target: str) -> str:
    source = _validate_qasm(qasm_str)
    normalized_target = validate_target(target)
    circuit = parse_and_normalize(source)
    return get_provider(normalized_target).transpile(circuit)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    source = _validate_qasm(qasm_str)
    normalized_target = validate_target(target)
    if not isinstance(shots, int) or isinstance(shots, bool) or not 1 <= shots <= 100_000:
        raise InputValidationError("shots must be an integer between 1 and 100000")
    circuit = parse_and_normalize(source)
    provider = get_provider(normalized_target)
    provider.transpile(circuit)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    seed_material = "%s:%s:%d" % (digest, normalized_target, shots)
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("ascii")).digest()[:8], "big")
    payload = provider.run(circuit, shots, seed, digest)
    return admit_result(payload, shots, circuit.classical_count)
