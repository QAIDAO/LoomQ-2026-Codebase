"""Minimal Braket local-simulator worker for the isolated runtime."""

from collections.abc import Mapping
import json
import re
import sys
from types import SimpleNamespace


_PAYLOAD_FIELDS = frozenset(("native_ir", "shots"))
_SAFE_VERSION_CHARACTERS = frozenset(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+-_"
)
_STANDALONE_STDGATES_INCLUDE = re.compile(
    r'^[ \t]*include[ \t]+"stdgates\.inc"[ \t]*;[ \t]*(?:\r?\n|$)',
    re.MULTILINE,
)
_OPENQASM_3_HEADER = re.compile(r"^(OPENQASM[ \t]+3\.0;[ \t]*(?:\r?\n|$))")
_MISSING_GATE_PATTERNS = {
    "sdg": re.compile(r"^[ \t]*sdg[ \t]+", re.MULTILINE),
    "tdg": re.compile(r"^[ \t]*tdg[ \t]+", re.MULTILINE),
    "cp": re.compile(r"^[ \t]*cp[ \t]*\(", re.MULTILINE),
    "ccx": re.compile(r"^[ \t]*ccx[ \t]+", re.MULTILINE),
}
_MISSING_GATE_DEFINITIONS = {
    "sdg": "gate sdg a { rz(-pi/2) a; }\n",
    "tdg": "gate tdg a { rz(-pi/4) a; }\n",
    "cp": (
        "gate cp(theta) a, b {\n"
        "  rz(theta/2) a;\n"
        "  rz(theta/2) b;\n"
        "  cnot a, b;\n"
        "  rz(-theta/2) b;\n"
        "  cnot a, b;\n"
        "}\n"
    ),
    "ccx": (
        "gate ccx a, b, c {\n"
        "  h c;\n"
        "  cnot b, c;\n"
        "  tdg c;\n"
        "  cnot a, c;\n"
        "  t c;\n"
        "  cnot b, c;\n"
        "  tdg c;\n"
        "  cnot a, c;\n"
        "  t b;\n"
        "  t c;\n"
        "  h c;\n"
        "  cnot a, b;\n"
        "  t a;\n"
        "  tdg b;\n"
        "  cnot a, b;\n"
        "}\n"
    ),
}


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

    return SimpleNamespace(LocalSimulator=LocalSimulator, Program=Program, version=version)


def _validate_payload(payload: object) -> tuple[str, int]:
    if type(payload) is not dict or set(payload) != _PAYLOAD_FIELDS:
        raise TypeError("worker payload must contain only native_ir and shots")

    native_ir = payload["native_ir"]
    shots = payload["shots"]
    if type(native_ir) is not str or not native_ir.strip():
        raise ValueError("native_ir must be a non-empty built-in str")
    if type(shots) is not int or shots <= 0:
        raise ValueError("shots must be a positive built-in int")
    return native_ir, shots


def _execution_source(native_ir: str) -> str:
    """Adapt only pinned Braket LocalSimulator parser gaps for execution.

    The emitted OpenQASM remains unchanged for LoomQ's target-IR contract.
    Braket LocalSimulator neither ships ``stdgates.inc`` nor implements the
    four standard gates below.  Remove only that complete standalone include,
    then add definitions only for gates present in the emitted source.  All
    other include directives and the official emitted target IR stay intact.
    """
    source = _STANDALONE_STDGATES_INCLUDE.sub("", native_ir)
    required = {
        name for name, pattern in _MISSING_GATE_PATTERNS.items() if pattern.search(source)
    }
    if "ccx" in required:
        required.add("tdg")
    definitions = "".join(
        _MISSING_GATE_DEFINITIONS[name] for name in ("sdg", "tdg", "cp", "ccx") if name in required
    )
    if not definitions:
        return source
    return _OPENQASM_3_HEADER.sub(r"\1" + definitions, source, count=1)


def _json_safe_counts(counts: object) -> dict[str, int]:
    if not isinstance(counts, Mapping) or not counts:
        raise TypeError("Braket measurement counts must be a non-empty mapping")

    safe_counts: dict[str, int] = {}
    for key, value in counts.items():
        if type(key) is not str or not key or any(bit not in "01" for bit in key):
            raise TypeError("Braket measurement count keys must be non-empty binary strings")
        if type(value) is not int or value <= 0:
            raise TypeError("Braket measurement count values must be positive built-in ints")
        safe_counts[key] = value
    return safe_counts


def _provider_task_id(task: object, result: object) -> str | None:
    metadata = getattr(result, "task_metadata", None)
    metadata_id = metadata.get("id") if isinstance(metadata, Mapping) else getattr(metadata, "id", None)
    for value in (getattr(task, "id", None), metadata_id):
        if type(value) is str and value:
            return value
    return None


def _safe_version(value: object) -> str:
    if (
        type(value) is str
        and value
        and len(value) <= 128
        and all(character in _SAFE_VERSION_CHARACTERS for character in value)
    ):
        return value
    return "unknown"


def execute_payload(payload: dict[str, object]) -> dict[str, object]:
    """Execute one validated local Braket request and return protocol data."""
    native_ir, shots = _validate_payload(payload)
    sdk = _import_braket()
    program = sdk.Program(source=_execution_source(native_ir))
    task = sdk.LocalSimulator().run(program, shots=shots)
    result = task.result()
    response: dict[str, object] = {
        "counts": _json_safe_counts(getattr(result, "measurement_counts", None)),
        "sdk_version": _safe_version(getattr(sdk, "version", "unknown")),
    }
    job_id = _provider_task_id(task, result)
    if job_id is not None:
        response["job_id"] = job_id
    return response


def main() -> int:
    """Read one request from stdin and write one safe JSON response."""
    try:
        payload = json.load(sys.stdin)
        response = execute_payload(payload)
        json.dump(response, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        sys.stderr.write("Braket worker failed\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
