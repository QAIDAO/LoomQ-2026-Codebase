#!/usr/bin/env python3
"""Run exactly one authorized OriginQ Bell-Phi+ tomography experiment.

The submit command has one external side effect: one call to
``run_quantum_state_tomography``.  It immediately persists the returned task
identifier and a raw provider query.  ``--collect`` is read-only and is the
only command permitted after submission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FILES = ROOT / "starter_kit" / "evidence" / "files"
PREFIX = "originq_tomography_bell_phi_plus"
RECEIPT = FILES / f"{PREFIX}-submission.json"
RAW = FILES / f"{PREFIX}-provider.raw.json"
METADATA = FILES / f"{PREFIX}-metadata.json"
QASM = FILES / f"{PREFIX}-logical-preparation.qasm"
CORRECTED_RECEIPT = FILES / f"{PREFIX}-corrected-submission.json"
CORRECTED_RAW = FILES / f"{PREFIX}-corrected-provider.raw.json"
CORRECTED_METADATA = FILES / f"{PREFIX}-corrected-metadata.json"
CORRECTED_QASM = FILES / f"{PREFIX}-corrected-input.qasm"
CORRECTED_ORIGINIR = FILES / f"{PREFIX}-corrected-program.originir"
QASM_TEXT = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
h q[0];
cx q[0],q[1];
"""
CORRECTED_QASM_TEXT = """OPENQASM 2.0;
include \"qelib1.inc\";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
"""
DEVICE = "WK_C180_2"
QUBITS = [49, 58]
SHOTS = 1000
RAW_FIELDS = [
    "probCount", "taskResult", "mappingQubit", "srcQubits", "measureQubits",
    "QProg", "startTime", "submitTime", "endTime", "createdAt", "completedAt",
]


def _token() -> str:
    value = os.environ.get("LOOMQ_ORIGINQ_TOKEN", "")
    if not value:
        raise RuntimeError("LOOMQ_ORIGINQ_TOKEN is not configured")
    return value


def _without_secret(value: Any, token: str) -> Any:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, list):
        return [_without_secret(item, token) for item in value]
    if isinstance(value, dict):
        return {key: _without_secret(item, token) for key, item in value.items()}
    return value


