"""Per-target execution backends.

Each runner receives target-native text and executes it with the target's
official SDK.
"""

from __future__ import annotations

import re
import tempfile
from math import floor
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

try:
    from .execution import ExecutionResult, utc_now
except ImportError:
    from execution import ExecutionResult, utc_now


def _measurement_width(native_program: str) -> Optional[int]:
    widths = [
        int(value) for value in re.findall(r"\bcreg\s+\w+\[(\d+)\]", native_program)
    ]
    if not widths:
        widths = [
            int(value) for value in re.findall(r"\bbit\[(\d+)\]\s+\w+", native_program)
        ]
    if not widths:
        match = re.search(r"^CREG\s+(\d+)\s*$", native_program, re.MULTILINE)
        widths = [int(match.group(1))] if match else []
    return sum(widths) if widths else None


def _normalize_counts(
    counts: Dict[str, int], *, width: Optional[int], reverse: bool = False
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for raw_key, value in counts.items():
        binary = _normalize_bitstring(raw_key, width=width, reverse=reverse)
        normalized[binary] = normalized.get(binary, 0) + int(value)
    return normalized


def _normalize_bitstring(raw_key, *, width: Optional[int], reverse: bool) -> str:
    key = str(raw_key).replace(" ", "")
    if set(key) <= {"0", "1"}:
        binary = key
    elif key.isdigit():
        binary = bin(int(key))[2:]
    else:
        raise RuntimeError(
            f"quantum backend returned a non-binary result key: {raw_key}"
        )
    if width is not None:
        binary = binary.zfill(width)
    return binary[::-1] if reverse else binary


def _little_endian(
    counts: Dict[str, int], width: Optional[int] = None
) -> Dict[str, int]:
    """仅用于兼容旧结果：把左低位字符串整体反转。"""
    return _normalize_counts(counts, width=width, reverse=True)


def _registers(native_program: str, *, quantum: bool):
    """读取 QASM 2/3 寄存器声明，返回每个寄存器的全局起点和长度。"""
    if quantum:
        patterns = (r"\bqreg\s+(\w+)\[(\d+)\]", r"\bqubit\[(\d+)\]\s+(\w+)")
    else:
        patterns = (r"\bcreg\s+(\w+)\[(\d+)\]", r"\bbit\[(\d+)\]\s+(\w+)")

    found = []
    for pattern_index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, native_program):
            # QASM 3 的名称和长度顺序与 QASM 2 相反。
            if pattern_index == 0:
                name, size = match.group(1), int(match.group(2))
            else:
                size, name = int(match.group(1)), match.group(2)
            found.append((match.start(), name, size))

    registers = {}
    offset = 0
    for _, name, size in sorted(found):
        registers[name] = (offset, size)
        offset += size
    return registers, offset


def _measurement_map(native_program: str):
    """把测量语句展开成 ``(量子位, 经典位)`` 的全局编号对。"""
    qregs, _ = _registers(native_program, quantum=True)
    cregs, classical_width = _registers(native_program, quantum=False)
    pairs = []

    def expand(token: str, registers):
        match = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", token.strip())
        if not match or match.group(1) not in registers:
            raise RuntimeError(f"cannot resolve measurement register: {token}")
        offset, size = registers[match.group(1)]
        if match.group(2) is None:
            return list(range(offset, offset + size))
        index = int(match.group(2))
        if index >= size:
            raise RuntimeError(f"measurement bit is out of range: {token}")
        return [offset + index]

    for raw_line in native_program.splitlines():
        line = raw_line.strip()
        qasm2 = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+?)\s*;", line)
        qasm3 = re.fullmatch(r"(.+?)\s*=\s*measure\s+(.+?)\s*;", line)
        if qasm2:
            qtokens = expand(qasm2.group(1), qregs)
            ctokens = expand(qasm2.group(2), cregs)
        elif qasm3:
            ctokens = expand(qasm3.group(1), cregs)
            qtokens = expand(qasm3.group(2), qregs)
        else:
            continue
        if len(qtokens) != len(ctokens):
            raise RuntimeError("measurement source and destination widths differ")
        pairs.extend(zip(qtokens, ctokens))
    return pairs, classical_width


