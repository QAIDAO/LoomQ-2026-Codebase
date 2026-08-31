import re
import time
from typing import Any, Dict

from .client import call_llm
from .policy import get_case_timeout

try:
    from ..l3 import (
        compile_hybrid_l3,
        execute_hybrid_l3,
    )
except ImportError:
    from l3 import (
        compile_hybrid_l3,
        execute_hybrid_l3,
    )


MAX_ATTEMPTS = 3
TIME_RESERVE_SECONDS = 5

SUPPORTED_TARGETS = {
    "spinq",
    "originq",
    "braket",
}


HYBRID_SYSTEM_PROMPT = """
You are the LoomQ hybrid quantum-classical execution agent.

The user describes a hybrid quantum/classical computation
in natural language.

You must generate a complete Hybrid-QASM program and choose
the requested LoomQ target and number of shots.

============================================================
QUANTUM PART
============================================================

Use OpenQASM 2.0.

The program must contain:

OPENQASM 2.0;
include "qelib1.inc";

Use qreg and exactly one classical register named c.

Supported quantum gates are:

h
x
s
sdg
t
tdg
ry
rz
cx
cu1
swap
ccx

Measurement syntax:

measure q[i] -> c[j];

============================================================
CLASSICAL PART
============================================================

The classical section must appear AFTER all quantum gates
and measurements.

Use exactly:

classical {
    ...
}

Supported user registers:

r1 through r9

Supported measurement references:

c[0], c[1], ...

Supported classical operations:

integer assignment
+
-
==
!=
if
else

Examples:

r1 = 10;
r2 = r1 + 5;
r3 = r2 - 2;

if (c[0] == 1) {
    r1 = 100;
} else {
    r1 = 10;
}

Nested if/else is allowed.

Do not generate loops.
Do not generate functions.
Do not generate floating-point classical arithmetic.
Do not place quantum operations after the classical block.

============================================================
EXECUTION
============================================================

Supported targets are exactly:

spinq
originq
braket

If the user explicitly requests a platform, use it.

SpinQ -> spinq
OriginQ / 本源量子 -> originq
AWS Braket / Braket -> braket

If no target is specified, use originq.

If shots are not specified, use 1024.

============================================================
OUTPUT PROTOCOL
============================================================

Return exactly:

LOOMQ_TASK: HYBRID_EXECUTE
TARGET: <spinq|originq|braket>
SHOTS: <positive integer>
HYBRID_QASM:
<complete Hybrid-QASM>

Do not use Markdown fences.
Do not add explanatory prose.
""".strip()


def _remaining_timeout(
    deadline: float,
) -> float:

    remaining = (
        deadline
        - time.monotonic()
        - TIME_RESERVE_SECONDS
    )

    if remaining <= 0:
        raise RuntimeError(
            "Hybrid execution timeout exceeded."
        )

    return remaining


def _parse_hybrid_reply(
    reply: str,
) -> Dict[str, Any]:

    if not isinstance(reply, str):
        return {
            "ok": False,
            "error": "LLM reply must be a string.",
        }

    if "LOOMQ_TASK: HYBRID_EXECUTE" not in reply:
        return {
            "ok": False,
            "error": (
                "Missing LOOMQ_TASK: HYBRID_EXECUTE."
            ),
        }

    target_match = re.search(
        r"(?im)^TARGET:\s*(spinq|originq|braket)\s*$",
        reply,
    )

    if not target_match:
        return {
            "ok": False,
            "error": "Missing or invalid TARGET.",
        }

    target = (
        target_match
        .group(1)
        .lower()
    )

    shots_match = re.search(
        r"(?im)^SHOTS:\s*(\d+)\s*$",
        reply,
    )

    if not shots_match:
        return {
            "ok": False,
            "error": "Missing SHOTS.",
        }

    shots = int(
        shots_match.group(1)
    )

    if shots <= 0:
        return {
            "ok": False,
            "error": "SHOTS must be positive.",
        }

    marker = "HYBRID_QASM:"

    if marker not in reply:
        return {
            "ok": False,
            "error": "Missing HYBRID_QASM section.",
        }

    source = reply.split(
        marker,
        1,
    )[1].strip()

    # Compile first.
    # This checks the Hybrid-QASM classical syntax
    # before actual quantum execution.
    try:
        quantum_ops, assembly = (
            compile_hybrid_l3(
                source
            )
        )

    except Exception as exc:
        return {
            "ok": False,
            "error": (
                "Hybrid-QASM compilation failed: "
                f"{exc}"
            ),
        }

    return {
        "ok": True,
        "target": target,
        "shots": shots,
        "hybrid_qasm": source,
        "quantum_ops": quantum_ops,
        "assembly": assembly,
    }


def execute_hybrid_from_prompt(
    prompt: str,
) -> Dict[str, Any]:

    if not isinstance(prompt, str):
        raise TypeError(
            "prompt must be a string"
        )

    prompt = prompt.strip()

    if not prompt:
        raise ValueError(
            "prompt must not be empty"
        )

    messages = [
        {
            "role": "system",
            "content": HYBRID_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    deadline = (
        time.monotonic()
        + get_case_timeout()
    )

    last_error = None

    for _ in range(
        MAX_ATTEMPTS
    ):

        reply = call_llm(
            messages,
            timeout=_remaining_timeout(
                deadline
            ),
        )

        parsed = (
            _parse_hybrid_reply(
                reply
            )
        )

        if not parsed["ok"]:

            last_error = (
                parsed["error"]
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": reply,
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your Hybrid-QASM failed "
                        "deterministic LoomQ validation.\n\n"
                        f"Error:\n{last_error}\n\n"
                        "Correct the program and return "
                        "exactly:\n\n"
                        "LOOMQ_TASK: HYBRID_EXECUTE\n"
                        "TARGET: <spinq|originq|braket>\n"
                        "SHOTS: <positive integer>\n"
                        "HYBRID_QASM:\n"
                        "<complete Hybrid-QASM>"
                    ),
                }
            )

            continue

        # Actual hybrid execution:
        #
        # Quantum simulator
        #       ↓
        # measurement
        #       ↓
        # RISC-V
        try:

            result = execute_hybrid_l3(
                parsed[
                    "hybrid_qasm"
                ],
                target=parsed[
                    "target"
                ],
                shots=parsed[
                    "shots"
                ],
            )

        except Exception as exc:

            last_error = str(
                exc
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": reply,
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The generated program compiled, "
                        "but failed during actual LoomQ "
                        "hybrid execution.\n\n"
                        f"Execution error:\n"
                        f"{last_error}\n\n"
                        "Correct the Hybrid-QASM while "
                        "preserving the user's requested "
                        "computation."
                    ),
                }
            )

            continue

        return {
            "prompt": prompt,
            "target": parsed["target"],
            "shots": parsed["shots"],
            "hybrid_qasm": parsed[
                "hybrid_qasm"
            ],
            "result": result,
        }

    raise RuntimeError(
        "Hybrid agent failed after "
        f"{MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )
