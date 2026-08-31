import json
from pathlib import Path
from typing import Any, Dict


_BACKEND_CAPABILITIES_PATH = (
    Path(__file__).resolve().parent.parent
    / "backend_capabilities.json"
)


def load_backend_capabilities() -> Dict[str, Any]:
    """
    Load the official LoomQ backend capability table.

    This file is the unique source of truth for
    L2 backend recommendation.
    """

    with _BACKEND_CAPABILITIES_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise RuntimeError(
            "backend_capabilities.json must contain "
            "a JSON object."
        )

    backends = data.get("backends")

    if not isinstance(backends, list):
        raise RuntimeError(
            "backend_capabilities.json must contain "
            "a 'backends' list."
        )

    for backend in backends:

        if not isinstance(backend, dict):
            raise RuntimeError(
                "Each backend entry must be "
                "a JSON object."
            )

        if "id" not in backend:
            raise RuntimeError(
                "Each backend entry must contain "
                "an 'id' field."
            )

    return data


def get_backend_capabilities_for_llm() -> str:
    """
    Return the official capability table as tool output
    for the LLM.

    IMPORTANT:
    This function only retrieves facts.
    It does NOT select or rank backends.
    """

    data = load_backend_capabilities()

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )
