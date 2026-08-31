from typing import List, Tuple

from .compiler import (
    compile_hybrid_source,
)


def compile_hybrid_l3(
    hybrid_qasm_str: str,
) -> Tuple[List[str], str]:

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

    return compile_hybrid_source(
        hybrid_qasm_str
    )
