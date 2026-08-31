import re
from collections import defaultdict
from typing import Any, Dict

try:
    from ..l1.api import run_l1
    from ..riscv_emulator import TinyRISCVEmulator
except ImportError:
    from l1.api import run_l1
    from riscv_emulator import TinyRISCVEmulator

from .compiler import (
    compile_hybrid_source,
    remove_classical_block,
)


SUPPORTED_TARGETS = {
    "spinq",
    "originq",
    "braket",
}


class HybridRuntimeError(RuntimeError):
    pass


def _get_classical_bit_count(
    qasm: str,
) -> int:
    """
    Hybrid-QASM currently uses a classical register
    named 'c'.

    Example:
        creg c[3];
    """

    matches = re.findall(
        r"\bcreg\s+c\s*\[\s*(\d+)\s*\]\s*;",
        qasm,
    )

    if len(matches) != 1:
        raise HybridRuntimeError(
            "Hybrid runtime requires exactly one "
            "classical register named c."
        )

    count = int(matches[0])

    if count <= 0:
        raise HybridRuntimeError(
            "Classical register size must be positive."
        )

    return count


def _bitstring_to_measurements(
    bitstring: str,
    classical_bits: int,
) -> Dict[int, int]:
    """
    Convert normalized LoomQ count keys to:

        c[0], c[1], ...

    LoomQ uses little-endian classical-bit semantics.

    A displayed bitstring:

        "101"

    is interpreted as:

        c[0] = 1
        c[1] = 0
        c[2] = 1
    """

    bits = "".join(
        ch
        for ch in bitstring
        if ch in {"0", "1"}
    )

    if len(bits) > classical_bits:
        raise HybridRuntimeError(
            f"Measurement bitstring '{bitstring}' "
            f"is wider than creg c[{classical_bits}]."
        )

    bits = bits.zfill(
        classical_bits
    )

    return {
        index: int(bits[-1 - index])
        for index in range(
            classical_bits
        )
    }


def _execute_classical_once(
    assembly: str,
    measurements: Dict[int, int],
) -> Dict[str, int]:
    """
    Execute one classical branch for one quantum
    measurement outcome.
    """

    emulator = TinyRISCVEmulator()

    emulator.load_program(
        assembly
    )

    # IMPORTANT:
    # load_program() resets registers, so measurements
    # must be injected afterwards.

    for index, value in measurements.items():

        register_index = 10 + index

        if register_index > 31:
            raise HybridRuntimeError(
                f"c[{index}] cannot be mapped to "
                "a RISC-V register."
            )

        emulator.set_register(
            f"x{register_index}",
            value,
        )

    return emulator.execute()


def _extract_user_registers(
    state: Dict[str, int],
) -> Dict[str, int]:

    return {
        f"r{index}": int(
            state.get(
                f"x{index}",
                0,
            )
        )
        for index in range(
            1,
            10,
        )
    }


def execute_hybrid_l3(
    hybrid_qasm_str: str,
    target: str = "originq",
    shots: int = 1024,
) -> Dict[str, Any]:
    """
    Execute Hybrid-QASM using:

        quantum part
            -> LoomQ L1 backend

        measurement c[k]
            -> RISC-V x10+k

        classical block
            -> TinyRISCVEmulator

    The current runtime implements one-way
    quantum-to-classical feed-forward.
    """

    if not isinstance(
        hybrid_qasm_str,
        str,
    ):
        raise TypeError(
            "hybrid_qasm_str must be a string"
        )

    if not hybrid_qasm_str.strip():
        raise ValueError(
            "hybrid_qasm_str must not be empty"
        )

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            "target must be one of: "
            "spinq, originq, braket"
        )

    if (
        not isinstance(shots, int)
        or isinstance(shots, bool)
        or shots <= 0
    ):
        raise ValueError(
            "shots must be a positive integer"
        )

    # ========================================================
    # Compile the hybrid source
    # ========================================================

    quantum_ops, assembly = (
        compile_hybrid_source(
            hybrid_qasm_str
        )
    )

    # Produce complete executable QASM by removing only
    # the classical block.
    quantum_qasm = (
        remove_classical_block(
            hybrid_qasm_str
        )
    )

    classical_bits = (
        _get_classical_bit_count(
            quantum_qasm
        )
    )

    # ========================================================
    # Quantum execution
    # ========================================================

    quantum_result = run_l1(
        quantum_qasm,
        target,
        shots,
    )

    counts = quantum_result[
        "counts"
    ]

    # ========================================================
    # Quantum measurement -> RISC-V
    # ========================================================

    branches = []

    classical_counts = defaultdict(
        int
    )

    classical_states = {}

    for bitstring, count in counts.items():

        measurements = (
            _bitstring_to_measurements(
                bitstring,
                classical_bits,
            )
        )

        state = (
            _execute_classical_once(
                assembly,
                measurements,
            )
        )

        registers = (
            _extract_user_registers(
                state
            )
        )

        state_key = tuple(
            registers[
                f"r{index}"
            ]
            for index in range(
                1,
                10,
            )
        )

        classical_counts[
            state_key
        ] += int(count)

        classical_states[
            state_key
        ] = registers

        branches.append(
            {
                "quantum_bitstring": bitstring,
                "measurements": {
                    f"c[{index}]": value
                    for index, value
                    in measurements.items()
                },
                "count": int(count),
                "probability": (
                    int(count) / shots
                ),
                "registers": registers,
            }
        )

    # ========================================================
    # Aggregate identical classical outcomes
    # ========================================================

    classical_outcomes = []

    for state_key, count in (
        classical_counts.items()
    ):

        classical_outcomes.append(
            {
                "registers": (
                    classical_states[
                        state_key
                    ]
                ),
                "count": count,
                "probability": (
                    count / shots
                ),
            }
        )

    branches.sort(
        key=lambda item: item["count"],
        reverse=True,
    )

    classical_outcomes.sort(
        key=lambda item: item["count"],
        reverse=True,
    )

    return {
        "target": target,
        "shots": shots,
        "quantum_qasm": quantum_qasm,
        "quantum_ops": quantum_ops,
        "assembly": assembly,
        "quantum_result": quantum_result,
        "branches": branches,
        "classical_outcomes": classical_outcomes,
    }
