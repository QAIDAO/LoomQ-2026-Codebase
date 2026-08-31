#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

L1 实现流程：
1. 解析比赛规定的 OpenQASM 2.0 子集；
2. 转换为统一的内部电路表示 CircuitIR；
3. 按目标平台生成 SpinQ OpenQASM 2.0、OriginIR 或 Braket OpenQASM 3.0；
4. 调用对应平台的本地模拟器执行线路；
5. 将不同平台的测量结果统一为大赛规定的结果 Schema。

L2 / L3 暂时保持为可选入口。
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple


import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone



SUPPORTED_TARGETS = ("spinq", "originq", "braket")

# L1 仅处理比赛白名单中的 12 种量子门。
SUPPORTED_GATES = {
    "h", "x", "s", "sdg", "t", "tdg",
    "rz", "ry", "cx", "cu1", "swap", "ccx",
}

# 将 QASM 指令先整理成统一的 Python 数据结构，后续三个平台共用同一份中间表示。
@dataclass
class Operation:
    name: str
    qubits: List[int] = field(default_factory=list)
    params: List[str] = field(default_factory=list)
    clbits: List[int] = field(default_factory=list)


@dataclass
class CircuitIR:
    num_qubits: int
    num_clbits: int
    operations: List[Operation]

# 解析寄存器、单个比特引用、测量语句和量子门语句时使用的正则表达式。
_QREF_RE = re.compile(r"^([A-Za-z_]\w*)\[(\d+)\]$")
_REG_RE = re.compile(r"^(qreg|creg)\s+([A-Za-z_]\w*)\[(\d+)\]$")
_MEASURE_RE = re.compile(r"^measure\s+(.+?)\s*->\s*(.+)$", re.IGNORECASE)
_GATE_RE = re.compile(
    r"^([A-Za-z_]\w*)\s*(?:\((.*?)\))?\s+(.+)$",
    re.DOTALL,
)

# 移除 QASM 中的块注释和行注释，避免注释内容干扰后续按分号拆分语句。
def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text

# 将门参数列表拆成字符串数组，例如 "0.1, pi/2" -> ["0.1", "pi/2"]。
def _split_params(text: Optional[str]) -> List[str]:
    if text is None or not text.strip():
        return []
    return [item.strip() for item in text.split(",")]

# 计算多个寄存器在统一比特编号中的起始偏移量。
def _register_offsets(regs: Dict[str, int]) -> Dict[str, int]:
    offsets: Dict[str, int] = {}
    cursor = 0
    for name, size in regs.items():
        offsets[name] = cursor
        cursor += size
    return offsets

# 将形如 q[2] 的寄存器引用解析为统一编号，并检查寄存器名和下标是否合法。
def _resolve_bit(ref: str, regs: Dict[str, int], offsets: Dict[str, int]) -> int:
    match = _QREF_RE.match(ref.strip())
    if not match:
        raise ValueError(f"Expected indexed bit reference, got: {ref!r}")
    name, index_text = match.groups()
    if name not in regs:
        raise ValueError(f"Unknown register {name!r}")
    index = int(index_text)
    if index < 0 or index >= regs[name]:
        raise ValueError(f"Index out of range: {ref}")
    return offsets[name] + index

