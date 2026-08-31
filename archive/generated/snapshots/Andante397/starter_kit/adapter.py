import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


# ---------------------------------------------------------------- IR

@dataclass
class Gate:
    name: str                       # 'h' / 'cx' / 'rz' ...
    qubits: List[int]               # 作用的比特, 已转成整数下标
    params: List[float] = field(default_factory=list)


@dataclass
class Measure:
    qubit: int
    clbit: int


@dataclass
class Circuit:
    n_qubits: int = 0
    n_clbits: int = 0
    ops: List[object] = field(default_factory=list)   # Gate | Measure
    qregs: Dict[str, int] = field(default_factory=dict)   # 名字 → 宽度
    cregs: Dict[str, int] = field(default_factory=dict)

    @property
    def gates(self) -> List[Gate]:
        return [op for op in self.ops if isinstance(op, Gate)]

    @property
    def measures(self) -> List[Measure]:
        return [op for op in self.ops if isinstance(op, Measure)]


# ---------------------------------------------------------------- 前端: QASM 2.0 解析

WHITELIST = {
    'h': 1, 'x': 1, 's': 1, 'sdg': 1, 't': 1, 'tdg': 1,     # 单比特无参
    'rz': 1, 'ry': 1,                                        # 单比特含参
    'cx': 2, 'cu1': 2, 'swap': 2,                            # 两比特
    'ccx': 3,                                                # 三比特
}

_DECL = re.compile(r'(\w+)\s*\[\s*(\d+)\s*\]')
_REF = re.compile(r'^(\w+)\s*(?:\[\s*(\d+)\s*\])?$')


def _resolve(token: str, regs: Dict[str, int]) -> List[int]:
    """'q[2]' → [2]；整寄存器 'q' → [0,1,2]（QASM 2.0 允许对整个寄存器施加操作）"""
    m = _REF.match(token.strip())
    if not m:
        raise ValueError(f'无法解析比特引用: {token!r}')
    name, index = m.group(1), m.group(2)
    if index is not None:
        return [int(index)]
    if name not in regs:
        raise ValueError(f'未声明的寄存器: {name!r}')
    return list(range(regs[name]))


def parse_qasm(qasm_str: str) -> Circuit:
    circ = Circuit()

    src = re.sub(r'//.*', '', qasm_str)
    for stmt in src.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        if stmt.startswith(('OPENQASM', 'include', 'barrier')):
            continue

        # qreg q[3]  /  creg c[3]
        if stmt.startswith(('qreg', 'creg')):
            kind, body = stmt[:4], stmt[4:]
            m = _DECL.search(body)
            if not m:
                raise ValueError(f'无法解析寄存器声明: {stmt!r}')
            name, width = m.group(1), int(m.group(2))
            if kind == 'qreg':
                circ.qregs[name] = width
                circ.n_qubits += width
            else:
                circ.cregs[name] = width
                circ.n_clbits += width
            continue

        # measure q[0] -> c[0]   或   measure q -> c
        if stmt.startswith('measure'):
            lhs, rhs = stmt[7:].split('->')
            qs = _resolve(lhs, circ.qregs)
            cs = _resolve(rhs, circ.cregs)
            if len(qs) != len(cs):
                raise ValueError(f'measure 两侧宽度不一致: {stmt!r}')
            circ.ops += [Measure(q, c) for q, c in zip(qs, cs)]
            continue

        # 门:  name(params) targets
        head, _, targets = stmt.partition(' ')
        name, params = head, []
        if '(' in head:
            name, raw = head.split('(', 1)
            params = [_evaluate(p) for p in raw.rstrip(')').split(',')]

        name = name.strip()
        if name not in WHITELIST:
            raise ValueError(f'白名单之外的门: {name!r}')

        operands = [_resolve(t, circ.qregs) for t in targets.split(',')]
        if len(operands) != WHITELIST[name]:
            raise ValueError(f'{name} 需要 {WHITELIST[name]} 个操作数, 收到 {len(operands)}')

        # 整寄存器广播: h q;  →  h q[0]; h q[1]; ...
        width = max(len(o) for o in operands)
        if any(len(o) not in (1, width) for o in operands):
            raise ValueError(f'操作数宽度无法广播: {stmt!r}')
        for k in range(width):
            circ.ops.append(Gate(name,
                                 [o[k] if len(o) == width else o[0] for o in operands],
                                 params))

    return circ


