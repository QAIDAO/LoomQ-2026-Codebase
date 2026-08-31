
import time

from .client import call_llm
from .policy import get_case_timeout
from .prompts import build_system_prompt

from .validator import (
    detect_task_type,
    strip_task_marker,
    validate_llm_qasm_reply,
    parse_backend_decision,
    validate_backend_constraints,
)

from .backend_tool import (
    get_backend_capabilities_for_llm,
)

from .backend_verifier import (
    verify_backend,
    find_matching_backends,
)


MAX_ATTEMPTS = 3
TIME_RESERVE_SECONDS = 5


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
            "L2 case timeout exceeded."
        )

    return remaining


def _append_retry(
    messages,
    reply,
    feedback,
):
    messages.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )

    messages.append(
        {
            "role": "user",
            "content": feedback,
        }
    )


def _format_selected_backend(
    decision,
) -> str:

    backend_id = decision[
        "backend_id"
    ]

    reason = decision.get(
        "reason",
        "",
    ).strip()

    if reason:
        return (
            f"Recommended backend: "
            f"{backend_id}\n"
            f"Reason: {reason}"
        )

    return (
        f"Recommended backend: "
        f"{backend_id}"
    )


def _format_no_match(
    decision,
) -> str:

    reason = decision.get(
        "reason",
        "",
    ).strip()

    if reason:
        return (
            "No backend satisfies all "
            "requested constraints.\n"
            f"Reason: {reason}"
        )

    return (
        "No backend satisfies all "
        "requested constraints."
    )


