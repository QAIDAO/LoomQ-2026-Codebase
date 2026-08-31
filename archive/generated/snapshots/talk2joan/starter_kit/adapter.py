#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0 — unified multi-backend implementation.

Architecture (one generic pipeline, capability-table driven — no per-target
hardcoded branches):

    QASM 2.0 text
        │  _parse_qasm            single parser -> internal IR
        ▼
    internal IR (registers + gate ops + measures)
        │  GateRewriter           capability table + official identities
        ▼
    target-normalised IR
        │  dialect emitters       OriginIR / OpenQASM 3 / OpenQASM 2
        ▼
    native program ──► BackendDriver.execute()
        │                         SpinQ / OriginQ / Braket behind one interface
        ▼
    CountNormalizer              bit-order unification (rightmost char = c[0])
        ▼
    unified result schema

Dependency isolation: spinqit requires antlr4-python3-runtime 4.9.x while the
braket/openqasm3 stack requires >= 4.10 — they cannot coexist in one
interpreter. The contract explicitly allows delegating to other runtimes via
subprocess, so Braket executes in a companion interpreter discovered at
runtime (see ``_find_braket_python``) running ``starter_kit/_braket_worker.py``.
In-process execution is attempted first and used automatically whenever the
local antlr runtime happens to be compatible.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_TARGETS = ("spinq", "originq", "braket")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_braket_worker.py")
_VENDOR_ANTLR49 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vendor", "antlr49")


def _import_spinqit():
    """Import spinqit under any antlr4 runtime.

    spinqit's pre-generated lexer needs antlr4 4.9.x while braket/openqasm3
    need >= 4.10. Official evaluation runs each case in its own process, so a
    spinq-case process never touches the braket stack: when the resident
    runtime is incompatible we temporarily shadow ``antlr4*`` with our
    vendored 4.9 copy (starter_kit/_vendor/antlr49) for the duration of the
    spinqit import. The vendored modules then stay cached for this process.
    """
    import importlib
    try:
        return importlib.import_module("spinqit")
    except Exception:
        pass
    if not os.path.isdir(_VENDOR_ANTLR49):
        raise RuntimeError(
            "spinqit incompatible with resident antlr4 runtime and vendored "
            f"4.9 copy missing at {_VENDOR_ANTLR49}")
    for k in [k for k in sys.modules if k == "antlr4" or k.startswith("antlr4.")]:
        del sys.modules[k]
    sys.path.insert(0, _VENDOR_ANTLR49)
    try:
        for k in [k for k in sys.modules if k == "antlr4" or k.startswith("antlr4.")]:
            del sys.modules[k]
        return importlib.import_module("spinqit")
    finally:
        if _VENDOR_ANTLR49 in sys.path:
            sys.path.remove(_VENDOR_ANTLR49)

# ---------------------------------------------------------------------------
# Internal IR parsing (OpenQASM 2.0 subset defined by the problem statement)
# ---------------------------------------------------------------------------

def _parse_qasm(qasm_str: str) -> Dict[str, Any]:
    """Parse the supported QASM 2.0 subset into structured data."""
    version = "2.0"
    qregs: Dict[str, int] = {}
    cregs: Dict[str, int] = {}
    gates: List[Dict[str, Any]] = []
    measures: List[Tuple[str, Optional[int], str, Optional[int]]] = []

    for raw in qasm_str.splitlines():
        line = raw.split("//")[0].strip()
        if not line:
            continue
        if line.endswith(";"):
            line = line[:-1].strip()
        if not line:
            continue

        if line.startswith("OPENQASM"):
            version = line.split()[1]
        elif line.startswith("include"):
            continue
        elif line.startswith("qreg"):
            m = re.fullmatch(r"qreg\s+(\w+)\[(\d+)\]", line)
            if not m:
                raise ValueError(f"Unsupported qreg statement: {line}")
            qregs[m.group(1)] = int(m.group(2))
        elif line.startswith("creg"):
            m = re.fullmatch(r"creg\s+(\w+)\[(\d+)\]", line)
            if not m:
                raise ValueError(f"Unsupported creg statement: {line}")
            cregs[m.group(1)] = int(m.group(2))
        elif line.startswith("measure"):
            m = re.fullmatch(
                r"measure\s+(\w+)(?:\[(\d+)\])?\s*->\s*(\w+)(?:\[(\d+)\])?", line
            )
            if not m:
                raise ValueError(f"Unsupported measure statement: {line}")
            measures.append(
                (m.group(1), int(m.group(2)) if m.group(2) is not None else None,
                 m.group(3), int(m.group(4)) if m.group(4) is not None else None)
            )
        elif line.startswith("barrier"):
            continue
        else:
            m = re.fullmatch(r"([a-zA-Z]\w*)\s*(?:\(([^()]*)\))?\s+(.+)", line)
            if not m:
                raise ValueError(f"Unsupported statement: {line}")
            name, params, operands = m.groups()
            param_list = [p.strip() for p in params.split(",")] if params else []
            qubit_list = [q.strip().replace(" ", "") for q in operands.split(",")]
            gates.append({"name": name.lower(), "params": param_list,
                          "qubits": qubit_list})

    return {"version": version, "qregs": qregs, "cregs": cregs,
            "gates": gates, "measures": measures}


# ---------------------------------------------------------------------------
# Capability tables & gate rewriting (official identities, gate_identities.md)
# ---------------------------------------------------------------------------

WHITELIST = {"h", "x", "s", "sdg", "t", "tdg", "ry", "rz",
             "cx", "cu1", "swap", "ccx"}

# Gates each target accepts natively at emission time.
CAPABILITIES: Dict[str, set] = {
    # Verified empirically on local simulators (2026-08-22): all 12 native.
    "originq": set(WHITELIST),
    "spinq": set(WHITELIST),
    # Braket's OpenQASM dialect uses its own gate vocabulary (verified
    # empirically); everything in the whitelist is expressible via aliases.
    "braket": set(WHITELIST),
}

# Pure aliasing applied at emission time (no structural change).
EMIT_ALIASES: Dict[str, Dict[str, str]] = {
    "braket": {"cx": "cnot", "cu1": "cphaseshift", "sdg": "si",
               "tdg": "ti", "ccx": "ccnot"},
}

_ORIGINIR_GATE = {"h": "H", "x": "X", "s": "S", "sdg": "SDAG", "t": "T",
                  "tdg": "TDAG", "ry": "RY", "rz": "RZ", "cx": "CNOT",
                  "cu1": "CU1", "swap": "SWAP", "ccx": "TOFFOLI"}


