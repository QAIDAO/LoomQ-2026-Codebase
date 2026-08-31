import re
import json
from typing import Any, Dict, Optional

try:
    from ..l1.parser import parse_qasm2
except ImportError:
    from l1.parser import parse_qasm2
def extract_qasm_block(text: str) -> str:
    text = text.strip()

    fenced_match = re.search(
        r"```(?:qasm)?\s*(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if fenced_match:
        return fenced_match.group(1).strip()

    return text

def validate_qasm_text(
    qasm_text: str
) -> Dict[str, Any]:

    cleaned_qasm = qasm_text.strip()

    if not cleaned_qasm:
        return {
            "ok": False,
            "qasm": "",
            "error": "Empty QASM output.",
        }

    try:
        circuit = parse_qasm2(cleaned_qasm)

    except Exception as exc:
        return {
            "ok": False,
            "qasm": cleaned_qasm,
            "error": str(exc),
        }

    return {
        "ok": True,
        "qasm": cleaned_qasm,
        "error": None,
        "circuit": circuit,
    }
def validate_llm_qasm_reply(
    reply_text: str
) -> Dict[str, Any]:

    extracted_qasm = extract_qasm_block(
        reply_text
    )

    result = validate_qasm_text(
        extracted_qasm
    )

    result["raw_reply"] = reply_text

    return result

def detect_task_type(
    reply_text: str
) -> str:

    upper_text = reply_text.upper()

    if "LOOMQ_TASK: QASM" in upper_text:
        return "qasm"

    if "LOOMQ_TASK: BACKEND" in upper_text:
        return "backend"

    # Backward-compatible fallback:
    # 如果模型忘了 marker，但确实给了 QASM，
    # 我们仍然尽量救回来。
    if "OPENQASM" in upper_text:
        return "qasm"

    return "unknown"


def strip_task_marker(
    reply_text: str
) -> str:

    lines = reply_text.splitlines()

    cleaned_lines = [
        line
        for line in lines
        if not line.strip().upper().startswith(
            "LOOMQ_TASK:"
        )
    ]

    return "\n".join(
        cleaned_lines
    ).strip()
def parse_backend_decision(
    reply_text: str,
):
    """
    Parse the structured backend decision produced
    by the LLM.

    Expected format:

    LOOMQ_TASK: BACKEND
    LOOMQ_DECISION:
    {
        "status": "selected",
        "backend_id": "...",
        "constraints": {...},
        "reason": "..."
    }
    """

    if not isinstance(reply_text, str):
        raise TypeError(
            "reply_text must be a string"
        )

    marker = "LOOMQ_DECISION:"

    if marker not in reply_text:
        return {
            "ok": False,
            "decision": None,
            "error": (
                "Missing LOOMQ_DECISION marker."
            ),
        }

    payload = reply_text.split(
        marker,
        1,
    )[1].strip()

    # Allow fenced JSON if the model accidentally
    # uses Markdown.
    if payload.startswith("```"):

        lines = payload.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        payload = "\n".join(
            lines
        ).strip()

    try:
        decoder = json.JSONDecoder()

        decision, _ = decoder.raw_decode(
            payload
        )

    except Exception as exc:

        return {
            "ok": False,
            "decision": None,
            "error": (
                "Invalid LOOMQ_DECISION JSON: "
                f"{exc}"
            ),
        }

    if not isinstance(decision, dict):

        return {
            "ok": False,
            "decision": None,
            "error": (
                "LOOMQ_DECISION must be "
                "a JSON object."
            ),
        }

    status = decision.get(
        "status"
    )

    if status not in {
        "selected",
        "no_match",
    }:

        return {
            "ok": False,
            "decision": None,
            "error": (
                "status must be either "
                "'selected' or 'no_match'."
            ),
        }

    backend_id = decision.get(
        "backend_id"
    )

    if status == "selected":

        if not isinstance(
            backend_id,
            str,
        ):

            return {
                "ok": False,
                "decision": None,
                "error": (
                    "A selected decision must "
                    "contain a string backend_id."
                ),
            }

    if status == "no_match":

        if backend_id is not None:

            return {
                "ok": False,
                "decision": None,
                "error": (
                    "A no_match decision must "
                    "use backend_id = null."
                ),
            }

    constraints = decision.get(
        "constraints"
    )

    if not isinstance(
        constraints,
        dict,
    ):

        return {
            "ok": False,
            "decision": None,
            "error": (
                "constraints must be "
                "a JSON object."
            ),
        }

    reason = decision.get(
        "reason"
    )

    if (
        reason is not None
        and not isinstance(reason, str)
    ):

        return {
            "ok": False,
            "decision": None,
            "error": (
                "reason must be a string "
                "when provided."
            ),
        }

    return {
        "ok": True,
        "decision": decision,
        "error": None,
    }
_ALLOWED_BACKEND_CONSTRAINTS = {
    "min_qubits",
    "platform",
    "local",
    "free",
    "strictly_free",
    "no_queue",
    "no_account",
    "qpu",
    "simulator",
    "cloud",
}


_BOOLEAN_BACKEND_CONSTRAINTS = {
    "local",
    "free",
    "strictly_free",
    "no_queue",
    "no_account",
    "qpu",
    "simulator",
    "cloud",
}


def validate_backend_constraints(
    constraints,
):
    if not isinstance(
        constraints,
        dict,
    ):
        return {
            "ok": False,
            "error": (
                "constraints must be a JSON object."
            ),
        }

    unknown = (
        set(constraints)
        - _ALLOWED_BACKEND_CONSTRAINTS
    )

    if unknown:
        return {
            "ok": False,
            "error": (
                "Unknown backend constraint fields: "
                + ", ".join(sorted(unknown))
            ),
        }

    if "min_qubits" in constraints:

        value = constraints["min_qubits"]

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            return {
                "ok": False,
                "error": (
                    "min_qubits must be "
                    "a positive integer."
                ),
            }

    if "platform" in constraints:

        platform = constraints[
            "platform"
        ]

        if platform not in {
            "spinq",
            "originq",
            "braket",
        }:
            return {
                "ok": False,
                "error": (
                    "platform must be one of: "
                    "spinq, originq, braket."
                ),
            }

    for key in (
        _BOOLEAN_BACKEND_CONSTRAINTS
    ):

        if key not in constraints:
            continue

        if not isinstance(
            constraints[key],
            bool,
        ):
            return {
                "ok": False,
                "error": (
                    f"{key} must be a boolean."
                ),
            }

    return {
        "ok": True,
        "error": None,
    }