"""SpinQit 基础模拟器 Runner 与 counts 归一化。"""

import importlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, NamedTuple, Sequence, Tuple, Type
from uuid import uuid4

from ..ir import Circuit, GateOperation, MeasureOperation
from ..measurements import (
    build_classical_key,
    measurement_mapping,
    quantum_bit_indices,
)
from ..results import create_result, validate_shots
from ..serializers.spinq import serialize_spinq


_WORKER_TIMEOUT_SECONDS = 120
_STDERR_LIMIT = 4000


class SpinQSDK(NamedTuple):
    config_class: Type[Any]
    circuit_class: Type[Any]
    gates: Mapping[str, Any]
    simulator_factory: Any
    compiler_factory: Any


class SpinQGateSpec(NamedTuple):
    qubit_count: int
    parameter_count: int


# QASM 名称与 SpinQit 0.2.4 顶层导出名称分离，便于集中检查 SDK 完整性。
_SPINQ_GATE_EXPORTS: Mapping[str, str] = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "Sd",
    "t": "T",
    "tdg": "Td",
    "ry": "Ry",
    "rz": "Rz",
    "cx": "CX",
    "cu1": "CP",
    "swap": "SWAP",
    "ccx": "CCX",
}

_SPINQ_GATE_SPECS: Mapping[str, SpinQGateSpec] = {
    "h": SpinQGateSpec(1, 0),
    "x": SpinQGateSpec(1, 0),
    "s": SpinQGateSpec(1, 0),
    "sdg": SpinQGateSpec(1, 0),
    "t": SpinQGateSpec(1, 0),
    "tdg": SpinQGateSpec(1, 0),
    "ry": SpinQGateSpec(1, 1),
    "rz": SpinQGateSpec(1, 1),
    "cx": SpinQGateSpec(2, 0),
    "cu1": SpinQGateSpec(2, 1),
    "swap": SpinQGateSpec(2, 0),
    "ccx": SpinQGateSpec(3, 0),
}


def _load_spinq_sdk() -> SpinQSDK:
    """延迟导入 SpinQit，保证其他后端不受本地 wheel 可用性影响。"""
    try:
        spinqit = importlib.import_module("spinqit")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "SpinQit SDK is not installed; install starter-kit/requirements-spinq.txt "
            "in the isolated SpinQ environment"
        ) from exc
    missing_gates = [
        qasm_name
        for qasm_name, export_name in _SPINQ_GATE_EXPORTS.items()
        if not hasattr(spinqit, export_name)
    ]
    if missing_gates:
        raise RuntimeError(
            "SpinQit SDK is missing required gate(s): %s"
            % ", ".join(missing_gates)
        )
    gates = {
        qasm_name: getattr(spinqit, export_name)
        for qasm_name, export_name in _SPINQ_GATE_EXPORTS.items()
    }
    return SpinQSDK(
        config_class=spinqit.BasicSimulatorConfig,
        circuit_class=spinqit.Circuit,
        gates=gates,
        simulator_factory=spinqit.get_basic_simulator,
        compiler_factory=spinqit.get_compiler,
    )


def _validate_final_measurements(circuit: Circuit) -> Tuple[Tuple[int, int], ...]:
    measurement_seen = False
    for operation in circuit.operations:
        if isinstance(operation, MeasureOperation):
            measurement_seen = True
        elif isinstance(operation, GateOperation) and measurement_seen:
            raise ValueError("SpinQ runner supports final measurements only")

    mapping = tuple(measurement_mapping(circuit))
    if not mapping:
        raise ValueError("SpinQ runner requires at least one measurement")
    return mapping


def _append_native_gate(
    native_circuit: Any,
    sdk: SpinQSDK,
    gate_name: str,
    operands: Tuple[Any, ...],
    parameters: Tuple[float, ...] = (),
) -> None:
    spec = _SPINQ_GATE_SPECS[gate_name]
    try:
        native_gate = sdk.gates[gate_name]
    except KeyError as exc:
        raise RuntimeError(
            "SpinQ SDK gate mapping is missing required gate %r" % gate_name
        ) from exc
    native_operand: Any = operands[0] if spec.qubit_count == 1 else operands
    if spec.parameter_count == 0:
        native_circuit << (native_gate, native_operand)
    else:
        # SpinQit 0.2.4 的参数位于 gate 和 qubit(s) 之后，且接受 float。
        native_circuit << (native_gate, native_operand, float(parameters[0]))