# 将比赛规定的 OpenQASM 2.0 子集解析为统一的 CircuitIR。
def parse_qasm(qasm_str: str) -> CircuitIR:
    """解析比赛规定的 OpenQASM 2.0 子集，并返回统一的内部电路表示。"""
    if not isinstance(qasm_str, str) or not qasm_str.strip():
        raise ValueError("qasm_str must be a non-empty string")

    # 1. 先去掉注释，再按分号拆成独立 QASM 语句。
    cleaned = _strip_comments(qasm_str)
    statements = [part.strip() for part in cleaned.split(";") if part.strip()]

    qregs: Dict[str, int] = {}
    cregs: Dict[str, int] = {}
    raw_ops: List[str] = []
    saw_header = False

    # 2. 第一遍读取文件头和量子/经典寄存器声明，其余语句暂存起来。
    for stmt in statements:
        if re.fullmatch(r"OPENQASM\s+2\.0", stmt, flags=re.IGNORECASE):
            saw_header = True
            continue
        if re.fullmatch(r'include\s+"qelib1\.inc"', stmt, flags=re.IGNORECASE):
            continue

        reg_match = _REG_RE.match(stmt)
        if reg_match:
            kind, name, size_text = reg_match.groups()
            size = int(size_text)
            if size <= 0:
                raise ValueError(f"Register {name!r} must have positive size")
            target = qregs if kind == "qreg" else cregs
            if name in target:
                raise ValueError(f"Duplicate register {name!r}")
            target[name] = size
            continue

        raw_ops.append(stmt)

    if not saw_header:
        raise ValueError("Input must declare OPENQASM 2.0")
    if not qregs:
        raise ValueError("No qreg declared")
    if not cregs:
        raise ValueError("No creg declared")

    # 3. 将不同寄存器映射到统一编号空间。
    q_offsets = _register_offsets(qregs)
    c_offsets = _register_offsets(cregs)
    operations: List[Operation] = []

    # 4. 第二遍解析测量和量子门，并写入统一的 Operation 列表。
    for stmt in raw_ops:
        measure_match = _MEASURE_RE.match(stmt)
        if measure_match:
            q_side, c_side = [x.strip() for x in measure_match.groups()]

            # 支持整组寄存器测量，例如 measure q -> c。
            if q_side in qregs and c_side in cregs:
                if qregs[q_side] != cregs[c_side]:
                    raise ValueError("Whole-register measurement requires equal register sizes")
                for i in range(qregs[q_side]):
                    operations.append(
                        Operation(
                            name="measure",
                            qubits=[q_offsets[q_side] + i],
                            clbits=[c_offsets[c_side] + i],
                        )
                    )
                continue

            q_index = _resolve_bit(q_side, qregs, q_offsets)
            c_index = _resolve_bit(c_side, cregs, c_offsets)
            operations.append(Operation(name="measure", qubits=[q_index], clbits=[c_index]))
            continue

        gate_match = _GATE_RE.match(stmt)
        if not gate_match:
            raise ValueError(f"Unsupported/invalid QASM statement: {stmt!r}")

        name, params_text, args_text = gate_match.groups()
        name = name.lower()
        if name not in SUPPORTED_GATES:
            raise ValueError(f"Gate {name!r} is outside the LoomQ 12-gate whitelist")

        params = _split_params(params_text)
        qubits = [
            _resolve_bit(item.strip(), qregs, q_offsets)
            for item in args_text.split(",")
            if item.strip()
        ]

        expected_qubits = {
            "h": 1, "x": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
            "rz": 1, "ry": 1,
            "cx": 2, "cu1": 2, "swap": 2,
            "ccx": 3,
        }[name]
        expected_params = 1 if name in {"rz", "ry", "cu1"} else 0
        if len(qubits) != expected_qubits:
            raise ValueError(f"Gate {name} expects {expected_qubits} qubits")
        if len(params) != expected_params:
            raise ValueError(f"Gate {name} expects {expected_params} parameter(s)")

        operations.append(Operation(name=name, qubits=qubits, params=params))

    return CircuitIR(
            num_qubits=sum(qregs.values()),
            num_clbits=sum(cregs.values()),
            operations=operations,
        )

# 将统一 IR 输出为 SpinQ 使用的 OpenQASM 2.0。
def _to_spinq(ir: CircuitIR) -> str:
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{ir.num_qubits}];",
        f"creg c[{ir.num_clbits}];",
    ]
    for op in ir.operations:
        if op.name == "measure":
            lines.append(f"measure q[{op.qubits[0]}] -> c[{op.clbits[0]}];")
        elif op.params:
            args = ", ".join(f"q[{q}]" for q in op.qubits)
            lines.append(f"{op.name}({','.join(op.params)}) {args};")
        else:
            args = ", ".join(f"q[{q}]" for q in op.qubits)
            lines.append(f"{op.name} {args};")
    return "\n".join(lines) + "\n"

# 将统一 IR 输出为 OriginQ 使用的规范 OriginIR。
def _to_originq(ir: CircuitIR) -> str:
    gate_names = {
        "h": "H",
        "x": "X",
        "s": "S",
        "sdg": "SDAG",
        "t": "T",
        "tdg": "TDAG",
        "ry": "RY",
        "rz": "RZ",
        "cx": "CNOT",
        "cu1": "CU1",
        "swap": "SWAP",
        "ccx": "TOFFOLI",
    }
    lines = [f"QINIT {ir.num_qubits}", f"CREG {ir.num_clbits}"]
    for op in ir.operations:
        if op.name == "measure":
            lines.append(f"MEASURE q[{op.qubits[0]}], c[{op.clbits[0]}]")
            continue
        name = gate_names[op.name]
        qargs = ", ".join(f"q[{q}]" for q in op.qubits)
        if op.params:
            lines.append(f"{name}({','.join(op.params)}) {qargs}")
        else:
            lines.append(f"{name} {qargs}")
    return "\n".join(lines) + "\n"

