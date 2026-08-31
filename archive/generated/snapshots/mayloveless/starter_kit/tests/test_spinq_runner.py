"""SpinQ Runner 的 native gate、位序、SDK 边界和集成测试。"""

import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema
from loomq.ir import Circuit, GateOperation, QubitRef
from loomq.parser import parse_qasm
from loomq.runners.spinq import (
    SpinQSDK,
    _build_spinq_circuit,
    _find_spinq_python,
    _load_spinq_sdk,
    _worker_environment,
    normalize_spinq_counts,
    run_spinq,
    run_spinq_native,
)


STARTER_KIT = Path(__file__).resolve().parents[1]
SPINQ_WORKER_CONFIGURED = bool(os.environ.get("LOOMQ_SPINQ_PYTHON"))


def qasm(body: str, qreg: str = "qreg q[2];", creg: str = "creg c[2];") -> str:
    return 'OPENQASM 2.0; include "qelib1.inc"; %s %s %s' % (
        qreg,
        creg,
        body,
    )


class FakeNativeCircuit:
    def __init__(self) -> None:
        self.operations = []
        self.qubits = []

    def allocateQubits(self, count):  # type: ignore[no-untyped-def]
        self.qubits = ["q%d" % index for index in range(count)]
        return self.qubits

    def __lshift__(self, operation):  # type: ignore[no-untyped-def]
        self.operations.append(operation)
        return self


def fake_sdk() -> SpinQSDK:
    return SpinQSDK(
        config_class=mock.Mock,
        circuit_class=FakeNativeCircuit,
        gates={
            "h": "H",
            "x": "X",
            "s": "S",
            "sdg": "Sd",
            "t": "T",
            "tdg": "Td",
            "ry": "Ry",
            "rz": "Rz",
            "cx": "CX",
            "cu1": "CP",
            "swap": "SWAP",
            "ccx": "CCX",
        },
        simulator_factory=mock.Mock,
        compiler_factory=mock.Mock,
    )


