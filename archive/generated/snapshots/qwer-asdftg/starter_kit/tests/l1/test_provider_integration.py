"""Real local-SDK coverage for the three LoomQ L1 provider runners.

These tests deliberately use the installed SDKs and local simulators.  They
skip as one module on a development interpreter without every SDK, while the
Python 3.10 Docker image is expected to provide all of them.
"""

from importlib import import_module
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from starter_kit import adapter
from starter_kit.evaluator import validate_schema
from starter_kit.loomq_l1.runners import run_spinq


ASYMMETRIC_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;
'''

SPINQ_NONIDENTITY_MEASUREMENT_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
x q[0];
measure q[0] -> c[2];
measure q[1] -> c[1];
measure q[2] -> c[0];
'''

SPINQ_NATIVE_REGRESSION_QASMS = {
    "whole-register": '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;
''',
    "ascii-spacing": '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q [ 0 ] -> c [ 1 ];
measure q [ 1 ] -> c [ 0 ];
''',
}

ALL_GATES_QASM = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[1];
s q[2];
sdg q[2];
t q[1];
tdg q[1];
rz(pi/5) q[0];
ry(-pi/7) q[2];
cx q[0],q[1];
cu1(pi/3) q[1],q[2];
swap q[0],q[2];
ccx q[0],q[1],q[2];
measure q -> c;
'''


def _single_gate_qasm(operation: str, qubits: int = 3) -> str:
    return f'''OPENQASM 2.0;