# 将统一 IR 输出为比赛 target-IR 契约要求的 Braket OpenQASM 3.0。
def _to_braket(ir: CircuitIR) -> str:
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        f"qubit[{ir.num_qubits}] q;",
        f"bit[{ir.num_clbits}] c;",
    ]
    for op in ir.operations:
        if op.name == "measure":
            lines.append(f"c[{op.clbits[0]}] = measure q[{op.qubits[0]}];")
            continue

        # OpenQASM 3 的标准门名称使用 cp(theta) 表示受控相位门。
        name = "cp" if op.name == "cu1" else op.name
        qargs = ", ".join(f"q[{q}]" for q in op.qubits)
        if op.params:
            lines.append(f"{name}({','.join(op.params)}) {qargs};")
        else:
            lines.append(f"{name} {qargs};")
    return "\n".join(lines) + "\n"


def transpile(qasm_str: str, target: str) -> str:
    """将 OpenQASM 2.0 转译为目标后端的原生指令字符串。target ∈ {'spinq','originq','braket'}"""
    target = target.lower().strip()

    if target not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target {target!r}; choose from {SUPPORTED_TARGETS}"
        )

    # 1. 先将输入的 OpenQASM 2.0 解析为统一的内部电路表示。
    ir = parse_qasm(qasm_str)

    # 2. 再根据目标平台输出对应的原生指令格式。
    if target == "spinq":
        return _to_spinq(ir)

    if target == "originq":
        return _to_originq(ir)

    if target == "braket":
        return _to_braket(ir)

    # 前面的 target 检查已经覆盖正常情况，这里保留兜底异常。
    raise ValueError(f"Unsupported target: {target}")

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_counts(raw_counts: Dict[Any, Any], width: int, reverse: bool = False) -> Dict[str, int]:
    """将不同后端返回的 counts 统一整理为 LoomQ 要求的二进制字符串 key。"""
    result: Dict[str, int] = {}
    for raw_key, raw_value in raw_counts.items():
        if isinstance(raw_key, int):
            key = format(raw_key, f"0{width}b")
        else:
            key = str(raw_key).replace(" ", "")
            if not key or set(key) - {"0", "1"}:
                raise ValueError(f"Backend returned non-binary count key: {raw_key!r}")
            key = key.zfill(width)
        if reverse:
            key = key[::-1]
        result[key] = result.get(key, 0) + int(raw_value)
    return result


def _run_spinq(qasm_str: str, shots: int) -> Dict[str, Any]:
    # 1. 按需导入 SpinQit，避免未安装该 SDK 时影响其他后端。
    try:
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler
    except ImportError as exc:
        raise RuntimeError("SpinQit is not installed in this environment") from exc

    # 2. 解析输入线路，并生成 SpinQ 可读取的 OpenQASM 2.0。
    ir = parse_qasm(qasm_str)
    native_qasm = _to_spinq(ir)

    # 3. SpinQ QASMCompiler 接受文件路径，因此先写入临时 .qasm 文件。
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
    try:
        tmp.write(native_qasm)
        tmp.close()
        # 4. 使用 SpinQ 的 QASM 编译器生成平台内部 IR。
        compiler = get_compiler("qasm")
        spinq_ir = compiler.compile(tmp.name, 0)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # 5. 初始化本地模拟器，配置 shots 并执行线路。
    engine = get_basic_simulator()
    config = BasicSimulatorConfig()
    config.configure_shots(shots)
    result = engine.execute(spinq_ir, config)
    # 6. SpinQ 返回的位串方向与 LoomQ 约定相反，因此统一反转为 c[n-1]...c[0]。
    counts = _normalize_counts(
        dict(result.counts),
        ir.num_clbits,
        reverse=True
    )

    return {
        "backend": "spinq_basic_simulator",
        "job_id": str(
            getattr(result, "job_id", None)
            or getattr(result, "task_id", None)
            or f"spinq-local-{uuid.uuid4().hex[:8]}"
        ),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _utc_now(),
        "meta": {"qubits_count": ir.num_qubits},
    }


