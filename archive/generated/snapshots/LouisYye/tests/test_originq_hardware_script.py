import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "starter_kit" / "examples" / "submit_originq_hardware.py"


def load_script():
    spec = importlib.util.spec_from_file_location("originq_hardware_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_submit_accepts_numeric_chip_id_and_records_device(monkeypatch, tmp_path):
    module = load_script()

    class Machine:
        received = None

        def async_real_chip_measure(self, **kwargs):
            self.received = kwargs
            return "job-180"

        def finalize(self):
            pass

    machine = Machine()
    monkeypatch.setattr(module, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(module, "TASK_PATH", tmp_path / "task.json")
    monkeypatch.setattr(module, "EVIDENCE_QASM_PATH", tmp_path / "bell.qasm")
    monkeypatch.setattr(module, "ORIGIN_IR_PATH", tmp_path / "bell.ir")
    monkeypatch.setattr(module, "_origin_ir", lambda: ("OPENQASM 2.0;", "QINIT 2\nCREG 2"))
    monkeypatch.setattr(module, "_cloud_machine", lambda: (machine, object()))

    assert module.submit(1024, True, 180) == 0
    assert machine.received["chip_id"] == 180
    metadata = json.loads(module.TASK_PATH.read_text())
    assert metadata["device"] == "origin_180"
    assert metadata["chip_id"] == 180
