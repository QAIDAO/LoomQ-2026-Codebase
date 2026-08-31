#!/usr/bin/env python3
"""Submit a QASM 2.0 circuit to SpinQ Cloud through the official public API.

This is a lightweight replacement for the SpinQit SDK path: it signs the
account username with the private key exactly like SpinQit 0.2.4, then builds
the same task JSON the SDK submits. It supports the subset of LoomQ gates that
can run on a 2-qubit SpinQ Gemini QPU.

Environment:
    SPINQ_USERNAME    SpinQ Cloud account username
    SPINQ_KEYFILE     path to the local RSA private key (PEM)
    SPINQ_HOST        optional, defaults to http://cloud.spinq.cn:6060
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import sys
import time
from typing import Any, Dict, List

import requests
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

try:
    from qasm_core import parse_qasm
except ImportError:
    from ..qasm_core import parse_qasm


DEFAULT_HOST = "http://cloud.spinq.cn:6060"
UA = "Mozilla/5.0"


def _sign(username: str, keyfile: str) -> str:
    with open(keyfile, encoding="utf-8") as handle:
        key = RSA.importKey(handle.read())
    digest = SHA256.new(username.encode("utf-8"))
    return base64.b64encode(PKCS1_v1_5.new(key).sign(digest)).decode("ascii")


def login(username: str, keyfile: str, host: str = DEFAULT_HOST) -> str:
    headers = {"Content-Type": "application/json", "User-Agent": UA, "Accept": "*/*"}
    response = requests.post(
        host + "/user/spinqit/login",
        data=json.dumps({"username": username, "signature": _sign(username, keyfile)}),
        headers=headers,
        timeout=30,
    )
    token = response.json().get("token")
    if not token:
        raise RuntimeError(f"SpinQ login failed: {response.text[:300]}")
    return token


def _add(operations: List[Dict[str, Any]], gate: str, tag: str, qubits: List[int], arguments: List[float]) -> None:
    operations.append({
        "timeSlot": len(operations) + 1,
        "nativeOperation": True,
        "gate": {"gname": gate, "gtag": tag},
        "qubits": qubits,
        "arguments": arguments,
    })


def _degrees(radians: float) -> float:
    """SpinQ Cloud R1 arguments are degrees in [0, 360), rounded to 2 decimals."""
    return round((math.degrees(radians) + 360.0) % 360.0, 2)


def _add_cnot(operations: List[Dict[str, Any]], control: int, target: int) -> None:
    # SpinQ cloud JSON uses [target+1, control+1] for a CNOT operation.
    _add(operations, "CNOT", "C2", [target + 1, control + 1], [])


def to_cloud_circuit(circuit: Any, platform_code: str = "gemini_vp") -> Dict[str, Any]:
    """Convert a parsed LoomQ circuit into SpinQ Cloud circuit JSON."""
    operations: List[Dict[str, Any]] = []
    for operation in circuit.operations:
        name = operation.name
        qubit = operation.qubits[0] + 1
        if name == "h":
            _add(operations, "H", "C1", [qubit], [])
        elif name == "x":
            _add(operations, "X", "C1", [qubit], [])
        elif name == "s":
            _add(operations, "Rz", "R1", [qubit], [_degrees(math.pi / 2)])
        elif name == "sdg":
            _add(operations, "Rz", "R1", [qubit], [_degrees(-math.pi / 2)])
        elif name == "t":
            _add(operations, "Rz", "R1", [qubit], [_degrees(math.pi / 4)])
        elif name == "tdg":
            _add(operations, "Rz", "R1", [qubit], [_degrees(-math.pi / 4)])
        elif name == "rz":
            _add(operations, "Rz", "R1", [qubit], [_degrees(operation.params[0])])
        elif name == "ry":
            _add(operations, "Ry", "R1", [qubit], [_degrees(operation.params[0])])
        elif name == "cx":
            control, target = operation.qubits
            if platform_code == "superconductor_vp":
                # The 8-qubit superconducting platform exposes ZCON (CZ),
                # not CNOT; CNOT(qc, qt) = H(qt) CZ(qc, qt) H(qt).
                _add(operations, "H", "C1", [target + 1], [])
                _add(operations, "ZCON", "C2", [target + 1, control + 1], [])
                _add(operations, "H", "C1", [target + 1], [])
            else:
                _add_cnot(operations, control, target)
        elif name == "swap":
            first, second = operation.qubits
            _add_cnot(operations, first, second)
            _add_cnot(operations, second, first)
            _add_cnot(operations, first, second)
        elif name == "cu1":
            control, target = operation.qubits
            angle = operation.params[0]
            _add(operations, "Rz", "R1", [control + 1], [_degrees(angle / 2)])
            _add_cnot(operations, control, target)
            _add(operations, "Rz", "R1", [target + 1], [_degrees(-angle / 2)])
            _add_cnot(operations, control, target)
            _add(operations, "Rz", "R1", [target + 1], [_degrees(angle / 2)])
        elif name == "measure":
            continue
        else:
            raise ValueError(f"gate {name} cannot be submitted to a 2-qubit SpinQ Gemini QPU")
    return {"operations": operations, "definitions": []}


def build_task(qasm: str, task_name: str, platform_code: str, simulator: bool, shots: int) -> Dict[str, Any]:
    circuit = parse_qasm(qasm)
    return {
        "tname": task_name,
        "bitNum": circuit.qubits,
        "clbitNum": circuit.cbits,
        "sourceType": "spinqit",
        "calcMatrix": False,
        "simulator": simulator,
        "proceedNow": True,
        "platformCode": platform_code,
        "description": "LoomQ-2026 hardware validation",
        "circuit": to_cloud_circuit(circuit, platform_code),
        "activeBits": list(range(1, circuit.qubits + 1)),
        "shots": shots,
        "sourceCode": qasm.strip(),
        "measuredQubits": None,
        "logToPhy": {index: index for index in range(circuit.qubits)},
    }


def wait_for_result(token: str, host: str, task_code: str, timeout_seconds: int = 420) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json", "token": token, "User-Agent": UA, "Accept": "*/*"}
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(
            host + "/task/user/retrieveCurrentTaskStatus",
            params={"taskCode": task_code},
            headers=headers,
            timeout=30,
        )
        status = response.json().get("taskStatus")
        if status == "S":
            result = requests.get(
                host + "/task/user/getTaskRunResultByTcodeV2",
                params={"taskCode": task_code},
                headers=headers,
                timeout=30,
            )
            return result.json()
        if status in {"F", "FAILED", "FAIL"}:
            raise RuntimeError(f"task {task_code} failed")
        time.sleep(3)
    raise TimeoutError(f"task {task_code} did not finish in {timeout_seconds}s")


def submit(qasm: str, task_name: str, platform_code: str = "gemini_vp", simulator: bool = False, shots: int = 1024) -> Dict[str, Any]:
    username = os.environ.get("SPINQ_USERNAME")
    keyfile = os.environ.get("SPINQ_KEYFILE")
    host = os.environ.get("SPINQ_HOST", DEFAULT_HOST)
    if not username or not keyfile:
        raise RuntimeError("SPINQ_USERNAME and SPINQ_KEYFILE must be set")
    token = login(username, keyfile, host)
    headers = {"Content-Type": "application/json", "token": token, "User-Agent": UA, "Accept": "*/*"}
    body = build_task(qasm, task_name, platform_code, simulator, shots)
    created = requests.post(host + "/task/user/create", data=json.dumps(body), headers=headers, timeout=60).json()
    task = created.get("task", created)
    task_code = task.get("tcode")
    if not task_code:
        raise RuntimeError(f"task create failed: {created}")
    result = wait_for_result(token, host, task_code)
    return {"create": created, "result": result, "tcode": task_code, "task_id": task.get("tid")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qasm", help="QASM 2.0 file (no measure statements)")
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--platform", default="gemini_vp", choices=("gemini_vp", "superconductor_vp", "simulator"))
    parser.add_argument("--simulator", action="store_true")
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    qasm = open(args.qasm, encoding="utf-8").read()
    outcome = submit(qasm, args.task_name, args.platform, args.simulator, args.shots)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(outcome, handle, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
