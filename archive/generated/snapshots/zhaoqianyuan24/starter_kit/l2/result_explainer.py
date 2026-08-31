import json
from typing import Any, Dict

from .client import call_llm
from .policy import get_case_timeout


RESULT_EXPLAIN_SYSTEM_PROMPT = """
You are the LoomQ result interpretation agent.

You are given:

1. The user's original request.
2. The generated Hybrid-QASM program.
3. Actual quantum measurement counts produced by a LoomQ backend.
4. Actual classical register outcomes produced by the RISC-V runtime.

Your job is to explain the result clearly and accurately.

IMPORTANT RULES:

- Treat the provided execution result as ground truth.
- Never invent measurement counts, probabilities, register values,
  backend properties, or circuit operations.
- Distinguish observed finite-shot results from ideal theoretical values.
- If an ideal probability is obvious from the circuit, you may explain it,
  but clearly distinguish theory from the measured/simulated result.
- Explain how quantum measurement controls the classical branch.
- When useful, explain what the relevant quantum gates do.
- Keep the explanation accessible to a user who may not know OpenQASM
  or RISC-V.
- Do not claim quantum speedup unless the experiment actually demonstrates it.
- Do not claim hardware noise when the result came from an ideal simulator.

Answer in the same language as the user's request whenever practical.
""".strip()


def _build_result_summary(
    hybrid_result: Dict[str, Any],
) -> Dict[str, Any]:

    runtime = hybrid_result["result"]

    quantum_result = runtime[
        "quantum_result"
    ]

    branches = []

    for branch in runtime.get(
        "branches",
        []
    ):
        branches.append(
            {
                "quantum_bitstring": (
                    branch[
                        "quantum_bitstring"
                    ]
                ),
                "measurements": (
                    branch[
                        "measurements"
                    ]
                ),
                "count": (
                    branch[
                        "count"
                    ]
                ),
                "probability": (
                    branch[
                        "probability"
                    ]
                ),
                "registers": (
                    branch[
                        "registers"
                    ]
                ),
            }
        )

    classical_outcomes = []

    for outcome in runtime.get(
        "classical_outcomes",
        []
    ):
        classical_outcomes.append(
            {
                "count": (
                    outcome[
                        "count"
                    ]
                ),
                "probability": (
                    outcome[
                        "probability"
                    ]
                ),
                "registers": (
                    outcome[
                        "registers"
                    ]
                ),
            }
        )

    return {
        "target": hybrid_result[
            "target"
        ],
        "shots": hybrid_result[
            "shots"
        ],
        "quantum_counts": (
            quantum_result[
                "counts"
            ]
        ),
        "branches": branches,
        "classical_outcomes": (
            classical_outcomes
        ),
    }



def explain_hybrid_result(
    hybrid_result: Dict[str, Any],
) -> str:

    if not isinstance(
        hybrid_result,
        dict,
    ):
        raise TypeError(
            "hybrid_result must be a dictionary"
        )

    required = {
        "prompt",
        "hybrid_qasm",
        "result",
        "target",
        "shots",
    }

    missing = (
        required
        - set(hybrid_result)
    )

    if missing:
        raise ValueError(
            "hybrid_result is missing: "
            + ", ".join(
                sorted(missing)
            )
        )

    summary = (
        _build_result_summary(
            hybrid_result
        )
    )

    # Convert the real execution result to JSON first.
    # Do NOT place a multiline json.dumps() call
    # directly inside an f-string.
    summary_json = json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )

    user_content = (
        "Original user request:\n\n"
        + hybrid_result["prompt"]
        + "\n\n"
        + "Generated Hybrid-QASM:\n\n"
        + hybrid_result["hybrid_qasm"]
        + "\n\n"
        + "Actual LoomQ execution result:\n\n"
        + summary_json
        + "\n\n"
        + "Explain what happened and what "
        + "the result means."
    )

    messages = [
        {
            "role": "system",
            "content": (
                RESULT_EXPLAIN_SYSTEM_PROMPT
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    return call_llm(
        messages,
        timeout=get_case_timeout(),
    ).strip()