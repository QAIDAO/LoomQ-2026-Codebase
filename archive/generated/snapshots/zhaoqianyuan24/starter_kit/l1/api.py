from typing import Any, Dict

from .gates import SUPPORTED_TARGETS
from .parser import parse_qasm2

from .emitters import (
    emit_spinq,
    emit_braket,
    emit_originq,
)

#from .backends.spinq import run_spinq
#from .backends.braket import run_braket
#from .backends.originq import run_originq


def transpile_l1(
    qasm_str: str,
    target: str
) -> str:

    target = target.strip().lower()

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target: {target}"
        )

    circuit = parse_qasm2(
        qasm_str
    )

    if target == "spinq":
        return emit_spinq(circuit)

    if target == "braket":
        return emit_braket(circuit)

    if target == "originq":
        return emit_originq(circuit)

    raise ValueError(
        f"Unsupported target: {target}"
    )


def run_l1(
    qasm_str: str,
    target: str,
    shots: int
) -> Dict[str, Any]:

    target = target.strip().lower()

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target: {target}"
        )

    circuit = parse_qasm2(
        qasm_str
    )
    if target == "spinq":
        from .backends.spinq import run_spinq
    
        return run_spinq(
            circuit,
            shots,
        )
    
    if target == "originq":
        from .backends.originq import run_originq
    
        return run_originq(
            circuit,
            shots,
        )
    
    if target == "braket":
        from .backends.braket import run_braket
    
        return run_braket(
            circuit,
            shots,
        )

    raise ValueError(
        f"Unsupported target: {target}"
    )