def _evaluate(expr: str) -> float:
    """QASM 参数可能写成 pi/2 这类表达式"""
    import math
    return float(eval(expr.strip(), {'__builtins__': {}}, {'pi': math.pi}))


# ---------------------------------------------------------------- 后端插件基类

class Backend:
    name: str = ''          # 填进 Schema 的 backend 字段

    def codegen(self, circ: Circuit) -> str:
        """IR → 目标平台原生指令字符串 (transpile 的返回值)"""
        raise NotImplementedError

    def execute(self, circ: Circuit, shots: int) -> Dict[str, int]:
        """跑电路, 返回 {比特串: 次数}。
        比特串按 **qubit 下标升序** 排列 (最左 = q[0])，
        统一由 normalize() 转成大赛要求的顺序。"""
        raise NotImplementedError


def normalize(raw: Dict[str, int], circ: Circuit) -> Dict[str, int]:
    """把 execute() 的 q0q1q2… 顺序，转成 c[n-1]…c[1]c[0] 顺序。
    """
    mapping = {m.clbit: m.qubit for m in circ.measures}
    width = circ.n_clbits or len(mapping)

    out: Dict[str, int] = {}
    for bits, n in raw.items():
        # c[n-1] 在最左, c[0] 在最右
        key = ''.join(
            bits[mapping[c]] if c in mapping and mapping[c] < len(bits) else '0'
            for c in range(width - 1, -1, -1)
        )
        out[key] = out.get(key, 0) + n
    return out


# ---------------------------------------------------------------- Braket 后端

class BraketBackend(Backend):
    name = 'braket_local'

    # QASM 门名 → OpenQASM 3 门名
    QASM3 = {'cx': 'cx', 'cu1': 'cp', 'ccx': 'ccx'}

    def codegen(self, circ: Circuit) -> str:
        lines = ['OPENQASM 3.0;', 'include "stdgates.inc";',
                 f'qubit[{circ.n_qubits}] q;']
        if circ.n_clbits:
            lines.append(f'bit[{circ.n_clbits}] c;')

        for op in circ.ops:
            if isinstance(op, Measure):
                lines.append(f'c[{op.clbit}] = measure q[{op.qubit}];')
                continue
            g = self.QASM3.get(op.name, op.name)
            args = ', '.join(f'q[{i}]' for i in op.qubits)
            if op.params:
                p = ', '.join(f'{v:.10g}' for v in op.params)
                lines.append(f'{g}({p}) {args};')
            else:
                lines.append(f'{g} {args};')

        return '\n'.join(lines)

    def execute(self, circ: Circuit, shots: int) -> Dict[str, int]:
        from braket.circuits import Circuit as BkCircuit
        from braket.devices import LocalSimulator

        bk = BkCircuit()
        # braket 只分配「被门作用过」的比特；先铺一层 I 保证寄存器宽度完整，
        # 否则未参与运算的比特会从结果串里消失，位序随之错位。
        for i in range(circ.n_qubits):
            bk.i(i)
        for g in circ.gates:
            self._apply(bk, g)

        result = LocalSimulator().run(bk, shots=shots).result()
        return dict(result.measurement_counts)

    @staticmethod
    def _apply(bk, g: Gate):
        q, p = g.qubits, g.params
        n = g.name
        if   n == 'h':    bk.h(q[0])
        elif n == 'x':    bk.x(q[0])
        elif n == 's':    bk.s(q[0])
        elif n == 'sdg':  bk.si(q[0])
        elif n == 't':    bk.t(q[0])
        elif n == 'tdg':  bk.ti(q[0])
        elif n == 'rz':   bk.rz(q[0], p[0])
        elif n == 'ry':   bk.ry(q[0], p[0])
        elif n == 'cx':   bk.cnot(q[0], q[1])
        elif n == 'cu1':  bk.cphaseshift(q[0], q[1], p[0])
        elif n == 'swap': bk.swap(q[0], q[1])
        elif n == 'ccx':  bk.ccnot(q[0], q[1], q[2])
        else: raise NotImplementedError(n)


