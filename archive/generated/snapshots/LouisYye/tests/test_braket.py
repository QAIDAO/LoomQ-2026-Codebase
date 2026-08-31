import os
import tempfile
from pathlib import Path

import pytest


# Configure a writable Numba cache before importing Braket.
NUMBA_CACHE = (
    Path(tempfile.gettempdir())
    / "loomq-numba-cache"
)
NUMBA_CACHE.mkdir(
    parents=True,
    exist_ok=True,
)
os.environ.setdefault(
    "NUMBA_CACHE_DIR",
    str(NUMBA_CACHE),
)


from starter_kit.adapter import run, transpile
from starter_kit.backend.braket import run_braket
from starter_kit.emitters.braket import emit_braket
from starter_kit.parser import parse_qasm


ROOT = Path(__file__).resolve().parents[1]
CIRCUITS = ROOT / "starter_kit" / "circuits"


def read_circuit(name: str) -> str:
    return (
        CIRCUITS / name
    ).read_text(encoding="utf-8")


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


def test_parser_supports_all_twelve_gates():
    circuit = parse_qasm(ALL_GATES_QASM)

    gate_names = [
        gate.name
        for gate in circuit.gates
    ]

    assert gate_names == [
        "h",
        "x",
        "s",
        "sdg",
        "t",
        "tdg",
        "ry",
        "rz",
        "cx",
        "cu1",
        "swap",
        "ccx",
    ]

    assert circuit.gates[6].params == pytest.approx(
        [0.2]
    )
    assert circuit.gates[7].params == pytest.approx(
        [0.3]
    )
    assert circuit.gates[9].params == pytest.approx(
        [0.4]
    )


def test_formal_output_includes_stdlib():
    qasm3 = transpile(
        read_circuit("bell.qasm"),
        target="braket",
    )

    assert qasm3.startswith("OPENQASM 3.0;")
    assert 'include "stdgates.inc";' in qasm3


def test_local_output_excludes_stdlib():
    circuit = parse_qasm(
        read_circuit("bell.qasm")
    )

    qasm3 = emit_braket(
        circuit,
        include_stdlib=False,
    )

    assert qasm3.startswith("OPENQASM 3.0;")
    assert 'include "stdgates.inc";' not in qasm3


def test_emitter_maps_all_braket_gates():
    circuit = parse_qasm(ALL_GATES_QASM)

    qasm3 = emit_braket(
        circuit,
        include_stdlib=False,
    )

    expected_operations = [
        "h q[0];",
        "x q[1];",
        "s q[0];",
        "si q[0];",
        "t q[0];",
        "ti q[0];",
        "ry(0.2) q[0];",
        "rz(0.3) q[1];",
        "cnot q[0], q[1];",
        "cphaseshift(0.4) q[0], q[1];",
        "swap q[0], q[1];",
        "ccnot q[0], q[1], q[2];",
    ]

    for operation in expected_operations:
        assert operation in qasm3


def test_emitter_preserves_measurement_mapping():
    qasm2 = """
    OPENQASM 2.0;
    include "qelib1.inc";

    qreg q[2];
    creg c[2];

    measure q[1] -> c[0];
    measure q[0] -> c[1];
    """

    circuit = parse_qasm(qasm2)

    qasm3 = emit_braket(
        circuit,
        include_stdlib=False,
    )

    assert "c[0] = measure q[1];" in qasm3
    assert "c[1] = measure q[0];" in qasm3


def test_all_twelve_gates_execute_locally():
    circuit = parse_qasm(ALL_GATES_QASM)

    qasm3 = emit_braket(
        circuit,
        include_stdlib=False,
    )

    measurement_map = {
        measurement.qubit: measurement.bit
        for measurement in circuit.measurements
    }

    result = run_braket(
        qasm3,
        shots=128,
        measurement_map=measurement_map,
        num_bits=circuit.num_bits,
    )

    assert result["shots"] == 128
    assert sum(result["counts"].values()) == 128
    assert result["bit_order"] == "little"
    assert result["backend"] == (
        "braket_local_simulator"
    )


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
        target="braket",
        shots=512,
    )

    assert result["shots"] == 512
    assert sum(result["counts"].values()) == 512
    assert set(result["counts"]) <= allowed_states
    assert result["bit_order"] == "little"
    assert result["job_id"]
    assert result["timestamp"]


@pytest.mark.parametrize(
    "shots",
    [0, -1],
)
def test_rejects_invalid_shots(shots: int):
    with pytest.raises(
        ValueError,
        match="shots must be positive",
    ):
        run(
            read_circuit("bell.qasm"),
            target="braket",
            shots=shots,
        )


@pytest.mark.parametrize(
    ("body", "expected_counts"),
    [
        (
            """
            x q[0];
            measure q -> c;
            """,
            {"01": 32},
        ),
        (
            """
            x q[1];
            measure q -> c;
            """,
            {"10": 32},
        ),
        (
            """
            x q[1];
            measure q[1] -> c[0];
            measure q[0] -> c[1];
            """,
            {"01": 32},
        ),
        (
            """
            x q[1];
            measure q[1] -> c[1];
            """,
            {"10": 32},
        ),
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

    result = run(
        qasm2,
        target="braket",
        shots=32,
    )

    assert result["counts"] == expected_counts
    
    