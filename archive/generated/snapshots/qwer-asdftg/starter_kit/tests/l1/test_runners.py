import json
import io
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from types import ModuleType
import tempfile
import unittest
from unittest.mock import patch

from starter_kit.loomq_l1.errors import (
    DependencyUnavailableError,
    ProviderExecutionError,
    UnsupportedTargetError,
)
from starter_kit.loomq_l1.model import RawExecution
from starter_kit.loomq_l1.normalize import normalize_counts
from starter_kit.loomq_l1.runners import (
    run,
    run_braket,
    run_originq,
    run_spinq,
)
from starter_kit.loomq_l1.runners import _common, braket, braket_worker, originq, spinq


class SpinQRunnerTests(unittest.TestCase):
    native_ir = (
        'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
        'qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\n'
    )

    @staticmethod
    def _run_fake_spinq(native_ir):
        class Compiler:
            def compile(self, path, mode):
                return "compiled-ir"

        class Engine:
            def execute(self, compiled_ir, config):
                return SimpleNamespace(counts={"10": 4}, job_id="spinq-regression")

        class BasicSimulatorConfig:
            def configure_shots(self, shots):
                self.shots = shots

        sdk = SimpleNamespace(
            get_compiler=lambda name: Compiler(),
            get_basic_simulator=lambda: Engine(),
            BasicSimulatorConfig=BasicSimulatorConfig,
            version="0.2.4-test",
        )
        with patch.object(spinq, "_import_spinq", return_value=sdk):
            return run_spinq(native_ir, 4)

    def test_missing_dependency_names_spinqit(self):
        with patch.object(spinq, "_import_spinq", side_effect=ImportError("missing")):
            with self.assertRaisesRegex(DependencyUnavailableError, "spinqit") as raised:
                run_spinq(self.native_ir, 4)
        self.assertIsInstance(raised.exception.__cause__, ImportError)

    def test_accepts_whole_register_measurement_in_native_qasm(self):
        native_ir = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            "qreg q[2];\ncreg c[2];\nx q[0];\nmeasure q -> c;\n"
        )

        raw = self._run_fake_spinq(native_ir)

        self.assertEqual(dict(raw.counts), {"01": 4})
        self.assertFalse(raw.reverse_bits)

    def test_accepts_parser_valid_ascii_spacing_in_native_qasm(self):
        native_ir = (
            'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
            "qreg q[2];\ncreg c[2];\nx q[0];\n"
            "measure q [ 0 ] -> c [ 1 ];\nmeasure q [ 1 ] -> c [ 0 ];\n"
        )

        raw = self._run_fake_spinq(native_ir)

        self.assertEqual(dict(raw.counts), {"10": 4})
        self.assertFalse(raw.reverse_bits)

    def test_executes_exact_qasm_and_removes_temporary_file(self):
        calls = {}

        class Compiler:
            def compile(self, path, mode):
                calls["compile_path"] = path
                calls["compile_mode"] = mode
                calls["content_during_compile"] = Path(path).read_text(encoding="utf-8")
                calls["exists_during_compile"] = os.path.exists(path)
                return "compiled-ir"

        class Engine:
            def execute(self, compiled_ir, config):
                calls["execute"] = (compiled_ir, config)
                return SimpleNamespace(
                    counts={"0": 3, "1": 1},
                    job_id="spinq-job-1",
                    task_id="spinq-task-1",
                )

        class BasicSimulatorConfig:
            def configure_shots(self, shots):
                calls["config"] = self
                calls["configured_shots"] = shots

        sdk = SimpleNamespace(
            get_compiler=lambda name: calls.setdefault("compiler_name", name) and Compiler(),
            get_basic_simulator=lambda: Engine(),
            BasicSimulatorConfig=BasicSimulatorConfig,
            version="0.2.4-test",
        )

        with patch.object(spinq, "_import_spinq", return_value=sdk):
            raw = run_spinq(self.native_ir, 4)

        self.assertIsInstance(raw, RawExecution)
        self.assertEqual(raw.backend, "spinq_basic_simulator")
        self.assertEqual(raw.job_id, "spinq-job-1")
        self.assertEqual(raw.counts, {"0": 3, "1": 1})
        self.assertEqual(raw.key_format, "binary")
        self.assertFalse(raw.reverse_bits)
        self.assertEqual(
            raw.metadata,
            {
                "target": "spinq",
                "provider": "spinq",
                "sdk": "spinqit",
                "sdk_version": "0.2.4-test",
            },
        )
        self.assertTrue(calls["compile_path"].endswith(".qasm"))
        self.assertEqual(calls["compile_mode"], 0)
        self.assertEqual(calls["compiler_name"], "qasm")
        self.assertEqual(calls["content_during_compile"], self.native_ir)
        self.assertTrue(calls["exists_during_compile"])
        self.assertEqual(calls["configured_shots"], 4)
        self.assertEqual(calls["execute"], ("compiled-ir", calls["config"]))
        self.assertFalse(os.path.exists(calls["compile_path"]))

    def test_uses_task_id_then_uuid_local_id_when_spinq_job_id_is_unavailable(self):
        class Compiler:
            def compile(self, path, mode):
                return "compiled-ir"

        class BasicSimulatorConfig:
            def configure_shots(self, shots):
                self.shots = shots

        for result, expected_job_id in (
            (SimpleNamespace(counts={"0": 1}, task_id="spinq-task-2"), "spinq-task-2"),
            (SimpleNamespace(counts={"0": 1}), None),
        ):
            class Engine:
                def execute(self, compiled_ir, config):
                    return result

            sdk = SimpleNamespace(
                get_compiler=lambda name: Compiler(),
                get_basic_simulator=lambda: Engine(),
                BasicSimulatorConfig=BasicSimulatorConfig,
            )
            with self.subTest(result=result):
                with patch.object(spinq, "_import_spinq", return_value=sdk):
                    raw = run_spinq(self.native_ir, 1)
                if expected_job_id is None:
                    self.assertRegex(raw.job_id, r"^spinq-local-[0-9a-f-]{36}$")
                    self.assertEqual(raw.metadata["sdk_version"], "unknown")
                else:
                    self.assertEqual(raw.job_id, expected_job_id)

    def test_write_failure_removes_spinq_temporary_file(self):
        descriptor, path = tempfile.mkstemp(suffix=".qasm")
        os.close(descriptor)
        write_error = OSError("write failed")

        class FailingTempFile:
            name = path

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def write(self, value):
                raise write_error

        with patch.object(spinq, "_import_spinq", return_value=SimpleNamespace()):
            with patch.object(spinq.tempfile, "NamedTemporaryFile", return_value=FailingTempFile()):
                with self.assertRaises(ProviderExecutionError) as raised:
                    run_spinq(self.native_ir, 1)

        self.assertIs(raised.exception.__cause__, write_error)
        self.assertFalse(os.path.exists(path))

    def test_provider_failure_is_redacted_translated_and_removes_file(self):
        calls = {}
        provider_error = RuntimeError("token=top-secret")

        class Compiler:
            def compile(self, path, mode):
                calls["path"] = path
                calls["content"] = Path(path).read_text(encoding="utf-8")
                raise provider_error

        sdk = SimpleNamespace(
            get_compiler=lambda name: Compiler(),
            get_basic_simulator=lambda: None,
            BasicSimulatorConfig=object,
        )

        with patch.object(spinq, "_import_spinq", return_value=sdk):
            with self.assertRaisesRegex(ProviderExecutionError, "SpinQ") as raised:
                run_spinq(self.native_ir, 4)

        self.assertIs(raised.exception.__cause__, provider_error)
        self.assertNotIn("top-secret", str(raised.exception))
        self.assertEqual(calls["content"], self.native_ir)
        self.assertFalse(os.path.exists(calls["path"]))