def _mapped_counts(
    counts: Dict[str, int], native_program: str, measured_qubits=None
) -> Dict[str, int]:
    """按测量语句生成比赛要求的 ``c[n-1]...c[0]`` key。"""
    pairs, classical_width = _measurement_map(native_program)
    if not pairs or not classical_width:
        return _little_endian(counts, _measurement_width(native_program))

    _, quantum_width = _registers(native_program, quantum=True)
    raw_qubits = (
        [int(qubit) for qubit in measured_qubits]
        if measured_qubits is not None
        else list(range(quantum_width))
    )
    if any(
        set(str(key).replace(" ", "")) <= {"0", "1"}
        and len(str(key).replace(" ", "")) > len(raw_qubits)
        for key in counts
    ):
        # 兼容不含真实寄存器宽度的旧 SDK/mock 结果。
        return _little_endian(counts, _measurement_width(native_program))

    qubit_positions = {qubit: index for index, qubit in enumerate(raw_qubits)}

    normalized = {}
    for raw_key, value in counts.items():
        raw_bits = _normalize_bitstring(raw_key, width=len(raw_qubits), reverse=False)
        classical_bits = ["0"] * classical_width

        # SDK 给出量子位测量值；这里按 q[i] -> c[j] 放到正确的经典位。
        for qubit, cbit in pairs:
            position = qubit_positions.get(qubit)
            if position is not None:
                classical_bits[cbit] = raw_bits[position]

        key = "".join(reversed(classical_bits))
        normalized[key] = normalized.get(key, 0) + int(value)
    return normalized


def _compile_spinq_qasm(native_qasm: str, *, omit_measurements: bool = False):
    """Compile OpenQASM 2 through SpinQit's path-only QASM compiler."""
    from spinqit.compiler.qasm_compiler import QASMCompiler

    source = native_qasm
    if omit_measurements:
        source = "\n".join(
            line
            for line in source.splitlines()
            if not line.lstrip().startswith("measure ")
        )
        source += "\n"

    with tempfile.TemporaryDirectory() as temp_dir:
        qasm_path = Path(temp_dir) / "circuit.qasm"
        qasm_path.write_text(source, encoding="utf-8")
        return QASMCompiler().compile(str(qasm_path), 0)


def _probabilities_to_counts(
    probabilities: Dict[str, float], shots: int, *, width: Optional[int] = None
) -> Dict[str, int]:
    """Round a probability distribution while preserving the exact shot total."""
    weights: Dict[str, float] = {}
    for key, value in probabilities.items():
        normalized = _normalize_bitstring(key, width=width, reverse=False)
        weights[normalized] = weights.get(normalized, 0.0) + max(0.0, float(value))
    total = sum(weights.values())
    if total <= 0:
        raise RuntimeError("quantum backend returned an empty probability distribution")

    scaled = {key: value * shots / total for key, value in weights.items()}
    counts = {key: floor(value) for key, value in scaled.items()}
    remainder = shots - sum(counts.values())
    for key in sorted(
        scaled, key=lambda item: (scaled[item] - counts[item], item), reverse=True
    )[:remainder]:
        counts[key] += 1
    return counts


def run_spinq(native_qasm: str, shots: int) -> ExecutionResult:
    """Execute native OpenQASM 2.0 on the SpinQit basic simulator."""
    from spinqit.backend.basic_simulator_backend import (
        BasicSimulatorBackend,
        BasicSimulatorConfig,
    )

    ir = _compile_spinq_qasm(native_qasm)
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = BasicSimulatorBackend().execute(ir, config)
    counts = _mapped_counts(dict(result.counts), native_qasm)
    return ExecutionResult(
        "spinq", f"local-spinq-{uuid4().hex}", shots, counts, utc_now()
    )


