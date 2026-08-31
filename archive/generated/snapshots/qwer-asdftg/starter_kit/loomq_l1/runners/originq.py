"""pyQPanda CPUQVM runner with deferred SDK imports."""

import os
import re
import tempfile
from collections.abc import Mapping
from types import SimpleNamespace

from ..errors import DependencyUnavailableError, ProviderExecutionError
from ..model import RawExecution
from ._common import installed_sdk_version, local_job_id, metadata


_CREG_PATTERN = re.compile(r"^CREG ([1-9][0-9]*)$", re.MULTILINE)
_INVERSE_GATE_PATTERN = re.compile(
    r"^(SDAG|TDAG)[ \t]+(q\[[0-9]+\])[ \t]*(\r?\n|$)", re.MULTILINE
)
_CU1_PATTERN = re.compile(
    r"^CU1(?P<spacing>[ \t]+)(?P<operands>q\[[0-9]+\][ \t]*,[ \t]*q\[[0-9]+\][ \t]*,[ \t]*\([^()\r\n]+\))[ \t]*(?P<newline>\r?\n|$)",
    re.MULTILINE,
)


def _import_originq() -> SimpleNamespace:
    import pyqpanda
    from pyqpanda import CPUQVM, convert_originir_to_qprog

    return SimpleNamespace(
        CPUQVM=CPUQVM,
        convert_originir_to_qprog=convert_originir_to_qprog,
        version=installed_sdk_version("pyqpanda", getattr(pyqpanda, "__version__", "unknown")),
    )


def _validate_inputs(native_ir: str, shots: int) -> None:
    if type(native_ir) is not str or not native_ir.strip():
        raise ProviderExecutionError("native_ir must be a non-empty string")
    if type(shots) is not int or shots <= 0:
        raise ProviderExecutionError("shots must be a positive built-in int")


def _creg_width(native_ir: str) -> int:
    matches = _CREG_PATTERN.findall(native_ir)
    if len(matches) != 1:
        raise ValueError("OriginIR must declare exactly one CREG width")
    return int(matches[0])


def _execution_source(native_ir: str) -> str:
    """Lower only the OriginIR spellings unsupported by pyQPanda 3.8.5."""

    def lower_inverse_gate(match: re.Match[str]) -> str:
        gate = "S" if match.group(1) == "SDAG" else "T"
        qubit = match.group(2)
        newline = match.group(3)
        return f"DAGGER{newline}{gate} {qubit}{newline}ENDDAGGER{newline}"

    source = _INVERSE_GATE_PATTERN.sub(lower_inverse_gate, native_ir)
    return _CU1_PATTERN.sub(
        lambda match: f"CR{match.group('spacing')}{match.group('operands')}{match.group('newline')}",
        source,
    )


def _binary_value(key: str, width: int) -> int | None:
    bits = key.replace(" ", "")
    if not bits or len(bits) > width or any(bit not in "01" for bit in bits):
        return None
    return int(bits, 2)


def _decimal_value(key: str, width: int) -> int | None:
    if (
        not key
        or (len(key) > 1 and key[0] == "0")
        or any(digit < "0" or digit > "9" for digit in key)
    ):
        return None
    value = int(key, 10)
    return value if value < (1 << width) else None


def _canonicalize_counts(raw_counts: object, width: int) -> dict[str, object]:
    if not isinstance(raw_counts, Mapping):
        raise TypeError("OriginQ result counts must be a mapping")
    if not raw_counts:
        return {}

    keys = tuple(raw_counts)
    if all(type(key) is int for key in keys):
        values = tuple(keys)
        if any(value < 0 or value >= (1 << width) for value in values):
            raise TypeError("OriginQ integer count key does not fit CREG width")
    elif all(type(key) is str for key in keys):
        binary_values = tuple(_binary_value(key, width) for key in keys)
        decimal_values = tuple(_decimal_value(key, width) for key in keys)
        supports_binary = all(value is not None for value in binary_values)
        supports_decimal = all(value is not None for value in decimal_values)
        if supports_binary and supports_decimal:
            if binary_values != decimal_values:
                raise TypeError("OriginQ count keys are ambiguous between binary and decimal")
            values = binary_values
        elif supports_binary:
            values = binary_values
        elif supports_decimal:
            values = decimal_values
        else:
            raise TypeError("OriginQ count keys mix unsupported binary and decimal formats")
    else:
        raise TypeError("OriginQ count keys must use one supported format")

    canonical: dict[str, object] = {}
    for key, value in zip(values, raw_counts.values()):
        binary_key = format(key, f"0{width}b")
        if binary_key in canonical:
            canonical[binary_key] += value
        else:
            canonical[binary_key] = value
    return canonical


def run_originq(native_ir: str, shots: int) -> RawExecution:
    """Execute OriginIR on CPUQVM using converter-provided classical bits.

    The emitted ``CREG`` width is checked against the deterministic cbit list
    returned by ``convert_originir_to_qprog`` before execution.
    """
    _validate_inputs(native_ir, shots)
    try:
        sdk = _import_originq()
    except ImportError as error:
        raise DependencyUnavailableError("pyqpanda is required for the OriginQ runner") from error

    machine = None
    failure = None
    try:
        width = _creg_width(native_ir)
        machine = sdk.CPUQVM()
        machine.init_qvm()
        path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".ir", delete=False, encoding="utf-8"
            ) as source:
                path = source.name
                source.write(_execution_source(native_ir))
            converted = sdk.convert_originir_to_qprog(path, machine)
            if not isinstance(converted, (tuple, list)) or len(converted) != 3:
                raise TypeError("OriginQ converter returned an unsupported shape")
            program, _qubits, cbits = converted
            if not hasattr(cbits, "__len__") or len(cbits) != width:
                raise TypeError("OriginQ converter returned an unexpected cbit list")
            counts = _canonicalize_counts(machine.run_with_configuration(program, cbits, shots), width)
        finally:
            if path is not None:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
    except Exception as error:
        failure = error
    finally:
        if machine is not None:
            try:
                machine.finalize()
            except Exception as error:
                if failure is None:
                    failure = error

    if failure is not None:
        raise ProviderExecutionError("OriginQ execution failed") from failure
    return RawExecution(
        backend="originq_cpu_simulator",
        job_id=local_job_id("originq"),
        counts=counts,
        key_format="binary",
        reverse_bits=False,
        metadata=metadata("originq", "originq", "pyqpanda", getattr(sdk, "version", "unknown")),
    )


__all__ = ["run_originq"]
