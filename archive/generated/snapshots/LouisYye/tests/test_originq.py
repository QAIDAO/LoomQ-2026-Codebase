import os
import tempfile
from pathlib import Path

import pytest
from qiskit import qasm2
from qiskit.quantum_info import Statevector


CACHE_ROOT = Path(tempfile.gettempdir()) / "loomq-originq-test-cache"
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_ROOT / "xdg"))


from starter_kit.adapter import run, transpile
from starter_kit.backend.originq import run_originq
from starter_kit.emitters.originq import emit_originq
from starter_kit.evaluator import calculate_hellinger_fidelity
from starter_kit.parser import parse_qasm


ROOT = Path(__file__).resolve().parents[1]
CIRCUITS = ROOT / "starter_kit" / "circuits"


def read_circuit(name: str) -> str:
    return (CIRCUITS / name).read_text(encoding="utf-8")


ALL_GATES_QASM = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
x q[1];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
ry(0.2) q[0];
rz(0.3) q[1];
cx q[0], q[1];
cu1(0.4) q[0], q[1];
swap q[0], q[1];
ccx q[0], q[1], q[2];
measure q -> c;
"""


SEMANTIC_QASM = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

h q[0];
h q[1];
x q[2];
s q[0];
sdg q[1];
t q[2];
tdg q[0];
ry(0.37) q[0];
rz(-0.29) q[1];
cx q[0], q[2];
cu1(0.61) q[0], q[1];
swap q[1], q[2];
ccx q[0], q[1], q[2];
h q[0];
h q[1];
h q[2];
measure q -> c;
"""


def test_contract_emitter_maps_all_twelve_gates():
    origin_ir = transpile(ALL_GATES_QASM, target="originq")

    expected = [
        "QINIT 3",
        "CREG 3",
        "H q[0]",
        "X q[1]",
        "S q[0]",
        "SDAG q[0]",
        "T q[0]",
        "TDAG q[0]",
        "RY q[0],(0.2)",
        "RZ q[1],(0.3)",
        "CNOT q[0], q[1]",
        "CR q[0], q[1],(0.4)",
        "SWAP q[0], q[1]",
        "TOFFOLI q[0], q[1], q[2]",
    ]

    for instruction in expected:
        assert instruction in origin_ir


def test_contract_emitter_preserves_measurements():
    origin_ir = transpile(
        read_circuit("bell.qasm"),
        target="originq",
    )

    assert "MEASURE q[0], c[0]" in origin_ir
    assert "MEASURE q[1], c[1]" in origin_ir


def test_execution_emitter_uses_pyqpanda_compatible_ir():
    circuit = parse_qasm(ALL_GATES_QASM)
    origin_ir = emit_originq(
        circuit,
        execution_compatible=True,
    )

    assert "SDAG" not in origin_ir
    assert "TDAG" not in origin_ir
    assert "DAGGER\nS q[0]\nENDDAGGER" in origin_ir
    assert "DAGGER\nT q[0]\nENDDAGGER" in origin_ir
    assert "U1 q[0],(0.2)" in origin_ir


def test_all_twelve_gates_execute_locally():
    circuit = parse_qasm(ALL_GATES_QASM)
    origin_ir = emit_originq(
        circuit,
        execution_compatible=True,
    )

    result = run_originq(origin_ir, shots=128)

    assert result["shots"] == 128
    assert sum(result["counts"].values()) == 128
    assert result["bit_order"] == "little"
    assert result["backend"] == "originq_local_simulator"


def test_all_twelve_gates_preserve_semantics():
    reference = qasm2.loads(
        SEMANTIC_QASM,
        custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS,
    )
    reference.remove_final_measurements(inplace=True)
    expected = {
        str(key): float(probability)
        for key, probability in (
            Statevector.from_instruction(reference)
            .probabilities_dict()
            .items()
        )
        if probability > 1e-12
    }

    shots = 8192
    result = run(SEMANTIC_QASM, target="originq", shots=shots)
    observed = {
        key: count / shots
        for key, count in result["counts"].items()
    }

    assert calculate_hellinger_fidelity(observed, expected) >= 0.97


@pytest.mark.parametrize(
    ("filename", "allowed_states"),
    [
        ("bell.qasm", {"00", "11"}),
        ("ghz3.qasm", {"000", "111"}),
    ],
)
def test_public_circuits(
    filename: str,
    allowed_states: set[str],
):
    result = run(
        read_circuit(filename),
        target="originq",
        shots=512,
    )

    assert result["shots"] == 512
    assert sum(result["counts"].values()) == 512
    assert set(result["counts"]) <= allowed_states
    assert result["bit_order"] == "little"
    assert result["job_id"]
    assert result["timestamp"]


@pytest.mark.parametrize("shots", [0, -1])
def test_rejects_invalid_shots(shots: int):
    with pytest.raises(ValueError, match="shots must be positive"):
        run(
            read_circuit("bell.qasm"),
            target="originq",
            shots=shots,
        )


@pytest.mark.parametrize(
    ("body", "expected_counts"),
    [
        ("x q[0];\nmeasure q -> c;", {"01": 32}),
        ("x q[1];\nmeasure q -> c;", {"10": 32}),
        (
            "x q[1];\n"
            "measure q[1] -> c[0];\n"
            "measure q[0] -> c[1];",
            {"01": 32},
        ),
        ("x q[1];\nmeasure q[1] -> c[1];", {"10": 32}),
    ],
)
def test_counts_use_qiskit_bit_order(
    body: str,
    expected_counts: dict[str, int],
):
    qasm2 = f"""
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    {body}
    """

    result = run(qasm2, target="originq", shots=32)
    assert result["counts"] == expected_counts
