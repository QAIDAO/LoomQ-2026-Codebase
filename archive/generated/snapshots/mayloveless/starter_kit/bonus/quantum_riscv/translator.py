"""将 L3 quantum_ops 的受支持子集翻译为 Quantum RISC-V words。"""

import re
from typing import Iterable, List

from .encoding import encode_qcx, encode_qh, encode_qmeas, encode_qx


class QuantumTranslationError(ValueError):
    """quantum_ops 不属于本 Bonus ISA 明确支持的子集。"""


_SINGLE_GATE_RE = re.compile(r"\A(h|x)\s+q\[(\d+)\]\s*;\Z", re.IGNORECASE)
_CX_RE = re.compile(
    r"\Acx\s+q\[(\d+)\]\s*,\s*q\[(\d+)\]\s*;\Z", re.IGNORECASE
)
_MEASURE_RE = re.compile(
    r"\Ameasure\s+q\[(\d+)\]\s*->\s*c\[(\d+)\]\s*;\Z", re.IGNORECASE
)


def quantum_ops_to_words(quantum_ops: Iterable[str]) -> List[int]:
    """按输入顺序编码；L3 c[k] 按官方映射写回 x10+k。"""
    if isinstance(quantum_ops, (str, bytes)):
        raise TypeError("quantum_ops must be an iterable of instruction strings")

    words: List[int] = []
    for operation in quantum_ops:
        if not isinstance(operation, str):
            raise TypeError("each quantum operation must be a string")
        text = operation.strip()
        single = _SINGLE_GATE_RE.fullmatch(text)
        if single:
            qubit = int(single.group(2))
            encoder = encode_qh if single.group(1).lower() == "h" else encode_qx
            words.append(encoder(qubit))
            continue

        controlled = _CX_RE.fullmatch(text)
        if controlled:
            words.append(encode_qcx(int(controlled.group(1)), int(controlled.group(2))))
            continue

        measurement = _MEASURE_RE.fullmatch(text)
        if measurement:
            classical_reg = 10 + int(measurement.group(2))
            words.append(encode_qmeas(int(measurement.group(1)), classical_reg))
            continue

        raise QuantumTranslationError(
            "unsupported by Quantum RISC-V Bonus ISA: %s" % text
        )
    return words