class SpinQNormalizationTests(unittest.TestCase):
    def test_standard_mapping_reorders_raw_key(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        counts = normalize_spinq_counts(circuit, [0, 1], {"10": 3}, 3)

        self.assertEqual({"01": 3}, counts)

    def test_crossed_mapping_uses_classical_targets(self) -> None:
        circuit = parse_qasm(
            qasm("measure q[0] -> c[1]; measure q[1] -> c[0];")
        )

        counts = normalize_spinq_counts(circuit, [0, 1], {"10": 2}, 2)

        self.assertEqual({"10": 2}, counts)

    def test_unmeasured_classical_bits_default_to_zero(self) -> None:
        circuit = parse_qasm(qasm("measure q[1] -> c[0];"))

        counts = normalize_spinq_counts(circuit, [1], {"1": 1}, 1)

        self.assertEqual({"01": 1}, counts)

    def test_invalid_raw_key_width_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        with self.assertRaisesRegex(ValueError, "width"):
            normalize_spinq_counts(circuit, [0, 1], {"1": 1}, 1)

    def test_non_binary_key_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        with self.assertRaisesRegex(ValueError, "binary"):
            normalize_spinq_counts(circuit, [0, 1], {"20": 1}, 1)

    def test_invalid_count_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        with self.assertRaisesRegex(ValueError, "non-negative integers"):
            normalize_spinq_counts(circuit, [0, 1], {"00": True}, 1)

    def test_counts_total_must_match_shots(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        with self.assertRaisesRegex(ValueError, "total must equal shots"):
            normalize_spinq_counts(circuit, [0, 1], {"00": 1}, 2)


class SpinQNativeCircuitTests(unittest.TestCase):
    def test_h_and_cx_are_mapped_to_native_gates(self) -> None:
        circuit = parse_qasm(
            qasm("h q[0]; cx q[0], q[1]; measure q -> c;")
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual([("H", "q0"), ("CX", ("q0", "q1"))], native.operations)

    def test_multiple_quantum_registers_use_global_order(self) -> None:
        circuit = parse_qasm(
            qasm(
                "h right[0]; cx left[1], right[0]; measure right[0] -> c[0];",
                qreg="qreg left[2]; qreg right[1];",
            )
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual([("H", "q2"), ("CX", ("q1", "q2"))], native.operations)

    def test_all_unparameterized_single_qubit_gates_use_scalar_operand(self) -> None:
        circuit = parse_qasm(
            qasm(
                "h q[0]; x q[0]; s q[0]; sdg q[0]; "
                "t q[0]; tdg q[0]; measure q[0] -> c[0];"
            )
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual(
            [
                ("H", "q0"),
                ("X", "q0"),
                ("S", "q0"),
                ("Sd", "q0"),
                ("T", "q0"),
                ("Td", "q0"),
            ],
            native.operations,
        )

    def test_parameterized_single_qubit_gates_pass_float_after_operand(self) -> None:
        circuit = parse_qasm(
            qasm("ry(pi/2) q[0]; rz(-pi/4) q[1]; measure q -> c;")
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual("Ry", native.operations[0][0])
        self.assertEqual("q0", native.operations[0][1])
        self.assertAlmostEqual(1.5707963267948966, native.operations[0][2])
        self.assertEqual("Rz", native.operations[1][0])
        self.assertEqual("q1", native.operations[1][1])
        self.assertAlmostEqual(-0.7853981633974483, native.operations[1][2])

    def test_two_qubit_gates_preserve_control_target_order(self) -> None:
        circuit = parse_qasm(
            qasm("cx q[1], q[0]; swap q[0], q[1]; measure q -> c;")
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual(
            [("CX", ("q1", "q0")), ("SWAP", ("q0", "q1"))],
            native.operations,
        )

    def test_cu1_maps_to_cp_with_operands_then_parameter(self) -> None:
        circuit = parse_qasm(qasm("cu1(pi/2) q[1], q[0]; measure q -> c;"))

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual("CP", native.operations[0][0])
        self.assertEqual(("q1", "q0"), native.operations[0][1])
        self.assertAlmostEqual(1.5707963267948966, native.operations[0][2])

    def test_ccx_uses_official_decomposition_in_exact_order(self) -> None:
        circuit = parse_qasm(
            qasm(
                "ccx q[2], q[0], q[1]; measure q -> c;",
                qreg="qreg q[3];",
                creg="creg c[3];",
            )
        )

        native = _build_spinq_circuit(circuit, fake_sdk())

        self.assertEqual(
            [
                ("H", "q1"),
                ("CX", ("q0", "q1")),
                ("Td", "q1"),
                ("CX", ("q2", "q1")),
                ("T", "q1"),
                ("CX", ("q0", "q1")),
                ("Td", "q1"),
                ("CX", ("q2", "q1")),
                ("T", "q0"),
                ("T", "q1"),
                ("H", "q1"),
                ("CX", ("q2", "q0")),
                ("T", "q2"),
                ("Td", "q0"),
                ("CX", ("q2", "q0")),
            ],
            native.operations,
        )

    def test_unsupported_gate_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))
        unsupported = replace(
            circuit,
            operations=(GateOperation("unknown", (QubitRef("q", 0),)),)
            + circuit.operations,
        )

        with self.assertRaisesRegex(ValueError, "does not support gate 'unknown'"):
            _build_spinq_circuit(unsupported, fake_sdk())

    def test_missing_sdk_gate_has_clear_error(self) -> None:
        circuit = parse_qasm(qasm("x q[0]; measure q -> c;"))
        sdk = fake_sdk()._replace(
            gates={name: gate for name, gate in fake_sdk().gates.items() if name != "x"}
        )

        with self.assertRaisesRegex(RuntimeError, "missing required gate 'x'"):
            _build_spinq_circuit(circuit, sdk)

    def test_invalid_ir_gate_shape_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))
        invalid = replace(
            circuit,
            operations=(GateOperation("ry", (QubitRef("q", 0),)),)
            + circuit.operations,
        )

        with self.assertRaisesRegex(ValueError, "expects 1 parameter"):
            _build_spinq_circuit(invalid, fake_sdk())


class SpinQRunnerTests(unittest.TestCase):
    def test_runner_configures_sdk_and_creates_schema(self) -> None:
        circuit = parse_qasm(
            qasm("h q[0]; cx q[0], q[1]; measure q -> c;")
        )

        class FakeConfig:
            last = None

            def __init__(self) -> None:
                self.shots = None
                self.measured_qubits = None
                FakeConfig.last = self

            def configure_shots(self, shots):  # type: ignore[no-untyped-def]
                self.shots = shots

            def configure_measure_qubits(self, qubits):  # type: ignore[no-untyped-def]
                self.measured_qubits = qubits

        compiler = mock.Mock()
        compiler.compile.return_value = "executable"
        simulator = mock.Mock()
        simulator.execute.return_value = SimpleNamespace(counts={"00": 1, "11": 1})
        sdk = SpinQSDK(
            config_class=FakeConfig,
            circuit_class=FakeNativeCircuit,
            gates=fake_sdk().gates,
            simulator_factory=mock.Mock(return_value=simulator),
            compiler_factory=mock.Mock(return_value=compiler),
        )

        with mock.patch("loomq.runners.spinq._load_spinq_sdk", return_value=sdk):
            result = run_spinq_native(circuit, 2)

        self.assertEqual("spinq_basic_simulator", result["backend"])
        self.assertEqual({"00": 1, "11": 1}, result["counts"])
        self.assertTrue(result["job_id"].startswith("spinq-local-"))
        sdk.compiler_factory.assert_called_once_with("native")
        compiler.compile.assert_called_once_with(mock.ANY, 0)
        self.assertEqual(2, FakeConfig.last.shots)
        self.assertEqual([0, 1], FakeConfig.last.measured_qubits)
        simulator.execute.assert_called_once_with("executable", FakeConfig.last)

    def test_no_measurement_is_rejected_before_sdk_load(self) -> None:
        circuit = parse_qasm(qasm("h q[0];"))

        with self.assertRaisesRegex(ValueError, "at least one measurement"):
            run_spinq_native(circuit, 1)

    def test_mid_circuit_measurement_is_rejected(self) -> None:
        circuit = parse_qasm(qasm("measure q[0] -> c[0]; h q[1];"))

        with self.assertRaisesRegex(ValueError, "final measurements only"):
            run_spinq_native(circuit, 1)

    def test_missing_sdk_has_clear_message(self) -> None:
        with mock.patch(
            "loomq.runners.spinq.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'spinqit'"),
        ):
            with self.assertRaisesRegex(RuntimeError, "requirements-spinq.txt"):
                _load_spinq_sdk()

    def test_missing_required_sdk_gate_names_qasm_gate(self) -> None:
        exports = {
            "H": object(),
            "X": object(),
            "S": object(),
            "Sd": object(),
            "T": object(),
            "Td": object(),
            "Ry": object(),
            "Rz": object(),
            "CX": object(),
            "SWAP": object(),
            "CCX": object(),
        }
        incomplete_sdk = SimpleNamespace(**exports)

        with mock.patch(
            "loomq.runners.spinq.importlib.import_module",
            return_value=incomplete_sdk,
        ):
            with self.assertRaisesRegex(RuntimeError, "required gate.*cu1"):
                _load_spinq_sdk()


class SpinQWorkerClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.circuit = parse_qasm(qasm("measure q -> c;"))
        self.result = {
            "backend": "spinq_basic_simulator",
            "job_id": "spinq-local-test",
            "shots": 2,
            "counts": {"00": 2},
            "bit_order": "little",
            "timestamp": "2026-08-02T00:00:00Z",
            "meta": {"simulator": "basic"},
        }

    def test_run_spinq_uses_worker_without_loading_sdk(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(self.result), stderr=""
        )
        with mock.patch(
            "loomq.runners.spinq._find_spinq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.spinq._worker_environment", return_value={}
        ), mock.patch(
            "loomq.runners.spinq.subprocess.run", return_value=completed
        ) as process, mock.patch(
            "loomq.runners.spinq._load_spinq_sdk"
        ) as sdk_loader:
            result = run_spinq(self.circuit, 2)

        self.assertEqual(self.result, result)
        sdk_loader.assert_not_called()
        command = process.call_args.args[0]
        self.assertEqual(
            ["/isolated/bin/python", "-m", "loomq.workers.spinq_worker"],
            command,
        )
        request = json.loads(process.call_args.kwargs["input"])
        self.assertEqual(2, request["shots"])
        self.assertIn("OPENQASM 2.0;", request["qasm"])
        self.assertEqual("utf-8", process.call_args.kwargs["encoding"])
        self.assertFalse(process.call_args.kwargs["check"])

    def test_configured_python_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            python_path = Path(directory) / "custom-python"
            python_path.touch()
            with mock.patch.dict(
                os.environ, {"LOOMQ_SPINQ_PYTHON": str(python_path)}
            ):
                self.assertEqual(python_path, _find_spinq_python())

    def test_worker_nonzero_exit_is_reported(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=3, stdout="", stderr="native failure"
        )
        with mock.patch(
            "loomq.runners.spinq._find_spinq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.spinq._worker_environment", return_value={}
        ), mock.patch(
            "loomq.runners.spinq.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(RuntimeError, "exit code 3: native failure"):
                run_spinq(self.circuit, 2)

    def test_invalid_worker_json_is_reported(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not-json", stderr=""
        )
        with mock.patch(
            "loomq.runners.spinq._find_spinq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.spinq._worker_environment", return_value={}
        ), mock.patch(
            "loomq.runners.spinq.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                run_spinq(self.circuit, 2)

    def test_non_object_worker_json_is_reported(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="[]", stderr=""
        )
        with mock.patch(
            "loomq.runners.spinq._find_spinq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.spinq._worker_environment", return_value={}
        ), mock.patch(
            "loomq.runners.spinq.subprocess.run", return_value=completed
        ):
            with self.assertRaisesRegex(RuntimeError, "JSON object"):
                run_spinq(self.circuit, 2)

    def test_worker_timeout_is_reported(self) -> None:
        with mock.patch(
            "loomq.runners.spinq._find_spinq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.spinq._worker_environment", return_value={}
        ), mock.patch(
            "loomq.runners.spinq.subprocess.run",
            side_effect=subprocess.TimeoutExpired("worker", 120),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 120 seconds"):
                run_spinq(self.circuit, 2)

    def test_macos_worker_environment_preserves_dyld_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            virtualenv = Path(directory) / ".venv-spinq"
            python_path = virtualenv / "bin" / "python"
            package_path = (
                virtualenv / "lib" / "python3.10" / "site-packages" / "spinqit"
            )
            python_path.parent.mkdir(parents=True)
            package_path.mkdir(parents=True)
            python_path.touch()

            with mock.patch("loomq.runners.spinq.sys.platform", "darwin"), mock.patch.dict(
                os.environ, {"DYLD_LIBRARY_PATH": "/existing"}, clear=False
            ):
                environment = _worker_environment(python_path)

        self.assertEqual(
            str(package_path) + os.pathsep + "/existing",
            environment["DYLD_LIBRARY_PATH"],
        )


class AdapterSpinQTests(unittest.TestCase):
    def test_adapter_routes_parsed_circuit_to_spinq(self) -> None:
        source = qasm("measure q -> c;")
        expected = {"backend": "sentinel"}

        with mock.patch("adapter.run_spinq", return_value=expected) as runner:
            result = adapter.run(source, "spinq", 32)

        self.assertIs(expected, result)
        circuit, shots = runner.call_args.args
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(32, shots)


@unittest.skipUnless(
    SPINQ_WORKER_CONFIGURED, "LOOMQ_SPINQ_PYTHON is not configured"
)
class SpinQIntegrationTests(unittest.TestCase):
    def run_public_circuit(self, name: str, expected: dict) -> None:
        source = (STARTER_KIT / "circuits" / name).read_text(encoding="utf-8")
        result = adapter.run(source, "spinq", 512)
        valid, reason = validate_schema(result)

        self.assertTrue(valid, reason)
        self.assertEqual(512, sum(result["counts"].values()))
        self.assertTrue(set(result["counts"]).issubset(expected))
        observed = {
            key: value / result["shots"] for key, value in result["counts"].items()
        }
        self.assertGreaterEqual(calculate_hellinger_fidelity(observed, expected), 0.97)

    def test_bell_basic_simulator(self) -> None:
        self.run_public_circuit("bell.qasm", {"00": 0.5, "11": 0.5})

    def test_ghz3_basic_simulator(self) -> None:
        self.run_public_circuit("ghz3.qasm", {"000": 0.5, "111": 0.5})


if __name__ == "__main__":
    unittest.main()
