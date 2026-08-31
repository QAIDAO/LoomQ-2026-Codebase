"""OriginQ Runner 的位序、隔离进程和真实组合电路测试。"""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import adapter
from evaluator import calculate_hellinger_fidelity, validate_schema
from loomq.parser import parse_qasm
from loomq.runners.originq import (
    _find_originq_python,
    normalize_originq_counts,
    run_originq,
)
from tests.test_l1_hidden_like import (
    DETERMINISTIC_SHOTS,
    SHOTS,
    basis_preparation,
    build_qasm,
    grover_3_operations,
    inverse_operations,
    qft_operations,
    random_identity_case,
)


STARTER_KIT = Path(__file__).resolve().parents[1]
ORIGINQ_CONFIGURED = bool(os.environ.get("LOOMQ_ORIGINQ_PYTHON"))
SPINQ_CONFIGURED = bool(os.environ.get("LOOMQ_SPINQ_PYTHON"))
BRAKET_INSTALLED = importlib.util.find_spec("braket") is not None


def qasm(body: str, qreg: str = "qreg q[2];", creg: str = "creg c[2];") -> str:
    return 'OPENQASM 2.0; include "qelib1.inc"; %s %s %s' % (
        qreg,
        creg,
        body,
    )


class OriginQNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.circuit = parse_qasm(qasm("measure q -> c;"))

    def test_raw_key_is_already_full_little_endian_classical_key(self) -> None:
        crossed = parse_qasm(
            qasm("measure q[0] -> c[1]; measure q[1] -> c[0];")
        )
        self.assertEqual(
            {"10": 4}, normalize_originq_counts(crossed, {"10": 4}, 4)
        )

    def test_key_width_includes_unmeasured_classical_bits(self) -> None:
        circuit = parse_qasm(qasm("measure q[1] -> c[0];"))
        self.assertEqual(
            {"01": 2}, normalize_originq_counts(circuit, {"01": 2}, 2)
        )

    def test_invalid_key_count_and_total_are_rejected(self) -> None:
        cases = (
            ({"2x": 1}, 1, "binary"),
            ({"0": 1}, 1, "width"),
            ({"00": True}, 1, "non-negative"),
            ({"00": 1}, 2, "total"),
        )
        for counts, shots, message in cases:
            with self.subTest(counts=counts):
                with self.assertRaisesRegex(ValueError, message):
                    normalize_originq_counts(self.circuit, counts, shots)


class OriginQWorkerClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.circuit = parse_qasm(qasm("measure q -> c;"))

    def run_with_completed(self, completed):  # type: ignore[no-untyped-def]
        with mock.patch(
            "loomq.runners.originq._find_originq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.originq.subprocess.run", return_value=completed
        ) as process:
            result = run_originq(self.circuit, 2)
        return result, process

    def test_run_uses_execution_originir_and_creates_schema(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"counts":{"00":2}}', stderr=""
        )
        result, process = self.run_with_completed(completed)

        self.assertEqual("originq_cpuqvm", result["backend"])
        self.assertEqual({"00": 2}, result["counts"])
        self.assertTrue(result["job_id"].startswith("originq-local-"))
        self.assertEqual({"simulator": "CPUQVM", "sdk": "pyqpanda"}, result["meta"])
        self.assertEqual(
            ["/isolated/bin/python", "-m", "loomq.workers.originq_worker"],
            process.call_args.args[0],
        )
        request = json.loads(process.call_args.kwargs["input"])
        self.assertEqual(2, request["shots"])
        self.assertIn("QINIT 2", request["originir"])
        self.assertEqual("utf-8", process.call_args.kwargs["encoding"])
        self.assertFalse(process.call_args.kwargs["check"])

    def test_configured_python_has_priority_and_missing_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            python_path = Path(directory) / "python"
            python_path.touch()
            with mock.patch.dict(
                os.environ, {"LOOMQ_ORIGINQ_PYTHON": str(python_path)}
            ):
                self.assertEqual(python_path, _find_originq_python())

            missing = Path(directory) / "missing"
            with mock.patch.dict(
                os.environ, {"LOOMQ_ORIGINQ_PYTHON": str(missing)}
            ):
                with self.assertRaisesRegex(RuntimeError, "LOOMQ_ORIGINQ_PYTHON"):
                    _find_originq_python()

    def test_worker_failures_are_reported(self) -> None:
        cases = (
            (
                subprocess.CompletedProcess(
                    args=[], returncode=3, stdout="", stderr="native failure"
                ),
                "exit code 3: native failure",
            ),
            (
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="not-json", stderr=""
                ),
                "invalid JSON",
            ),
            (
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="[]", stderr=""
                ),
                "JSON object",
            ),
        )
        for completed, message in cases:
            with self.subTest(message=message), mock.patch(
                "loomq.runners.originq._find_originq_python",
                return_value=Path("/isolated/bin/python"),
            ), mock.patch(
                "loomq.runners.originq.subprocess.run", return_value=completed
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    run_originq(self.circuit, 2)

    def test_worker_timeout_is_reported(self) -> None:
        with mock.patch(
            "loomq.runners.originq._find_originq_python",
            return_value=Path("/isolated/bin/python"),
        ), mock.patch(
            "loomq.runners.originq.subprocess.run",
            side_effect=subprocess.TimeoutExpired("worker", 120),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 120 seconds"):
                run_originq(self.circuit, 2)

    def test_measurement_contract_is_checked_before_worker(self) -> None:
        no_measurement = parse_qasm(qasm("h q[0];"))
        with self.assertRaisesRegex(ValueError, "at least one measurement"):
            run_originq(no_measurement, 1)

        mid_circuit = parse_qasm(qasm("measure q[0] -> c[0]; h q[1];"))
        with self.assertRaisesRegex(ValueError, "final measurements only"):
            run_originq(mid_circuit, 1)


@unittest.skipUnless(
    ORIGINQ_CONFIGURED, "LOOMQ_ORIGINQ_PYTHON is not configured"
)
class OriginQIntegrationTests(unittest.TestCase):
    def probabilities(self, source: str, shots: int = SHOTS):  # type: ignore[no-untyped-def]
        result = adapter.run(source, "originq", shots)
        valid, reason = validate_schema(result)
        self.assertTrue(valid, reason)
        self.assertEqual("little", result["bit_order"])
        self.assertEqual(shots, sum(result["counts"].values()))
        return {key: count / shots for key, count in result["counts"].items()}

    def assert_deterministic(self, source: str, key: str) -> None:
        observed = self.probabilities(source, DETERMINISTIC_SHOTS)
        self.assertGreaterEqual(observed.get(key, 0.0), 0.999)

    def test_bell_and_ghz3_real_cpuqvm_fidelity(self) -> None:
        cases = (
            ("bell.qasm", {"00": 0.5, "11": 0.5}),
            ("ghz3.qasm", {"000": 0.5, "111": 0.5}),
        )
        for filename, expected in cases:
            with self.subTest(filename=filename):
                source = (STARTER_KIT / "circuits" / filename).read_text(
                    encoding="utf-8"
                )
                observed = self.probabilities(source)
                self.assertTrue(set(observed).issubset(expected))
                self.assertGreaterEqual(
                    calculate_hellinger_fidelity(observed, expected), 0.97
                )

    def test_all_twelve_gates_execute_in_fixed_random_inverse(self) -> None:
        source, initial_key, forward = random_identity_case(20260801)
        self.assertEqual(
            {"h", "x", "s", "sdg", "t", "tdg", "ry", "rz", "cx", "cu1", "swap", "ccx"},
            {operation.name for operation in forward},
        )
        self.assert_deterministic(source, initial_key)

    def test_qft4_inverse_restores_nonzero_basis_state(self) -> None:
        qft = qft_operations(4)
        operations = basis_preparation("1010") + qft + inverse_operations(qft)
        self.assert_deterministic(build_qasm(4, operations), "1010")

    def test_grover3_amplifies_111(self) -> None:
        observed = self.probabilities(build_qasm(3, grover_3_operations()))
        self.assertEqual("111", max(observed, key=observed.__getitem__))
        self.assertGreaterEqual(observed.get("111", 0.0), 0.70)

    def test_multiple_registers_cross_mapping_and_unmeasured_bits(self) -> None:
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg qb[2]; qreg qa[1];
creg ca[2]; creg cb[2];
x qb[1]; ry(pi) qa[0]; rz(-pi/4) qb[1];
ccx qb[1], qa[0], qb[0];
measure qa[0] -> cb[0]; measure qb[0] -> ca[1];
"""
        self.assert_deterministic(source, "0110")


@unittest.skipUnless(
    ORIGINQ_CONFIGURED and SPINQ_CONFIGURED and BRAKET_INSTALLED,
    "all three local backends are required",
)
class OriginQCrossBackendTests(unittest.TestCase):
    def test_ghz3_matches_spinq_and_braket(self) -> None:
        # 直接读取 GHZ-3 公开电路足以验证三条完整执行链路的 Fidelity。
        source = (STARTER_KIT / "circuits" / "ghz3.qasm").read_text(
            encoding="utf-8"
        )
        distributions = []
        for target in ("spinq", "originq", "braket"):
            result = adapter.run(source, target, SHOTS)
            valid, reason = validate_schema(result)
            self.assertTrue(valid, reason)
            distributions.append(
                {key: count / SHOTS for key, count in result["counts"].items()}
            )
        self.assertGreaterEqual(
            calculate_hellinger_fidelity(distributions[0], distributions[1]), 0.97
        )
        self.assertGreaterEqual(
            calculate_hellinger_fidelity(distributions[1], distributions[2]), 0.97
        )


if __name__ == "__main__":
    unittest.main()