# ---------------------------------------------------------------- OriginQ 后端

class OriginQBackend(Backend):
    #本源量子。codegen 生成 OriginIR 文本，execute 直接执行这段文本
   
    name = 'originq_cpuqvm'

    # QASM 门名 → OriginIR 门名（无参 / 含参）
    SIMPLE = {'h': 'H', 'x': 'X', 's': 'S', 't': 'T',
              'cx': 'CNOT', 'swap': 'SWAP', 'ccx': 'TOFFOLI'}
    PARAM = {'rz': 'RZ', 'ry': 'RY', 'cu1': 'CP'}
    DAGGER = {'sdg': 'S', 'tdg': 'T'}      # OriginIR 用 DAGGER 块表达共轭转置

    def codegen(self, circ: Circuit) -> str:
        lines = [f'QINIT {circ.n_qubits}', f'CREG {circ.n_clbits or circ.n_qubits}']

        for op in circ.ops:
            if isinstance(op, Measure):
                lines.append(f'MEASURE q[{op.qubit}],c[{op.clbit}]')
                continue

            args = ','.join(f'q[{i}]' for i in op.qubits)
            n = op.name

            if n in self.SIMPLE:
                lines.append(f'{self.SIMPLE[n]} {args}')
            elif n in self.PARAM:
                p = ','.join(f'{v:.10g}' for v in op.params)
                lines.append(f'{self.PARAM[n]} {args},({p})')
            elif n in self.DAGGER:
                lines += ['DAGGER', f'{self.DAGGER[n]} {args}', 'ENDDAGGER']
            else:
                raise NotImplementedError(f'OriginQ 未映射的门: {n}')

        return '\n'.join(lines)

    def execute(self, circ: Circuit, shots: int) -> Dict[str, int]:
        from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
        from pyqpanda3.core import CPUQVM

        prog = convert_originir_string_to_qprog(self.codegen(circ))
        qvm = CPUQVM()
        qvm.run(prog, shots)

        # OriginQ 返回的串是 q[n-1]…q[0]（最右 = q0），
        # 而本中间层内部约定「最左 = q0」，故翻转对齐。
        return {bits[::-1]: n for bits, n in qvm.result().get_counts().items()}


# ---------------------------------------------------------------- 后端注册表

BACKENDS = {
    'braket':  BraketBackend(),
    'originq': OriginQBackend(),
    # 'spinq': SpinQBackend(),   # TODO: spinqit 装不上时留空
}


# ---------------------------------------------------------------- 大赛契约接口

def transpile(qasm_str: str, target: str) -> str:
    return BACKENDS[target].codegen(parse_qasm(qasm_str))


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    backend = BACKENDS[target]
    circ = parse_qasm(qasm_str)

    raw = backend.execute(circ, shots)
    counts = normalize(raw, circ)

    return {
        'backend':   backend.name,
        'job_id':    uuid.uuid4().hex[:8],
        'shots':     shots,
        'counts':    counts,
        'bit_order': 'little',
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'meta': {
            'transpiled_gates': len(circ.gates),
            'depth': len(circ.gates),        # TODO: 真正的深度计算
        },
    }


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* env vars."""
    raise NotImplementedError("L2 is optional; implement agent_chat(prompt)")


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    raise NotImplementedError(
        "L3 is optional; implement compile_hybrid(hybrid_qasm_str)"
    )

