import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

from starter_kit import adapter
from starter_kit.qasm_L1.execution import ExecutionResult, save_hardware_evidence
from starter_kit.qasm_L1 import runners


class RealRunnerTests(unittest.TestCase):
    def test_adapter_cli_runs_every_qasm_in_a_directory(self):
        result = {
            "counts": {"0": 4},
            "meta": {"artifact_files": {"program": "circuit.qasm", "result": "result.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            input_directory = Path(directory) / "circuits"
            input_directory.mkdir()
            (input_directory / "a.qasm").write_text("OPENQASM 2.0;", encoding="utf-8")
            (input_directory / "b.qasm").write_text("OPENQASM 2.0;", encoding="utf-8")
            with mock.patch.object(adapter, "run_and_save", return_value=result) as run_saved:
                exit_code = adapter.main(
                    [
                        str(input_directory),
                        "--target",
                        "braket",
                        "--shots",
                        "4",
                        "--output",
                        str(Path(directory) / "output"),
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_saved.call_count, 2)

    def test_adapter_cli_real_switch_uses_real_runner(self):
        result = {
            "counts": {"0": 4},
            "meta": {"evidence_files": {"program": "circuit.qasm", "result": "result.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            circuit = Path(directory) / "bell.qasm"
            circuit.write_text("OPENQASM 2.0;", encoding="utf-8")
            with mock.patch.dict(
                "os.environ", {"BRAKET_DEVICE_ARN": "arn:aws:braket:test::device/qpu/mock/device"}
            ), mock.patch.object(adapter, "run_real", return_value=result) as run_real:
                exit_code = adapter.main(
                    [str(circuit), "--target", "braket", "--shots", "4", "--real"]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_real.call_count, 1)
        self.assertEqual(
            run_real.call_args.kwargs["device_arn"],
            "arn:aws:braket:test::device/qpu/mock/device",
        )

    def test_adapter_run_and_save_exports_local_program_and_result(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q -> c;
'''
        execution = ExecutionResult(
            "spinq",
            "LOCAL-TASK-1",
            4,
            {"1": 4},
            "2026-08-09T00:00:00+00:00",
        )
        local_runner = mock.Mock(return_value=execution)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            adapter.RUNNERS, {"spinq": local_runner}
        ):
            result = adapter.run_and_save(qasm, "spinq", 4, directory)
            paths = result["meta"]["artifact_files"]
            program = Path(paths["program"]).read_text(encoding="utf-8")
            saved_result = json.loads(Path(paths["result"]).read_text(encoding="utf-8"))

        self.assertIn("OPENQASM 2.0;", program)
        self.assertEqual(saved_result["job_id"], "LOCAL-TASK-1")
        self.assertEqual(local_runner.call_count, 1)

    def test_adapter_run_real_exports_evidence_without_changing_run_contract(self):
        qasm = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
x q[0];
measure q -> c;
'''
        execution = ExecutionResult(
            "spinq_real",
            "SPIN-TASK-2",
            4,
            {"1": 4},
            "2026-08-09T00:00:00+00:00",
            raw_result={"task_code": "SPIN-TASK-2", "token": "do-not-save"},
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            adapter.REAL_RUNNERS, {"spinq": mock.Mock(return_value=execution)}
        ):
            result = adapter.run_real(
                qasm,
                "spinq",
                4,
                username="alice",
                keyfile="/keys/alice.pem",
                evidence_directory=directory,
            )
            raw_path = Path(result["meta"]["evidence_files"]["raw_result"])
            raw = json.loads(raw_path.read_text(encoding="utf-8"))

        self.assertEqual(result["job_id"], "SPIN-TASK-2")
        self.assertEqual(raw["token"], "[REDACTED]")

    def test_spinq_preserves_task_code_and_omits_explicit_measurement(self):
        observed = {}

        class Compiler:
            def compile(self, path, level):
                observed["source"] = Path(path).read_text(encoding="utf-8")
                self.assertEqual(level, 0)
                return "spin-ir"

            def assertEqual(self, left, right):
                unittest.TestCase().assertEqual(left, right)

        class Config:
            def configure_platform(self, value):
                observed["platform"] = value

            def configure_shots(self, value):
                observed["shots"] = value

            def configure_task(self, name, description):
                observed["task"] = (name, description)

        class Cloud:
            def execute(self, ir, _config):
                self_ir = ir
                self.assertEqual(self_ir, "spin-ir")
                return SimpleNamespace(
                    task_code="SPIN-TASK-1",
                    task_name="LoomQ L1",
                    platform="gemini_vp",
                    counts={"01": 8},
                    probabilities={"01": 1.0},
                )

            def assertEqual(self, left, right):
                unittest.TestCase().assertEqual(left, right)

        spinqit = ModuleType("spinqit")
        spinqit.SpinQCloudConfig = Config
        spinqit.get_spinq_cloud = lambda *_args: Cloud()
        compiler_module = ModuleType("spinqit.compiler.qasm_compiler")
        compiler_module.QASMCompiler = Compiler
        modules = {
            "spinqit": spinqit,
            "spinqit.compiler": ModuleType("spinqit.compiler"),
            "spinqit.compiler.qasm_compiler": compiler_module,
        }
        with mock.patch.dict(sys.modules, modules):
            result = runners.run_spinq_real(
                "OPENQASM 2.0;\nqreg q[1];\ncreg c[1];\nmeasure q -> c;\n",
                8,
                username="alice",
                keyfile="/keys/alice.pem",
                platform="gemini_vp",
            )

        self.assertEqual(result.job_id, "SPIN-TASK-1")
        self.assertEqual(result.counts, {"10": 8})
        self.assertNotIn("measure ", observed["source"])

    def test_braket_preserves_quantum_task_id(self):
        observed = {}

        class Program:
            def __init__(self, source):
                self.source = source

        class Device:
            def __init__(self, arn):
                observed["arn"] = arn

            def run(self, program, *args, **kwargs):
                observed["source"] = program.source
                observed["args"] = args
                observed["kwargs"] = kwargs
                result = SimpleNamespace(
                    measurement_counts={"01": 5},
                    task_metadata={"id": "AWS-TASK-1"},
                    measured_qubits=[0, 1],
                    additional_metadata={"provider": "mock"},
                )
                return SimpleNamespace(id="AWS-TASK-1", result=lambda: result)

        aws_module = ModuleType("braket.aws")
        aws_module.AwsDevice = Device
        openqasm_module = ModuleType("braket.ir.openqasm")
        openqasm_module.Program = Program
        with mock.patch.dict(
            sys.modules,
            {"braket.aws": aws_module, "braket.ir.openqasm": openqasm_module},
        ):
            result = runners.run_braket_real(
                'OPENQASM 3.0;\ninclude "stdgates.inc";\n',
                5,
                device_arn="arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1",
                s3_destination_folder=("bucket", "tasks"),
            )

        self.assertEqual(result.job_id, "AWS-TASK-1")
        self.assertEqual(result.counts, {"10": 5})
        self.assertNotIn("stdgates.inc", observed["source"])

    def test_originq_uses_transpiled_originir_and_named_backend(self):
        observed = {}

        class Options:
            pass

        class CloudResult:
            def get_probs_list(self):
                return [{"00": 0.51, "11": 0.49}]

        class Job:
            def job_id(self):
                return "ORIGIN-TASK-1"

            def result(self):
                return CloudResult()

        class Backend:
            def run(self, program, shots, options):
                observed["run"] = (program, shots, options)
                return Job()

        class Service:
            def __init__(self, api_key):
                observed["token"] = api_key

            def backends(self):
                return {"WK_C180": True, "72": False}

            def backend(self, name):
                observed["backend"] = name
                return Backend()

        def convert_originir(source):
            observed["originir"] = source
            return "QPROG"

        pyqpanda3 = ModuleType("pyqpanda3")
        compiler = ModuleType("pyqpanda3.intermediate_compiler")
        compiler.convert_originir_string_to_qprog = convert_originir
        qcloud = ModuleType("pyqpanda3.qcloud")
        qcloud.QCloudOptions = Options
        qcloud.QCloudService = Service
        with mock.patch.dict(
            sys.modules,
            {
                "pyqpanda3": pyqpanda3,
                "pyqpanda3.intermediate_compiler": compiler,
                "pyqpanda3.qcloud": qcloud,
            },
        ):
            result = runners.run_originq_real(
                "QINIT 2\nCREG 2\n",
                7,
                token="origin-secret",
            )

        self.assertEqual(result.job_id, "ORIGIN-TASK-1")
        self.assertEqual(sum(result.counts.values()), 7)
        self.assertEqual(result.counts_source, "probabilities")
        self.assertEqual(observed["originir"], "QINIT 2\nCREG 2\n")
        self.assertEqual(observed["backend"], "WK_C180")
        self.assertEqual(observed["run"][:2], (["QPROG"], 7))
        self.assertIsInstance(observed["run"][2], Options)

    def test_originq_tolerates_known_backend_status_parse_error(self):
        class Options:
            pass

        class Result:
            def get_probs_list(self):
                return [{"0": 1.0}]

        class Job:
            def job_id(self):
                return "ORIGIN-TASK-2"

            def result(self):
                return Result()

        class Backend:
            def run(self, program, shots, options):
                return Job()

        class Service:
            def __init__(self, api_key):
                pass

            def backends(self):
                raise RuntimeError("value is not array (which is 3)")

            def backend(self, name):
                return Backend()

        compiler = ModuleType("pyqpanda3.intermediate_compiler")
        compiler.convert_originir_string_to_qprog = lambda source: "QPROG"
        qcloud = ModuleType("pyqpanda3.qcloud")
        qcloud.QCloudOptions = Options
        qcloud.QCloudService = Service
        with mock.patch.dict(
            sys.modules,
            {
                "pyqpanda3": ModuleType("pyqpanda3"),
                "pyqpanda3.intermediate_compiler": compiler,
                "pyqpanda3.qcloud": qcloud,
            },
        ):
            result = runners.run_originq_real(
                "QINIT 1\nCREG 1\nMEASURE q[0], c[0]\n",
                4,
                token="origin-secret",
            )

        self.assertEqual(result.job_id, "ORIGIN-TASK-2")
        self.assertEqual(result.raw_result["backend_check"], "sdk_response_incompatible")

    def test_hardware_evidence_is_serializable_and_redacted(self):
        execution = ExecutionResult(
            "originq_real",
            "TASK-1",
            4,
            {"00": 2, "11": 2},
            "2026-08-09T00:00:00+00:00",
            raw_result={"token": "do-not-save", "nested": {"Authorization": "secret"}},
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = save_hardware_evidence(
                execution, "QINIT 2\nCREG 2\n", directory, program_suffix="originir"
            )
            raw = json.loads(Path(paths["raw_result"]).read_text(encoding="utf-8"))
            normalized = json.loads(Path(paths["result"]).read_text(encoding="utf-8"))

        self.assertEqual(raw["token"], "[REDACTED]")
        self.assertEqual(raw["nested"]["Authorization"], "[REDACTED]")
        self.assertEqual(normalized["job_id"], "TASK-1")


if __name__ == "__main__":
    unittest.main()
