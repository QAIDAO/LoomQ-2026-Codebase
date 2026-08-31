import re
from typing import Any, Dict

def _contains_any(
    text: str,
    terms,
) -> bool:
    return any(
        term in text
        for term in terms
    )


def _set_boolean_requirement(
    requirements,
    key,
    text,
    positive_terms,
    negative_terms,
):
    # Negative expressions must be checked first.
    #
    # Example:
    # "I don't want a real QPU"
    #
    # contains both:
    #   "qpu"
    #   "don't want ... qpu"
    #
    # Therefore the negative meaning has priority.

    if _contains_any(
        text,
        negative_terms,
    ):
        requirements[key] = False
        return

    if _contains_any(
        text,
        positive_terms,
    ):
        requirements[key] = True
def extract_backend_requirements(
    prompt: str
) -> Dict[str, Any]:

    if not isinstance(prompt, str):
        raise TypeError(
            "prompt must be a string"
        )

    text = prompt.strip()

    if not text:
        raise ValueError(
            "prompt must not be empty"
        )

    lower = text.lower()

    requirements = {}


    # ========================================================
    # Minimum qubit count
    #
    # Examples:
    #   28 qubits
    #   28-qubit circuit
    #   28 qbits
    #   28 个量子比特
    #   28 量子位
    # ========================================================

    qubit_patterns = [
        r"(\d+)\s*[- ]?\s*qubits?",
        r"(\d+)\s*[- ]?\s*qbits?",
        r"(\d+)\s*(?:个)?\s*量子比特",
        r"(\d+)\s*(?:个)?\s*量子位",
    ]

    for pattern in qubit_patterns:

        match = re.search(
            pattern,
            lower,
        )

        if match:
            requirements[
                "min_qubits"
            ] = int(
                match.group(1)
            )

            break


    # ========================================================
    # Platform preference
    # ========================================================

    if "spinq" in lower:
        requirements[
            "platform"
        ] = "spinq"

    elif (
        "originq" in lower
        or "本源量子" in text
    ):
        requirements[
            "platform"
        ] = "originq"

    elif "braket" in lower:
        requirements[
            "platform"
        ] = "braket"


    # ========================================================
    # Local execution
    # ========================================================
    local_positive_terms = [
        "local",
        "locally",
        "on my machine",
        "本地",
        "本机",
        "本地运行",
    ]

    local_negative_terms = [
        "not local",
        "not locally",
        "don't run locally",
        "do not run locally",
        "don't run this locally",
        "do not run this locally",
        "don't run it locally",
        "do not run it locally",
        "don't want local",
        "do not want local",
        "avoid local",
        "不要本地",
        "不需要本地",
        "不想本地运行",
        "不要在本地运行",
        "不要本地运行",
        "不要在本机运行",
        "不在本地运行",
    ]

    _set_boolean_requirement(
        requirements,
        "local",
        lower,
        local_positive_terms,
        local_negative_terms,
    )

#    if any(
#        term in lower
#        for term in local_terms
#    ):
#        requirements[
#            "local"
#        ] = True


    # ========================================================
    # Free
    #
    # Generic "free" allows:
    #   free
    #   free_quota
    # ========================================================

    free_terms = [
        "free",
        "no cost",
        "without cost",
        "免费",
        "不花钱",
        "零成本",
    ]

    if any(
        term in lower
        for term in free_terms
    ):
        requirements[
            "free"
        ] = True


    # ========================================================
    # Strictly free
    #
    # This is stronger than free:
    # only cost == "free" is accepted.
    # ========================================================

    strictly_free_terms = [
        "strictly free",
        "completely free",
        "fully free",
        "完全免费",
        "必须完全免费",
        "不要免费额度",
        "不限免费额度",
    ]

    if any(
        term in lower
        for term in strictly_free_terms
    ):
        requirements[
            "strictly_free"
        ] = True


    # ========================================================
    # No queue
    # ========================================================

    no_queue_terms = [
        "no queue",
        "without queue",
        "no waiting",
        "without waiting",
        "不排队",
        "不用排队",
        "无需排队",
        "不等待",
    ]

    if any(
        term in lower
        for term in no_queue_terms
    ):
        requirements[
            "no_queue"
        ] = True


    # ========================================================
    # No account
    # ========================================================

    no_account_terms = [
        "no account",
        "without account",
        "no registration",
        "without registration",
        "不需要账号",
        "无需账号",
        "不要账号",
        "不用注册",
        "无需注册",
    ]

    if any(
        term in lower
        for term in no_account_terms
    ):
        requirements[
            "no_account"
        ] = True


    # ========================================================
    # Real QPU
    # ========================================================
    qpu_positive_terms = [
        "qpu",
        "real quantum computer",
        "real quantum hardware",
        "real hardware",
        "real chip",
        "真机",
        "真实量子计算机",
        "真实量子硬件",
        "量子真机",
    ]

    qpu_negative_terms = [
        # English: QPU
        "don't need qpu",
        "do not need qpu",
        "don't need a qpu",
        "do not need a qpu",
        "don't need a real qpu",
        "do not need a real qpu",

        "don't want qpu",
        "do not want qpu",
        "don't want a qpu",
        "do not want a qpu",
        "don't want a real qpu",
        "do not want a real qpu",

        "no qpu",
        "not a qpu",
        "avoid qpu",

        # English: real hardware
        "don't need real hardware",
        "do not need real hardware",
        "don't need real quantum hardware",
        "do not need real quantum hardware",

        "don't want real hardware",
        "do not want real hardware",
        "don't want real quantum hardware",
        "do not want real quantum hardware",

        "avoid real hardware",

        # Chinese
        "不需要真机",
        "不要真机",
        "不想用真机",
        "无需真机",
        "不需要量子真机",
        "不要量子真机",

        "不需要真实量子计算机",
        "不要真实量子计算机",
        "不想用真实量子计算机",

        "不需要真实量子硬件",
        "不要真实量子硬件",
        "不想用真实量子硬件",
    ]

    _set_boolean_requirement(
        requirements,
        "qpu",
        lower,
        qpu_positive_terms,
        qpu_negative_terms,
    )

    # ========================================================
    # Simulator
    # ========================================================
    simulator_positive_terms = [
        "simulator",
        "simulation backend",
        "模拟器",
        "仿真器",
    ]

    simulator_negative_terms = [
        "not a simulator",
        "no simulator",
        "don't need a simulator",
        "do not need a simulator",
        "don't want a simulator",
        "do not want a simulator",
        "avoid simulator",
        "不需要模拟器",
        "不要模拟器",
        "不想用模拟器",
        "无需模拟器",
        "不要仿真器",
    ]

    _set_boolean_requirement(
        requirements,
        "simulator",
        lower,
        simulator_positive_terms,
        simulator_negative_terms,
    )
 
#    if any(
#        term in lower
#        for term in simulator_terms
#    ):
#        requirements[
#            "simulator"
#        ] = True


    # ========================================================
    # Cloud
    # ========================================================

    cloud_terms = [
        "cloud",
        "cloud backend",
        "云端",
        "云计算",
    ]

    if any(
        term in lower
        for term in cloud_terms
    ):
        requirements[
            "cloud"
        ] = True


    return requirements