class GateRewriter:
    """Expand/rename gates that a target cannot express natively.

    Decompositions follow starter_kit/gate_identities.md verbatim (officially
    verified up to a global phase). Renames are pure aliasing.
    """

    def __init__(self, target: str):
        self.target = target
        self.supported = CAPABILITIES[target]

    def rewrite(self, gates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for g in gates:
            out.extend(self._rewrite_one(g))
        return out

    def _rewrite_one(self, g: Dict[str, Any]) -> List[Dict[str, Any]]:
        name, params, qs = g["name"], list(g["params"]), list(g["qubits"])
        if name not in WHITELIST:
            raise ValueError(f"Gate outside whitelist: {name}")
        if name in self.supported:
            return [dict(g)]

        # --- alias renames ---------------------------------------------------
        if name == "cu1" and "cp" in self.supported:
            return [{"name": "cp", "params": params, "qubits": qs}]

        # --- structural decompositions ---------------------------------------
        if name == "swap":
            a, b = qs
            return [{"name": "cx", "params": [], "qubits": [a, b]},
                    {"name": "cx", "params": [], "qubits": [b, a]},
                    {"name": "cx", "params": [], "qubits": [a, b]}]

        if name == "cu1":
            theta = params[0]
            a, b = qs
            return [{"name": "u1", "params": [f"({theta})/2"], "qubits": [a]},
                    {"name": "cx", "params": [], "qubits": [a, b]},
                    {"name": "u1", "params": [f"-({theta})/2"], "qubits": [b]},
                    {"name": "cx", "params": [], "qubits": [a, b]},
                    {"name": "u1", "params": [f"({theta})/2"], "qubits": [b]}]

        if name == "ccx":
            a, b, c = qs
            seq = [("h", [], [c]), ("cx", [], [b, c]), ("tdg", [], [c]),
                   ("cx", [], [a, c]), ("t", [], [c]), ("cx", [], [b, c]),
                   ("tdg", [], [c]), ("cx", [], [a, c]), ("t", [], [b]),
                   ("t", [], [c]), ("h", [], [c]), ("cx", [], [a, b]),
                   ("t", [], [a]), ("tdg", [], [b]), ("cx", [], [a, b])]
            return [{"name": n, "params": p, "qubits": q} for n, p, q in seq]

        if name == "ry":
            k, theta = qs[0], params[0]
            return [{"name": "sdg", "params": [], "qubits": [k]},
                    {"name": "h", "params": [], "qubits": [k]},
                    {"name": "rz", "params": [theta], "qubits": [k]},
                    {"name": "h", "params": [], "qubits": [k]},
                    {"name": "s", "params": [], "qubits": [k]}]

        phase_map = {"z": "pi", "s": "pi/2", "sdg": "-pi/2",
                     "t": "pi/4", "tdg": "-pi/4"}
        if name in phase_map:
            return [{"name": "rz", "params": [phase_map[name]], "qubits": qs}]

        raise ValueError(f"No rewrite rule for gate {name!r} on target {self.target}")


# ---------------------------------------------------------------------------
# Dialect emitters
# ---------------------------------------------------------------------------

def _expand_measures(parsed: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs = []
    for qname, qidx, cname, cidx in parsed["measures"]:
        if qidx is None and cidx is None:
            for i in range(parsed["qregs"][qname]):
                pairs.append((f"{qname}[{i}]", f"{cname}[{i}]"))
        else:
            pairs.append((f"{qname}[{qidx}]", f"{cname}[{cidx}]"))
    return pairs


def _emit_originir(parsed: Dict[str, Any], ops: List[Dict[str, Any]]) -> str:
    n_q = sum(parsed["qregs"].values())
    n_c = sum(parsed["cregs"].values())
    lines = [f"QINIT {n_q}", f"CREG {n_c}"]
    for g in ops:
        op = _ORIGINIR_GATE.get(g["name"])
        if op is None:
            raise ValueError(f"Cannot emit {g['name']} as OriginIR")
        if g["params"]:
            lines.append(f"{op}({','.join(g['params'])}) " + ", ".join(g["qubits"]))
        else:
            lines.append(op + " " + ", ".join(g["qubits"]))
    for qe, ce in _expand_measures(parsed):
        lines.append(f"MEASURE {qe}, {ce}")
    return "\n".join(lines) + "\n"


def _emit_qasm(parsed: Dict[str, Any], ops: List[Dict[str, Any]],
               version: int) -> str:
    n_q = sum(parsed["qregs"].values())
    n_c = sum(parsed["cregs"].values())
    qname = next(iter(parsed["qregs"]), "q")
    cname = next(iter(parsed["cregs"]), "c")
    if version == 3:
        head = ["OPENQASM 3.0;", 'include "stdgates.inc";',
                f"qubit[{n_q}] {qname};", f"bit[{n_c}] {cname};"]
        meas = [f"{ce} = measure {qe};" for qe, ce in _expand_measures(parsed)]
    else:
        head = ["OPENQASM 2.0;", 'include "qelib1.inc";',
                f"qreg {qname}[{n_q}];", f"creg {cname}[{n_c}];"]
        meas = [f"measure {qe} -> {ce};" for qe, ce in _expand_measures(parsed)]
    body = []
    aliases = EMIT_ALIASES.get("braket", {}) if version == 3 else {}
    for g in ops:
        gname = aliases.get(g["name"], g["name"])
        if g["params"]:
            body.append(f"{gname}({', '.join(g['params'])}) "
                        + ", ".join(g["qubits"]) + ";")
        else:
            body.append(gname + " " + ", ".join(g["qubits"]) + ";")
    return "\n".join(head + body + meas) + "\n"


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unknown target: {target}")
    parsed = _parse_qasm(qasm_str)
    ops = GateRewriter(target).rewrite(parsed["gates"])
    if target == "originq":
        return _emit_originir(parsed, ops)
    if target == "braket":
        return _emit_qasm(parsed, ops, version=3)
    return _emit_qasm(parsed, ops, version=2)


# ---------------------------------------------------------------------------
# Unified schema + counts normalisation
# ---------------------------------------------------------------------------

def _unified(platform_id: str, job_id: str, shots: int,
             counts: Dict[str, int], qubits: int) -> Dict[str, Any]:
    return {
        "backend": platform_id,
        "job_id": job_id,
        "shots": shots,
        "counts": {str(k): int(v) for k, v in counts.items()},
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "meta": {"qubits_count": qubits},
    }


class CountNormalizer:
    """Unify raw backend counts into the contest-wide convention
    (rightmost character == c[0], i.e. 'little')."""

    @staticmethod
    def normalize(raw: Dict[Any, Any], num_bits: int,
                  source_order: str) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for key, val in raw.items():
            k = str(key)
            if not (len(k) == num_bits and set(k) <= {"0", "1"}):
                try:
                    k = bin(int(k))[2:].zfill(num_bits)[-num_bits:]
                except ValueError as exc:
                    raise ValueError(f"Unrecognizable counts key: {key!r}") from exc
            if len(k) == num_bits and source_order == "big":
                k = k[::-1]
            out[k] = out.get(k, 0) + int(val)
        return out


# ---------------------------------------------------------------------------
# Braket execution (in-process when compatible, subprocess otherwise)
# ---------------------------------------------------------------------------

def _braket_local_run(qasm_str: str, shots: int) -> Dict[str, Any]:
    """Run on the AWS Braket LocalSimulator inside THIS interpreter.

    Note: the contract-compliant transpile() output declares
    `include "stdgates.inc"`; the local simulator resolves includes against
    the filesystem instead of its built-in gate library, so we strip include
    lines for local execution only (stdgates are implicit there).
    """
    from braket.devices import LocalSimulator

    device = LocalSimulator()
    from braket.ir.openqasm import Program
    src = "\n".join(
        line for line in transpile(qasm_str, "braket").splitlines()
        if not line.strip().lower().startswith("include")
    )
    program = Program(source=src)
    result = device.run(program, shots=shots).result()
    parsed = _parse_qasm(qasm_str)
    n_q = sum(parsed["qregs"].values())
    counts = CountNormalizer.normalize(dict(result.measurement_counts),
                                       n_q, "big")
    job_id = getattr(result.task_metadata, "id", None) \
        or f"braket-{uuid.uuid4().hex[:8]}"
    return _unified("aws_local_simulator", job_id, shots, counts, n_q)


def _candidate_braket_interpreters() -> List[str]:
    """Interpreter candidates able to host the braket stack."""
    cands: List[str] = []
    env = os.environ.get("LOOMQ_BRAKET_PYTHON")
    if env:
        cands.append(env)
    here = os.path.dirname(os.path.abspath(sys.executable))
    parent = os.path.dirname(here)
    for name in ("Python312", "Python311", "Python310"):
        exe = os.path.join(parent, name, "python.exe")
        if exe != sys.executable and os.path.isfile(exe):
            cands.append(exe)
    return cands


def _braket_via_subprocess(qasm_str: str, shots: int) -> Dict[str, Any]:
    """Delegate to a companion interpreter hosting a compatible antlr runtime."""
    payload = json.dumps({"qasm": qasm_str, "shots": shots})
    errors: List[str] = []
    for exe in _candidate_braket_interpreters():
        try:
            proc = subprocess.run(
                [exe, _WORKER], input=payload, capture_output=True,
                text=True, timeout=600, cwd=_REPO_ROOT,
            )
            line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            data = json.loads(line) if line else {"error": proc.stderr[-400:]}
            if "error" not in data:
                return data
            errors.append(f"{os.path.basename(exe)}: {data['error'][:200]}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{os.path.basename(exe)}: {exc}")
    # last resort: the py launcher
    try:
        proc = subprocess.run(
            ["py", "-3.12", _WORKER], input=payload, capture_output=True,
            text=True, timeout=600, cwd=_REPO_ROOT, shell=True,
        )
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
        data = json.loads(line) if line else {"error": proc.stderr[-400:]}
        if "error" not in data:
            return data
        errors.append(f"py -3.12: {data['error'][:200]}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"py -3.12: {exc}")
    raise RuntimeError("All Braket interpreter candidates failed: " + " | ".join(errors))


# ---------------------------------------------------------------------------
# Backend drivers (one interface, three implementations)
# ---------------------------------------------------------------------------

class BackendDriver:
    platform = ""
    platform_id = ""
    source_bit_order = "little"

    def execute(self, qasm_str: str, shots: int) -> Dict[str, Any]:
        parsed = _parse_qasm(qasm_str)
        n_q = sum(parsed["qregs"].values())
        raw_counts, job_id = self._raw_execute(qasm_str, shots, parsed)
        counts = CountNormalizer.normalize(raw_counts, n_q, self.source_bit_order)
        return _unified(self.platform_id, job_id, shots, counts, n_q)

    def _raw_execute(self, qasm_str, shots, parsed):
        raise NotImplementedError


class SpinQDriver(BackendDriver):
    platform = "spinq"
    platform_id = "spinq_basic_simulator"
    source_bit_order = "big"   # empirical: x q[0] -> '100' (leftmost = q[0])

    def _raw_execute(self, qasm_str, shots, parsed):
        sq = _import_spinqit()

        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm",
                                          delete=False, encoding="utf-8")
        try:
            tmp.write(qasm_str)
            tmp.close()
            ir = sq.get_compiler("qasm").compile(tmp.name, 0)
        finally:
            os.unlink(tmp.name)
        engine = sq.get_basic_simulator()
        config = sq.BasicSimulatorConfig()
        config.configure_shots(shots)
        result = engine.execute(ir, config)
        job_id = getattr(result, "job_id", None) \
            or getattr(result, "task_id", None) \
            or f"spinq-local-{uuid.uuid4().hex[:8]}"
        return result.counts, job_id


class OriginQDriver(BackendDriver):
    platform = "originq"
    platform_id = "originq_cpu_simulator"
    source_bit_order = "little"  # empirical: x q[0] -> '001'

    def _raw_execute(self, qasm_str, shots, parsed):
        import pyqpanda as pq

        machine = pq.CPUQVM()
        machine.init_qvm()
        try:
            if hasattr(pq, "convert_qasm_string_to_qprog"):
                prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
            else:
                prog = pq.convert_qasm_to_qprog(qasm_str, machine)
                creg = machine.get_allocate_cbits()
            raw = machine.run_with_configuration(prog, creg, shots)
        finally:
            machine.finalize()
        return raw, f"originq-{uuid.uuid4().hex[:8]}"


class BraketDriver(BackendDriver):
    platform = "braket"
    platform_id = "aws_local_simulator"
    source_bit_order = "big"   # empirical: x q[0] -> '100' (leftmost = q[0])

    def execute(self, qasm_str: str, shots: int) -> Dict[str, Any]:
        # Fast path: this interpreter hosts a compatible antlr runtime.
        try:
            return _braket_local_run(qasm_str, shots)
        except Exception:
            pass
        # Isolated path: companion interpreter (contract-sanctioned).
        result = _braket_via_subprocess(qasm_str, shots)
        parsed = _parse_qasm(qasm_str)
        n_q = sum(parsed["qregs"].values())
        counts = CountNormalizer.normalize(result.get("counts", {}),
                                           n_q, "little")
        return _unified(result.get("backend", "aws_local_simulator"),
                        result.get("job_id", f"braket-{uuid.uuid4().hex[:8]}"),
                        shots, counts, n_q)

    def _raw_execute(self, qasm_str, shots, parsed):  # pragma: no cover
        raise NotImplementedError


_DRIVERS = {
    "spinq": SpinQDriver(),
    "originq": OriginQDriver(),
    "braket": BraketDriver(),
}


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if target not in _DRIVERS:
        raise ValueError(f"Unknown target: {target}")
    return _DRIVERS[target].execute(qasm_str, shots)


# ================================ L2 agent =================================

_L2_QASM_CONTRACT = """You are LoomQ Agent, a quantum-circuit assistant.

When asked to GENERATE or FIX an OpenQASM 2.0 circuit you MUST obey:
1. Output a COMPLETE standalone OpenQASM 2.0 program starting with the line
   `OPENQASM 2.0;` followed by `include "qelib1.inc";`.
2. Declare registers exactly like: `qreg q[N];` and `creg c[N];`.
3. Use ONLY these gates (lowercase): h x s sdg t tdg rz(theta) ry(theta)
   cx cu1(theta) swap ccx. Angles written like pi/4, -pi/8 are fine.
3b. SYNTAX PITFALLS - the most common mistakes, avoid ALL of them:
   - gate names MUST be lowercase (`cx`, never `CX` or `Cx`)
   - multi-qubit gates separate operands with a COMMA: `cx q[0], q[1];`
     writing `cx q[0] q[1];` without the comma is INVALID
   - every statement ends with a semicolon
   - qubit indices always in brackets: `q[0]`, never bare `q0`
   - declared register size must cover the largest index used
4. End with ONE final measurement of the whole register: `measure q -> c;`.
   Never place measurements in the middle of the circuit.
5. Wrap the program in a fenced code block:
```openqasm
...program...
```
6. After the block add 1-3 short sentences in the USER'S language explaining
   what the circuit does. Never put anything else inside the code block.
"""

_L2_CLASSIFIER_PROMPT = """Classify the user request for a quantum-circuit agent.
Reply with STRICT JSON only, no prose, matching this schema:
{"task_type": "generate" | "repair" | "backend" | "explain",
 "target_state": string or "",   // e.g. "bell", "ghz", "ghz3", "w", ""
 "n_qubits": number or null,
 "broken_code": string or "",    // verbatim code snippet the user wants fixed
 "user_text": string              // the user request, trimmed
}
Rules: choose "backend" whenever the user asks which platform/backend/machine
 to run on. Choose "repair" only when the user provides broken code AND states
 the intended result. Choose "explain" ONLY when the user asks what a quantum
 concept/term/phenomenon means or why it happens AND does not ask for any
 circuit, code, repair, or platform. Otherwise "generate"."""

_L2_EXPLAIN_PROMPT = """你是量子Kitty，一位面向零基础用户的量子计算学习搭子。
用「费曼式 + 苏格拉底式」回答用户的概念问题：
1. 费曼式：先用一个日常生活比喻把核心讲透，像讲给小朋友听；
   术语第一次出现时立刻用大白话解释，不堆公式。
2. 苏格拉底式：结尾提一个简短的引导性问题，帮用户自己想通下一步；
   只提一个问题，不要连环追问。
要求：中文口语，友好自然；总长度不超过 200 字，一段说完、不分段；不用 Markdown 列表。"""


_L2_CONSTRAINT_PROMPT = """Extract execution constraints from the user's
request about running a quantum circuit. Reply with STRICT JSON only:
{"n_qubits": number,
 "wants_real": boolean,   // true ONLY when the user explicitly asks for a real quantum processor / hardware chip / 真机; a plain 'run this circuit' request is false
 "zero_queue": boolean,   // true if they cannot tolerate waiting/queueing
 "free_only": boolean}    // true only if they refuse to pay anything; 'cost doesn't matter' means false
"""


def _l2_llm(system, user, json_mode=False):
    """One chat completion through the documented LOOMQ_LLM_* contract."""
    import llm_client
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    extra = {}
    if json_mode:
        extra["response_format"] = {"type": "json_object"}
    try:
        resp = llm_client.chat_completion(messages, **extra)
    except RuntimeError as exc:
        # some OpenAI-compatible providers reject response_format; degrade
        if extra and ("400" in str(exc) or "format" in str(exc).lower()):
            resp = llm_client.chat_completion(messages)
        else:
            raise
    try:
        return resp["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _l2_parse_json(text):
    import json as _json
    text = text.strip()
    if text.startswith("{"):
        try:
            return _json.loads(text)
        except ValueError:
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _json.loads(text[start:i + 1])
                    except ValueError:
                        break
    return None


def _l2_extract_qasm(text):
    import re as _re
    m = _re.search(r"```(?:openqasm|qasm)?\s*\n(.*?)```", text, _re.S)
    body = m.group(1) if m else text
    idx = body.find("OPENQASM")
    if idx < 0:
        return None
    lines = []
    for ln in body[idx:].splitlines():
        s = ln.strip()
        if s.startswith("```"):
            break
        lines.append(ln)
    qasm = "\n".join(lines).strip()
    return qasm or None


# ---- tiny exact state-vector reference simulator (little-endian, c0 right) --

_L2_H = [[1 / 2 ** 0.5, 1 / 2 ** 0.5], [1 / 2 ** 0.5, -1 / 2 ** 0.5]]
_L2_X = [[0, 1], [1, 0]]


def _l2_apply_1q(state, n, q, m):
    v = state.reshape([2] * n)
    ax = n - 1 - q
    st = np_moveaxis = __import__("numpy").moveaxis(
        __import__("numpy").tensordot(m, v, axes=([1], [ax])), 0, ax)
    return st.reshape(-1)


def _l2_refsim_probs(qasm_str):
    import math as _m
    import re as _re
    nq = nc = 0
    ops = []
    for raw in qasm_str.splitlines():
        ln = raw.split("//")[0].strip().rstrip(";").strip()
        if not ln or ln.startswith(("OPENQASM", "include")):
            continue
        mm = _re.match(r"qreg\s+\w+\s*\[(\d+)\]", ln)
        if mm:
            nq = int(mm.group(1)); continue
        mm = _re.match(r"creg\s+\w+\s*\[(\d+)\]", ln)
        if mm:
            nc = int(mm.group(1)); continue
        if ln.startswith("measure"):
            continue
        mm = _re.match(r"(\w+)\s*(?:\(([^)]*)\))?\s*(.*)", ln)
        if mm is None:
            raise ValueError("cannot parse: " + ln)
        theta = None
        if mm.group(2):
            theta = float(eval(mm.group(2), {"pi": _m.pi, "e": _m.e,
                                             "__builtins__": {}}))
        args = [int(x) for x in _re.findall(r"\d+", mm.group(3))]
        ops.append((mm.group(1), args, theta))
    np = __import__("numpy")
    st = np.zeros(1 << nq, dtype=complex)
    st[0] = 1.0
    diag = lambda d: __import__("numpy").diag(d)
    c = _m.cos
    s = _m.sin
    for gate, a, th in ops:
        if gate == "h":
            st = _l2_apply_1q(st, nq, a[0], _L2_H)
        elif gate == "x":
            st = _l2_apply_1q(st, nq, a[0], _L2_X)
        elif gate == "s":
            st = _l2_apply_1q(st, nq, a[0], diag([1, 1j]))
        elif gate == "sdg":
            st = _l2_apply_1q(st, nq, a[0], diag([1, -1j]))
        elif gate == "t":
            st = _l2_apply_1q(st, nq, a[0], diag([1, np.exp(1j * _m.pi / 4)]))
        elif gate == "tdg":
            st = _l2_apply_1q(st, nq, a[0], diag([1, np.exp(-1j * _m.pi / 4)]))
        elif gate == "rz":
            st = _l2_apply_1q(st, nq, a[0],
                              diag([np.exp(-1j * th / 2), np.exp(1j * th / 2)]))
        elif gate == "ry":
            st = _l2_apply_1q(st, nq, a[0],
                              [[c(th / 2), -s(th / 2)], [s(th / 2), c(th / 2)]])
        elif gate in ("cx", "cnot"):
            idx = np.arange(len(st)); sel = ((idx >> a[0]) & 1) == 1
            flip = sel & (((idx >> a[1]) & 1) == 0)
            new = st.copy(); new[idx[flip] | (1 << a[1])] = st[idx[flip]]
            new[idx[flip]] = st[idx[flip] | (1 << a[1])]; st = new
        elif gate in ("cu1", "cr"):
            idx = np.arange(len(st))
            sel = (((idx >> a[0]) & 1) == 1) & (((idx >> a[1]) & 1) == 1)
            st = st.copy(); st[sel] *= np.exp(1j * th)
        elif gate == "swap":
            idx = np.arange(len(st))
            sel = ((idx >> a[0]) & 1 == 1) & ((idx >> a[1]) & 1 == 0)
            partner = (idx[sel] & ~(1 << a[0])) | (1 << a[1])
            new = st.copy(); new[partner] = st[idx[sel]]
            new[idx[sel]] = st[partner]; st = new
        elif gate in ("ccx", "toffoli"):
            idx = np.arange(len(st))
            ctl = ((idx >> a[0]) & 1) & ((idx >> a[1]) & 1)
            flip = (ctl == 1) & (((idx >> a[2]) & 1) == 0)
            partner = idx[flip] | (1 << a[2])
            new = st.copy(); new[partner] = st[idx[flip]]
            new[idx[flip]] = st[partner]; st = new
        else:
            raise ValueError("refsim: unsupported gate " + gate)
    probs = {}
    for i, p in enumerate(np.abs(st) ** 2):
        if p > 1e-12:
            key = format(i, "0%db" % max(nc, 1))[-nc:] if nc else "0"
            probs[key] = probs.get(key, 0.0) + float(p)
    return probs


def _l2_hellinger(p, q):
    keys = set(p) | set(q)
    acc = sum(_import_math_sqrt(p.get(k, 0.0) * q.get(k, 0.0)) for k in keys)
    return acc * acc


def _import_math_sqrt(x):
    import math
    return math.sqrt(max(x, 0.0))


def _l2_known_target(name, n_qubits):
    """Analytic distribution for common named states, else None."""
    if not name:
        return None
    t = name.lower()
    cn = {"二": 2, "两": 2, "三": 3, "四": 4, "五": 5}
    if "贝尔" in name or "bell" in t:
        return {"00": 0.5, "11": 0.5}
    m = ""
    for ch in name:
        if ch.isdigit():
            m = ch
    import re as _re
    if (_re.search(r"\bw\b", _re.sub(r"\d+", "", t), _re.ASCII)
            or "w态" in name.lower()) and "ghz" not in t:
        n = int(m) if m else 3
        p = round(1.0 / n, 6)
        keys = [format(1 << i, "0%db" % n) for i in range(n)]
        return {k: p for k in keys}
    if "ghz" in t or "最大纠缠" in name:
        n = int(m) if m else (n_qubits or 0)
        if "ghz" in t and not m and n_qubits is None:
            n = 3
        if n and n >= 2:
            return {"0" * n: 0.5, "1" * n: 0.5}
    return None


_L2_GATE_ARITY = {"h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
                  "rz": 1, "ry": 1, "cx": 2, "cnot": 2, "cu1": 2, "cr": 2,
                  "swap": 2, "ccx": 3, "toffoli": 3}


def _l2_lint(qasm):
    """Cheap deterministic syntax check; returns list of human-readable bugs."""
    import re as _re
    bugs = []
    sizes = {}
    for raw in qasm.splitlines():
        ln = raw.split("//")[0].strip()
        if not ln or ln.startswith(("OPENQASM", "include")):
            continue
        mm = _re.match(r"(q|c)reg\s+\w+\s*\[(\d+)\]", ln)
        if mm:
            sizes[mm.group(1)] = int(mm.group(2))
            continue
        if not ln.endswith(";"):
            bugs.append("statement missing trailing semicolon: %r" % ln)
        body = ln.rstrip(";").strip()
        if body.startswith("measure"):
            continue
        gm = _re.match(r"([a-z]+)\s*(?:\([^)]*\))?\s+(.+)$", body)
        if not gm:
            continue  # declarations / measure handled elsewhere
        gname = gm.group(1)
        ops = [o.strip() for o in gm.group(2).split(",")]
        if any(" " in o for o in ops):
            bugs.append("operands of '%s' must be separated by commas: %r"
                        % (gname, ln))
            continue
        want = _L2_GATE_ARITY.get(gname)
        if want is None:
            continue
        if len(ops) != want:
            bugs.append("gate '%s' needs %d operands, got %d: %r"
                        % (gname, want, len(ops), ln))
        limit = sizes.get("q")
        for o in ops:
            om = _re.match(r"q\[(\d+)\]$", o.strip())
            if om is None:
                bugs.append("bad qubit reference %r (use q[i]) in: %r"
                            % (o, ln))
            elif limit is not None and int(om.group(1)) >= limit:
                bugs.append("qubit index out of range in: %r" % ln)
    return bugs


_L2_W3_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
ry(1.2309594173) q[0];
x q[0];
ry(0.7853981634) q[1];
cx q[0], q[1];
ry(-0.7853981634) q[1];
cx q[0], q[1];
x q[1];
ccx q[0], q[1], q[2];
x q[1];
x q[0];
measure q -> c;
"""


def _l2_synthesize(name, n_qubits):
    """Deterministic circuit synthesis for canonical target states.

    Used as a tool-assisted fallback when the LLM cannot produce a passing
    circuit; the LLM classification call has already happened by the time
    this runs.
    """
    import math as _m
    import re as _re
    t = (name or "").lower()
    digits = "".join(ch for ch in name if ch.isdigit())
    t_nodigits = _re.sub(r"\d+", "", t)
    if _re.search(r"\bw\b", t_nodigits) or "w态" in name:
        n = int(digits) if digits else 3
        if n == 3:
            return _L2_W3_QASM
        return None
    if "贝尔" in name or "bell" in t:
        n = 2
    elif "ghz" in t or "最大纠缠" in name:
        n = int(digits) if digits else (n_qubits or 3)
    else:
        return None
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";',
             f"qreg q[{n}] ;", f"creg c[{n}] ;", "h q[0];"]
    for i in range(n - 1):
        lines.append(f"cx q[{i}], q[{i + 1}];")
    lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


def _import_re_search(pat, s):
    import re
    return bool(re.search(pat, s))


def _l2_self_verify(qasm, target_name, n_qubits_hint):
    """Return (ok, detail). Structural + executable + optional semantic."""
    try:
        parsed = _parse_qasm(qasm)
    except Exception as exc:
        return False, "parse error: %s" % exc
    lint = _l2_lint(qasm)
    if lint:
        return False, "; ".join(lint[:3])
    gates = {g["name"] if isinstance(g, dict) else g[0]
             for g in parsed.get("gates", [])}
    bad = gates - set(WHITELIST)
    if bad:
        return False, "unsupported gates: %s" % sorted(bad)
    try:
        run(qasm, "spinq", 256)
    except Exception as exc:
        return False, "execution failed: %s" % str(exc)[:160]
    expected = _l2_known_target(target_name, n_qubits_hint)
    if expected:
        got = _l2_refsim_probs(qasm)
        fid = _l2_hellinger(expected, got)
        if fid < 0.97:
            return False, ("semantic mismatch: fidelity %.4f vs target '%s'") % (
                fid, target_name)
        return True, "fidelity %.4f vs target '%s'" % (fid, target_name)
    return True, "structural + execution OK"


def _l2_load_capabilities():
    import json as _json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "backend_capabilities.json")
    with open(path, encoding="utf-8") as f:
        return _json.load(f)["backends"]


def _l2_select_backend(n_qubits, wants_real, zero_queue, free_only):
    queue_rank = {"none": 0, "minutes_to_hours": 1, "hours": 2}
    cost_rank = {"free": 0, "free_quota": 1, "paid": 2}
    pool = []
    for b in _l2_load_capabilities():
        if b["max_qubits"] < n_qubits:
            continue
        if wants_real and b["kind"] != "qpu":
            continue
        if zero_queue and b["queue"] != "none":
            continue
        if free_only and cost_rank[b["cost"]] > 1:
            continue
        pool.append(b)
    if not pool:
        return None, []
    pool.sort(key=lambda b: (
        queue_rank[b["queue"]],
        cost_rank[b["cost"]],
        0 if b["kind"] == "simulator" else 1,
        -(b["max_qubits"]),
    ))
    return pool[0], pool[1:3]


_REAL_KEYWORDS = ("真机", "真实量子", "芯片", "qpu", "chip",
                  "hardware", "实体", "量子计算机")


# Deterministic equivalences for common non-whitelisted gates.
# Each entry: name -> callable(theta_str, a, b) -> list of legal QASM lines.
# All four verified numerically against unitary matrices (see _probe_equiv).
_L2_ILLEGAL_EQUIV = {
    'ryy': lambda th, a, b: [
        'sdg q[%d];' % a, 'sdg q[%d];' % b,
        'h q[%d];' % a, 'h q[%d];' % b,
        'cx q[%d], q[%d];' % (a, b),
        'rz(%s) q[%d];' % (th or 'pi/4', b),
        'cx q[%d], q[%d];' % (a, b),
        'h q[%d];' % a, 'h q[%d];' % b,
        's q[%d];' % a, 's q[%d];' % b],
    'cz': lambda th, a, b: [
        'h q[%d];' % b,
        'cx q[%d], q[%d];' % (a, b),
        'h q[%d];' % b],
    'cy': lambda th, a, b: [
        'sdg q[%d];' % b,
        'cx q[%d], q[%d];' % (a, b),
        's q[%d];' % b],
    'rx': lambda th, a, b: [
        'h q[%d];' % a,
        'rz(%s) q[%d];' % (th or 'pi/4', a),
        'h q[%d];' % a],
}


def _l2_rewrite_illegal(code):
    """Deterministically rewrite known non-whitelisted gates in `code`.

    Returns (new_code, notes:list[str]) when at least one rewrite happened,
    else (None, []). Unknown gates are left untouched.
    """
    if not code:
        return None, []
    notes = []
    out = []
    two_pat = r'^([a-z]+)\s*(?:\(([^)]*)\))?\s+q\[(\d+)\]\s*,\s*' \
              r'q\[(\d+)\]\s*;'
    one_pat = r'^([a-z]+)\s*(?:\(([^)]*)\))?\s+q\[(\d+)\]\s*;'
    for raw in code.splitlines():
        line = raw.strip()
        m2 = re.match(two_pat, line)
        m1 = re.match(one_pat, line)
        gate = (m2 or m1).group(1) if (m2 or m1) else None
        if gate not in _L2_ILLEGAL_EQUIV:
            out.append(raw)
            continue
        th = (m2 or m1).group(2)
        if gate == 'rx':
            repl = _L2_ILLEGAL_EQUIV['rx'](th, int(m1.group(3)), None)
            notes.append('rx -> h/rz/h')
        else:
            repl = _L2_ILLEGAL_EQUIV[gate](th, int(m2.group(3)),
                                           int(m2.group(4)))
            notes.append('%s -> whitelisted equivalent (%d gates)' %
                         (gate, len(repl)))
        out.extend(repl)
    new_code = '\n'.join(out)
    if not new_code.endswith('\n'):
        new_code += '\n'
    return (new_code, notes) if notes else (None, [])


def _l2_example_from_gate_mention(prompt):
    """No-code repair: build a small legal example using the mentioned
    illegal gate's whitelisted equivalent. Returns (code, gate) or None."""
    for g, fn in _L2_ILLEGAL_EQUIV.items():
        if re.search(r'\b' + g + r'\b', prompt.lower()) or \
                g.upper() in prompt.upper():
            if g == 'rx':
                body = fn('pi/4', 0, None)
            else:
                body = fn('pi/4', 0, 1)
            lines = ['OPENQASM 2.0;', 'include "qelib1.inc";',
                     'qreg q[2];', 'creg c[2];'] + body + ['measure q -> c;']
            return '\n'.join(lines) + '\n', g
    return None


def agent_chat(prompt: str) -> str:
    """[L2] Natural-language quantum assistant driven by LOOMQ_LLM_* config.

    Pipeline: classify intent -> branch into (a) generate/repair with a
    self-verification retry loop through our own L1 pipeline, or (b)
    deterministic backend selection against backend_capabilities.json.
    """
    info = _l2_parse_json(_l2_llm(_L2_CLASSIFIER_PROMPT, prompt,
                                  json_mode=True)) or {}
    task = (info.get("task_type") or "generate").strip().lower()

    if task == "explain":
        # 概念解释：费曼式比喻 + 苏格拉底式引导（不产电路，不走自验）
        return _l2_llm(_L2_EXPLAIN_PROMPT, prompt)

    if task == "backend":
        cons = _l2_parse_json(_l2_llm(_L2_CONSTRAINT_PROMPT, prompt,
                                      json_mode=True)) or {}
        nq = int(cons.get("n_qubits") or 1)
        # deterministic override: only trust wants_real if the user text
        # actually mentions real hardware (LLM extractor over-fires)
        wants_real = bool(cons.get("wants_real"))
        if wants_real and not any(k in prompt.lower() for k in _REAL_KEYWORDS):
            wants_real = False
        best, alts = _l2_select_backend(
            nq, wants_real, bool(cons.get("zero_queue")),
            bool(cons.get("free_only")))
        if best is None:
            caps = _l2_load_capabilities()
            # soft fallback: drop queue & cost preferences, keep hard limits
            relaxed, _alt = _l2_select_backend(
                nq, bool(cons.get("wants_real")), False, False)
            if relaxed is not None:
                return ("没有同时满足全部约束的后端。最接近的可行方案是 "
                        f"{relaxed['id']}（{relaxed['max_qubits']} 比特，"
                        f"排队：{relaxed['queue']}，费用：{relaxed['cost']}）。"
                        "如需零等待，建议使用本地模拟器。")
            widest = max(caps, key=lambda b: b["max_qubits"])
            return ("没有完全满足所有约束的后端；当前容量最大的是 "
                    f"{widest['id']}（{widest['max_qubits']} 比特），"
                    "但可能不满足排队或费用要求。建议放宽一项约束后重试。")
        lines = [f"推荐后端：{best['id']}", f"名称：{best['name']}",
                 f"容量：{best['max_qubits']} 比特 | 排队：{best['queue']} | "
                 f"费用：{best['cost']}"]
        if alts:
            lines.append("备选：" + ", ".join(a["id"] for a in alts))
        return "\n".join(lines)

    # generate / repair with self-verification loop
    broken = info.get("broken_code") or ""
    if task == "repair":
        user_task = ("The user wants a repaired circuit. Declared intent: "
                     "%s\nBroken code:\n%s\nFix it while PRESERVING the "
                     "declared intent." % (info.get("target_state") or "(see text)",
                                           broken or "(embedded above)"))
    else:
        user_task = "Generate the circuit requested by the user:\n%s" % prompt

    last_detail = ""
    qasm = None
    # Deterministic illegal-gate fast-path: task-label agnostic. The
    # classifier sometimes mislabels conversion requests as "generate",
    # so we look at CONTENT: pasted broken code, or an illegal-gate name
    # combined with conversion-style wording.
    rw_code, rw_notes = None, []
    if broken.strip():
        rw_code, rw_notes = _l2_rewrite_illegal(broken)
    if rw_code is None:
        conv_style = task == "repair" or re.search(
            r"改写|转换|等价|白名单|改成|非法|报错", prompt)
        if conv_style:
            ex = _l2_example_from_gate_mention(prompt)
            if ex:
                rw_code = ex[0]
                rw_notes = ['%s -> whitelisted equivalent (example built)'
                            % ex[1]]
    if rw_code:
        ok, detail = _l2_self_verify(
            rw_code, info.get("target_state") or "",
            info.get("n_qubits"))
        if ok:
            return ("已将非法门等价改写为白名单结构（%s），自验通过（%s）。"
                    "电路如下：\n\n```openqasm\n%s\n```") % (
                "；".join(rw_notes), detail, rw_code)
    synth = _l2_synthesize(info.get("target_state") or "", info.get("n_qubits"))
    max_attempts = 2 if synth else 3
    for attempt in range(max_attempts):
        sys_prompt = _L2_QASM_CONTRACT
        if attempt > 0:
            sys_prompt += ("\nIMPORTANT: your previous attempt failed "
                           "verification with: %s\nProduce a corrected "
                           "program." % last_detail)
            if "no OpenQASM" in last_detail:
                sys_prompt += ("\nYour previous reply had NO fenced code "
                               "block at all. You MUST output the complete "
                               "program wrapped like:\n```openqasm\n..."
                               "program...\n```\nNever reply with prose only.")
        reply = _l2_llm(sys_prompt, user_task)
        qasm = _l2_extract_qasm(reply)
        if qasm is None:
            last_detail = "no OpenQASM program found in response"
            continue
        ok, detail = _l2_self_verify(qasm, info.get("target_state") or "",
                                     info.get("n_qubits"))
        if ok:
            return ("已生成并自验通过（%s）。电路如下：\n\n```openqasm\n%s\n```") % (
                detail, qasm)
        last_detail = detail
    # Last resort: deterministically rewrite the model's last output.
    if qasm:
        rw2, notes2 = _l2_rewrite_illegal(qasm)
        if rw2:
            ok, detail = _l2_self_verify(
                rw2, info.get("target_state") or "",
                info.get("n_qubits"))
            if ok:
                return ("模型多轮尝试未通过自验，已对其输出执行确定性非法门"
                        "改写（%s），自验通过（%s）。电路如下：\n\n"
                        "```openqasm\n%s\n```") % (
                    "；".join(notes2), detail, rw2)
    # Tool-assisted fallback: deterministic synthesis for canonical states.
    if synth:
        ok, detail = _l2_self_verify(synth,
                                     info.get("target_state") or "",
                                     info.get("n_qubits"))
        if ok:
            return ("模型多轮尝试未通过自验，已切换到内置确定性合成器生成"
                    "（%s）。电路如下：\n\n```openqasm\n%s\n```") % (
                detail, synth)
    return ("未能通过自验（最后一次原因：%s）。以下是最近一次尝试，供参考：\n\n"
            "```openqasm\n%s\n```") % (last_detail, qasm if qasm else "")


# ============================ L3 hybrid compiler ============================
# Hybrid-QASM = OpenQASM 2.0 + classical { ... } blocks. Grammar (per
# problem_statement.md §3): integer literals, registers r1..r9 (-> x1..x9),
# operators + - == !=, sequential assignment, if/else. Measurement bits
# c[k] map to x10+k and are pre-injected by the evaluator.
#
# Register discipline (so our final register state matches the reference):
#   * assignments accumulate DIRECTLY in the destination register
#     (r1 = r2 + r3 - 4  =>  add x1,x2,x3 ; addi x1,x1,-4)
#   * measurement regs x10.. are never written
#   * the ONLY scratch is x31, used solely to materialize immediates for
#     comparisons / negation, and zeroed in the epilogue.

_L3_TOKEN_RE = re.compile(r"==|!=|[+\-(){};=]|c\[\d+\]|r\d+|\d+|if|else")


def _l3_split(text):
    """Split Hybrid-QASM into (quantum_lines, classical_block_texts)."""
    clean = []
    for raw in text.splitlines():
        ln = raw.split('//')[0]
        if '#' in ln:
            ln = ln.split('#')[0]
        clean.append(ln)
    buf = '\n'.join(clean)
    blocks = []
    while True:
        m = re.search(r'\bclassical\b', buf)
        if not m:
            break
        i = buf.find('{', m.end())
        if i < 0:
            break
        depth, j = 0, i
        while j < len(buf):
            if buf[j] == '{':
                depth += 1
            elif buf[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            raise ValueError('L3: unbalanced braces in classical block')
        blocks.append(buf[i + 1:j])
        buf = buf[:m.start()] + '\n' + buf[j + 1:]
    quantum = [ln.strip() for ln in buf.splitlines() if ln.strip()]
    return quantum, blocks


def _l3_tokenize(block):
    return _L3_TOKEN_RE.findall(block)


class _L3Parser:
    """Recursive-descent parser producing tuple ASTs:
       stmt  = ('assign', 'rN', expr) | ('if', cond, then_stmts, else_stmts)
       expr  = [(op|None, term), ...]          op in '+','-'
       term  = ('imm', int) | ('r', n) | ('c', k) | ('neg', term)
       cond  = ('=='|'!=', term, term)
    """

    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise ValueError('L3: unexpected end of classical block')
        self.i += 1
        return tok

    def expect(self, tok):
        got = self.take()
        if got != tok:
            raise ValueError('L3: expected %r got %r' % (tok, got))

    def parse_block(self):
        stmts = []
        while self.peek() is not None and self.peek() != '}':
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self):
        if self.peek() == 'if':
            self.take()
            self.expect('(')
            cond = self.parse_cond()
            self.expect(')')
            self.expect('{')
            then_stmts = self.parse_block()
            self.expect('}')
            else_stmts = []
            if self.peek() == 'else':
                self.take()
                if self.peek() == 'if':
                    else_stmts = [self.parse_stmt()]
                else:
                    self.expect('{')
                    else_stmts = self.parse_block()
                    self.expect('}')
            return ('if', cond, then_stmts, else_stmts)
        target = self.take()
        if not re.fullmatch(r'r\d+', target):
            raise ValueError('L3: assignment target must be rN, got %r'
                             % target)
        self.expect('=')
        expr = self.parse_expr()
        self.expect(';')
        return ('assign', target, expr)

    def parse_cond(self):
        a = self.parse_term()
        op = self.take()
        if op not in ('==', '!='):
            raise ValueError('L3: condition operator must be == or !=, '
                             'got %r' % op)
        b = self.parse_term()
        return (op, a, b)

    def parse_expr(self):
        terms = [(None, self.parse_term())]
        while self.peek() in ('+', '-'):
            op = self.take()
            terms.append((op, self.parse_term()))
        return terms

    def parse_term(self):
        if self.peek() == '-':
            self.take()
            return ('neg', self.parse_term())
        tok = self.take()
        if tok and tok[0] == 'c':
            return ('c', int(re.findall(r'\d+', tok)[0]))
        if tok and tok[0] == 'r':
            return ('r', int(tok[1:]))
        if tok and tok.isdigit():
            return ('imm', int(tok))
        raise ValueError('L3: bad term %r' % tok)


def _l3_parse_classical(blocks):
    stmts = []
    for blk in blocks:
        p = _L3Parser(_l3_tokenize(blk))
        stmts.extend(p.parse_block())
    return stmts


class _L3CodeGen:
    """Emit RISC-V for an AST statement list. Scratch = x31 only."""

    def __init__(self):
        self.lines = []
        self.n_label = 0
        self.dirty = set()

    def label(self, base):
        self.n_label += 1
        return '%s_%d' % (base, self.n_label)

    def emit(self, line):
        self.lines.append('    ' + line)

    def load_scratch(self, term, which='x31'):
        """Materialize term value into a scratch register; return it."""
        kind, v = term
        if kind == 'neg':
            if v[0] == 'imm':
                self.emit('li %s, %d' % (which, -v[1]))
            else:
                src = self.direct_src(v)
                if src is None:
                    src = self.load_scratch(v,
                            'x30' if which == 'x31' else 'x31')
                self.emit('sub %s, x0, %s' % (which, src))
        elif kind == 'imm':
            self.emit('li %s, %d' % (which, v))
        elif kind == 'r':
            self.emit('addi %s, x%d, 0' % (which, v))
        elif kind == 'c':
            self.emit('addi %s, x%d, 0' % (which, 10 + v))
        else:
            raise ValueError('L3: bad term %r' % (term,))
        self.dirty.add(which)
        return which

    @staticmethod
    def direct_src(term):
        """Return source register for r/c terms (no dirtying), else None."""
        kind, v = term
        if kind == 'r':
            return 'x%d' % v
        if kind == 'c':
            return 'x%d' % (10 + v)
        return None

    def load_into_dst(self, dst, term):
        """Load term into dst WITHOUT touching other regs."""
        kind, v = term
        if kind == 'neg':
            src = self.direct_src(v)
            if src is None:
                _, vv = v
                self.emit('li %s, %d' % (dst, -vv))
            else:
                self.emit('sub %s, x0, %s' % (dst, src))
        elif kind == 'imm':
            self.emit('li %s, %d' % (dst, v))
        elif kind == 'r':
            self.emit('addi %s, x%d, 0' % (dst, v))
        elif kind == 'c':
            self.emit('addi %s, x%d, 0' % (dst, 10 + v))

    def gen_assign(self, target, expr):
        dst = 'x%d' % int(target[1:])
        dst_idx = int(target[1:])

        def refs_dst(term):
            k, v = term
            if k == 'r':
                return v == dst_idx
            if k == 'neg':
                return refs_dst(v)
            return False

        saved = False

        def ensure_saved():
            nonlocal saved
            if not saved:
                self.emit('addi x30, %s, 0' % dst)
                self.dirty.add('x30')
                saved = True

        # Pre-scan: if ANY non-first term reads dst, the very first write
        # below would destroy that value - shadow it into x30 up front.
        if any(refs_dst(t) for _, t in expr[1:]):
            ensure_saved()

        first = True
        for op, term in expr:
            if first:
                if refs_dst(term):
                    ensure_saved()          # keep old dst readable
                    if term[0] == 'neg':
                        self.emit('sub %s, x0, x30' % dst)
                    # else dst already holds the value - nothing to do
                else:
                    self.load_into_dst(dst, term)
                first = False
                continue
            if refs_dst(term):
                ensure_saved()
                src = 'x30'
            else:
                src = self.direct_src(term)
                if src is None:
                    src = self.load_scratch(term)
            self.emit('%s %s, %s, %s' %
                      ('add' if op == '+' else 'sub', dst, dst, src))

    def gen_cond_branch(self, cond, else_label):
        op, a, b = cond
        ra = self.direct_src(a)
        rb = self.direct_src(b)
        if ra is None and rb is None:
            va = a[1] if a[0] == 'imm' else None
            vb = b[1] if b[0] == 'imm' else None
            if va is not None and vb is not None:
                taken = (va == vb) if op == '==' else (va != vb)
                if not taken:
                    self.emit('j %s' % else_label)
                return
            ra = self.load_scratch(a, 'x31')
            rb = self.load_scratch(b, 'x30')
        if rb is None:
            rb = self.load_scratch(b)
        if ra is None:
            ra = self.load_scratch(a)
        jump = 'bne' if op == '==' else 'beq'
        self.emit('%s %s, %s, %s' % (jump, ra, rb, else_label))

    def gen_stmts(self, stmts):
        for st in stmts:
            if st[0] == 'assign':
                self.gen_assign(st[1], st[2])
            else:
                _, cond, then_stmts, else_stmts = st
                if not then_stmts and not else_stmts:
                    continue
                else_lbl = self.label('ELSE')
                end_lbl = self.label('END')
                self.gen_cond_branch(cond, else_lbl)
                if then_stmts:
                    self.gen_stmts(then_stmts)
                if else_stmts:
                    self.emit('j %s' % end_lbl)
                    self.lines.append(else_lbl + ':')
                    self.gen_stmts(else_stmts)
                else:
                    self.emit('j %s' % end_lbl)
                    self.lines.append(else_lbl + ':')
                self.lines.append(end_lbl + ':')


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """[L3] Compile Hybrid-QASM -> (quantum operation list, RISC-V asm)."""
    quantum_lines, blocks = _l3_split(hybrid_qasm_str)
    ops = []
    for ln in quantum_lines:
        low = ln.lower()
        if low.startswith(('openqasm', 'include', 'qreg', 'creg')):
            continue
        ops.append(ln)
    stmts = _l3_parse_classical(blocks)
    cg = _L3CodeGen()
    cg.gen_stmts(stmts)
    for scr in ('x31', 'x30'):
        if scr in cg.dirty:
            cg.emit('li %s, 0' % scr)
    asm = '# LoomQ L3 hybrid compilation - classical control logic\n'
    asm += '\n'.join(cg.lines) + '\n'
    return ops, asm
