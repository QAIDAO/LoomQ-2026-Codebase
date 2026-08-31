import math

import pytest

from starter_kit.l2.backends import select
from starter_kit.l2.normalize import normalize
from starter_kit.l2.reference import reference_distribution
from starter_kit.l2.simulate import simulate
from starter_kit.l2.synthesize import synthesize
from starter_kit.l2.verify import fidelity


def circuit(body, n=3):
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[{n}];
creg c[{n}];
{body}
measure q -> c;
'''


@pytest.mark.parametrize(("body", "target"), [
    ("h q[0]; cx q[0],q[1];", {"kind": "bell", "n": 2}),
    ("h q[0]; cx q[0],q[1]; cx q[1],q[2];", {"kind": "ghz", "n": 3}),
    ("h q[0]; h q[1]; h q[2];", {"kind": "uniform", "n": 3}),
])
def test_reference_circuits_have_unit_fidelity(body, target):
    n = target["n"]
    _, parsed = normalize(circuit(body, n=n))
    assert fidelity(simulate(parsed), reference_distribution(target)) == pytest.approx(1.0)


def test_w3_distribution():
    # ry angles plus controlled construction are not needed to test the reference itself.
    expected = reference_distribution({"kind": "w", "n": 3})
    assert expected == pytest.approx({"001": 1/3, "010": 1/3, "100": 1/3})


def test_measurement_mapping_is_respected():
    source = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[2];
x q[1];
measure q[1] -> c[0];
measure q[0] -> c[1];'''
    _, parsed = normalize(source)
    assert simulate(parsed) == pytest.approx({"01": 1.0})


def test_swap_ccx_and_rotation_semantics():
    source = circuit("x q[0]; swap q[0],q[1]; x q[0]; ccx q[0],q[1],q[2];", 3)
    _, parsed = normalize(source)
    assert simulate(parsed) == pytest.approx({"111": 1.0})
    rotated = circuit(f"ry({math.pi / 2}) q[0];", 1)
    _, parsed = normalize(rotated)
    assert simulate(parsed) == pytest.approx({"0": 0.5, "1": 0.5})


def test_unsupported_gate_is_normalized_to_whitelist():
    source = circuit("rx(0.4) q[0]; cz q[0],q[1];", 2)
    text, parsed = normalize(source)
    assert {gate.name for gate in parsed.gates} <= {
        "h", "x", "s", "sdg", "t", "tdg", "ry", "rz", "cx", "swap", "ccx"
    }
    assert "rx(" not in text and "cz " not in text


def test_backend_selection_applies_hard_constraints():
    # Ties among valid local simulators go to the table's recommended default.
    assert select({"min_qubits": 15, "queue": "none", "cost": "free", "no_account": True})["id"] == "braket_local_simulator"
    assert select({"min_qubits": 50, "requires_hardware": True})["id"] == "originq_wukong"
    assert select({"min_qubits": 25, "local_only": True})["id"] == "braket_local_simulator"
    assert select({"min_qubits": 30, "no_account": True})["id"] == "originq_local_simulator"


@pytest.mark.parametrize(("constraints", "expected"), [
    # No table entry is free AND queue-free AND real hardware: relaxing the soft
    # constraints must never turn a hardware question into a simulator answer.
    ({"requires_hardware": True, "cost": "free", "queue": "none"}, "spinq_cloud_qpu"),
    ({"requires_hardware": True, "no_account": True}, "spinq_cloud_qpu"),
    # Capacity beyond every machine falls back to the largest qualifying one.
    ({"requires_hardware": True, "min_qubits": 100}, "originq_wukong"),
])
def test_hardware_requirement_is_never_relaxed(constraints, expected):
    selected = select(constraints)
    assert selected["kind"] == "qpu"
    assert selected["id"] == expected


def test_managed_cloud_beats_a_queueing_qpu_when_hardware_is_not_requested():
    assert select({"min_qubits": 34})["id"] == "braket_cloud"


def test_selection_is_total():
    for constraints in ({}, None, {"min_qubits": "abc"}, {"min_qubits": 9999}):
        assert select(constraints)["id"]