class OriginQRunnerTests(unittest.TestCase):
    native_ir = (
        "QINIT 3\nCREG 3\nH q[0]\n"
        "MEASURE q[0], c[0]\nMEASURE q[1], c[1]\nMEASURE q[2], c[2]\n"
    )

    def test_missing_dependency_names_pyqpanda(self):
        with patch.object(originq, "_import_originq", side_effect=ImportError("missing")):
            with self.assertRaisesRegex(DependencyUnavailableError, "pyqpanda") as raised:
                run_originq(self.native_ir, 4)
        self.assertIsInstance(raised.exception.__cause__, ImportError)

    def test_executes_converter_program_with_converted_cbits_and_cleans_up(self):
        calls = {}

        class CPUQVM:
            def init_qvm(self):
                calls["initialized"] = True

            def run_with_configuration(self, program, cbits, shots):
                calls["run"] = (program, cbits, shots)
                return {1: 2, 6: 2}

            def finalize(self):
                calls["finalized"] = calls.get("finalized", 0) + 1

        cbits = ["c0", "c1", "c2"]

        def convert(path, machine):
            calls["path"] = path
            calls["machine"] = machine
            calls["content"] = Path(path).read_text(encoding="utf-8")
            calls["exists_during_convert"] = os.path.exists(path)
            return ("origin-program", ["q0", "q1", "q2"], cbits)

        sdk = SimpleNamespace(
            CPUQVM=CPUQVM,
            convert_originir_to_qprog=convert,
            version="3.8.5-test",
        )
        with patch.object(originq, "_import_originq", return_value=sdk):
            raw = run_originq(self.native_ir, 4)

        self.assertIsInstance(raw, RawExecution)
        self.assertEqual(raw.backend, "originq_cpu_simulator")
        self.assertRegex(raw.job_id, r"^originq-local-[0-9a-f-]{36}$")
        self.assertEqual(raw.counts, {"001": 2, "110": 2})
        self.assertEqual(raw.key_format, "binary")
        self.assertFalse(raw.reverse_bits)
        self.assertEqual(
            raw.metadata,
            {
                "target": "originq",
                "provider": "originq",
                "sdk": "pyqpanda",
                "sdk_version": "3.8.5-test",
            },
        )
        self.assertTrue(calls["path"].endswith(".ir"))
        self.assertEqual(calls["content"], self.native_ir)
        self.assertTrue(calls["exists_during_convert"])
        self.assertTrue(calls["initialized"])
        self.assertEqual(calls["run"], ("origin-program", cbits, 4))
        self.assertEqual(calls["finalized"], 1)
        self.assertFalse(os.path.exists(calls["path"]))

    def test_execution_copy_lowers_inverse_gates_to_dagger_blocks(self):
        native_ir = (
            "QINIT 2\nCREG 2\nSDAG q[0]\nTDAG q[0]\nCU1 q[0], q[1], (0.2)\n"
            "MEASURE q[0], c[0]\nMEASURE q[1], c[1]\n"
        )
        expected_execution_ir = (
            "QINIT 2\nCREG 2\nDAGGER\nS q[0]\nENDDAGGER\n"
            "DAGGER\nT q[0]\nENDDAGGER\nCR q[0], q[1], (0.2)\n"
            "MEASURE q[0], c[0]\nMEASURE q[1], c[1]\n"
        )
        calls = {}

        class CPUQVM:
            def init_qvm(self):
                pass

            def run_with_configuration(self, program, cbits, shots):
                return {"00": shots}

            def finalize(self):
                pass

        def convert(path, machine):
            calls["content"] = Path(path).read_text(encoding="utf-8")
            return ("origin-program", ["q0", "q1"], ["c0", "c1"])

        sdk = SimpleNamespace(CPUQVM=CPUQVM, convert_originir_to_qprog=convert)
        with patch.object(originq, "_import_originq", return_value=sdk):
            raw = run_originq(native_ir, 2)

        self.assertEqual(raw.counts, {"00": 2})
        self.assertEqual(calls["content"], expected_execution_ir)

    def test_canonicalizes_decimal_and_binary_originq_count_keys_without_ambiguity(self):
        def run_with_counts(counts, width=3):
            class CPUQVM:
                def init_qvm(self):
                    pass

                def run_with_configuration(self, program, cbits, shots):
                    return counts

                def finalize(self):
                    pass

            sdk = SimpleNamespace(
                CPUQVM=CPUQVM,
                convert_originir_to_qprog=lambda path, machine: (
                    "origin-program",
                    [f"q{index}" for index in range(width)],
                    [f"c{index}" for index in range(width)],
                ),
            )
            with patch.object(originq, "_import_originq", return_value=sdk):
                native_ir = f"QINIT {width}\nCREG {width}\n"
                return run_originq(native_ir, 4)

        self.assertEqual(run_with_counts({"2": 4}).counts, {"010": 4})
        self.assertEqual(run_with_counts({"101": 4}).counts, {"101": 4})
        with self.assertRaises(ProviderExecutionError):
            run_with_counts({"001": 2, "2": 2})
        with self.assertRaises(ProviderExecutionError):
            run_with_counts({"10": 4}, width=4)

    def test_write_failure_removes_originq_temporary_file_and_finalizes_machine(self):
        descriptor, path = tempfile.mkstemp(suffix=".ir")
        os.close(descriptor)
        calls = {}
        write_error = OSError("write failed")

        class CPUQVM:
            def init_qvm(self):
                pass

            def finalize(self):
                calls["finalized"] = calls.get("finalized", 0) + 1

        class FailingTempFile:
            name = path

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def write(self, value):
                raise write_error

        sdk = SimpleNamespace(CPUQVM=CPUQVM, convert_originir_to_qprog=lambda path, machine: None)
        with patch.object(originq, "_import_originq", return_value=sdk):
            with patch.object(originq.tempfile, "NamedTemporaryFile", return_value=FailingTempFile()):
                with self.assertRaises(ProviderExecutionError) as raised:
                    run_originq(self.native_ir, 1)

        self.assertIs(raised.exception.__cause__, write_error)
        self.assertEqual(calls["finalized"], 1)
        self.assertFalse(os.path.exists(path))

    def test_converter_failure_is_redacted_translated_and_finalizes_after_cleanup(self):
        calls = {}
        provider_error = RuntimeError("api-key=top-secret")

        class CPUQVM:
            def init_qvm(self):
                calls["initialized"] = True

            def finalize(self):
                calls["finalized"] = calls.get("finalized", 0) + 1

        def convert(path, machine):
            calls["path"] = path
            calls["content"] = Path(path).read_text(encoding="utf-8")
            raise provider_error

        sdk = SimpleNamespace(CPUQVM=CPUQVM, convert_originir_to_qprog=convert)
        with patch.object(originq, "_import_originq", return_value=sdk):
            with self.assertRaisesRegex(ProviderExecutionError, "OriginQ") as raised:
                run_originq(self.native_ir, 4)

        self.assertIs(raised.exception.__cause__, provider_error)
        self.assertNotIn("top-secret", str(raised.exception))
        self.assertEqual(calls["content"], self.native_ir)
        self.assertEqual(calls["finalized"], 1)
        self.assertFalse(os.path.exists(calls["path"]))