def agent_chat_impl(
    prompt: str,
) -> str:

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
            "content": build_system_prompt(),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    case_timeout = (
        get_case_timeout()
    )

    deadline = (
        time.monotonic()
        + case_timeout
    )

    backend_tool_used = False

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):

        timeout = (
            _remaining_timeout(
                deadline
            )
        )

        reply = call_llm(
            messages,
            timeout=timeout,
        )

        task_type = (
            detect_task_type(
                reply
            )
        )

        # ==================================================
        # QASM
        # ==================================================

        if task_type == "qasm":

            clean_reply = (
                strip_task_marker(
                    reply
                ).strip()
            )

            validation = (
                validate_llm_qasm_reply(
                    clean_reply
                )
            )

            if validation["ok"]:
                return validation["qasm"]

            last_error = (
                validation["error"]
            )

            _append_retry(
                messages,
                reply,
                (
                    "The OpenQASM response failed "
                    "deterministic LoomQ L1 validation.\n\n"
                    f"Validation error:\n"
                    f"{last_error}\n\n"
                    "Correct the circuit and return:\n\n"
                    "LOOMQ_TASK: QASM\n"
                    "<complete valid OpenQASM 2.0>"
                ),
            )

            continue

        # ==================================================
        # BACKEND
        # ==================================================

        if task_type == "backend":

            # ----------------------------------------------
            # First backend step:
            #
            # Give the LLM the official capability table.
            #
            # Python does NOT select anything here.
            # ----------------------------------------------

            if not backend_tool_used:

                capabilities = (
                    get_backend_capabilities_for_llm()
                )

                backend_tool_used = True

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
                            "[LOOMQ TOOL RESULT]\n"
                            "tool: "
                            "get_backend_capabilities\n\n"
                            "The following is the official "
                            "backend capability table and "
                            "the unique source of truth for "
                            "this recommendation:\n\n"
                            f"{capabilities}\n\n"
                            "Now interpret the original "
                            "user constraints and make the "
                            "backend decision yourself.\n\n"
                            "Return only the required "
                            "LOOMQ_DECISION format."
                        ),
                    }
                )

                continue

            # ----------------------------------------------
            # The tool has already been supplied.
            #
            # Now the LLM must make the decision.
            # ----------------------------------------------

            parsed = (
                parse_backend_decision(
                    reply
                )
            )

            if not parsed["ok"]:

                last_error = (
                    parsed["error"]
                )

                _append_retry(
                    messages,
                    reply,
                    (
                        "Your backend decision format "
                        "is invalid.\n\n"
                        f"Error:\n{last_error}\n\n"
                        "Re-read the official backend "
                        "tool result and return a valid "
                        "LOOMQ_DECISION."
                    ),
                )

                continue

            decision = (
                parsed["decision"]
            )

            constraints = (
                decision["constraints"]
            )

            schema_validation = (
                validate_backend_constraints(
                    constraints
                )
            )

            if not schema_validation["ok"]:

                last_error = (
                    schema_validation[
                        "error"
                    ]
                )

                _append_retry(
                    messages,
                    reply,
                    (
                        "Your extracted backend "
                        "constraints are not valid.\n\n"
                        f"Error:\n{last_error}\n\n"
                        "Re-read the original user "
                        "request and the backend tool "
                        "result, then return a corrected "
                        "LOOMQ_DECISION."
                    ),
                )

                continue

            status = decision[
                "status"
            ]

            # ----------------------------------------------
            # SELECTED
            # ----------------------------------------------

            if status == "selected":

                backend_id = (
                    decision["backend_id"]
                )

                verification = (
                    verify_backend(
                        backend_id,
                        constraints,
                    )
                )

                if verification["ok"]:
                    return (
                        _format_selected_backend(
                            decision
                        )
                    )

                violations = (
                    verification[
                        "violations"
                    ]
                )

                last_error = "; ".join(
                    violations
                )

                feedback_lines = [
                    "Your backend selection failed "
                    "deterministic verification.",
                    "",
                    f"Selected backend: "
                    f"{backend_id}",
                    "",
                    "Violations:",
                ]

                for violation in violations:
                    feedback_lines.append(
                        f"- {violation}"
                    )

                feedback_lines.extend(
                    [
                        "",
                        "Do not guess and do not ask "
                        "Python to choose for you.",
                        "Re-read the official backend "
                        "tool result and choose the "
                        "backend yourself.",
                        "",
                        "Return a corrected "
                        "LOOMQ_DECISION.",
                    ]
                )

                _append_retry(
                    messages,
                    reply,
                    "\n".join(
                        feedback_lines
                    ),
                )

                continue

            # ----------------------------------------------
            # NO MATCH
            #
            # Python only verifies whether the LLM's
            # claim is true.
            #
            # It does NOT tell the LLM which backend
            # is correct.
            # ----------------------------------------------

            if status == "no_match":

                matches = (
                    find_matching_backends(
                        constraints
                    )
                )

                if not matches:

                    return (
                        _format_no_match(
                            decision
                        )
                    )

                last_error = (
                    "The model claimed that no "
                    "backend matches, but at least "
                    "one official backend satisfies "
                    "the stated constraints."
                )

                _append_retry(
                    messages,
                    reply,
                    (
                        "Your no_match decision is "
                        "incorrect.\n\n"
                        "At least one backend in the "
                        "official capability table "
                        "satisfies the constraints "
                        "you stated.\n\n"
                        "I will not provide the "
                        "correct backend ID. "
                        "Re-read the tool result, "
                        "select it yourself, and "
                        "return a corrected "
                        "LOOMQ_DECISION."
                    ),
                )

                continue

        # ==================================================
        # UNKNOWN PROTOCOL
        # ==================================================

        last_error = (
            "LLM response did not follow "
            "the LoomQ protocol."
        )

        _append_retry(
            messages,
            reply,
            (
                "Your response did not follow "
                "the LoomQ protocol.\n\n"
                "For circuit generation/repair:\n"
                "LOOMQ_TASK: QASM\n"
                "<OpenQASM 2.0>\n\n"
                "For backend recommendation, "
                "request the backend capability tool:\n"
                "LOOMQ_TASK: BACKEND\n"
                "LOOMQ_ACTION: "
                "GET_BACKEND_CAPABILITIES"
            ),
        )

    raise RuntimeError(
        "L2 agent failed after "
        f"{MAX_ATTEMPTS} LLM calls. "
        f"Last error: {last_error}"
    )