"""SpinQit BasicSimulator runner with deferred SDK imports."""

import os
import tempfile
from collections.abc import Mapping
from types import SimpleNamespace

from ..errors import DependencyUnavailableError, ProviderExecutionError
from ..model import RawExecution
from ..parser import parse_qasm
from ._common import installed_sdk_version, local_job_id, metadata, metadata_id


def _import_spinq() -> SimpleNamespace:
    import spinqit
    from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

    return SimpleNamespace(
        BasicSimulatorConfig=BasicSimulatorConfig,
        get_basic_simulator=get_basic_simulator,
        get_compiler=get_compiler,
        version=installed_sdk_version("spinqit", getattr(spinqit, "__version__", "unknown")),
    )


def _validate_inputs(native_ir: str, shots: int) -> None:
    if type(native_ir) is not str or not native_ir.strip():
        raise ProviderExecutionError("native_ir must be a non-empty string")
    if type(shots) is not int or shots <= 0:
        raise ProviderExecutionError("shots must be a positive built-in int")


def _measurement_map(native_ir: str) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    circuit = parse_qasm(native_ir)
    qubit_width = circuit.num_qubits
    cbit_width = circuit.num_clbits
    measurements = tuple(
        (measurement.qubit, measurement.cbit) for measurement in circuit.measurements
    )
    if not measurements:
        raise ValueError("SpinQ OpenQASM must contain explicit measurements")
    return qubit_width, cbit_width, measurements


def _remap_counts(native_ir: str, raw_counts: Mapping[object, object]) -> dict[str, int]:
    qubit_width, cbit_width, measurements = _measurement_map(native_ir)
    remapped: dict[str, int] = {}
    for raw_key, count in raw_counts.items():
        if type(raw_key) is not str:
            raise TypeError("SpinQ count keys must be binary strings")
        bits = raw_key.replace(" ", "")
        if len(bits) != qubit_width or any(bit not in "01" for bit in bits):
            raise TypeError("SpinQ count keys must match the qreg width")
        if type(count) is not int or count < 0:
            raise TypeError("SpinQ count values must be non-negative built-in ints")

        canonical = ["0"] * cbit_width
        for qubit, cbit in measurements:
            canonical[cbit_width - 1 - cbit] = bits[qubit]
        key = "".join(canonical)
        remapped[key] = remapped.get(key, 0) + count
    return remapped


def run_spinq(native_ir: str, shots: int) -> RawExecution:
    """Execute OpenQASM 2 through SpinQit's BasicSimulator."""
    _validate_inputs(native_ir, shots)
    try:
        sdk = _import_spinq()
    except ImportError as error:
        raise DependencyUnavailableError("spinqit is required for the SpinQ runner") from error

    path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".qasm", delete=False, encoding="utf-8"
        ) as source:
            path = source.name
            source.write(native_ir)

        compiler = sdk.get_compiler("qasm")
        ir = compiler.compile(path, 0)
        engine = sdk.get_basic_simulator()
        config = sdk.BasicSimulatorConfig()
        config.configure_shots(shots)
        result = engine.execute(ir, config)
        counts = result.counts
        if not isinstance(counts, Mapping):
            raise TypeError("SpinQ result counts must be a mapping")
        counts = _remap_counts(native_ir, counts)
        job_id = local_job_id(
            "spinq",
            getattr(result, "job_id", None),
            getattr(result, "task_id", None),
            metadata_id(getattr(result, "task_metadata", None)),
        )
        return RawExecution(
            backend="spinq_basic_simulator",
            job_id=job_id,
            counts=counts,
            key_format="binary",
            reverse_bits=False,
            metadata=metadata("spinq", "spinq", "spinqit", getattr(sdk, "version", "unknown")),
        )
    except Exception as error:
        raise ProviderExecutionError("SpinQ execution failed") from error
    finally:
        if path is not None:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


__all__ = ["run_spinq"]
