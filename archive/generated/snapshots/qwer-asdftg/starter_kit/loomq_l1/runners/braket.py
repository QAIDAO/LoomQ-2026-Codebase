"""Amazon Braket LocalSimulator runner with deferred SDK imports."""

from collections.abc import Mapping
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from ..errors import DependencyUnavailableError, ProviderExecutionError
from ..model import RawExecution
from ._common import local_job_id, metadata, metadata_id
from .braket_worker import _execution_source as _braket_execution_source


_WORKER_RESPONSE_FIELDS = frozenset(("counts", "job_id", "sdk_version"))
_SAFE_VERSION_CHARACTERS = frozenset(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+-_"
)
_WORKER_ENVIRONMENT_VARIABLES = ("PATH", "SystemRoot", "LANG", "LC_ALL")
_WORKER_CWD = str(Path(__file__).resolve().parents[2])


def _import_braket() -> SimpleNamespace:
    import braket
    from braket.devices import LocalSimulator
    from braket.ir.openqasm import Program

    try:
        from braket import _sdk
    except ImportError:
        version = getattr(braket, "__version__", "unknown")
    else:
        version = getattr(_sdk, "__version__", getattr(braket, "__version__", "unknown"))

    return SimpleNamespace(
        LocalSimulator=LocalSimulator,
        Program=Program,
        version=version,
    )


def _validate_inputs(native_ir: str, shots: int) -> None:
    if type(native_ir) is not str or not native_ir.strip():
        raise ProviderExecutionError("native_ir must be a non-empty string")
    if type(shots) is not int or shots <= 0:
        raise ProviderExecutionError("shots must be a positive built-in int")


def _task_id(task: object, result: object) -> str:
    return local_job_id(
        "braket",
        getattr(task, "id", None),
        metadata_id(getattr(result, "task_metadata", None)),
    )


def _worker_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or not value:
        raise TypeError("Braket worker counts must be a non-empty mapping")

    counts: dict[str, int] = {}
    for key, count in value.items():
        if type(key) is not str or not key or any(bit not in "01" for bit in key):
            raise TypeError("Braket worker count keys must be non-empty binary strings")
        if type(count) is not int or count <= 0:
            raise TypeError("Braket worker count values must be positive built-in ints")
        counts[key] = count
    return counts


def _worker_version(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 128
        or any(character not in _SAFE_VERSION_CHARACTERS for character in value)
    ):
        raise TypeError("Braket worker SDK version is invalid")
    return value


def _worker_response(stdout: object) -> tuple[dict[str, int], str | None, str]:
    response = json.loads(stdout)
    if type(response) is not dict or not set(response).issubset(_WORKER_RESPONSE_FIELDS):
        raise TypeError("Braket worker response has invalid fields")
    if "counts" not in response or "sdk_version" not in response:
        raise TypeError("Braket worker response is incomplete")

    job_id = response.get("job_id")
    if "job_id" in response and (type(job_id) is not str or not job_id):
        raise TypeError("Braket worker job ID is invalid")
    return _worker_counts(response["counts"]), job_id, _worker_version(response["sdk_version"])


def _worker_environment() -> dict[str, str]:
    """Return only runtime bootstrap variables for the isolated worker."""
    return {
        name: value
        for name in _WORKER_ENVIRONMENT_VARIABLES
        if type(value := os.environ.get(name)) is str and value
    }


def _run_braket_worker(worker_python: str, native_ir: str, shots: int) -> RawExecution:
    try:
        completed = subprocess.run(
            [worker_python, "-m", "loomq_l1.runners.braket_worker"],
            input=json.dumps({"native_ir": native_ir, "shots": shots}),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
            env=_worker_environment(),
            cwd=_WORKER_CWD,
        )
    except subprocess.TimeoutExpired as error:
        raise ProviderExecutionError("Braket worker timed out") from error
    except Exception as error:
        raise ProviderExecutionError("Braket worker could not be started") from error

    if type(completed.returncode) is not int or completed.returncode != 0:
        raise ProviderExecutionError("Braket worker failed")

    try:
        counts, job_id, version = _worker_response(completed.stdout)
    except Exception as error:
        raise ProviderExecutionError("Braket worker returned an invalid response") from error

    return RawExecution(
        backend="braket_local_simulator",
        job_id=local_job_id("braket", job_id),
        counts=counts,
        key_format="binary",
        reverse_bits=True,
        metadata=metadata("braket", "braket", "amazon-braket-sdk", version),
    )


def run_braket(native_ir: str, shots: int) -> RawExecution:
    """Execute OpenQASM 3 on Braket's local simulator.

    Braket's real LocalSimulator returns the opposite count-key order from
    LoomQ's canonical c[n-1]...c[0] convention, so ``reverse_bits=True``.
    """
    _validate_inputs(native_ir, shots)
    worker_python = os.environ.get("LOOMQ_BRAKET_PYTHON")
    if type(worker_python) is str and worker_python:
        return _run_braket_worker(worker_python, native_ir, shots)

    try:
        sdk = _import_braket()
    except ImportError as error:
        raise DependencyUnavailableError(
            "amazon-braket-sdk is required for the Braket runner"
        ) from error

    try:
        program = sdk.Program(source=_braket_execution_source(native_ir))
        task = sdk.LocalSimulator().run(program, shots=shots)
        result = task.result()
        counts = result.measurement_counts
        if not isinstance(counts, Mapping):
            raise TypeError("Braket result counts must be a mapping")
        return RawExecution(
            backend="braket_local_simulator",
            job_id=_task_id(task, result),
            counts=counts,
            key_format="binary",
            reverse_bits=True,
            metadata=metadata(
                "braket", "braket", "amazon-braket-sdk", getattr(sdk, "version", "unknown")
            ),
        )
    except Exception as error:
        raise ProviderExecutionError("Braket execution failed") from error


__all__ = ["run_braket"]
