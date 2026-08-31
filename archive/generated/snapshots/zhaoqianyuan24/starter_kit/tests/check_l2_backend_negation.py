from l2.backend_requirements import (
    extract_backend_requirements,
)

from l2.backend_verifier import (
    find_matching_backends,
)


def backend_ids(requirements):
    return {
        backend["id"]
        for backend in find_matching_backends(
            requirements
        )
    }


def check_extract(
    prompt,
    key,
    expected,
):
    result = (
        extract_backend_requirements(
            prompt
        )
    )

    print()
    print("=" * 70)
    print(prompt)
    print(result)

    assert key in result
    assert result[key] is expected


# ============================================================
# English negation
# ============================================================

check_extract(
    "I do not need a real QPU.",
    "qpu",
    False,
)

check_extract(
    "I don't want a simulator.",
    "simulator",
    False,
)

check_extract(
    "Do not run this locally.",
    "local",
    False,
)


# ============================================================
# Chinese negation
# ============================================================

check_extract(
    "我不需要真机。",
    "qpu",
    False,
)

check_extract(
    "我不要模拟器。",
    "simulator",
    False,
)

check_extract(
    "不要在本地运行。",
    "local",
    False,
)


# ============================================================
# Positive forms must still work
# ============================================================

check_extract(
    "I need a real QPU.",
    "qpu",
    True,
)

check_extract(
    "Please use a simulator.",
    "simulator",
    True,
)

check_extract(
    "Run it locally.",
    "local",
    True,
)


# ============================================================
# Unspecified must remain unspecified
# ============================================================

requirements = (
    extract_backend_requirements(
        "I need a 20-qubit circuit."
    )
)

assert "qpu" not in requirements
assert "simulator" not in requirements
assert "local" not in requirements


# ============================================================
# Backend filtering
# ============================================================

requirements = (
    extract_backend_requirements(
        "I need at least 20 qubits "
        "but I do not want a real QPU."
    )
)

matches = backend_ids(
    requirements
)

assert (
    "spinq_cloud_qpu"
    not in matches
)

assert (
    "originq_wukong"
    not in matches
)


requirements = (
    extract_backend_requirements(
        "I need at least 20 qubits "
        "and I don't want a simulator."
    )
)

matches = backend_ids(
    requirements
)

assert (
    "spinq_taurus_simulator"
    not in matches
)

assert (
    "originq_local_simulator"
    not in matches
)

assert (
    "braket_local_simulator"
    not in matches
)


print()
print("=" * 70)
print(
    "ALL L2 BACKEND NEGATION TESTS PASSED"
)
print("=" * 70)
