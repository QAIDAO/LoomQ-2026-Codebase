"""Native SDK integration tests; skipped when optional SDKs are unavailable."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for path in (STARTER_KIT, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import adapter  # noqa: E402
from test_l1_property import (  # noqa: E402
    _all_gates_qasm,
    _fidelity,
    _reference_distribution,
)
from loomq.qasm import parse_openqasm2  # noqa: E402


SDK_MODULES = {"spinq": "spinqit", "originq": "pyqpanda", "braket": "braket"}
SURROGATE_CIRCUITS = STARTER_KIT / "circuits" / "l1_surrogate"


class L1NativeBackendTests(unittest.TestCase):
    def test_native_spinq_accepts_parameter_expression_boundaries(self) -> None:
        if importlib.util.find_spec(SDK_MODULES["spinq"]) is None:
            self.skipTest("spinqit is not installed")
        qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
rz(1e-9) q[0];
ry(-1e-9) q[1];
cu1((pi/2)+0.125) q[0], q[1];
rz(-2*pi) q[0];
measure q -> c;
"""
        expected = _reference_distribution(parse_openqasm2(qasm))
        payload = _run_native(qasm, "spinq", 8192)
        observed = {
            state: count / payload["shots"]
            for state, count in payload["counts"].items()
        }
        self.assertGreaterEqual(_fidelity(observed, expected), 0.97)
        self.assertEqual(payload.get("meta", {}).get("executor"), "spinqit.BasicSimulator")

    def test_native_spinq_sparse_partial_measurement_mapping(self) -> None:
        if importlib.util.find_spec(SDK_MODULES["spinq"]) is None:
            self.skipTest("spinqit is not installed")
        qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
x q[1];
measure q[1] -> c[2];
"""
        payload = _run_native(qasm, "spinq", 128)
        self.assertEqual(payload["counts"], {"100": 128})

    def test_native_named_hidden_family_surrogates(self) -> None:
        if not SURROGATE_CIRCUITS.is_dir():
            self.skipTest("local-only hidden surrogate corpus is not included")
        circuits = {
            path.stem: path.read_text(encoding="utf-8")
            for path in sorted(SURROGATE_CIRCUITS.glob("*.qasm"))
        }
        self.assertEqual(set(circuits), {"ghz5", "grover3", "qft4"})

        tested = 0
        for target in adapter.SUPPORTED_TARGETS:
            if importlib.util.find_spec(SDK_MODULES[target]) is None:
                continue
            tested += 1
            for name, qasm in circuits.items():
                with self.subTest(target=target, circuit=name):
                    expected = _reference_distribution(parse_openqasm2(qasm))
                    payload = _run_native(qasm, target, 8192)
                    observed = {
                        state: count / payload["shots"]
                        for state, count in payload["counts"].items()
                    }
                    self.assertGreaterEqual(_fidelity(observed, expected), 0.97)
                    self.assertNotEqual(
                        payload.get("meta", {}).get("executor"),
                        "loomq.reference_statevector",
                    )
        if tested == 0:
            self.skipTest("native SDKs are not installed")

    def test_native_bit_order_for_each_backend(self) -> None:
        tested = 0
        for target in adapter.SUPPORTED_TARGETS:
            if importlib.util.find_spec(SDK_MODULES[target]) is None:
                continue
            tested += 1
            with self.subTest(target=target):
                q0_result = _run_native(_basis_qasm(0), target, 128)
                q1_result = _run_native(_basis_qasm(1), target, 128)
                self.assertEqual(q0_result["counts"], {"01": 128})
                self.assertEqual(q1_result["counts"], {"10": 128})
                self.assertNotEqual(
                    q0_result.get("meta", {}).get("executor"),
                    "loomq.reference_statevector",
                )
        if tested == 0:
            self.skipTest("native SDKs are not installed")

    def test_native_backends_support_all_twelve_gates(self) -> None:
        qasm = _all_gates_qasm()
        expected = _reference_distribution(parse_openqasm2(qasm))
        tested = 0
        for target in adapter.SUPPORTED_TARGETS:
            if importlib.util.find_spec(SDK_MODULES[target]) is None:
                continue
            tested += 1
            with self.subTest(target=target):
                payload = _run_native(qasm, target, 8192)
                observed = {
                    state: count / payload["shots"]
                    for state, count in payload["counts"].items()
                }
                self.assertGreaterEqual(_fidelity(observed, expected), 0.97)
        if tested == 0:
            self.skipTest("native SDKs are not installed")

    def test_native_partial_measurement_mapping(self) -> None:
        qasm = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[3];
creg c[3];
x q[0];
measure q[0] -> c[2];
measure q[1] -> c[1];
measure q[2] -> c[0];
"""
        tested = 0
        for target in adapter.SUPPORTED_TARGETS:
            if importlib.util.find_spec(SDK_MODULES[target]) is None:
                continue
            tested += 1
            with self.subTest(target=target):
                payload = _run_native(qasm, target, 128)
                self.assertEqual(payload["counts"], {"100": 128})
        if tested == 0:
            self.skipTest("native SDKs are not installed")


def _run_native(qasm: str, target: str, shots: int) -> dict:
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LOOMQ_FORCE_REFERENCE_SIMULATOR", None)
        return adapter.run(qasm, target, shots)


def _basis_qasm(qubit: int) -> str:
    return f"""OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
x q[{qubit}];
measure q -> c;
"""


if __name__ == "__main__":
    unittest.main()
