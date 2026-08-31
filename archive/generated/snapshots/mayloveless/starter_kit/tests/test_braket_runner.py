"""Braket Runner 的映射、SDK 边界和 Adapter 路由测试。"""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema
from loomq.ir import Circuit
from loomq.parser import parse_qasm
from loomq.runners.braket import (
    _load_braket_sdk,
    normalize_braket_measurements,
    run_braket,
)


STARTER_KIT = Path(__file__).resolve().parents[1]
BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None


def qasm(body: str, qreg: str = "qreg q[2];", creg: str = "creg c[2];") -> str:
    return 'OPENQASM 2.0; include "qelib1.inc"; %s %s %s' % (
        qreg,
        creg,
        body,
    )


class BraketNormalizationTests(unittest.TestCase):
    def test_standard_measurement_bit_order(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        counts = normalize_braket_measurements(circuit, [0, 1], [[1, 0]])

        self.assertEqual({"01": 1}, counts)

    def test_crossed_measurement_mapping(self) -> None:
        circuit = parse_qasm(
            qasm("measure q[0] -> c[1]; measure q[1] -> c[0];")
        )

        counts = normalize_braket_measurements(circuit, [0, 1], [[1, 0]])

        self.assertEqual({"10": 1}, counts)

    def test_register_measurement_expands_by_index(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))

        counts = normalize_braket_measurements(
            circuit, [1, 0], [[1, 0], [0, 1]]
        )

        self.assertEqual({"10": 1, "01": 1}, counts)

    def test_multiple_registers_use_declaration_order_for_global_indices(self) -> None:
        circuit = parse_qasm(
            qasm(
                "measure right[0] -> high[0]; measure left[1] -> low[0];",
                qreg="qreg left[2]; qreg right[1];",
                creg="creg low[1]; creg high[1];",
            )
        )

        counts = normalize_braket_measurements(circuit, [1, 2], [[0, 1]])

        self.assertEqual({"10": 1}, counts)

    def test_unmeasured_classical_bits_default_to_zero(self) -> None:
        circuit = parse_qasm(qasm("measure q[0] -> c[0];"))

        counts = normalize_braket_measurements(circuit, [0], [[1]])

        self.assertEqual({"01": 1}, counts)

    def test_duplicate_classical_write_is_rejected(self) -> None:
        circuit = parse_qasm(
            qasm("measure q[0] -> c[0]; measure q[1] -> c[0];")
        )

        with self.assertRaisesRegex(ValueError, "more than one measurement"):
            normalize_braket_measurements(circuit, [0, 1], [[0, 1]])


class BraketRunnerTests(unittest.TestCase):
    def test_runner_uses_task_id_and_builds_schema(self) -> None:
        circuit = parse_qasm(qasm("measure q -> c;"))
        raw_result = SimpleNamespace(
            measured_qubits=[0, 1], measurements=[[0, 0], [1, 1]]
        )

        class FakeTask:
            id = "local-task-123"

            def result(self):  # type: ignore[no-untyped-def]
                return raw_result

        device = mock.Mock()
        device.run.return_value = FakeTask()
        LocalSimulator = mock.Mock(return_value=device)
        Program = mock.Mock()

        with mock.patch(
            "loomq.runners.braket._load_braket_sdk",
            return_value=(LocalSimulator, Program),
        ):
            result = run_braket(circuit, 2)

        self.assertEqual("local-task-123", result["job_id"])
        self.assertEqual("braket_local_simulator", result["backend"])
        self.assertEqual({"00": 1, "11": 1}, result["counts"])
        LocalSimulator.assert_called_once_with("braket_sv")
        self.assertIn("OPENQASM 3.0;", Program.call_args.kwargs["source"])
        self.assertNotIn('include "stdgates.inc";', Program.call_args.kwargs["source"])
        device.run.assert_called_once_with(Program.return_value, shots=2)

    def test_missing_sdk_has_clear_message(self) -> None:
        with mock.patch(
            "loomq.runners.braket.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'braket'"),
        ):
            with self.assertRaisesRegex(RuntimeError, "install starter-kit/requirements.txt"):
                _load_braket_sdk()


class AdapterRunTests(unittest.TestCase):
    def test_adapter_routes_parsed_circuit_to_braket(self) -> None:
        source = qasm("measure q -> c;")
        expected = {"backend": "sentinel"}

        with mock.patch("adapter.run_braket", return_value=expected) as runner:
            result = adapter.run(source, "braket", 32)

        self.assertIs(expected, result)
        circuit, shots = runner.call_args.args
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(32, shots)

    def test_adapter_routes_parsed_circuit_to_originq(self) -> None:
        source = qasm("measure q -> c;")
        expected = {"backend": "sentinel"}

        with mock.patch("adapter.run_originq", return_value=expected) as runner:
            result = adapter.run(source, "originq", 32)

        self.assertIs(expected, result)
        circuit, shots = runner.call_args.args
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(32, shots)

    def test_unknown_run_target_is_rejected_before_parsing(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported run target"):
            adapter.run("not parsed", "unknown", 1)


@unittest.skipUnless(BRAKET_INSTALLED, "amazon-braket-sdk is not installed")
class BraketIntegrationTests(unittest.TestCase):
    def run_public_circuit(self, name: str, expected: dict) -> None:
        source = (STARTER_KIT / "circuits" / name).read_text(encoding="utf-8")
        # 真实采样使用较高 shots，避免 0.97 保真度断言受随机波动影响。
        result = adapter.run(source, "braket", 4096)
        valid, reason = validate_schema(result)

        self.assertTrue(valid, reason)
        self.assertEqual(4096, sum(result["counts"].values()))
        self.assertTrue(set(result["counts"]).issubset(expected))
        observed = {
            key: value / result["shots"] for key, value in result["counts"].items()
        }
        self.assertGreaterEqual(calculate_hellinger_fidelity(observed, expected), 0.97)

    def test_bell_local_simulator(self) -> None:
        self.run_public_circuit("bell.qasm", {"00": 0.5, "11": 0.5})

    def test_ghz3_local_simulator(self) -> None:
        self.run_public_circuit("ghz3.qasm", {"000": 0.5, "111": 0.5})


if __name__ == "__main__":
    unittest.main()