def _append_ccx_decomposition(
    native_circuit: Any, sdk: SpinQSDK, operands: Tuple[Any, ...]
) -> None:
    """按官方 qelib1 恒等式展开 CCX。"""
    control_a, control_b, target = operands
    # SpinQit 0.2.4 原生 CCX 在控制位叠加态上会终止 Basic Simulator 进程。
    instructions = (
        ("h", (target,)),
        ("cx", (control_b, target)),
        ("tdg", (target,)),
        ("cx", (control_a, target)),
        ("t", (target,)),
        ("cx", (control_b, target)),
        ("tdg", (target,)),
        ("cx", (control_a, target)),
        ("t", (control_b,)),
        ("t", (target,)),
        ("h", (target,)),
        ("cx", (control_a, control_b)),
        ("t", (control_a,)),
        ("tdg", (control_b,)),
        ("cx", (control_a, control_b)),
    )
    for gate_name, gate_operands in instructions:
        _append_native_gate(native_circuit, sdk, gate_name, gate_operands)


def _build_spinq_circuit(circuit: Circuit, sdk: SpinQSDK) -> Any:
    native_circuit = sdk.circuit_class()
    qubit_count = sum(register.size for register in circuit.quantum_registers)
    native_qubits = list(native_circuit.allocateQubits(qubit_count))
    if len(native_qubits) != qubit_count:
        raise RuntimeError("SpinQit allocated an unexpected number of qubits")
    global_indices = quantum_bit_indices(circuit)

    for operation in circuit.operations:
        if not isinstance(operation, GateOperation):
            continue
        spec = _SPINQ_GATE_SPECS.get(operation.name)
        if spec is None:
            raise ValueError(
                "SpinQ runner does not support gate %r" % operation.name
            )
        if len(operation.qubits) != spec.qubit_count:
            raise ValueError(
                "SpinQ gate %r expects %d qubit operand(s), got %d"
                % (operation.name, spec.qubit_count, len(operation.qubits))
            )
        if len(operation.parameters) != spec.parameter_count:
            raise ValueError(
                "SpinQ gate %r expects %d parameter(s), got %d"
                % (operation.name, spec.parameter_count, len(operation.parameters))
            )
        operands = tuple(native_qubits[global_indices[item]] for item in operation.qubits)
        if operation.name == "ccx":
            _append_ccx_decomposition(native_circuit, sdk, operands)
        else:
            _append_native_gate(
                native_circuit,
                sdk,
                operation.name,
                operands,
                operation.parameters,
            )
    return native_circuit


def normalize_spinq_counts(
    circuit: Circuit,
    measured_qubits: Sequence[int],
    raw_counts: Mapping[str, int],
    shots: int,
) -> Dict[str, int]:
    """将 SpinQ 首字符对应首量子位的 key 转为 LoomQ 位序。"""
    validate_shots(shots)
    if not isinstance(raw_counts, dict) or not raw_counts:
        raise ValueError("SpinQ counts must be a non-empty dict")

    normalized_qubits = [int(qubit) for qubit in measured_qubits]
    if len(set(normalized_qubits)) != len(normalized_qubits):
        raise ValueError("SpinQ measured_qubits contains duplicates")
    mapping = measurement_mapping(circuit)
    normalized: Counter[str] = Counter()
    raw_total = 0

    for key, count in raw_counts.items():
        if not isinstance(key, str) or set(key) - {"0", "1"}:
            raise ValueError("SpinQ count keys must be binary strings")
        if len(key) != len(normalized_qubits):
            raise ValueError("SpinQ count key width does not match measured_qubits")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("SpinQ count values must be non-negative integers")

        # SpinQ key 从左到右依次对应 configure_measure_qubits 的量子位。
        quantum_values = {
            qubit: int(value) for qubit, value in zip(normalized_qubits, key)
        }
        normalized_key = build_classical_key(circuit, mapping, quantum_values)
        normalized[normalized_key] += count
        raw_total += count

    if raw_total != shots:
        raise ValueError("SpinQ counts total must equal shots exactly")
    return dict(normalized)