class BraketRunnerTests(unittest.TestCase):
    native_ir = "OPENQASM 3.0;\nbit[1] c;\nqubit[1] q;\nc[0] = measure q[0];\n"

    def _worker_result(self, payload):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    @contextmanager
    def _direct_braket_environment(self):
        """Temporarily select the direct SDK path despite Docker's worker ENV."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOOMQ_BRAKET_PYTHON", None)
            yield

    def test_direct_path_environment_scope_restores_worker_configuration(self):
        with patch.dict(os.environ, {"LOOMQ_BRAKET_PYTHON": "/docker/worker"}, clear=False):
            with self._direct_braket_environment():
                self.assertNotIn("LOOMQ_BRAKET_PYTHON", os.environ)
            self.assertEqual(os.environ["LOOMQ_BRAKET_PYTHON"], "/docker/worker")

    def test_worker_path_sends_only_protocol_payload_and_returns_raw_execution(self):
        worker_response = {
            "counts": {"0": 3, "1": 1},
            "job_id": "braket-worker-task-1",
            "sdk_version": "1.108.0-test",
        }
        worker_environment = {
            "LOOMQ_BRAKET_PYTHON": "C:/braket/python.exe",
            "PATH": "C:/braket",
            "SystemRoot": "C:/Windows",
            "AWS_SECRET_ACCESS_KEY": "aws-secret-must-not-reach-worker",
            "API_TOKEN": "token-must-not-reach-worker",
        }
        with patch.dict(os.environ, worker_environment, clear=True):
            allowed_environment = braket._worker_environment()
            with patch.object(
                braket.subprocess,
                "run",
                return_value=self._worker_result(worker_response),
            ) as run_worker:
                raw = run_braket(self.native_ir, 4)

        run_worker.assert_called_once_with(
            ["C:/braket/python.exe", "-m", "loomq_l1.runners.braket_worker"],
            input=json.dumps({"native_ir": self.native_ir, "shots": 4}),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env=allowed_environment,
            cwd=str(Path(braket.__file__).resolve().parents[2]),
        )
        self.assertEqual(raw.backend, "braket_local_simulator")
        self.assertEqual(raw.job_id, "braket-worker-task-1")
        self.assertEqual(raw.counts, {"0": 3, "1": 1})
        self.assertEqual(raw.key_format, "binary")
        self.assertTrue(raw.reverse_bits)
        self.assertEqual(
            raw.metadata,
            {
                "target": "braket",
                "provider": "braket",
                "sdk": "amazon-braket-sdk",
                "sdk_version": "1.108.0-test",
            },
        )

    def test_worker_path_uses_local_job_id_when_response_omits_provider_id(self):
        with patch.dict(os.environ, {"LOOMQ_BRAKET_PYTHON": "C:/braket/python.exe"}, clear=True):
            with patch.object(
                braket.subprocess,
                "run",
                return_value=self._worker_result(
                    {"counts": {"0": 1}, "sdk_version": "1.108.0"}
                ),
            ):
                raw = run_braket(self.native_ir, 1)

        self.assertRegex(raw.job_id, r"^braket-local-[0-9a-f-]{36}$")
        self.assertEqual(raw.counts, {"0": 1})

    def test_worker_protocol_failures_are_safe_and_translated(self):
        fake_credential = "credential-should-never-leak"
        aws_secret = ("aws-" "secret-should-never-leak")
        api_token = ("api-" "token-should-never-leak")
        cases = {
            "timeout": subprocess.TimeoutExpired(
                ["C:/braket/python.exe", "-m", "loomq_l1.runners.braket_worker"],
                120,
                stderr=fake_credential,
            ),
            "nonzero": SimpleNamespace(returncode=1, stdout="", stderr=fake_credential),
            "bad-json": SimpleNamespace(returncode=0, stdout="{", stderr=""),
            "nonmapping-counts": self._worker_result(
                {"counts": ["0"], "sdk_version": "1.108.0"}
            ),
            "empty-counts": self._worker_result(
                {"counts": {}, "sdk_version": "1.108.0"}
            ),
            "invalid-job-id": self._worker_result(
                {"counts": {"0": 1}, "job_id": 4, "sdk_version": "1.108.0"}
            ),
            "missing-sdk-version": self._worker_result({"counts": {"0": 1}}),
            "bad-sdk-version": self._worker_result(
                {"counts": {"0": 1}, "sdk_version": f"1.108.0 {fake_credential}"}
            ),
            "is-mock-marker": self._worker_result(
                {"counts": {"0": 1}, "sdk_version": "1.108.0", "is_mock": False}
            ),
        }
        with patch.dict(
            os.environ,
            {
                "LOOMQ_BRAKET_PYTHON": "C:/braket/python.exe",
                "FAKE_CREDENTIAL": fake_credential,
                "AWS_SECRET_ACCESS_KEY": aws_secret,
                "API_TOKEN": api_token,
            },
            clear=True,
        ):
            for name, result in cases.items():
                with self.subTest(name=name):
                    run_kwargs = (
                        {"side_effect": result}
                        if isinstance(result, BaseException)
                        else {"return_value": result}
                    )
                    with patch.object(braket.subprocess, "run", **run_kwargs):
                        with self.assertRaises(ProviderExecutionError) as raised:
                            run_braket(self.native_ir, 1)
                    self.assertNotIn(fake_credential, str(raised.exception))
                    self.assertNotIn(aws_secret, str(raised.exception))
                    self.assertNotIn(api_token, str(raised.exception))

    def test_worker_environment_allowlist_excludes_secrets_from_real_probe_process(self):
        parent_environment = {
            "PATH": os.environ["PATH"],
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONPATH": "parent-pythonpath-must-not-reach-worker",
            "AWS_SECRET_ACCESS_KEY": "aws-secret-must-not-reach-worker",
            "API_TOKEN": "token-must-not-reach-worker",
            "SPINQ_API_KEY": "spinq-key-must-not-reach-worker",
            "ORIGINQ_SECRET": "originq-secret-must-not-reach-worker",
            "LOOMQ_BRAKET_PYTHON": "C:/braket/python.exe",
        }
        system_root = os.environ.get("SystemRoot")
        if system_root:
            parent_environment["SystemRoot"] = system_root

        with patch.dict(os.environ, parent_environment, clear=True):
            allowed_environment = braket._worker_environment()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import json, os; print(json.dumps(dict(os.environ)))",
                ],
                text=True,
                capture_output=True,
                check=True,
                env=allowed_environment,
            )

        child_environment = json.loads(completed.stdout)
        self.assertEqual(child_environment["PATH"], parent_environment["PATH"])
        for name in ("LANG", "LC_ALL"):
            self.assertEqual(child_environment[name], parent_environment[name])
        if system_root:
            child_system_root = next(
                value
                for name, value in child_environment.items()
                if name.casefold() == "systemroot"
            )
            self.assertEqual(child_system_root, system_root)
        for name in (
            "AWS_SECRET_ACCESS_KEY",
            "API_TOKEN",
            "SPINQ_API_KEY",
            "ORIGINQ_SECRET",
            "LOOMQ_BRAKET_PYTHON",
            "PYTHONPATH",
        ):
            self.assertNotIn(name, child_environment)

    def test_direct_path_does_not_start_worker_without_environment_configuration(self):
        class Program:
            def __init__(self, *, source):
                self.source = source

        class Task:
            id = "braket-direct-task"

            def result(self):
                return SimpleNamespace(measurement_counts={"0": 1}, task_metadata={})

        class LocalSimulator:
            def run(self, program, *, shots):
                return Task()

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator, version="1.108.0")
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", return_value=sdk):
                with patch.object(braket.subprocess, "run") as run_worker:
                    raw = run_braket(self.native_ir, 1)

        run_worker.assert_not_called()
        self.assertEqual(raw.job_id, "braket-direct-task")

    def test_missing_dependency_names_amazon_braket_sdk(self):
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", side_effect=ImportError("missing")):
                with self.assertRaisesRegex(DependencyUnavailableError, "amazon-braket-sdk") as raised:
                    run_braket(self.native_ir, 4)
        self.assertIsInstance(raised.exception.__cause__, ImportError)

    def test_lazy_import_reads_braket_sdk_version_module(self):
        sdk_module = ModuleType("braket")
        sdk_module.__path__ = []
        devices_module = ModuleType("braket.devices")
        devices_module.LocalSimulator = object
        ir_module = ModuleType("braket.ir")
        ir_module.__path__ = []
        openqasm_module = ModuleType("braket.ir.openqasm")
        openqasm_module.Program = object
        version_module = ModuleType("braket._sdk")
        version_module.__version__ = "1.108.0-sdk"

        with patch.dict(
            sys.modules,
            {
                "braket": sdk_module,
                "braket.devices": devices_module,
                "braket.ir": ir_module,
                "braket.ir.openqasm": openqasm_module,
                "braket._sdk": version_module,
            },
        ):
            imported = braket._import_braket()

        self.assertEqual(imported.version, "1.108.0-sdk")

    def test_lazy_import_falls_back_to_braket_module_version(self):
        sdk_module = ModuleType("braket")
        sdk_module.__path__ = []
        sdk_module.__version__ = "1.108.0-module"
        devices_module = ModuleType("braket.devices")
        devices_module.LocalSimulator = object
        ir_module = ModuleType("braket.ir")
        ir_module.__path__ = []
        openqasm_module = ModuleType("braket.ir.openqasm")
        openqasm_module.Program = object

        with patch.dict(
            sys.modules,
            {
                "braket": sdk_module,
                "braket.devices": devices_module,
                "braket.ir": ir_module,
                "braket.ir.openqasm": openqasm_module,
                "braket._sdk": None,
            },
        ):
            imported = braket._import_braket()

        self.assertEqual(imported.version, "1.108.0-module")

    def test_executes_openqasm_program_on_local_simulator(self):
        calls = {}

        class Program:
            def __init__(self, *, source):
                self.source = source
                calls["program"] = self

        class Task:
            id = "braket-task-1"

            def result(self):
                calls["result_called"] = True
                return SimpleNamespace(
                    measurement_counts={"0": 4},
                    task_metadata={"id": "braket-result-1"},
                )

        class LocalSimulator:
            def run(self, program, *, shots):
                calls["run"] = (program, shots)
                return Task()

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator, version="1.108.0-test")
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", return_value=sdk):
                raw = run_braket(self.native_ir, 4)

        self.assertIsInstance(raw, RawExecution)
        self.assertEqual(raw.backend, "braket_local_simulator")
        self.assertEqual(raw.job_id, "braket-task-1")
        self.assertEqual(raw.counts, {"0": 4})
        self.assertEqual(raw.key_format, "binary")
        self.assertTrue(raw.reverse_bits)
        self.assertEqual(
            raw.metadata,
            {
                "target": "braket",
                "provider": "braket",
                "sdk": "amazon-braket-sdk",
                "sdk_version": "1.108.0-test",
            },
        )
        self.assertEqual(calls["program"].source, self.native_ir)
        self.assertEqual(calls["run"], (calls["program"], 4))
        self.assertTrue(calls["result_called"])

    def test_direct_path_uses_execution_only_compatibility_source(self):
        calls = {}
        native_ir = (
            "OPENQASM 3.0;\n"
            "include \"stdgates.inc\";\n"
            "bit[1] c;\n"
            "qubit[1] q;\n"
            "x q[0];\n"
            "c[0] = measure q[0];\n"
        )

        class Program:
            def __init__(self, *, source):
                calls["source"] = source

        class Task:
            id = "braket-direct-compatibility"

            def result(self):
                return SimpleNamespace(measurement_counts={"1": 1}, task_metadata={})

        class LocalSimulator:
            def run(self, program, *, shots):
                return Task()

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator, version="1.108.0-test")
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", return_value=sdk):
                raw = run_braket(native_ir, 1)

        self.assertEqual(raw.counts, {"1": 1})
        self.assertNotIn('include "stdgates.inc";', calls["source"])
        self.assertIn("x q[0];", calls["source"])

    def test_uses_braket_metadata_id_attribute_mapping_or_uuid_fallback(self):
        class Program:
            def __init__(self, *, source):
                self.source = source

        for metadata, expected_job_id in (
            (SimpleNamespace(id="braket-metadata-attribute"), "braket-metadata-attribute"),
            ({"id": "braket-metadata-mapping"}, "braket-metadata-mapping"),
            (SimpleNamespace(), None),
        ):
            class Task:
                id = None

                def result(self):
                    return SimpleNamespace(measurement_counts={"0": 1}, task_metadata=metadata)

            class LocalSimulator:
                def run(self, program, *, shots):
                    return Task()

            sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator)
            with self.subTest(metadata=metadata):
                with self._direct_braket_environment():
                    with patch.object(braket, "_import_braket", return_value=sdk):
                        raw = run_braket(self.native_ir, 1)
                if expected_job_id is None:
                    self.assertRegex(raw.job_id, r"^braket-local-[0-9a-f-]{36}$")
                    self.assertEqual(raw.metadata["sdk_version"], "unknown")
                else:
                    self.assertEqual(raw.job_id, expected_job_id)

    def test_provisional_braket_bit_order_is_plumbed_without_claiming_sdk_validation(self):
        class Program:
            def __init__(self, *, source):
                self.source = source

        class Task:
            id = "braket-task-asymmetric"

            def result(self):
                return SimpleNamespace(measurement_counts={"10": 4}, task_metadata=SimpleNamespace())

        class LocalSimulator:
            def run(self, program, *, shots):
                return Task()

        native_ir = "OPENQASM 3.0;\nbit[2] c;\nqubit[2] q;\n"
        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator)
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", return_value=sdk):
                raw = run_braket(native_ir, 4)

        self.assertTrue(raw.reverse_bits)
        self.assertEqual(normalize_counts(raw.counts, 2, raw.key_format, raw.reverse_bits), {"01": 4})

    def test_provider_failure_is_redacted_and_translated(self):
        provider_error = RuntimeError("secret=top-secret")

        class Program:
            def __init__(self, *, source):
                self.source = source

        class LocalSimulator:
            def run(self, program, *, shots):
                raise provider_error

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator)
        with self._direct_braket_environment():
            with patch.object(braket, "_import_braket", return_value=sdk):
                with self.assertRaisesRegex(ProviderExecutionError, "Braket") as raised:
                    run_braket(self.native_ir, 4)

        self.assertIs(raised.exception.__cause__, provider_error)
        self.assertNotIn("top-secret", str(raised.exception))


class BraketWorkerTests(unittest.TestCase):
    native_ir = "OPENQASM 3.0;\nbit[1] c;\nqubit[1] q;\nc[0] = measure q[0];\n"

    def test_execute_payload_runs_exact_local_sdk_chain_and_returns_protocol_response(self):
        calls = {}

        class Program:
            def __init__(self, *, source):
                self.source = source
                calls["program"] = self

        class Task:
            id = "braket-worker-task"

            def result(self):
                calls["result"] = True
                return SimpleNamespace(measurement_counts={"0": 2, "1": 2}, task_metadata={})

        class LocalSimulator:
            def run(self, program, *, shots):
                calls["run"] = (program, shots)
                return Task()

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator, version="1.108.0-test")
        with patch.object(braket_worker, "_import_braket", return_value=sdk):
            response = braket_worker.execute_payload(
                {"native_ir": self.native_ir, "shots": 4}
            )

        self.assertEqual(
            response,
            {
                "counts": {"0": 2, "1": 2},
                "job_id": "braket-worker-task",
                "sdk_version": "1.108.0-test",
            },
        )
        self.assertEqual(calls["program"].source, self.native_ir)
        self.assertEqual(calls["run"], (calls["program"], 4))
        self.assertTrue(calls["result"])

    def test_execute_payload_removes_only_standalone_stdgates_include_before_program(self):
        calls = {}
        native_ir = (
            "OPENQASM 3.0;\n"
            "\tinclude \t\"stdgates.inc\" \t;\t\n"
            "include \"custom.inc\";\n"
            "include \"stdgates.inc\"; // leave this untouched\n"
            "qubit[1] q;\n"
            "bit[1] c;\n"
            "c[0] = measure q[0];\n"
        )
        expected_execution_source = (
            "OPENQASM 3.0;\n"
            "include \"custom.inc\";\n"
            "include \"stdgates.inc\"; // leave this untouched\n"
            "qubit[1] q;\n"
            "bit[1] c;\n"
            "c[0] = measure q[0];\n"
        )

        class Program:
            def __init__(self, *, source):
                calls["source"] = source

        class Task:
            def result(self):
                return SimpleNamespace(measurement_counts={"0": 1}, task_metadata={})

        class LocalSimulator:
            def run(self, program, *, shots):
                return Task()

        sdk = SimpleNamespace(Program=Program, LocalSimulator=LocalSimulator, version="1.108.0")
        with patch.object(braket_worker, "_import_braket", return_value=sdk):
            braket_worker.execute_payload({"native_ir": native_ir, "shots": 1})

        self.assertEqual(calls["source"], expected_execution_source)

    def test_execution_source_injects_only_missing_standard_gate_definitions(self):
        native_ir = (
            "OPENQASM 3.0;\n"
            "include \"stdgates.inc\";\n"
            "bit[3] c;\n"
            "qubit[3] q;\n"
            "sdg q[0];\n"
            "tdg q[1];\n"
            "cp(0.5) q[0], q[1];\n"
            "ccx q[0], q[1], q[2];\n"
            "c = measure q;\n"
        )
        expected_execution_source = (
            "OPENQASM 3.0;\n"
            "gate sdg a { rz(-pi/2) a; }\n"
            "gate tdg a { rz(-pi/4) a; }\n"
            "gate cp(theta) a, b {\n"
            "  rz(theta/2) a;\n"
            "  rz(theta/2) b;\n"
            "  cnot a, b;\n"
            "  rz(-theta/2) b;\n"
            "  cnot a, b;\n"
            "}\n"
            "gate ccx a, b, c {\n"
            "  h c;\n"
            "  cnot b, c;\n"
            "  tdg c;\n"
            "  cnot a, c;\n"
            "  t c;\n"
            "  cnot b, c;\n"
            "  tdg c;\n"
            "  cnot a, c;\n"
            "  t b;\n"
            "  t c;\n"
            "  h c;\n"
            "  cnot a, b;\n"
            "  t a;\n"
            "  tdg b;\n"
            "  cnot a, b;\n"
            "}\n"
            "bit[3] c;\n"
            "qubit[3] q;\n"
            "sdg q[0];\n"
            "tdg q[1];\n"
            "cp(0.5) q[0], q[1];\n"
            "ccx q[0], q[1], q[2];\n"
            "c = measure q;\n"
        )

        self.assertEqual(braket_worker._execution_source(native_ir), expected_execution_source)
    def test_execute_payload_rejects_nonexact_or_invalid_payloads_before_sdk_import(self):
        invalid_payloads = (
            None,
            [],
            {},
            {"native_ir": self.native_ir},
            {"shots": 1},
            {"native_ir": self.native_ir, "shots": 1, "extra": "no"},
            {"native_ir": "", "shots": 1},
            {"native_ir": b"qasm", "shots": 1},
            {"native_ir": self.native_ir, "shots": True},
            {"native_ir": self.native_ir, "shots": 0},
        )
        with patch.object(braket_worker, "_import_braket") as import_sdk:
            for payload in invalid_payloads:
                with self.subTest(payload=repr(payload)):
                    with self.assertRaises((TypeError, ValueError)):
                        braket_worker.execute_payload(payload)

        import_sdk.assert_not_called()

    def test_main_emits_one_json_response_and_redacts_worker_errors(self):
        output = io.StringIO()
        errors = io.StringIO()
        expected_response = {"counts": {"0": 1}, "sdk_version": "1.108.0"}
        with patch.object(braket_worker.sys, "stdin", io.StringIO('{"native_ir":"qasm","shots":1}')):
            with patch.object(braket_worker.sys, "stdout", output):
                with patch.object(braket_worker.sys, "stderr", errors):
                    with patch.object(
                        braket_worker, "execute_payload", return_value=expected_response
                    ) as execute:
                        self.assertEqual(braket_worker.main(), 0)

        execute.assert_called_once_with({"native_ir": "qasm", "shots": 1})
        self.assertEqual(json.loads(output.getvalue()), expected_response)
        self.assertEqual(errors.getvalue(), "")

        output = io.StringIO()
        errors = io.StringIO()
        fake_credential = "worker-credential-should-never-leak"
        with patch.object(braket_worker.sys, "stdin", io.StringIO(f"not-json {fake_credential}")):
            with patch.object(braket_worker.sys, "stdout", output):
                with patch.object(braket_worker.sys, "stderr", errors):
                    self.assertEqual(braket_worker.main(), 1)

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "Braket worker failed\n")
        self.assertNotIn(fake_credential, errors.getvalue())


class SDKVersionTests(unittest.TestCase):
    def test_installed_sdk_version_prefers_distribution_metadata(self):
        with patch.object(_common, "distribution_version", return_value="0.2.4"):
            self.assertEqual(_common.installed_sdk_version("spinqit", "unknown"), "0.2.4")


class RunnerValidationAndDispatchTests(unittest.TestCase):
    native_ir = "OPENQASM 2.0;\n"

    def test_invalid_native_ir_and_shots_raise_loomq_error_before_sdk_import(self):
        invalid_native_ir = (None, 1, b"qasm", "", "   \n")
        invalid_shots = (True, False, 1.5, 0, -1)

        for runner in (run_spinq, run_originq, run_braket):
            for native_ir in invalid_native_ir:
                with self.subTest(runner=runner.__name__, native_ir=repr(native_ir)):
                    with self.assertRaises(ProviderExecutionError):
                        runner(native_ir, 1)
            for shots in invalid_shots:
                with self.subTest(runner=runner.__name__, shots=repr(shots)):
                    with self.assertRaises(ProviderExecutionError):
                        runner(self.native_ir, shots)

    def test_dispatcher_selects_exact_target_and_rejects_unknown_target(self):
        expected = RawExecution("fake", None, {"0": 1})
        fake_runner = unittest.mock.Mock(return_value=expected)
        with patch("starter_kit.loomq_l1.runners._RUNNERS", {"spinq": fake_runner}):
            self.assertIs(run(self.native_ir, "spinq", 1), expected)
        fake_runner.assert_called_once_with(self.native_ir, 1)

        with self.assertRaises(UnsupportedTargetError):
            run(self.native_ir, "unknown", 1)

    def test_requirements_are_exact_direct_pins(self):
        requirements = Path(__file__).parents[2] / "requirements.txt"
        self.assertEqual(
            requirements.read_text(encoding="utf-8"),
            "amazon-braket-sdk==1.108.0\n"
            "numpy==1.26.4\n"
            "pyqpanda==3.8.5\n"
            "spinqit==0.2.4\n",
        )


if __name__ == "__main__":
    unittest.main()
