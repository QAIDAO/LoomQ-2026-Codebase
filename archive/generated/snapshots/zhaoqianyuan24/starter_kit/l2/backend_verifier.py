import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_backends() -> List[Dict[str, Any]]:
    path = (
        Path(__file__).resolve().parent.parent
        / "backend_capabilities.json"
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = json.load(handle)

    return data["backends"]


def get_backend(
    backend_id: str
) -> Optional[Dict[str, Any]]:

    for backend in load_backends():

        if backend["id"] == backend_id:
            return backend

    return None


def extract_backend_id(
    reply_text: str
) -> Optional[str]:

    lower_reply = reply_text.lower()

    for backend in load_backends():

        backend_id = backend["id"]

        if backend_id.lower() in lower_reply:
            return backend_id

    return None


def is_local_backend(
    backend: Dict[str, Any]
) -> bool:

    return (
        backend["kind"] == "simulator"
        and backend["queue"] == "none"
        and backend["requires_account"] is False
    )


def verify_backend(
    backend_id: str,
    requirements: Dict[str, Any],
) -> Dict[str, Any]:

    backend = get_backend(
        backend_id
    )
    if backend is None:
        return {
            "ok": False,
            "backend": None,
            "violations": [
                f"Unknown backend id: {backend_id}"
            ],
        }
    
    violations = []
        
    platform = requirements.get(
        "platform"
    )

    if (
        platform is not None
        and backend["platform"] != platform
    ):
        violations.append(
            f"{backend_id} belongs to platform "
            f"'{backend['platform']}', "
            f"but '{platform}' is required."
        )
    min_qubits = requirements.get(
        "min_qubits"
    )

    if (
        min_qubits is not None
        and backend["max_qubits"] < min_qubits
    ):
        violations.append(
            f"{backend_id} supports at most "
            f"{backend['max_qubits']} qubits, "
            f"but at least {min_qubits} are required."
        )
        
    if requirements.get(
        "cloud"
    ):

        if backend["kind"] not in {
            "cloud",
            "qpu",
        }:
            violations.append(
                f"{backend_id} is not "
                f"a cloud-access backend."
            )
        
                
    
    # --------------------------------------------------
    # Qubit capacity
    # --------------------------------------------------


    # --------------------------------------------------
    # Local execution
    # --------------------------------------------------
    if "local" in requirements:

        local_required = (
            requirements["local"]
        )

        backend_is_local = (
            is_local_backend(
                backend
            )
        )

        if (
            local_required
            and not backend_is_local
        ):
            violations.append(
                f"{backend_id} is not a local "
                f"no-account simulator."
            )

        if (
            local_required is False
            and backend_is_local
        ):
            violations.append(
                f"{backend_id} is a local backend, "
                f"but local execution was "
                f"explicitly excluded."
            )

    # --------------------------------------------------
    # Free execution
    # --------------------------------------------------

    if requirements.get("free"):

        if backend["cost"] not in {
            "free",
            "free_quota",
        }:
            violations.append(
                f"{backend_id} does not satisfy "
                f"the free-cost requirement."
            )

    # --------------------------------------------------
    # Strictly free
    # --------------------------------------------------

    if requirements.get(
        "strictly_free"
    ):

        if backend["cost"] != "free":
            violations.append(
                f"{backend_id} is not strictly free "
                f"(cost={backend['cost']})."
            )

    # --------------------------------------------------
    # No queue
    # --------------------------------------------------

    if requirements.get(
        "no_queue"
    ):

        if backend["queue"] != "none":
            violations.append(
                f"{backend_id} has queue status "
                f"'{backend['queue']}'."
            )

    # --------------------------------------------------
    # No account
    # --------------------------------------------------

    if requirements.get(
        "no_account"
    ):

        if backend["requires_account"]:
            violations.append(
                f"{backend_id} requires an account."
            )

    # --------------------------------------------------
    # Real QPU required
    # --------------------------------------------------
    if "qpu" in requirements:

        qpu_required = requirements["qpu"]

        if (
            qpu_required
            and backend["kind"] != "qpu"
        ):
            violations.append(
                f"{backend_id} is not a QPU backend."
            )

        if (
            qpu_required is False
            and backend["kind"] == "qpu"
        ):
            violations.append(
                f"{backend_id} is a QPU backend, "
                f"but QPU execution was explicitly excluded."
            )
    if "simulator" in requirements:

        simulator_required = (
            requirements["simulator"]
        )

        if (
            simulator_required
            and backend["kind"] != "simulator"
        ):
            violations.append(
                f"{backend_id} is not "
                f"a simulator backend."
            )

        if (
            simulator_required is False
            and backend["kind"] == "simulator"
        ):
            violations.append(
                f"{backend_id} is a simulator, "
                f"but simulator execution was "
                f"explicitly excluded."
            )
    return {
        "ok": len(violations) == 0,
        "backend": backend,
        "violations": violations,
    }


def find_matching_backends(
    requirements: Dict[str, Any]
) -> List[Dict[str, Any]]:

    matches = []

    for backend in load_backends():

        result = verify_backend(
            backend["id"],
            requirements,
        )

        if result["ok"]:
            matches.append(
                backend
            )

    return matches
