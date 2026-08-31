"""Braket 本地模拟器 Runner 与测量结果归一化。"""

import importlib
from collections import Counter
from typing import Any, Dict, Sequence, Tuple, Type
from uuid import uuid4

from ..ir import Circuit
from ..measurements import build_classical_key, measurement_mapping
from ..results import create_result, validate_shots
from ..serializers.braket import serialize_braket


def _load_braket_sdk() -> Tuple[Type[Any], Type[Any]]:
    """延迟导入 SDK，避免仅使用 transpile 时因缺少依赖而崩溃。"""
    try:
        devices = importlib.import_module("braket.devices")
        openqasm = importlib.import_module("braket.ir.openqasm")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "Braket SDK is not installed; install starter-kit/requirements.txt"
        ) from exc
    return devices.LocalSimulator, openqasm.Program


def normalize_braket_measurements(
    circuit: Circuit,
    measured_qubits: Sequence[int],
    measurements: Sequence[Sequence[int]],
) -> Dict[str, int]:
    """按 Circuit 的经典位语义将 Braket 测量矩阵转换为 counts。"""
    columns: Dict[int, int] = {}
    for column, raw_qubit in enumerate(measured_qubits):
        qubit = int(raw_qubit)
        if qubit in columns:
            raise ValueError("Braket measured_qubits contains duplicate qubit %d" % qubit)
        columns[qubit] = column

    mapping = measurement_mapping(circuit)

    counts: Counter[str] = Counter()
    for row in measurements:
        if len(row) != len(measured_qubits):
            raise ValueError("Braket measurement row width does not match measured_qubits")
        quantum_values: Dict[int, int] = {}
        for quantum_index, classical_index in mapping:
            if quantum_index not in columns:
                raise ValueError(
                    "measured qubit %d is missing from Braket result" % quantum_index
                )
            value = int(row[columns[quantum_index]])
            if value not in (0, 1):
                raise ValueError("Braket measurement values must be binary")
            quantum_values[quantum_index] = value

        key = build_classical_key(circuit, mapping, quantum_values)
        counts[key] += 1
    return dict(counts)


def run_braket(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """在 Braket braket_sv 本地模拟器执行 Circuit。"""
    validate_shots(shots)
    LocalSimulator, Program = _load_braket_sdk()
    # 本地模拟器会将 stdgates.inc 视作本地文件，提交时不输出该声明。
    qasm3 = serialize_braket(circuit, include_stdgates=False, execution_mode=True)
    device = LocalSimulator("braket_sv")
    program = Program(source=qasm3)
    task = device.run(program, shots=shots)
    raw_result = task.result()

    measured_qubits = getattr(raw_result, "measured_qubits", None)
    measurements = getattr(raw_result, "measurements", None)
    if measured_qubits is None or measurements is None:
        raise RuntimeError("Braket result does not expose measured_qubits and measurements")
    counts = normalize_braket_measurements(circuit, measured_qubits, measurements)

    task_id = getattr(task, "id", None)
    job_id = str(task_id) if task_id else "braket-local-%s" % uuid4()
    return create_result(
        backend="braket_local_simulator",
        job_id=job_id,
        shots=shots,
        counts=counts,
        meta={"simulator": "braket_sv"},
    )
