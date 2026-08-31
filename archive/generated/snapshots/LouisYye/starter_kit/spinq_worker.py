#!/usr/bin/env python3
"""Isolated SpinQit worker. Reads one JSON request from stdin."""

import json
import os
import sys
import tempfile


RESULT_PREFIX = "LOOMQ_SPINQ_RESULT="


def execute(qasm: str, shots: int) -> dict:
    from spinqit import (
        BasicSimulatorConfig,
        get_basic_simulator,
        get_compiler,
    )

    path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".qasm",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(qasm)
            path = handle.name

        intermediate = get_compiler("qasm").compile(path, 0)
        config = BasicSimulatorConfig()
        config.configure_shots(shots)
        result = get_basic_simulator().execute(intermediate, config)

        return {
            "counts": {
                str(key): int(value)
                for key, value in result.counts.items()
            },
            "num_qubits": int(intermediate.qnum),
            "num_bits": int(intermediate.cnum),
        }
    finally:
        if path and os.path.exists(path):
            os.unlink(path)


def main() -> int:
    try:
        request = json.loads(sys.stdin.read())
        response = execute(
            qasm=request["qasm"],
            shots=int(request["shots"]),
        )
        print(RESULT_PREFIX + json.dumps(response, sort_keys=True))
        return 0
    except Exception as exc:
        error = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(RESULT_PREFIX + json.dumps(error, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
