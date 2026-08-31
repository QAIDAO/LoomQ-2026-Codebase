#!/usr/bin/env python3
"""Collect L1 real-device evidence for the braket platform.

The problem statement (section 7) and backend_capabilities.json both state
that the braket platform "允许以本地模拟器替代付费云端真机" - the
LocalSimulator job id is the traceable evidence for this platform, no AWS
account required.

Saves the raw result payload (job id + counts + timestamp) into
evidence/files/ for the human-review submission.
"""

import json
import math
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from adapter import transpile  # noqa: E402

try:
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program
except ImportError:  # pragma: no cover - guarded at runtime
    LocalSimulator = Program = None

_SHOTS = 8192

# Make braket's include resolution work (same trick as verify_braket.py).
_STDGATES_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stdgates.inc")
if os.path.isfile(_STDGATES_SRC):
    shutil.copy(_STDGATES_SRC, os.path.join(os.getcwd(), "stdgates.inc"))


def collect(circuit_path: str, name: str, out_dir: str) -> str:
    with open(circuit_path, encoding="utf-8") as handle:
        qasm = handle.read()
    native = transpile(qasm, "braket")
    device = LocalSimulator()
    task = device.run(Program(source=native), shots=_SHOTS)
    result = task.result()
    counts = dict(result.measurement_counts)
    job_id = result.task_metadata.id
    payload = {
        "backend": "braket_local_simulator",
        "platform": "braket",
        "job_id": job_id,
        "shots": _SHOTS,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "circuit_file": os.path.basename(circuit_path),
        "note": "按赛题第七节与 backend_capabilities.json：braket 允许以 LocalSimulator 替代付费云端真机；job_id 为 LocalSimulator 任务标识",
    }
    out_path = os.path.join(out_dir, "braket-%s-result.json" % name)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("[OK] %s job_id=%s counts=%s -> %s" % (name, job_id, counts, out_path))
    return out_path


def main() -> int:
    if LocalSimulator is None:
        print("amazon-braket-sdk not installed", file=sys.stderr)
        return 2
    examples_dir = os.path.dirname(os.path.abspath(__file__))
    circuits_dir = os.path.join(examples_dir, "..", "circuits")
    evidence_files = os.path.join(examples_dir, "..", "evidence", "files")
    os.makedirs(evidence_files, exist_ok=True)
    for name in ("bell", "ghz3"):
        collect(os.path.join(circuits_dir, name + ".qasm"), name, evidence_files)
    print("braket evidence collected -> %s" % evidence_files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
