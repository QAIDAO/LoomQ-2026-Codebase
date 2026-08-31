"""Final-verification helpers for the official L1 circuit families."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import re
import tempfile
from typing import Any

from .gate_policy import PUBLIC_GATE_WHITELIST
from .pipeline import trace_transpilation
from .qasm import GateOperation, MeasureOperation, Program, parse_openqasm2
from .simulator import _parameter_value


STARTER_KIT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class VerificationRecord:
    case: str
    target: str
    check: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def official_family_circuits() -> dict[str, str]:
    """Build eight transparent surrogates matching the published family list."""

    circuits = {
        "bell": (STARTER_KIT / "circuits" / "bell.qasm").read_text(
            encoding="utf-8"
        ),
        "ghz3": (STARTER_KIT / "circuits" / "ghz3.qasm").read_text(
            encoding="utf-8"
        ),
        "ghz5": _ghz(5),
        "qft4": _qft4(),
        "grover3": _grover3(),
    }
    for index, seed in enumerate((0xA17E, 0xB29F, 0xC3D0), start=1):
        circuits[f"random{index}"] = _random_circuit(seed)
    if len(circuits) != 8:
        raise AssertionError("official family verification must contain eight circuits")
    return circuits


def verify_official_family_roundtrips() -> list[VerificationRecord]:
    records: list[VerificationRecord] = []
    for case, source in official_family_circuits().items():
        expected = _signature(parse_openqasm2(source))
        for target in ("spinq", "originq", "braket"):
            try:
                trace = trace_transpilation(source, target)
                observed = _target_signature(target, trace.public_ir)
                if observed != expected:
                    raise AssertionError("target IR semantic signature changed")
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "roundtrip",
                        "pass",
                        hashlib.sha256(trace.public_ir.encode("utf-8")).hexdigest(),
                    )
                )
            except Exception as exc:
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "roundtrip",
                        "fail",
                        f"{type(exc).__name__}: {exc}",
                    )
                )
    return records


def verify_vendor_parsers(*, require_native: bool = False) -> list[VerificationRecord]:
    """Ask installed vendor SDKs to consume every emitted target artifact."""

    records: list[VerificationRecord] = []
    circuits = official_family_circuits()
    modules = {"spinq": "spinqit", "originq": "pyqpanda", "braket": "braket"}
    for target, module in modules.items():
        if importlib.util.find_spec(module) is None:
            status = "fail" if require_native else "skip"
            for case in circuits:
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-parser",
                        status,
                        f"optional module {module} is not installed",
                    )
                )
            continue
        for case, source in circuits.items():
            artifact = trace_transpilation(source, target).runtime_ir
            try:
                _vendor_accepts(target, artifact)
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-parser",
                        "pass",
                        f"{module} accepted emitted IR",
                    )
                )
            except Exception as exc:
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-parser",
                        "fail",
                        f"{type(exc).__name__}: {exc}",
                    )
                )
    return records


def verify_vendor_executions(
    *, require_native: bool = False, shots: int = 8192
) -> list[VerificationRecord]:
    """Execute each pipeline runtime artifact through its target SDK."""

    from .backends import run as run_backend

    records: list[VerificationRecord] = []
    circuits = official_family_circuits()
    modules = {"spinq": "spinqit", "originq": "pyqpanda", "braket": "braket"}
    for target, module in modules.items():
        if importlib.util.find_spec(module) is None:
            status = "fail" if require_native else "skip"
            for case in circuits:
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-execution",
                        status,
                        f"optional module {module} is not installed",
                    )
                )
            continue
        for case, source in circuits.items():
            trace = trace_transpilation(source, target)
            expected_sha256 = hashlib.sha256(
                trace.runtime_ir.encode("utf-8")
            ).hexdigest()
            previous = os.environ.get("LOOMQ_REQUIRE_NATIVE")
            os.environ["LOOMQ_REQUIRE_NATIVE"] = "1"
            try:
                result = run_backend(source, target, shots)
                executed = result.get("meta", {}).get("executed_artifact", {})
                acceptance = result.get("meta", {}).get("acceptance", {})
                if executed.get("sha256") != expected_sha256:
                    raise AssertionError("runner artifact hash differs from pipeline output")
                if acceptance.get("status") != "accepted":
                    raise AssertionError("native result did not pass semantic acceptance")
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-execution",
                        "pass",
                        expected_sha256,
                    )
                )
            except Exception as exc:
                records.append(
                    VerificationRecord(
                        case,
                        target,
                        "vendor-execution",
                        "fail",
                        f"{type(exc).__name__}: {exc}",
                    )
                )
            finally:
                if previous is None:
                    os.environ.pop("LOOMQ_REQUIRE_NATIVE", None)
                else:
                    os.environ["LOOMQ_REQUIRE_NATIVE"] = previous
    return records


def _vendor_accepts(target: str, artifact: str) -> None:
    if target == "spinq":
        from spinqit import get_compiler

        path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".qasm",
                delete=False,
                encoding="utf-8",
            ) as handle:
                handle.write(artifact)
                path = handle.name
            get_compiler("qasm").compile(path, 0)
        finally:
            if path:
                Path(path).unlink(missing_ok=True)
        return
    if target == "originq":
        import pyqpanda as pq

        machine = pq.CPUQVM()
        machine.init_qvm()
        try:
            if hasattr(pq, "convert_originir_string_to_qprog"):
                pq.convert_originir_string_to_qprog(artifact, machine)
            elif hasattr(pq, "convert_originir_str_to_qprog"):
                pq.convert_originir_str_to_qprog(artifact, machine)
            elif hasattr(pq, "convert_originir_to_qprog"):
                path = ""
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".originir",
                        delete=False,
                        encoding="utf-8",
                    ) as handle:
                        handle.write(artifact)
                        path = handle.name
                    pq.convert_originir_to_qprog(path, machine)
                finally:
                    if path:
                        Path(path).unlink(missing_ok=True)
            else:
                raise RuntimeError("installed pyqpanda exposes no OriginIR parser")
        finally:
            machine.finalize()
        return
    if target == "braket":
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program as OpenQASMProgram

        LocalSimulator().run(OpenQASMProgram(source=artifact), shots=1).result()
        return
    raise ValueError(f"Unsupported target: {target}")


def _signature(program: Program) -> list[tuple[Any, ...]]:
    result: list[tuple[Any, ...]] = []
    for operation in program.operations:
        if isinstance(operation, GateOperation):
            result.append(
                (
                    "gate",
                    operation.name,
                    _angle(operation.parameter),
                    tuple(_index(item) for item in operation.operands),
                )
            )
        elif operation.source == program.quantum_register.name:
            result.extend(
                ("measure", index, index)
                for index in range(program.quantum_register.size)
            )
        else:
            result.append(
                (
                    "measure",
                    _index(operation.source),
                    _index(operation.destination),
                )
            )
    return result


def _target_signature(target: str, source: str) -> list[tuple[Any, ...]]:
    if target == "spinq":
        return _signature(parse_openqasm2(source))
    if target == "originq":
        return _origin_signature(source)
    if target == "braket":
        return _braket_signature(source)
    raise ValueError(f"Unsupported target: {target}")


def _origin_signature(source: str) -> list[tuple[Any, ...]]:
    names = {
        "H": "h",
        "X": "x",
        "S": "s",
        "SDAG": "sdg",
        "T": "t",
        "TDAG": "tdg",
        "RZ": "rz",
        "RY": "ry",
        "CNOT": "cx",
        "CU1": "cu1",
        "CR": "cu1",
        "SWAP": "swap",
        "TOFFOLI": "ccx",
    }
    result: list[tuple[Any, ...]] = []
    dagger = False
    for line in map(str.strip, source.splitlines()):
        if not line or line.startswith(("QINIT ", "CREG ")):
            continue
        if line == "DAGGER":
            if dagger:
                raise ValueError("nested OriginIR DAGGER blocks are unsupported")
            dagger = True
            continue
        if line == "ENDDAGGER":
            if not dagger:
                raise ValueError("OriginIR ENDDAGGER has no matching DAGGER")
            dagger = False
            continue
        if line.startswith("MEASURE "):
            if dagger:
                raise ValueError("measurement inside OriginIR DAGGER block")
            left, right = map(str.strip, line[8:].split(","))
            result.append(("measure", _index(left), _index(right)))
            continue
        parameterized = re.fullmatch(r"([A-Z0-9]+)\s+(.+),\((.*)\)", line)
        if parameterized is not None and parameterized.group(1) in names:
            result.append(
                (
                    "gate",
                    _dagger_name(names[parameterized.group(1)], dagger),
                    _angle(parameterized.group(3)),
                    tuple(
                        _index(item)
                        for item in parameterized.group(2).split(",")
                    ),
                )
            )
            continue
        match = re.fullmatch(r"([A-Z0-9]+)(?:\((.+)\))?\s+(.+)", line)
        if match is None or match.group(1) not in names:
            raise ValueError(f"unrecognized OriginIR statement: {line}")
        result.append(
            (
                "gate",
                _dagger_name(names[match.group(1)], dagger),
                _angle(match.group(2)),
                tuple(_index(item) for item in match.group(3).split(",")),
            )
        )
    if dagger:
        raise ValueError("unterminated OriginIR DAGGER block")
    return result


def _braket_signature(source: str) -> list[tuple[Any, ...]]:
    names = {
        "si": "sdg",
        "ti": "tdg",
        "cnot": "cx",
        "cp": "cu1",
        "cphaseshift": "cu1",
        "ccnot": "ccx",
    }
    qubits = re.search(r"qubit\[(\d+)\]", source)
    if qubits is None:
        raise ValueError("OpenQASM 3 artifact has no qubit declaration")
    width = int(qubits.group(1))
    result: list[tuple[Any, ...]] = []
    for statement in (item.strip() for item in source.split(";")):
        if not statement or statement.startswith(
            ("OPENQASM ", "include ", "qubit[", "bit[")
        ):
            continue
        if re.fullmatch(r"\w+\s*=\s*measure\s+\w+", statement):
            result.extend(("measure", index, index) for index in range(width))
            continue
        partial = re.fullmatch(
            r"\w+\[(\d+)\]\s*=\s*measure\s+\w+\[(\d+)\]", statement
        )
        if partial:
            result.append(
                ("measure", int(partial.group(2)), int(partial.group(1)))
            )
            continue
        match = re.fullmatch(r"([a-z]+)(?:\((.+)\))?\s+(.+)", statement)
        if match is None:
            raise ValueError(f"unrecognized OpenQASM 3 statement: {statement}")
        name = names.get(match.group(1), match.group(1))
        if name not in PUBLIC_GATE_WHITELIST:
            raise ValueError(f"OpenQASM 3 emitted unknown semantic gate: {name}")
        result.append(
            (
                "gate",
                name,
                _angle(match.group(2)),
                tuple(_index(item) for item in match.group(3).split(",")),
            )
        )
    return result


def _dagger_name(name: str, dagger: bool) -> str:
    if not dagger:
        return name
    inverse = {"s": "sdg", "t": "tdg"}
    if name not in inverse:
        raise ValueError(f"unsupported OriginIR daggered gate: {name}")
    return inverse[name]


def _ghz(width: int) -> str:
    gates = ["h q[0];"] + [
        f"cx q[{index - 1}], q[{index}];" for index in range(1, width)
    ]
    return _program(width, gates)


def _qft4() -> str:
    gates = ["x q[0];", "x q[2];"]
    for current in reversed(range(4)):
        gates.append(f"h q[{current}];")
        for control in reversed(range(current)):
            gates.append(
                f"cu1(pi/{1 << (current - control)}) q[{current}], q[{control}];"
            )
    gates.extend(["swap q[0], q[3];", "swap q[1], q[2];"])
    return _program(4, gates)


def _grover3() -> str:
    gates = ["h q[0];", "h q[1];", "h q[2];"]
    for _iteration in range(2):
        gates.extend(["h q[2];", "ccx q[0], q[1], q[2];", "h q[2];"])
        gates.extend(["h q[0];", "h q[1];", "h q[2];"])
        gates.extend(["x q[0];", "x q[1];", "x q[2];"])
        gates.extend(["h q[2];", "ccx q[0], q[1], q[2];", "h q[2];"])
        gates.extend(["x q[0];", "x q[1];", "x q[2];"])
        gates.extend(["h q[0];", "h q[1];", "h q[2];"])
    return _program(3, gates)


def _random_circuit(seed: int) -> str:
    rng = random.Random(seed)
    width = 5
    gates: list[str] = [
        "h q[0];",
        "x q[1];",
        "s q[2];",
        "sdg q[2];",
        "t q[3];",
        "tdg q[3];",
        "rz(pi/7) q[0];",
        "ry(-pi/5) q[1];",
        "cx q[0], q[1];",
        "cu1(pi/3) q[1], q[2];",
        "swap q[2], q[3];",
        "ccx q[0], q[1], q[4];",
    ]
    for _offset in range(12):
        gate = rng.choice(("h", "x", "s", "t", "rz", "ry", "cx", "cu1", "swap"))
        if gate in {"h", "x", "s", "t"}:
            gates.append(f"{gate} q[{rng.randrange(width)}];")
        elif gate in {"rz", "ry"}:
            gates.append(f"{gate}({rng.choice((-3, -1, 1, 5))}*pi/7) q[{rng.randrange(width)}];")
        elif gate == "cu1":
            first, second = rng.sample(range(width), 2)
            gates.append(f"cu1(pi/5) q[{first}], q[{second}];")
        else:
            first, second = rng.sample(range(width), 2)
            gates.append(f"{gate} q[{first}], q[{second}];")
    return _program(width, gates)


def _program(width: int, gates: list[str]) -> str:
    return "\n".join(
        [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{width}];",
            f"creg c[{width}];",
            *gates,
            "measure q -> c;",
            "",
        ]
    )


def _angle(expression: str | None) -> float | None:
    return (
        None
        if expression is None
        else round(_parameter_value(expression.lower()), 12)
    )


def _index(operand: str) -> int:
    match = re.search(r"\[(\d+)\]", operand.strip())
    if match is None:
        raise ValueError(f"indexed operand expected: {operand}")
    return int(match.group(1))
