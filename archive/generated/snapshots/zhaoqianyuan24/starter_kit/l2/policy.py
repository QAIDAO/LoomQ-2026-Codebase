import json
from pathlib import Path


def load_l2_policy() -> dict:
    path = (
        Path(__file__).resolve().parent.parent
        / "l2_policy.json"
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def get_protocol() -> str:
    policy = load_l2_policy()

    return policy[
        "protocol"
    ]


def get_temperature() -> float:
    policy = load_l2_policy()

    return policy[
        "temperature"
    ]


def get_stream() -> bool:
    policy = load_l2_policy()

    return policy[
        "stream"
    ]


def get_case_timeout() -> float:
    policy = load_l2_policy()

    return float(
        policy[
            "per_case"
        ][
            "timeout_seconds"
        ]
    )


def get_formal_model() -> str:
    policy = load_l2_policy()

    return policy[
        "formal_model"
    ]
    
def get_thinking():
    policy = load_l2_policy()

    return policy.get(
        "thinking",
        {"type": "disabled"},
    )