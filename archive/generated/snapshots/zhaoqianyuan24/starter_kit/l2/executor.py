import re
import time
from typing import Any, Dict

from .client import call_llm
from .policy import get_case_timeout
from .validator import (
    extract_qasm_block,
    validate_qasm_text,
)

try:
    from ..l1.api import run_l1
except ImportError:
    from l1.api import run_l1


MAX_ATTEMPTS = 3
TIME_RESERVE_SECONDS = 5

SUPPORTED_TARGETS = {
    "spinq",
    "originq",
    "braket",
}


EXECUTION_SYSTEM_PROMPT = """
You are the LoomQ quantum execution agent.

The user will describe a quantum circuit in natural language
and may also specify where and how many times to execute it.

Your job is to:

1. Understand the requested quantum circuit.
2. Generate complete valid OpenQASM 2.0.
3. Determine the requested LoomQ target.
4. Determine the requested number of shots.

Supported targets are exactly:

spinq
originq
braket

If the user explicitly requests one of these platforms,
use that target.

Examples:

"SpinQ" -> spinq
"OriginQ" or "本源量子" -> originq
"Braket" or "AWS Braket" -> braket

If the user does not specify a target, use:

originq

If the user does not specify shots, use:

1024

Supported LoomQ gates are:

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

Return exactly this format:

LOOMQ_TASK: EXECUTE
TARGET: <spinq|originq|braket>
SHOTS: <positive integer>
QASM:
OPENQASM 2.0;
include "qelib1.inc";
...

Do not use Markdown code fences.
Do not add prose outside this format.
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
            "L2 execution case timeout exceeded."
        )

    return remaining


def _parse_execution_reply(
    reply: str,
) -> Dict[str, Any]:

    if not isinstance(reply, str):
        return {
            "ok": False,
            "error": "LLM reply must be a string.",
        }

    if "LOOMQ_TASK: EXECUTE" not in reply:
        return {
            "ok": False,
            "error": (
                "Missing LOOMQ_TASK: EXECUTE marker."
            ),
        }

    target_match = re.search(
        r"(?im)^TARGET:\s*([A-Za-z0-9_-]+)\s*$",
        reply,
    )

    if not target_match:
        return {
            "ok": False,
            "error": "Missing TARGET field.",
        }

    target = (
        target_match
        .group(1)
        .strip()
        .lower()
    )

    if target not in SUPPORTED_TARGETS:
        return {
            "ok": False,
            "error": (
                f"Unsupported target: {target}. "
                "Expected spinq, originq, or braket."
            ),
        }

    shots_match = re.search(
        r"(?im)^SHOTS:\s*(\d+)\s*$",
        reply,
    )

    if not shots_match:
        return {
            "ok": False,
            "error": "Missing SHOTS field.",
        }

    shots = int(
        shots_match.group(1)
    )

    if shots <= 0:
        return {
            "ok": False,
            "error": (
                "SHOTS must be a positive integer."
            ),
        }

    qasm_marker = "QASM:"

    if qasm_marker not in reply:
        return {
            "ok": False,
            "error": "Missing QASM section.",
        }

    qasm = reply.split(
        qasm_marker,
        1,
    )[1].strip()

    qasm = extract_qasm_block(
        qasm
    )

    validation = validate_qasm_text(
        qasm
    )

    if not validation["ok"]:
        return {
            "ok": False,
            "error": (
                "Generated QASM failed LoomQ "
                "L1 validation: "
                f"{validation['error']}"
            ),
        }

    return {
        "ok": True,
        "target": target,
        "shots": shots,
        "qasm": validation["qasm"],
    }


def execute_from_prompt(
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
            "content": EXECUTION_SYSTEM_PROMPT,
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

    for _ in range(MAX_ATTEMPTS):

        reply = call_llm(
            messages,
            timeout=_remaining_timeout(
                deadline
            ),
        )

        parsed = _parse_execution_reply(
            reply
        )

        if parsed["ok"]:

            execution = run_l1(
                parsed["qasm"],
                parsed["target"],
                parsed["shots"],
            )

            return {
                "qasm": parsed["qasm"],
                "target": parsed["target"],
                "shots": parsed["shots"],
                "execution": execution,
            }

        last_error = parsed["error"]

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
                    "Your execution plan failed "
                    "deterministic LoomQ validation.\n\n"
                    f"Error:\n{last_error}\n\n"
                    "Correct it and return exactly:\n\n"
                    "LOOMQ_TASK: EXECUTE\n"
                    "TARGET: <spinq|originq|braket>\n"
                    "SHOTS: <positive integer>\n"
                    "QASM:\n"
                    "<complete valid OpenQASM 2.0>"
                ),
            }
        )

    raise RuntimeError(
        "LoomQ execution agent failed after "
        f"{MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )
