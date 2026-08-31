from l2.backend_requirements import (
    extract_backend_requirements,
)

from l2.backend_verifier import (
    find_matching_backends,
)


def ids(requirements):
    return {
        backend["id"]
        for backend in find_matching_backends(
            requirements
        )
    }


def check(
    name,
    requirements,
    expected,
):
    actual = ids(
        requirements
    )

    expected = set(
        expected
    )

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print(
        "requirements =",
        requirements,
    )

    print(
        "actual       =",
        sorted(actual),
    )

    print(
        "expected     =",
        sorted(expected),
    )

    assert actual == expected, (
        f"{name}: "
        f"expected {expected}, "
        f"got {actual}"
    )


# ============================================================
# Local simulator boundaries
# ============================================================

check(
    "20-qubit local",
    {
        "min_qubits": 20,
        "local": True,
    },
    {
        "spinq_taurus_simulator",
        "originq_local_simulator",
        "braket_local_simulator",
    },
)


check(
    "24-qubit local",
    {
        "min_qubits": 24,
        "local": True,
    },
    {
        "spinq_taurus_simulator",
        "originq_local_simulator",
        "braket_local_simulator",
    },
)


check(
    "25-qubit local",
    {
        "min_qubits": 25,
        "local": True,
    },
    {
        "originq_local_simulator",
        "braket_local_simulator",
    },
)


check(
    "26-qubit local",
    {
        "min_qubits": 26,
        "local": True,
    },
    {
        "originq_local_simulator",
    },
)


check(
    "30-qubit local",
    {
        "min_qubits": 30,
        "local": True,
    },
    {
        "originq_local_simulator",
    },
)


check(
    "31-qubit local",
    {
        "min_qubits": 31,
        "local": True,
    },
    set(),
)


# ============================================================
# QPU boundaries
# ============================================================

check(
    "8-qubit free QPU",
    {
        "min_qubits": 8,
        "qpu": True,
        "free": True,
    },
    {
        "spinq_cloud_qpu",
        "originq_wukong",
    },
)


check(
    "9-qubit free QPU",
    {
        "min_qubits": 9,
        "qpu": True,
        "free": True,
    },
    {
        "originq_wukong",
    },
)


check(
    "60-qubit QPU",
    {
        "min_qubits": 60,
        "qpu": True,
    },
    {
        "originq_wukong",
    },
)


check(
    "73-qubit QPU",
    {
        "min_qubits": 73,
        "qpu": True,
    },
    set(),
)


# ============================================================
# Platform constraints
# ============================================================

check(
    "SpinQ 8-qubit QPU",
    {
        "min_qubits": 8,
        "qpu": True,
        "platform": "spinq",
    },
    {
        "spinq_cloud_qpu",
    },
)


check(
    "OriginQ local",
    {
        "local": True,
        "platform": "originq",
    },
    {
        "originq_local_simulator",
    },
)


check(
    "Braket local",
    {
        "local": True,
        "platform": "braket",
    },
    {
        "braket_local_simulator",
    },
)


# ============================================================
# Cost semantics
# ============================================================

check(
    "Strictly free QPU",
    {
        "qpu": True,
        "strictly_free": True,
    },
    set(),
)


check(
    "Free-quota QPU allowed",
    {
        "qpu": True,
        "free": True,
    },
    {
        "spinq_cloud_qpu",
        "originq_wukong",
    },
)


# ============================================================
# Natural-language extraction
# ============================================================

english = extract_backend_requirements(
    "I need a 28-qubit circuit locally. "
    "It must be completely free, "
    "with no queue and no account."
)

assert english["min_qubits"] == 28
assert english["local"] is True
assert english["strictly_free"] is True
assert english["no_queue"] is True
assert english["no_account"] is True


chinese = extract_backend_requirements(
    "我需要运行一个28个量子比特的电路，"
    "要求本地运行、完全免费、不排队、无需账号。"
)

assert chinese["min_qubits"] == 28
assert chinese["local"] is True
assert chinese["strictly_free"] is True
assert chinese["no_queue"] is True
assert chinese["no_account"] is True


print()
print("=" * 70)
print("ALL L2 BACKEND LOGIC TESTS PASSED")
print("=" * 70)