def run_spinq_real(
    native_qasm: str,
    shots: int,
    *,
    username: str,
    keyfile: str,
    platform: str = "triangulum_vp",
    host: str = "http://cloud.spinq.cn:6060",
    task_name: str = "LoomQ L1",
    task_description: str = "",
) -> ExecutionResult:
    """Submit OpenQASM 2 to a physical device on SpinQ Cloud.

    ``keyfile`` is the RSA private-key file registered for ``username``.
    Platform access is account-specific; common physical platform codes include
    ``gemini_vp``, ``triangulum_vp``, and ``superconductor_vp``.
    """
    from spinqit import SpinQCloudConfig, get_spinq_cloud

    if not username or not keyfile:
        raise ValueError("SpinQ Cloud username and RSA keyfile are required")

    # SpinQ Cloud performs terminal measurement automatically and rejects
    # explicit measurement instructions in the compiled IR.
    ir = _compile_spinq_qasm(native_qasm, omit_measurements=True)
    config = SpinQCloudConfig()
    config.configure_platform(platform)
    config.configure_shots(shots)
    config.configure_task(task_name, task_description)

    result = get_spinq_cloud(username, keyfile, host).execute(ir, config)
    if result is None or result.counts is None:
        raise RuntimeError("SpinQ Cloud task completed without measurement counts")
    width = _measurement_width(native_qasm)
    raw_counts = dict(result.counts)
    if sum(int(value) for value in raw_counts.values()) == shots:
        counts = _mapped_counts(raw_counts, native_qasm)
        counts_source = "measurement_counts"
    elif getattr(result, "probabilities", None):
        probability_counts = _probabilities_to_counts(
            result.probabilities, shots, width=width
        )
        counts = _mapped_counts(probability_counts, native_qasm)
        counts_source = "probabilities"
    else:
        raise RuntimeError("SpinQ Cloud counts total does not equal requested shots")
    job_id = str(getattr(result, "task_code", "") or "")
    if not job_id:
        raise RuntimeError("SpinQ Cloud result did not contain a traceable task code")
    raw_result = {
        "task_code": job_id,
        "task_name": getattr(result, "task_name", None),
        "platform": getattr(result, "platform", None) or platform,
        "counts": dict(result.counts),
        "probabilities": getattr(result, "probabilities", None),
    }
    return ExecutionResult(
        "spinq_real",
        job_id,
        shots,
        counts,
        utc_now(),
        device=platform,
        counts_source=counts_source,
        raw_result=raw_result,
        metadata={"timestamp_source": "client_submit_utc"},
    )


def run_braket(native_qasm: str, shots: int) -> ExecutionResult:
    """Execute native OpenQASM 3 on the AWS Braket local simulator."""
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program as OpenQASMProgram

    # Keep the standard include in the transpiled IR, but omit it when running
    # locally: this Braket version resolves includes as filesystem paths while
    # already providing the emitted native gates itself.
    braket3 = native_qasm.replace('include "stdgates.inc";', "")
    task = LocalSimulator().run(OpenQASMProgram(source=braket3), shots=shots)
    result = task.result()
    counts = _mapped_counts(
        dict(result.measurement_counts), native_qasm, result.measured_qubits
    )
    task_metadata = getattr(result, "task_metadata", None)
    job_id = str(getattr(task_metadata, "id", "") or f"local-braket-{uuid4().hex}")
    return ExecutionResult(
        "braket", job_id, shots, counts, utc_now(), device="LocalSimulator"
    )


def run_braket_real(
    native_qasm: str,
    shots: int,
    *,
    device_arn: str,
    s3_destination_folder: Optional[Tuple[str, str]] = None,
) -> ExecutionResult:
    """Submit OpenQASM 3 to an AWS Braket QPU and wait for its result.

    AWS credentials and region are resolved by the standard boto3 credential
    chain. ``device_arn`` must identify a gate-model QPU that supports every
    operation emitted by the transpiler.
    """
    from braket.aws import AwsDevice
    from braket.ir.openqasm import Program as OpenQASMProgram

    if not device_arn or "/qpu/" not in device_arn:
        raise ValueError("device_arn must identify an AWS Braket QPU")

    braket3 = native_qasm.replace('include "stdgates.inc";', "")
    program = OpenQASMProgram(source=braket3)
    device = AwsDevice(device_arn)
    if s3_destination_folder is None:
        task = device.run(program, shots=shots)
    else:
        task = device.run(program, s3_destination_folder, shots=shots)
    submitted_at = utc_now()
    result = task.result()
    counts = _mapped_counts(
        dict(result.measurement_counts), native_qasm, result.measured_qubits
    )
    job_id = str(getattr(task, "id", "") or "")
    if not job_id:
        raise RuntimeError("AWS Braket task did not contain a traceable task ID")
    task_metadata = getattr(result, "task_metadata", None)
    raw_result = {
        "task_id": job_id,
        "task_metadata": task_metadata,
        "measurement_counts": dict(result.measurement_counts),
        "measured_qubits": getattr(result, "measured_qubits", None),
        "additional_metadata": getattr(result, "additional_metadata", None),
    }
    return ExecutionResult(
        "braket_real",
        job_id,
        shots,
        counts,
        submitted_at,
        device=device_arn,
        raw_result=raw_result,
        metadata={"timestamp_source": "client_submit_utc"},
    )