def _run_originq(qasm_str: str, shots: int) -> Dict[str, Any]:
    # 1. 按需导入 pyQPanda，避免未安装该 SDK 时影响其他后端。
    try:
        import pyqpanda as pq
    except ImportError as exc:
        raise RuntimeError("pyqpanda is not installed in this environment") from exc

    # 2. pyQPanda 可以直接导入 OpenQASM 2.0，因此复用规范化后的 QASM。
    ir = parse_qasm(qasm_str)
    canonical_qasm = _to_spinq(ir)  # pyQPanda 直接导入 OpenQASM 2.0。
    machine = pq.CPUQVM()
    machine.init_qvm()
    try:
        # 3. 优先使用字符串导入接口；旧版本仅提供文件导入时走兼容分支。
        if hasattr(pq, "convert_qasm_string_to_qprog"):
            prog, qreg, creg = pq.convert_qasm_string_to_qprog(canonical_qasm, machine)
        else:
            # 兼容仅提供文件导入接口的 pyQPanda 版本。
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
            try:
                tmp.write(canonical_qasm)
                tmp.close()
                converted = pq.convert_qasm_to_qprog(tmp.name, machine)
            finally:
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

            if isinstance(converted, tuple):
                prog, qreg, creg = converted
            else:
                prog = converted
                qreg = machine.get_allocate_qubits()
                creg = machine.get_allocate_cbits()

        # 4. 按指定 shots 执行，并将结果统一为 LoomQ counts 格式。
        raw_counts = machine.run_with_configuration(prog, creg, shots)
        counts = _normalize_counts(dict(raw_counts), ir.num_clbits)
    finally:
        # 5. 无论运行成功与否都释放 QVM 资源。
        machine.finalize()

    return {
        "backend": "originq_cpu_simulator",
        "job_id": f"originq-local-{uuid.uuid4().hex[:8]}",
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _utc_now(),
        "meta": {"qubits_count": ir.num_qubits},
    }


def _run_braket(qasm_str: str, shots: int) -> Dict[str, Any]:
    # 1. 按需导入 AWS Braket SDK，避免未安装该 SDK 时影响其他后端。
    try:
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program
    except ImportError as exc:
        raise RuntimeError(
            "amazon-braket-sdk is not installed in this environment"
        ) from exc

    # 2. 解析输入线路，并生成专门供本地 Braket LocalSimulator 执行的 QASM 3。
    # 比赛 target IR 保留 stdgates.inc；本地模拟器则使用 Braket 自身的门名称。
    ir = parse_qasm(qasm_str)
    qasm3_for_execution = _to_braket_runtime(ir)

    # 3. 初始化免费本地模拟器并提交任务。
    device = LocalSimulator()

    task = device.run(
        Program(source=qasm3_for_execution),
        shots=shots
    )

    # 4. 等待本地任务完成并取得测量结果。
    result = task.result()

    # 5. Braket 的测量位顺序与 LoomQ 约定相反，因此反转为 c[n-1]...c[0]。
    counts = _normalize_counts(
        dict(result.measurement_counts),
        ir.num_clbits,
        reverse=True
    )

    task_id = getattr(
        getattr(result, "task_metadata", None),
        "id",
        None
    )

    return {
        "backend": "braket_local_simulator",
        "job_id": str(
            task_id or f"braket-local-{uuid.uuid4().hex[:8]}"
        ),
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": _utc_now(),
        "meta": {
            "qubits_count": ir.num_qubits
        },
    }

def _to_braket_runtime(ir: CircuitIR) -> str:
    """生成供 Braket LocalSimulator 实际执行的 OpenQASM 3 指令。"""

    gate_names = {
        "h": "h",
        "x": "x",
        "s": "s",
        "sdg": "si",
        "t": "t",
        "tdg": "ti",
        "ry": "ry",
        "rz": "rz",
        "cx": "cnot",
        "cu1": "cphaseshift",
        "swap": "swap",
        "ccx": "ccnot",
    }

    lines = [
        "OPENQASM 3.0;",
        f"qubit[{ir.num_qubits}] q;",
        f"bit[{ir.num_clbits}] c;",
    ]

    for op in ir.operations:
        if op.name == "measure":
            lines.append(
                f"c[{op.clbits[0]}] = measure q[{op.qubits[0]}];"
            )
            continue

        name = gate_names[op.name]
        qargs = ", ".join(f"q[{q}]" for q in op.qubits)

        if op.params:
            lines.append(
                f"{name}({','.join(op.params)}) {qargs};"
            )
        else:
            lines.append(
                f"{name} {qargs};"
            )

    return "\n".join(lines) + "\n"


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """运行电路并返回符合大赛标准 Schema 的字典结果"""
    if not isinstance(shots, int) or isinstance(shots, bool) or shots <= 0:
        raise ValueError("shots must be a positive integer")

    target = target.lower().strip()
    if target == "spinq":
        return _run_spinq(qasm_str, shots)
    if target == "originq":
        return _run_originq(qasm_str, shots)
    if target == "braket":
        return _run_braket(qasm_str, shots)
    raise ValueError(f"Unsupported target {target!r}; choose from {SUPPORTED_TARGETS}")


def agent_chat(prompt: str) -> str:
    """[L2 可选] 从 LOOMQ_LLM_* 环境变量读取配置，返回智能体响应文本"""
    raise NotImplementedError("L2 is optional; implement agent_chat(prompt) to enter")


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """[L3 可选] 混合编译接口。输入 Hybrid-QASM，返回 (量子操作序列, RISC-V 汇编文本)"""
    raise NotImplementedError(
        "L3 is optional; implement compile_hybrid(hybrid_qasm_str) to enter"
    )
