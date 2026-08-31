import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from starter_kit import adapter
from starter_kit.evaluator import validate_schema
from starter_kit.loomq_l1.errors import (
    DependencyUnavailableError,
    NormalizationError,
    ProviderExecutionError,
    QASMParseError,
    UnsupportedTargetError,
)
from starter_kit.loomq_l1.model import RawExecution


SOURCE = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[2];
h q[0];
h q[1];
cx q[0],q[1];
x q[2];
ccx q[0],q[1],q[2];
measure q[0] -> c[0];
measure q[1] -> c[1];
'''


class AdapterContractTests(unittest.TestCase):
    def _raw_execution(self, target, *, metadata=None):
        return RawExecution(
            backend=f"{target}_backend",
            job_id=f"{target}-job",
            counts={"01": 3, "10": 2},
            key_format="binary",
            reverse_bits=True,
            metadata={} if metadata is None else metadata,
        )

    def test_dispatch_maps_are_exactly_the_three_provider_functions(self):
        self.assertEqual(set(adapter.EMITTERS), {"spinq", "originq", "braket"})
        self.assertEqual(set(adapter.RUNNERS), {"spinq", "originq", "braket"})
        for target in adapter.SUPPORTED_TARGETS:
            with self.subTest(target=target):
                self.assertTrue(callable(adapter.EMITTERS[target]))
                self.assertTrue(callable(adapter.RUNNERS[target]))

    def test_adapter_loads_when_evaluator_imports_it_as_a_top_level_module(self):
        starter_kit = Path(__file__).resolve().parents[2]
        completed = subprocess.run(
            [sys.executable, "-c", "import adapter; print(adapter.__file__)"],
            cwd=starter_kit,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("adapter.py", completed.stdout)

    def test_transpile_emits_the_selected_native_header_from_parsed_source(self):
        expected_headers = {
            "spinq": "OPENQASM 2.0;",
            "originq": "QINIT 3",
            "braket": "OPENQASM 3.0;",
        }
        for target, header in expected_headers.items():
            with self.subTest(target=target):
                native = adapter.transpile(SOURCE, target)
                self.assertTrue(native.startswith(header))
                self.assertEqual(native, adapter.EMITTERS[target](adapter.parse_qasm(SOURCE)))

    def test_transpile_parses_and_emits_once_for_only_the_selected_target(self):
        calls = {"emitter": []}
        real_parse = adapter.parse_qasm

        def emitter(circuit):
            calls["emitter"].append(circuit)
            return "native-spinq"

        emitters = dict(adapter.EMITTERS)
        emitters["spinq"] = emitter
        with patch.object(adapter, "parse_qasm", wraps=real_parse) as parse:
            with patch.object(adapter, "EMITTERS", emitters):
                self.assertEqual(adapter.transpile(SOURCE, "spinq"), "native-spinq")

        self.assertEqual(parse.call_count, 1)
        self.assertEqual(len(calls["emitter"]), 1)

    def test_run_dispatches_exact_native_artifact_and_returns_valid_little_endian_schema(self):
        for target in adapter.SUPPORTED_TARGETS:
            with self.subTest(target=target):
                expected_native = adapter.transpile(SOURCE, target)
                seen = {}

                def runner(native_ir, shots):
                    seen["native_ir"] = native_ir
                    seen["shots"] = shots
                    return self._raw_execution(target)

                runners = dict(adapter.RUNNERS)
                runners[target] = runner
                with patch.object(adapter, "RUNNERS", runners):
                    result = adapter.run(SOURCE, target, 5)

                self.assertEqual(seen, {"native_ir": expected_native, "shots": 5})
                self.assertEqual(result["counts"], {"10": 3, "01": 2})
                self.assertEqual(result["shots"], 5)
                self.assertEqual(result["bit_order"], "little")
                self.assertEqual(sum(result["counts"].values()), 5)
                self.assertEqual(validate_schema(result), (True, "schema valid"))

    def test_run_parses_emits_runs_and_normalizes_once_for_only_selected_target(self):
        calls = {"emitter": [], "runner": []}
        real_parse = adapter.parse_qasm

        def emitter(circuit):
            calls["emitter"].append(circuit)
            return "only-native-artifact"

        def runner(native_ir, shots):
            calls["runner"].append((native_ir, shots))
            return self._raw_execution("spinq")

        emitters = dict(adapter.EMITTERS)
        runners = dict(adapter.RUNNERS)
        emitters["spinq"] = emitter
        runners["spinq"] = runner
        with patch.object(adapter, "parse_qasm", wraps=real_parse) as parse:
            with patch.object(adapter, "EMITTERS", emitters):
                with patch.object(adapter, "RUNNERS", runners):
                    with patch.object(adapter, "build_result", wraps=adapter.build_result) as build:
                        adapter.run(SOURCE, "spinq", 5)

        self.assertEqual(parse.call_count, 1)
        self.assertEqual(len(calls["emitter"]), 1)
        self.assertEqual(calls["runner"], [("only-native-artifact", 5)])
        self.assertEqual(build.call_count, 1)

    def test_rejects_unsupported_target_before_parse_or_runner(self):
        with patch.object(adapter, "parse_qasm") as parse:
            with self.assertRaisesRegex(UnsupportedTargetError, "unsupported target"):
                adapter.run(SOURCE, "unknown", 1)
        parse.assert_not_called()

    def test_rejects_non_builtin_source_and_target_with_existing_loomq_errors(self):
        class StringSubclass(str):
            pass

        for source in (None, b"qasm", StringSubclass(SOURCE)):
            with self.subTest(source=repr(source)):
                with self.assertRaisesRegex(QASMParseError, "source must be a string"):
                    adapter.transpile(source, "spinq")
        for target in (None, b"spinq", StringSubclass("spinq")):
            with self.subTest(target=repr(target)):
                with self.assertRaisesRegex(UnsupportedTargetError, "unsupported target"):
                    adapter.transpile(SOURCE, target)

    def test_run_rejects_invalid_shots_before_parse_or_runner(self):
        for shots in (True, False, 1.0, 0, -1):
            with self.subTest(shots=repr(shots)):
                with patch.object(adapter, "parse_qasm") as parse:
                    with self.assertRaisesRegex(NormalizationError, "shots must be a positive"):
                        adapter.run(SOURCE, "spinq", shots)
                parse.assert_not_called()

    def test_transpile_never_calls_runner_and_missing_selected_sdk_error_propagates(self):
        runners = dict(adapter.RUNNERS)

        def no_runner(*args):
            raise AssertionError("transpile must not invoke a runner")

        runners["spinq"] = no_runner
        with patch.object(adapter, "RUNNERS", runners):
            self.assertTrue(adapter.transpile(SOURCE, "spinq"))

        dependency_error = DependencyUnavailableError("spinqit is required")

        def missing_sdk(native_ir, shots):
            raise dependency_error

        runners["spinq"] = missing_sdk
        with patch.object(adapter, "RUNNERS", runners):
            with self.assertRaises(DependencyUnavailableError) as raised:
                adapter.run(SOURCE, "spinq", 5)
        self.assertIs(raised.exception, dependency_error)

    def test_provider_execution_error_propagates_with_its_original_cause(self):
        provider_cause = RuntimeError("provider failed")
        try:
            raise provider_cause
        except RuntimeError as cause:
            provider_error = ProviderExecutionError("SpinQ execution failed")
            provider_error.__cause__ = cause

        def failing_runner(native_ir, shots):
            raise provider_error

        runners = dict(adapter.RUNNERS)
        runners["spinq"] = failing_runner
        with patch.object(adapter, "RUNNERS", runners):
            with self.assertRaises(ProviderExecutionError) as raised:
                adapter.run(SOURCE, "spinq", 5)
        self.assertIs(raised.exception, provider_error)
        self.assertIs(raised.exception.__cause__, provider_cause)

    def test_metadata_merges_canonical_values_and_rejects_nested_mock_result(self):
        metadata = {
            "target": "provider-target",
            "emitted_gate_count": -1,
            "circuit_depth": -1,
            "provider": "test-provider",
            "sdk": "test-sdk",
            "is_mock": False,
            "nested": {"items": [{"is_mock": True, "value": "kept"}]},
        }
        raw = self._raw_execution("spinq", metadata=metadata)
        runners = dict(adapter.RUNNERS)
        runners["spinq"] = lambda native_ir, shots: raw
        with patch.object(adapter, "RUNNERS", runners):
            with self.assertRaisesRegex(NormalizationError, "mock execution results are not allowed"):
                adapter.run(SOURCE, "spinq", 5)

        self.assertEqual(raw.metadata, metadata)

    def test_metadata_merges_canonical_values_and_preserves_false_mock_marker(self):
        metadata = {
            "target": "provider-target",
            "emitted_gate_count": -1,
            "circuit_depth": -1,
            "provider": "test-provider",
            "sdk": "test-sdk",
            "is_mock": False,
            "nested": {"is_mock": False, "value": "kept"},
        }
        raw = self._raw_execution("spinq", metadata=metadata)
        runners = dict(adapter.RUNNERS)
        runners["spinq"] = lambda native_ir, shots: raw
        with patch.object(adapter, "RUNNERS", runners):
            result = adapter.run(SOURCE, "spinq", 5)

        self.assertEqual(raw.metadata, metadata)
        self.assertEqual(result["meta"]["target"], "spinq")
        self.assertEqual(result["meta"]["emitted_gate_count"], 5)
        self.assertEqual(result["meta"]["circuit_depth"], 3)
        self.assertEqual(result["meta"]["provider"], "test-provider")
        self.assertEqual(result["meta"]["sdk"], "test-sdk")
        self.assertFalse(result["meta"]["is_mock"])
        self.assertFalse(result["meta"]["nested"]["is_mock"])

    def test_metadata_depth_tracks_parallel_and_dependent_canonical_operations(self):
        parallel = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[1];
h q[0]; h q[1];
measure q[0] -> c[0];
'''
        dependent = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[2]; creg c[1];
h q[0]; x q[0]; h q[1];
measure q[0] -> c[0];
'''
        runners = dict(adapter.RUNNERS)
        runners["spinq"] = lambda native_ir, shots: RawExecution(
            "backend", "job", {"0": shots}
        )
        with patch.object(adapter, "RUNNERS", runners):
            self.assertEqual(adapter.run(parallel, "spinq", 2)["meta"]["circuit_depth"], 1)
            self.assertEqual(adapter.run(dependent, "spinq", 2)["meta"]["circuit_depth"], 2)

    def test_declared_l2_and_l3_entrypoints_are_safe_and_available(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOOMQ_LLM_BASE_URL"):
                adapter.agent_chat("hello")
        operations, assembly = adapter.compile_hybrid(
            '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[0];
classical { r1 = c[0] + 1; }
'''
        )
        self.assertEqual(operations, ["measure q[0] -> c[0];"])
        self.assertIn("addi x1, x28, 0", assembly)


if __name__ == "__main__":
    unittest.main()
