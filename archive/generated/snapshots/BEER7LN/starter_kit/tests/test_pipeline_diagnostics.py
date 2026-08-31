"""Contracts for the staged L1 pipeline and native-result diagnostics."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest
from unittest import mock


STARTER_KIT = Path(__file__).resolve().parents[1]
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.backends import (  # noqa: E402
    NativeBackendUnavailable,
    _diagnose_native_result,
)
from loomq.diagnostics import acceptance_threshold, probe_bit_order  # noqa: E402
from loomq.gate_policy import PUBLIC_GATE_WHITELIST  # noqa: E402
from loomq.pipeline import trace_transpilation  # noqa: E402
from loomq.qasm import GateOperation, parse_openqasm2  # noqa: E402


BELL = (STARTER_KIT / "circuits" / "bell.qasm").read_text(encoding="utf-8")


class PipelineTraceTests(unittest.TestCase):
    def test_every_target_records_the_same_explicit_stages(self) -> None:
        for target in adapter.SUPPORTED_TARGETS:
            with self.subTest(target=target):
                trace = trace_transpilation(BELL, target)
                self.assertEqual(
                    [stage.name for stage in trace.stages],
                    [
                        "receive",
                        "parse",
                        "public-basis",
                        "canonicalize",
                        "emit-public",
                        "emit-runtime",
                    ],
                )
                basis = trace.stages[2].details
                self.assertEqual(basis["rewritten_gate_count"], 0)
                self.assertTrue(set(basis["output_gates"]) <= PUBLIC_GATE_WHITELIST)
                self.assertTrue(trace.public_ir.strip())
                self.assertTrue(trace.runtime_ir.strip())

    def test_public_contract_and_runtime_dialects_are_explicitly_separate(self) -> None:
        origin = trace_transpilation(_all_gates_qasm(), "originq")
        braket = trace_transpilation(_all_gates_qasm(), "braket")

        self.assertIn("SDAG q[0]", origin.public_ir)
        self.assertIn("DAGGER", origin.runtime_ir)
        self.assertNotEqual(origin.public_ir, origin.runtime_ir)
        self.assertIn('include "stdgates.inc";', braket.public_ir)
        self.assertNotIn('include "stdgates.inc";', braket.runtime_ir)
        self.assertNotEqual(braket.public_ir, braket.runtime_ir)

    def test_reference_fallback_exposes_pipeline_and_reason(self) -> None:
        with mock.patch.dict(
            "os.environ", {"LOOMQ_FORCE_REFERENCE_SIMULATOR": "1"}
        ):
            payload = adapter.run(BELL, "spinq", 128)
        meta = payload["meta"]
        self.assertEqual(meta["pipeline"]["target"], "spinq")
        self.assertEqual(meta["pipeline"]["stages"][-1]["name"], "emit-runtime")
        self.assertTrue(meta["fallback"]["used"])
        self.assertIn("LOOMQ_FORCE_REFERENCE_SIMULATOR", meta["fallback"]["reason"])

    def test_all_canonical_operations_remain_in_public_basis(self) -> None:
        program = parse_openqasm2(BELL)
        names = {
            operation.name
            for operation in program.operations
            if isinstance(operation, GateOperation)
        }
        self.assertTrue(names <= PUBLIC_GATE_WHITELIST)

    def test_runner_receives_the_exact_pipeline_runtime_artifact(self) -> None:
        trace = trace_transpilation(BELL, "spinq")
        fake = _native_payload(
            trace,
            counts={"00": 64, "11": 64},
        )
        with mock.patch("loomq.backends._run_spinq", return_value=fake) as runner:
            payload = adapter.run(BELL, "spinq", 128)

        self.assertEqual(runner.call_args.args[0], trace.runtime_ir)
        self.assertEqual(runner.call_args.args[1], trace.canonical_qasm)
        self.assertEqual(
            payload["meta"]["executed_artifact"]["sha256"],
            hashlib.sha256(trace.runtime_ir.encode("utf-8")).hexdigest(),
        )

    def test_release_mode_forbids_forced_fallback_and_missing_sdk(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"LOOMQ_RELEASE_MODE": "1", "LOOMQ_FORCE_REFERENCE_SIMULATOR": "1"},
        ):
            with self.assertRaisesRegex(RuntimeError, "forbids"):
                adapter.run(BELL, "spinq", 128)

        with mock.patch.dict("os.environ", {"LOOMQ_RELEASE_MODE": "1"}):
            with mock.patch(
                "loomq.backends._run_spinq",
                side_effect=NativeBackendUnavailable("missing"),
            ):
                with self.assertRaises(NativeBackendUnavailable):
                    adapter.run(BELL, "spinq", 128)

    def test_release_mode_rejects_native_semantic_failure_without_fallback(self) -> None:
        trace = trace_transpilation(BELL, "spinq")
        fake = _native_payload(trace, counts={"01": 128})
        with mock.patch.dict("os.environ", {"LOOMQ_RELEASE_MODE": "1"}):
            with mock.patch("loomq.backends._run_spinq", return_value=fake):
                with self.assertRaisesRegex(RuntimeError, "semantic acceptance"):
                    adapter.run(BELL, "spinq", 128)


class DistributionDiagnosticTests(unittest.TestCase):
    def test_acceptance_threshold_tightens_with_more_shots(self) -> None:
        self.assertLess(acceptance_threshold(4, 128), 0.97)
        self.assertEqual(acceptance_threshold(2, 8192), 0.97)
        self.assertEqual(acceptance_threshold(32, 8192), 0.97)
        with self.assertRaises(ValueError):
            acceptance_threshold(0, 8192)

    def test_bit_order_probe_corrects_only_a_material_improvement(self) -> None:
        corrected, diagnosis = probe_bit_order(
            {"100": 128}, {"001": 1.0}
        )
        self.assertEqual(corrected, {"001": 128})
        self.assertEqual(diagnosis.decision, "reversed")
        self.assertTrue(diagnosis.corrected)

        unchanged, ambiguous = probe_bit_order(
            {"00": 64, "11": 64}, {"00": 0.5, "11": 0.5}
        )
        self.assertEqual(unchanged, {"00": 64, "11": 64})
        self.assertEqual(ambiguous.decision, "ambiguous")
        self.assertFalse(ambiguous.corrected)

    def test_native_diagnostic_updates_counts_and_meta(self) -> None:
        source = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
x q[0];
measure q -> c;
"""
        trace = trace_transpilation(source, "spinq")
        native = _native_payload(trace, counts={"10": 128})
        checked, accepted = _diagnose_native_result(
            source,
            "spinq",
            128,
            native,
            trace,
        )
        self.assertTrue(accepted)
        self.assertEqual(checked["counts"], {"01": 128})
        self.assertTrue(checked["meta"]["bit_order_probe"]["corrected"])
        self.assertEqual(checked["meta"]["acceptance"]["status"], "accepted")

    def test_native_diagnostic_rejects_semantically_wrong_counts(self) -> None:
        trace = trace_transpilation(BELL, "spinq")
        native = _native_payload(trace, shots=8192, counts={"01": 8192})
        checked, accepted = _diagnose_native_result(
            BELL,
            "spinq",
            8192,
            native,
            trace,
        )
        self.assertFalse(accepted)
        self.assertEqual(checked["meta"]["acceptance"]["status"], "rejected")


def _native_payload(
    trace: object,
    *,
    shots: int = 128,
    counts: dict[str, int],
) -> dict[str, object]:
    return {
        "backend": "test",
        "job_id": "native-job",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": "2026-08-21T00:00:00Z",
        "meta": {
            "executor": "fake-native",
            "executed_artifact": {
                "sha256": hashlib.sha256(trace.runtime_ir.encode("utf-8")).hexdigest()
            },
        },
    }


def _all_gates_qasm() -> str:
    return """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
x q[0];
s q[0];
sdg q[0];
t q[0];
tdg q[0];
rz(pi/7) q[0];
ry(-pi/5) q[0];
cx q[0], q[1];
cu1(pi/3) q[0], q[1];
swap q[0], q[1];
ccx q[0], q[1], q[2];
measure q -> c;
"""


if __name__ == "__main__":
    unittest.main()
