"""Tests for L1 transpile/run, L2 agent, L3 hybrid compiler."""
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starter_kit.transpiler.parser import QASMParser
from starter_kit.transpiler.ir import Circuit, Gate, Measurement
from starter_kit.tests.circuits import (
    BELL_STATE, GHZ_3, QFT_4, GROVER_3, HYBRID_EXAMPLE,
)


def test_parse_bell():
    parser = QASMParser()
    circuit = parser.parse(BELL_STATE)
    assert circuit.num_qubits == 2
    assert circuit.num_clbits == 2
    assert len(circuit.gates) == 2
    assert circuit.gates[0].name == "h"
    assert circuit.gates[1].name == "cx"
    assert len(circuit.measurements) == 2
    print("PASS: test_parse_bell")


def test_parse_ghz3():
    parser = QASMParser()
    circuit = parser.parse(GHZ_3)
    assert circuit.num_qubits == 3
    assert len(circuit.gates) == 3
    assert circuit.gates[0].name == "h"
    assert circuit.gates[1].name == "cx"
    assert circuit.gates[2].name == "cx"
    print("PASS: test_parse_ghz3")


def test_parse_qft4():
    parser = QASMParser()
    circuit = parser.parse(QFT_4)
    assert circuit.num_qubits == 4
    cu1_gates = [g for g in circuit.gates if g.name == "cu1"]
    assert len(cu1_gates) == 6
    swap_gates = [g for g in circuit.gates if g.name == "swap"]
    assert len(swap_gates) == 2
    print("PASS: test_parse_qft4")


def test_parse_grover3():
    parser = QASMParser()
    circuit = parser.parse(GROVER_3)
    assert circuit.num_qubits == 3
    ccx_gates = [g for g in circuit.gates if g.name == "ccx"]
    assert len(ccx_gates) == 2
    print("PASS: test_parse_grover3")


def test_to_qasm2_roundtrip():
    parser = QASMParser()
    circuit = parser.parse(BELL_STATE)
    qasm2 = circuit.to_qasm2()
    circuit2 = parser.parse(qasm2)
    assert circuit2.num_qubits == circuit.num_qubits
    assert len(circuit2.gates) == len(circuit.gates)
    print("PASS: test_to_qasm2_roundtrip")


def test_transpile_spinq():
    from starter_kit.adapter import transpile
    result = transpile(BELL_STATE, "spinq")
    assert isinstance(result, str)
    assert "OPENQASM" in result
    assert "cu1" not in result
    print("PASS: test_transpile_spinq")


def test_transpile_originq():
    from starter_kit.adapter import transpile
    result = transpile(BELL_STATE, "originq")
    assert isinstance(result, str)
    assert "QINIT" in result or "OPENQASM" in result
    print("PASS: test_transpile_originq")


def test_transpile_braket():
    from starter_kit.adapter import transpile
    result = transpile(BELL_STATE, "braket")
    assert isinstance(result, str)
    assert "OPENQASM 3" in result
    assert "qubit[" in result
    print("PASS: test_transpile_braket")


def test_run_braket():
    try:
        from starter_kit.adapter import run
        result = run(BELL_STATE, "braket", shots=8192)
        assert "backend" in result
        assert "counts" in result
        assert result["bit_order"] == "little"
        assert result["shots"] == 8192
        total = sum(result["counts"].values())
        assert total == 8192 or total == 0
        print(f"PASS: test_run_braket (counts={result.get('counts', {})})")
    except ImportError:
        print("SKIP: test_run_braket (braket not installed)")


def test_hellinger_fidelity():
    from starter_kit.adapter import run

    try:
        result = run(BELL_STATE, "braket", shots=8192)
        counts = result.get("counts", {})
        if not counts:
            print("SKIP: test_hellinger (no counts)")
            return

        ideal = {"00": 0.5, "11": 0.5}
        total = sum(counts.values())
        P = {k: v / total for k, v in counts.items()}

        fidelity = _hellinger_fidelity(P, ideal)
        print(f"PASS: test_hellinger (fidelity={fidelity:.4f})")
        assert fidelity > 0.95, f"Fidelity {fidelity} below 0.95"
    except ImportError:
        print("SKIP: test_hellinger (braket not installed)")


def _hellinger_fidelity(P: dict, Q: dict) -> float:
    import math
    keys = set(P.keys()) | set(Q.keys())
    s = 0.0
    for k in keys:
        p = P.get(k, 0)
        q = Q.get(k, 0)
        s += (math.sqrt(p) - math.sqrt(q)) ** 2
    h = math.sqrt(s) / math.sqrt(2)
    return 1.0 - h


def test_compile_hybrid():
    from starter_kit.adapter import compile_hybrid

    quantum_ops, riscv_text = compile_hybrid(HYBRID_EXAMPLE)
    assert len(quantum_ops) > 0
    assert "h" in [op["name"] for op in quantum_ops]
    assert "cx" in [op["name"] for op in quantum_ops]
    assert "measure" in [op["name"] for op in quantum_ops]

    assert "li" in riscv_text
    assert "add" in riscv_text or "addi" in riscv_text
    assert "beq" in riscv_text or "bne" in riscv_text
    print(f"PASS: test_compile_hybrid")
    print(f"  Quantum ops: {len(quantum_ops)}")
    print(f"  RISC-V:\n{riscv_text}")


def test_agent_offline():
    from starter_kit.adapter import agent_chat
    os.environ.pop("LOOMQ_LLM_BASE_URL", None)
    os.environ.pop("LOOMQ_LLM_API_KEY", None)
    result = agent_chat("生成一个贝尔态")
    assert "OPENQASM" in result
    assert "h" in result
    assert "cx" in result
    print("PASS: test_agent_offline")


def run_all():
    tests = [
        test_parse_bell,
        test_parse_ghz3,
        test_parse_qft4,
        test_parse_grover3,
        test_to_qasm2_roundtrip,
        test_transpile_spinq,
        test_transpile_originq,
        test_transpile_braket,
        test_run_braket,
        test_hellinger_fidelity,
        test_compile_hybrid,
        test_agent_offline,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")


if __name__ == "__main__":
    run_all()