def _write_json(path: Path, payload: Any, token: str) -> None:
    path.write_text(
        json.dumps(_without_secret(payload, token), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _field(result: Any, name: str) -> Any:
    try:
        return result[name]
    except (KeyError, IndexError):
        return None


def _provider_snapshot(job: Any, token: str) -> dict[str, Any]:
    queried = job.query(keys=RAW_FIELDS)
    status = str(queried.job_status())
    # ``query`` omits qstTaskResult/qstFidelity on this SDK, while ``result``
    # exposes them after completion.  This is a read-only retrieval of the
    # same existing task, never a second submission.
    result = job.result() if status == "JobStatus.FINISHED" else queried
    raw_origin = result.origin_data()
    status = str(result.job_status())
    completed = status == "JobStatus.FINISHED"
    return {
        "origin_data": raw_origin,
        "job_id": result.job_id(),
        "job_status": status,
        "timing_info": result.timing_info(),
        "fields": {field: _field(result, field) for field in RAW_FIELDS},
        "state_fidelity": _try(lambda: result.get_state_fidelity()) if completed else None,
        "density_matrix": _try(lambda: result.get_state_tomography_density()) if completed else None,
        "counts": _try(lambda: result.get_counts()) if completed else None,
        "probabilities": _try(lambda: result.get_probs()) if completed else None,
        "result_availability": "complete" if completed else "unavailable: provider task did not finish",
    }


def _try(fn: Any) -> Any:
    try:
        return fn()
    except (KeyError, IndexError, RuntimeError, ValueError, TypeError) as exc:
        return {"unavailable": type(exc).__name__, "message": str(exc)}


def _service_and_backend(token: str) -> tuple[Any, Any]:
    from pyqpanda3 import qcloud

    service = qcloud.QCloudService(api_key=token)
    availability = service.backends()
    if availability.get(DEVICE) is not True:
        raise RuntimeError(f"{DEVICE} is not currently available")
    backend = service.backend(DEVICE)
    info = backend.chip_info()
    if info.chip_id() != DEVICE or not set(QUBITS).issubset(set(info.available_qubits())):
        raise RuntimeError(f"{DEVICE} does not expose the requested physical qubit block")
    if not hasattr(backend, "run_quantum_state_tomography"):
        raise RuntimeError(f"{DEVICE} does not expose tomography support")
    return qcloud, backend


def _program_and_options(qcloud: Any) -> tuple[Any, Any]:
    from pyqpanda3.core import CNOT, H, QProg

    options = qcloud.QCloudOptions()
    options.set_mapping(True)
    options.set_specified_block(QUBITS)
    options.set_is_prob_counts(False)
    program = QProg()
    program << H(0) << CNOT(0, 1)
    return program, options


def _corrected_program_and_options(qcloud: Any) -> tuple[Any, Any]:
    from pyqpanda3.core import CNOT, H, QProg, measure

    options = qcloud.QCloudOptions()
    options.set_mapping(True)
    options.set_specified_block(QUBITS)
    options.set_is_prob_counts(False)
    program = QProg()
    program << H(0) << CNOT(0, 1) << measure(0, 0) << measure(1, 1)
    return program, options


def corrected_preflight(*, save: bool) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Prove the measured tomography input and Bell preparation locally."""
    token = _token()
    qcloud, backend = _service_and_backend(token)
    program, options = _corrected_program_and_options(qcloud)
    pairs = [
        [qubit.get_qubit_addr(), cbit.get_cbit_addr()]
        for qubit, cbit in program.get_measure_qubits_cbits()
    ]
    originir = program.originir()
    gates = program.count_ops()
    measurement_gate = (
        len(program.get_measure_nodes()) == 2
        and pairs == [[0, 0], [1, 1]]
        and gates == {"H": 1, "CNOT": 1}
        and originir.count("MEASURE") == 2
    )
    if not measurement_gate:
        raise RuntimeError("PROGRAM_MEASUREMENT_GATE failed")
    from starter_kit.loomq.compiler.parser import parse_qasm
    from starter_kit.loomq.simulator import probabilities

    distribution = probabilities(parse_qasm(CORRECTED_QASM_TEXT))
    expected = {"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5}
    semantic_pass = all(abs(float(distribution.get(bit, 0.0)) - value) < 1e-12 for bit, value in expected.items())
    if not semantic_pass:
        raise RuntimeError(f"reference Bell semantic check failed: {distribution}")
    report = {
        "PROGRAM_MEASUREMENT_GATE": "PASS",
        "measurement_count": len(program.get_measure_nodes()),
        "measurement_pairs": pairs,
        "gate_counts": gates,
        "originir": originir,
        "reference_simulator": {"PASS": True, "distribution": {bit: distribution.get(bit, 0.0) for bit in expected}},
        "backend": DEVICE,
        "requested_physical_qubits": QUBITS,
        "shots": SHOTS,
        "options": {
            "mapping": options.is_mapping(),
            "specified_block": options.specified_block(),
            "prob_counts": options.is_prob_counts(),
        },
    }
    if save:
        FILES.mkdir(parents=True, exist_ok=True)
        CORRECTED_QASM.write_text(CORRECTED_QASM_TEXT, encoding="utf-8")
        CORRECTED_ORIGINIR.write_text(originir, encoding="utf-8")
        _write_json(FILES / f"{PREFIX}-corrected-preflight.json", report, token)
    return backend, program, options, report


def submit_once() -> int:
    token = _token()
    if RECEIPT.exists():
        raise RuntimeError(f"refusing a second tomography submission; receipt already exists: {RECEIPT}")
    FILES.mkdir(parents=True, exist_ok=True)
    QASM.write_text(QASM_TEXT, encoding="utf-8")
    qcloud, backend = _service_and_backend(token)
    program, options = _program_and_options(qcloud)
    try:
        # The only QPU submission call in this program.
        job = backend.run_quantum_state_tomography(program, SHOTS, options)
        job_id = job.job_id()
    except Exception as exc:
        _write_json(RECEIPT, {"submission": "failed", "error": str(exc)}, token)
        raise
    _write_json(RECEIPT, {
        "submission": "accepted_by_sdk", "job_id": job_id, "backend": DEVICE,
        "shots": SHOTS, "requested_physical_qubits": QUBITS,
        "logical_preparation_sha256": hashlib.sha256(QASM_TEXT.encode("utf-8")).hexdigest(),
    }, token)
    try:
        _write_json(RAW, _provider_snapshot(job, token), token)
    except Exception as exc:
        _write_json(RAW, {"job_id": job_id, "initial_query_error": str(exc)}, token)
    print(f"job_id={job_id}")
    return 0


def collect() -> int:
    token = _token()
    if not RECEIPT.exists():
        raise RuntimeError("no tomography submission receipt exists")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    job_id = receipt.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError("receipt has no submitted job ID")
    qcloud, _backend = _service_and_backend(token)
    job = qcloud.QCloudJob(job_id)
    snapshot = _provider_snapshot(job, token)
    _write_json(RAW, snapshot, token)
    _write_json(METADATA, {
        "job_id": job_id, "backend": DEVICE, "shots": SHOTS,
        "requested_physical_qubits": QUBITS,
        "provider_status": snapshot["job_status"],
        "provider_timing_info": snapshot["timing_info"],
        "logical_preparation_sha256": hashlib.sha256(QASM_TEXT.encode("utf-8")).hexdigest(),
        "raw_provider_response_sha256": hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
    }, token)
    print(f"job_id={job_id}")
    print(f"status={snapshot['job_status']}")
    return 0


def submit_corrected_once() -> int:
    token = _token()
    if not RECEIPT.exists():
        raise RuntimeError("attempt 1 receipt is missing; corrected retry is not authorized")
    if CORRECTED_RECEIPT.exists():
        raise RuntimeError("refusing a third tomography submission; corrected receipt already exists")
    first = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if first.get("job_id") != "EE7D22A38D5A9F246A2031BC7A31C3AD":
        raise RuntimeError("attempt 1 receipt does not match the authorized missing-measurements failure")
    backend, program, options, preflight = corrected_preflight(save=True)
    try:
        # The only corrected retry authorized after the measurement gate passed.
        job = backend.run_quantum_state_tomography(program, SHOTS, options)
        job_id = job.job_id()
    except Exception as exc:
        _write_json(CORRECTED_RECEIPT, {"submission": "failed", "error": str(exc)}, token)
        raise
    _write_json(CORRECTED_RECEIPT, {
        "attempt": 2, "submission": "accepted_by_sdk", "job_id": job_id,
        "backend": DEVICE, "shots": SHOTS, "requested_physical_qubits": QUBITS,
        "input_kind": "corrected measured Bell Phi+ tomography input",
        "program_measurement_gate": preflight["PROGRAM_MEASUREMENT_GATE"],
        "logical_input_sha256": hashlib.sha256(CORRECTED_QASM_TEXT.encode("utf-8")).hexdigest(),
    }, token)
    try:
        _write_json(CORRECTED_RAW, _provider_snapshot(job, token), token)
    except Exception as exc:
        _write_json(CORRECTED_RAW, {"job_id": job_id, "initial_query_error": str(exc)}, token)
    print(f"job_id={job_id}")
    return 0


def collect_corrected() -> int:
    token = _token()
    if not CORRECTED_RECEIPT.exists():
        raise RuntimeError("no corrected tomography submission receipt exists")
    receipt = json.loads(CORRECTED_RECEIPT.read_text(encoding="utf-8"))
    job_id = receipt.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise RuntimeError("corrected receipt has no submitted job ID")
    qcloud, _backend = _service_and_backend(token)
    snapshot = _provider_snapshot(qcloud.QCloudJob(job_id), token)
    _write_json(CORRECTED_RAW, snapshot, token)
    _write_json(CORRECTED_METADATA, {
        "attempt": 2, "job_id": job_id, "backend": DEVICE, "shots": SHOTS,
        "requested_physical_qubits": QUBITS, "input_kind": "corrected measured Bell Phi+ tomography input",
        "provider_status": snapshot["job_status"], "provider_timing_info": snapshot["timing_info"],
        "logical_input_sha256": hashlib.sha256(CORRECTED_QASM_TEXT.encode("utf-8")).hexdigest(),
        "raw_provider_response_sha256": hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "user_confirmed_free_quota_seconds": 118.760,
        "user_confirmed_no_paid_charge": True,
    }, token)
    print(f"job_id={job_id}")
    print(f"status={snapshot['job_status']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit-one-tomography", action="store_true")
    mode.add_argument("--collect", action="store_true")
    mode.add_argument("--preflight-corrected", action="store_true")
    mode.add_argument("--submit-corrected-one-tomography", action="store_true")
    mode.add_argument("--collect-corrected", action="store_true")
    args = parser.parse_args()
    if args.submit_one_tomography:
        return submit_once()
    if args.collect:
        return collect()
    if args.preflight_corrected:
        _backend, _program, _options, report = corrected_preflight(save=True)
        print(f"PROGRAM_MEASUREMENT_GATE={report['PROGRAM_MEASUREMENT_GATE']}")
        print(f"reference_simulator={report['reference_simulator']['PASS']}")
        return 0
    if args.submit_corrected_one_tomography:
        return submit_corrected_once()
    return collect_corrected()


if __name__ == "__main__":
    raise SystemExit(main())