def run_originq(native_qasm: str, shots: int) -> ExecutionResult:
    """Execute on the official pyqpanda CPUQVM, fed the transpiled OriginIR.

    ``ORIGINQ_GATES`` renders every gate in a pyqpanda-native form: parameter
    gates as ``RZ q[0],(θ)``/``CR q[0], q[1],(θ)``, including contract-safe
    RZ equivalents for the phase-gate daggers ``sdg``/``tdg``.  The transpile
    output is therefore fed verbatim to ``convert_originir_str_to_qprog``.

    pyqpanda returns little-endian counts keys (``c[0]`` rightmost), matching
    the contract, so no bit reversal is applied here.
    """
    try:
        from pyqpanda import CPUQVM, convert_originir_str_to_qprog
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyqpanda is required for the originq run path") from exc

    machine = CPUQVM()
    machine.init_qvm()
    try:
        program, _, cbits = convert_originir_str_to_qprog(native_qasm, machine)
        result = machine.run_with_configuration(program, cbits, shots)
        counts = _normalize_counts(
            dict(result), width=_measurement_width(native_qasm), reverse=False
        )
        return ExecutionResult(
            "originq", f"local-originq-{uuid4().hex}", shots, counts, utc_now()
        )
    finally:
        machine.finalize()


def run_originq_real(
    native_qasm: str,
    shots: int,
    *,
    token: str,
) -> ExecutionResult:
    """Submit transpiled OriginIR to a named Origin Quantum backend via QPanda3."""
    try:
        from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
        from pyqpanda3.qcloud import QCloudOptions, QCloudService
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pyqpanda3 is required for the OriginQ real-QPU path"
        ) from exc

    if not token:
        raise ValueError("Origin Quantum Cloud API token is required")

    service = QCloudService(api_key=token)
    backend_check = "available"
    try:
        available_backends = service.backends()
    except RuntimeError as exc:
        # pyqpanda3 0.3.2 cannot parse the current backend-status response,
        # which contains numeric status values instead of the older bool array.
        if "value is not array" not in str(exc):
            raise
        backend_check = "sdk_response_incompatible"
    else:
        if not available_backends.get("WK_C180_2", False):
            raise RuntimeError("OriginQ backend WK_C180_2 is offline or unavailable")

    program = convert_originir_string_to_qprog(native_qasm)
    options = QCloudOptions()

    submitted_at = utc_now()
    job = service.backend("WK_C180_2").run([program], shots, options)
    job_id = str(job.job_id())
    if not job_id:
        raise RuntimeError("OriginQ Cloud did not return a traceable task ID")

    try:
        cloud_result = job.result()
    except RuntimeError as exc:
        raise RuntimeError(
            f"OriginQ job {job_id} was submitted but result retrieval failed: {exc}"
        ) from exc
    probabilities = cloud_result.get_probs_list()[0]
    counts = _probabilities_to_counts(
        probabilities, shots, width=_measurement_width(native_qasm)
    )
    return ExecutionResult(
        "originq_real",
        job_id,
        shots,
        counts,
        submitted_at,
        device="WK_C180",
        counts_source="probabilities",
        raw_result={
            "task_id": job_id,
            "backend": "WK_C180",
            "backend_check": backend_check,
            "probabilities": probabilities,
        },
        metadata={"timestamp_source": "client_submit_utc"},
    )
