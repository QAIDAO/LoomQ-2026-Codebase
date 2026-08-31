#!/usr/bin/env python3
"""Subprocess worker for the Braket backend.

Reads {"qasm": <str>, "shots": <int>} as a JSON line on stdin, executes the
circuit on the AWS Braket LocalSimulator inside THIS interpreter (which hosts
a compatible antlr4 runtime), and prints the unified result schema as JSON on
stdout. Errors are reported as {"error": "..."}.
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.readline())
        qasm = payload["qasm"]
        shots = int(payload["shots"])

        from starter_kit.adapter import _braket_local_run
        result = _braket_local_run(qasm, shots)
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:  # noqa: BLE001 - report everything to parent
        json.dump({"error": f"{type(exc).__name__}: {exc}"}, sys.stdout)
        sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