@pytest.mark.parametrize("target", [
    {"kind": "ghz", "n": 3, "measure_all": True},
    {"kind": "bell", "n": 2},
    {"kind": "w", "n": 3},
    {"kind": "uniform", "n": 2},
    {"kind": "basis", "n": 3, "state": "101"},
    {"kind": "custom", "n": 2, "expected_distribution": {"01": 0.25, "10": 0.75}},
])
def test_synthesized_circuits_match_their_declared_target(target):
    program, score = synthesize(target)
    assert score >= 0.999
    _, parsed = normalize(program)
    assert fidelity(simulate(parsed), reference_distribution(target)) >= 0.999


def _body(program):
    skip = ("OPENQASM", "include", "qreg", "creg", "measure")
    return [line for line in program.splitlines() if not line.startswith(skip)]


@pytest.mark.parametrize("n", (2, 3, 4))
def test_w_synthesis_uses_the_readable_canonical_cascade(n):
    program, score = synthesize({"kind": "w", "n": n})
    assert score >= 0.999
    # A readable ry/cx cascade, not the generic state-preparation wall.
    assert "rz(" not in program
    assert program.count("cx ") == 3 * (n - 1)
    expected = {format(1 << bit, f"0{n}b"): 1.0 / n for bit in range(n)}
    assert fidelity(simulate(normalize(program)[1]), expected) >= 0.999


def test_product_targets_collapse_to_x_and_h():
    """Fixed bits plus even superpositions must not become a rotation wall."""
    program, score = synthesize({
        "kind": "custom",
        "n": 3,
        "expected_distribution": {"010": 0.25, "011": 0.25, "110": 0.25, "111": 0.25},
    })
    assert score >= 0.999
    assert _body(program) == ["h q[0];", "x q[1];", "h q[2];"]


def test_correlated_targets_are_not_mistaken_for_products():
    """Both marginals are 0.5 here, but the qubits are correlated, not independent."""
    program, score = synthesize({
        "kind": "custom",
        "n": 2,
        "expected_distribution": {"01": 0.5, "10": 0.5},
    })
    assert score >= 0.999
    assert _body(program) != ["h q[0];", "h q[1];"]
    observed = simulate(normalize(program)[1])
    assert fidelity(observed, {"01": 0.5, "10": 0.5}) >= 0.999


def test_synthesis_declines_undeclarable_targets():
    assert synthesize({"kind": "custom", "n": 3}) is None
    assert synthesize({}) is None
    assert synthesize("nonsense") is None


def test_explicit_distribution_overrides_a_wrong_kind_label():
    target = {
        "kind": "bell", "n": 2,
        "expected_distribution": {"01": 0.5, "10": 0.5},
    }
    assert reference_distribution(target) == {"01": 0.5, "10": 0.5}


@pytest.mark.parametrize("invalid", [
    {"0": 0.5, "11": 0.5},
    {"0x": 1.0},
    {"00": -1.0, "11": 2.0},
    {"000": 1.0},
    {"00": 0.0, "11": 0.0},
])
def test_invalid_explicit_distribution_falls_back_to_kind(invalid):
    target = {"kind": "bell", "n": 2, "expected_distribution": invalid}
    assert reference_distribution(target) == {"00": 0.5, "11": 0.5}


@pytest.mark.parametrize("wrapped", [
    "```qasm\n{body}\n```",
    "```\n{body}\n```",
    "这是修好的代码：\n```qasm\n{body}\n```\n希望有帮助。",
])
def test_normalize_strips_markdown_fences(wrapped):
    body = circuit("h q[0]; cx q[0],q[1];", n=2)
    text, parsed = normalize(wrapped.format(body=body))
    assert text.startswith("OPENQASM 2.0;")
    assert len(parsed.gates) == 2


def test_wrong_distribution_fails_threshold():
    observed = {"001": 0.5, "110": 0.5}
    expected = {"000": 0.5, "111": 0.5}
    assert fidelity(observed, expected) < 0.99