include "qelib1.inc";
qreg q[{qubits}];
creg c[{qubits}];
{operation}
measure q -> c;
'''


EXPECTED_ASYMMETRIC_RAW = {
    "spinq": ({"01": 128}, False),
    "originq": ({"01": 128}, False),
    "braket": ({"10": 128}, True),
}

BRAKET_MISSING_GATE_QASMS = {
    "sdg": _single_gate_qasm("sdg q[0];"),
    "tdg": _single_gate_qasm("tdg q[0];"),
    "cp": _single_gate_qasm("cu1(pi/3) q[0],q[1];"),
    "ccx": _single_gate_qasm("ccx q[0],q[1],q[2];"),
}

ORIGINQ_EXECUTION_COMPATIBILITY_QASMS = {
    "SDAG": _single_gate_qasm("sdg q[0];"),
    "TDAG": _single_gate_qasm("tdg q[0];"),
    "CU1": _single_gate_qasm("cu1(pi/3) q[0],q[1];"),
}

SDK_REQUIREMENTS = {
    "spinq": ("spinqit", "spinqit", "0.2.4"),
    "originq": ("pyqpanda", "pyqpanda", "3.8.5"),
    "braket": ("braket", "amazon-braket-sdk", "1.108.0"),
}


def _missing_sdk_modules() -> tuple[str, ...]:
    missing = []
    for module_name, _distribution, _expected_version in SDK_REQUIREMENTS.values():
        try:
            import_module(module_name)
        except Exception:
            missing.append(module_name)
    return tuple(missing)


MISSING_SDK_MODULES = _missing_sdk_modules()
IN_ISOLATED_DOCKER_RUNTIME = bool(os.environ.get("LOOMQ_BRAKET_PYTHON"))


@unittest.skipIf(
    not IN_ISOLATED_DOCKER_RUNTIME and MISSING_SDK_MODULES,
    "requires real local SDKs: " + ", ".join(MISSING_SDK_MODULES),
)
class ProviderIntegrationTests(unittest.TestCase):
    """Exercise the exact pins through the public adapter and native runners."""

    @unittest.skipUnless(
        IN_ISOLATED_DOCKER_RUNTIME,
        "requires the Docker isolated Braket runtime",
    )
    def test_braket_worker_runtime_is_configured(self):
        """The image exposes the exact SDK pins through two Python 3.10 runtimes."""
        worker = os.environ["LOOMQ_BRAKET_PYTHON"]
        self.assertTrue(Path(worker).is_file())
        self.assertEqual(sys.version_info[:2], (3, 10))

        for module_name, distribution, expected_version in (
            SDK_REQUIREMENTS["spinq"],
            SDK_REQUIREMENTS["originq"],
        ):
            with self.subTest(module=module_name):
                import_module(module_name)
                self.assertEqual(version(distribution), expected_version)

        completed = subprocess.run(
            [
                worker,
                "-c",
                (
                    "import braket, importlib.metadata as metadata, json, sys; "
                    "print(json.dumps({'python': list(sys.version_info[:2]), "
                    "'module': braket.__name__, "
                    "'version': metadata.version('amazon-braket-sdk')}))"
                ),
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        worker_runtime = json.loads(completed.stdout)
        self.assertEqual(worker_runtime["python"], [3, 10])
        self.assertEqual(worker_runtime["module"], "braket")
        self.assertEqual(worker_runtime["version"], "1.108.0")

    def _raw_execution(self, qasm: str, target: str, shots: int):
        native_ir = adapter.transpile(qasm, target)
        self.assertTrue(native_ir.strip(), f"{target} returned empty native IR")
        return adapter.RUNNERS[target](native_ir, shots)

    def _assert_sdk_metadata(self, target: str, metadata: dict[str, object]) -> None:
        _module_name, distribution, expected_version = SDK_REQUIREMENTS[target]
        if target != "braket" or not IN_ISOLATED_DOCKER_RUNTIME:
            self.assertEqual(version(distribution), expected_version)
        self.assertEqual(metadata["sdk"], distribution)
        self.assertEqual(metadata["sdk_version"], expected_version)

    def test_asymmetric_bit_order(self):
        """The canonical count key renders c[1]c[0], so x(q[0]) is ``01``."""
        for target in SDK_REQUIREMENTS:
            with self.subTest(target=target):
                result = adapter.run(ASYMMETRIC_QASM, target, shots=128)
                self.assertEqual(result["counts"], {"01": 128})
                self.assertEqual(sum(result["counts"].values()), 128)

                raw = self._raw_execution(ASYMMETRIC_QASM, target, shots=128)
                expected_counts, expected_reverse_bits = EXPECTED_ASYMMETRIC_RAW[target]
                self.assertEqual(dict(raw.counts), expected_counts)
                self.assertIs(raw.reverse_bits, expected_reverse_bits)
                self.assertEqual(sum(raw.counts.values()), 128)
                self._assert_sdk_metadata(target, raw.metadata)

    def test_spinq_nonidentity_measurement_map_preserves_classical_positions(self):
        """SpinQ raw qubit order is remapped before LoomQ normalization."""
        result = adapter.run(SPINQ_NONIDENTITY_MEASUREMENT_QASM, "spinq", shots=128)
        self.assertEqual(result["counts"], {"100": 128})
        self.assertEqual(sum(result["counts"].values()), 128)

        raw = self._raw_execution(SPINQ_NONIDENTITY_MEASUREMENT_QASM, "spinq", shots=128)
        self.assertEqual(dict(raw.counts), {"100": 128})
        self.assertIs(raw.reverse_bits, False)
        self.assertEqual(sum(raw.counts.values()), 128)
        self._assert_sdk_metadata("spinq", raw.metadata)

    def test_spinq_runner_accepts_parser_valid_native_measurement_forms(self):
        expected_counts = {
            "whole-register": {"01": 128},
            "ascii-spacing": {"10": 128},
        }
        for form, native_ir in SPINQ_NATIVE_REGRESSION_QASMS.items():
            with self.subTest(form=form):
                raw = run_spinq(native_ir, 128)
                self.assertEqual(dict(raw.counts), expected_counts[form])
                self.assertIs(raw.reverse_bits, False)
                self.assertEqual(sum(raw.counts.values()), 128)
                self._assert_sdk_metadata("spinq", raw.metadata)

    def test_braket_missing_standard_gates_execute_individually(self):
        """Pinned Braket needs execution-only definitions for these four gates."""
        for gate, qasm in BRAKET_MISSING_GATE_QASMS.items():
            with self.subTest(gate=gate):
                native_ir = adapter.transpile(qasm, "braket")
                self.assertIn('include "stdgates.inc";', native_ir)

                raw = self._raw_execution(qasm, "braket", shots=32)
                self.assertEqual(sum(raw.counts.values()), 32)
                self.assertIs(raw.reverse_bits, True)
                self._assert_sdk_metadata("braket", raw.metadata)

                result = adapter.run(qasm, "braket", shots=32)
                self.assertEqual(validate_schema(result), (True, "schema valid"))
                self.assertEqual(sum(result["counts"].values()), 32)

    def test_originq_execution_compatibility_gates_keep_target_ir_unchanged(self):
        """Pinned pyQPanda needs DAGGER blocks and CR only in its execution copy."""
        for target_gate, qasm in ORIGINQ_EXECUTION_COMPATIBILITY_QASMS.items():
            with self.subTest(target_gate=target_gate):
                native_ir = adapter.transpile(qasm, "originq")
                self.assertIn(target_gate, native_ir)

                raw = self._raw_execution(qasm, "originq", shots=32)
                self.assertEqual(sum(raw.counts.values()), 32)
                self.assertIs(raw.reverse_bits, False)
                self._assert_sdk_metadata("originq", raw.metadata)

                result = adapter.run(qasm, "originq", shots=32)
                self.assertEqual(validate_schema(result), (True, "schema valid"))
                self.assertEqual(sum(result["counts"].values()), 32)

    def test_all_gates_transpile_run_and_validate_schema(self):
        """Every L1 gate parses, emits, and executes on every local backend."""
        for target in SDK_REQUIREMENTS:
            with self.subTest(target=target):
                native_ir = adapter.transpile(ALL_GATES_QASM, target)
                self.assertTrue(native_ir.strip())

                result = adapter.run(ALL_GATES_QASM, target, shots=256)
                self.assertEqual(validate_schema(result), (True, "schema valid"))
                self.assertEqual(sum(result["counts"].values()), 256)
                self._assert_sdk_metadata(target, result["meta"])


if __name__ == "__main__":
    unittest.main()