def run_spinq_native(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """仅在安装了 SpinQit 的独立环境中执行。"""
    validate_shots(shots)
    mapping = _validate_final_measurements(circuit)
    measured_qubits = sorted({quantum for quantum, _ in mapping})
    sdk = _load_spinq_sdk()
    native_circuit = _build_spinq_circuit(circuit, sdk)

    compiler = sdk.compiler_factory("native")
    executable = compiler.compile(native_circuit, 0)
    config = sdk.config_class()
    config.configure_shots(shots)
    # SpinQit 0.2.4 的 BasicSimulatorConfig 接收量子位全局索引。
    config.configure_measure_qubits(measured_qubits)
    raw_result = sdk.simulator_factory().execute(executable, config)
    raw_counts = getattr(raw_result, "counts", None)
    if raw_counts is None:
        raise RuntimeError("SpinQ result does not expose counts")
    counts = normalize_spinq_counts(circuit, measured_qubits, raw_counts, shots)

    return create_result(
        backend="spinq_basic_simulator",
        job_id="spinq-local-%s" % uuid4(),
        shots=shots,
        counts=counts,
        meta={
            "simulator": "basic",
            "compiler": "native",
            "optimization_level": 0,
        },
    )


def _starter_kit_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _find_spinq_python() -> Path:
    configured = os.environ.get("LOOMQ_SPINQ_PYTHON")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path
        raise RuntimeError(
            "SpinQ isolated Python was not found; set LOOMQ_SPINQ_PYTHON"
        )

    root = _starter_kit_root()
    candidates = (
        Path("/opt/spinq-venv/bin/python"),
        root / ".venv-spinq" / "bin" / "python",
        root / ".venv-spinq" / "Scripts" / "python.exe",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError("SpinQ isolated Python was not found; set LOOMQ_SPINQ_PYTHON")


def _spinq_package_directory(python_path: Path) -> Path:
    # 不解析 python symlink，否则会离开虚拟环境并定位到系统解释器目录。
    virtualenv_root = python_path.expanduser().absolute().parent.parent
    matches = sorted(virtualenv_root.glob("lib/python*/site-packages/spinqit"))
    if not matches:
        raise RuntimeError("SpinQit package directory was not found in isolated Python")
    return matches[0]


def _worker_environment(python_path: Path) -> Dict[str, str]:
    environment = os.environ.copy()
    if sys.platform == "darwin":
        package_directory = str(_spinq_package_directory(python_path))
        existing = environment.get("DYLD_LIBRARY_PATH")
        environment["DYLD_LIBRARY_PATH"] = (
            package_directory + os.pathsep + existing
            if existing
            else package_directory
        )
    return environment


def _stderr_excerpt(stderr: str) -> str:
    message = stderr.strip()
    if len(message) <= _STDERR_LIMIT:
        return message
    return "..." + message[-_STDERR_LIMIT:]


def run_spinq(circuit: Circuit, shots: int) -> Dict[str, Any]:
    """通过独立 Python Worker 执行 SpinQit，避免与 Braket 依赖冲突。"""
    validate_shots(shots)
    python_path = _find_spinq_python()
    request = json.dumps(
        {"qasm": serialize_spinq(circuit), "shots": shots},
        ensure_ascii=False,
    )
    command = [str(python_path), "-m", "loomq.workers.spinq_worker"]

    try:
        completed = subprocess.run(
            command,
            input=request,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_WORKER_TIMEOUT_SECONDS,
            check=False,
            cwd=str(_starter_kit_root()),
            env=_worker_environment(python_path),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "SpinQ worker timed out after %d seconds" % _WORKER_TIMEOUT_SECONDS
        ) from exc

    if completed.returncode != 0:
        details = _stderr_excerpt(completed.stderr)
        suffix = ": %s" % details if details else ""
        raise RuntimeError(
            "SpinQ worker failed with exit code %d%s"
            % (completed.returncode, suffix)
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SpinQ worker returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("SpinQ worker result must be a JSON object")
    return result
