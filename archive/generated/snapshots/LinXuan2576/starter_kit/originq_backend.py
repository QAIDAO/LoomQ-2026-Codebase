#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LoomQ-2026 适配器：OriginQ 后端实现（最终修复版）

修复内容：
- 移除 pyqpanda.reset 调用，避免破坏量子比特
- 参数门应用改为显式顺序（RZ/RY/RX 使用 (qubit, angle)，CU1 使用 (angle, control, target)）
- 运行时分解兜底增加 None 检查
- 构建线路前初始化变量，确保异常释放安全
- 保留测量结果比特序反转（小端序）
- 删除未使用的 CNOT_REVERSE 常量
"""

import ast
import atexit
import datetime
import json
import logging
import math
import re
import threading
import uuid
from typing import Any, Dict, List, Tuple, Optional

# ============================================================================
# 日志配置
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ============================================================================
# 常量定义
# ============================================================================
TARGET_ORIGINQ = "originq"
BACKEND_NAME = "originq_local_simulator"
BIT_ORDER = "little"

# ============================================================================
# pyqpanda 导入与虚拟机生命周期管理
# ============================================================================
try:
    import pyqpanda
    from pyqpanda import *
    PYQPANDA_AVAILABLE = True
except ImportError:
    PYQPANDA_AVAILABLE = False
    pyqpanda = None
    class PyQPandaError(Exception):
        pass
else:
    PyQPandaError = Exception

_QM_INITIALIZED = False
_QM_INIT_LOCK = threading.Lock()

def _ensure_qm_initialized() -> None:
    """确保 pyqpanda 量子虚拟机已初始化（仅执行一次）"""
    global _QM_INITIALIZED
    if _QM_INITIALIZED:
        return
    with _QM_INIT_LOCK:
        if not _QM_INITIALIZED:
            try:
                pyqpanda.init(pyqpanda.QMachineType.CPU)
                _QM_INITIALIZED = True
                logging.info("pyqpanda virtual machine initialized")
            except Exception as e:
                logging.error(f"pyqpanda init failed: {e}", exc_info=True)
                raise PyQPandaError(f"pyqpanda init failed: {e}")

def _shutdown_qmachine() -> None:
    """程序退出时释放量子虚拟机"""
    global _QM_INITIALIZED
    if _QM_INITIALIZED and PYQPANDA_AVAILABLE:
        try:
            pyqpanda.finalize()
            _QM_INITIALIZED = False
            logging.info("pyqpanda virtual machine finalized")
        except Exception as e:
            logging.error(f"pyqpanda finalize failed: {e}", exc_info=True)

atexit.register(_shutdown_qmachine)

# ============================================================================
# 门映射与分解
# ============================================================================
GATE_MAP = {
    'h': 'H',
    'x': 'X',
    's': 'S',
    'sdg': 'SDAG',
    't': 'T',
    'tdg': 'TDAG',
    'rz': 'RZ',
    'ry': 'RY',
    'rx': 'RX',
    'cx': 'CNOT',
    'cu1': 'CU1',
    'swap': 'SWAP',
    'ccx': 'TOFFOLI',
}

# 安全数学表达式允许的节点类型
_ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.Name,
    ast.Constant,
)

_SAFE_FUNCTIONS = {
    'pi': math.pi,
    'e': math.e,
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'exp': math.exp,
    'log': math.log,
    'abs': abs,
}

def _safe_eval_math(expr: str) -> float:
    """安全解析数学表达式，仅支持数字、运算符、括号和预定义函数/常量。"""
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {expr}") from e

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST_NODES):
            raise ValueError(f"表达式包含不允许的节点: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("函数调用仅支持预定义函数")
            if node.func.id not in _SAFE_FUNCTIONS:
                raise ValueError(f"未知函数: {node.func.id}")
        if isinstance(node, ast.Name):
            if node.id not in _SAFE_FUNCTIONS:
                raise ValueError(f"未知变量: {node.id}")

    code = compile(tree, '<string>', 'eval')
    namespace = {'__builtins__': None}
    namespace.update(_SAFE_FUNCTIONS)
    try:
        result = eval(code, namespace)
    except Exception as e:
        raise ValueError(f"表达式求值失败: {expr}") from e
    return float(result)

# ============================================================================
# 门分解函数
# ============================================================================
def _decompose_swap(q0: int, q1: int) -> List[Tuple[str, List[float], List[int]]]:
    return [('CNOT', [], [q0, q1]),
            ('CNOT', [], [q1, q0]),
            ('CNOT', [], [q0, q1])]

def _decompose_cu1(theta: float, q0: int, q1: int) -> List[Tuple[str, List[float], List[int]]]:
    half_theta = theta / 2.0
    return [('RZ', [half_theta], [q1]),
            ('CNOT', [], [q0, q1]),
            ('RZ', [-half_theta], [q1]),
            ('CNOT', [], [q0, q1]),
            ('RZ', [half_theta], [q0])]

def _decompose_ccx(q0: int, q1: int, q2: int) -> List[Tuple[str, List[float], List[int]]]:
    # 标准 Toffoli 分解 (Nielsen & Chuang)
    return [
        ('H', [], [q2]),
        ('CNOT', [], [q1, q2]),
        ('TDAG', [], [q2]),
        ('CNOT', [], [q0, q2]),
        ('T', [], [q2]),
        ('CNOT', [], [q1, q2]),
        ('TDAG', [], [q2]),
        ('CNOT', [], [q0, q2]),
        ('T', [], [q1]),
        ('T', [], [q2]),
        ('CNOT', [], [q0, q1]),
        ('H', [], [q2]),
        ('T', [], [q0]),
        ('TDAG', [], [q1]),
        ('CNOT', [], [q0, q1]),
    ]

def _decompose_ry(theta: float, q: int) -> List[Tuple[str, List[float], List[int]]]:
    pi_half = math.pi / 2.0
    return [('RZ', [pi_half], [q]),
            ('RX', [theta], [q]),
            ('RZ', [-pi_half], [q])]

DECOMPOSITION_REGISTRY = {
    'swap': _decompose_swap,
    'cu1': _decompose_cu1,
    'ccx': _decompose_ccx,
}

# ============================================================================
# QASM 解析器
# ============================================================================
class QASMParseError(Exception):
    pass

def _parse_qasm(qasm_str: str) -> Dict[str, Any]:
    """解析 OpenQASM 2.0 字符串，返回中间表示（包含寄存器映射）。"""
    lines = []
    for line in qasm_str.split('\n'):
        line = re.sub(r'(#|//).*$', '', line).strip()
        if line:
            lines.append(line)

    qreg_size = 0
    creg_size = 0
    qreg_map = {}
    creg_map = {}
    operations = []

    for line_no, line in enumerate(lines, 1):
        line_clean = line.rstrip(';').strip()
        if not line_clean:
            continue

        tokens = line_clean.split()
        first = tokens[0].lower()

        if first in ('openqasm', 'include', 'barrier'):
            continue

        if first == 'qreg':
            m = re.match(r'qreg\s+(\w+)\s*\[\s*(\d+)\s*\]', line_clean, re.IGNORECASE)
            if not m:
                raise QASMParseError(f"第{line_no}行：无法解析 qreg 声明: {line}")
            name = m.group(1)
            size = int(m.group(2))
            if len(qreg_map) >= 1:
                raise QASMParseError("当前适配器暂不支持多个量子寄存器")
            qreg_map[name] = size
            qreg_size = size
            continue

        if first == 'creg':
            m = re.match(r'creg\s+(\w+)\s*\[\s*(\d+)\s*\]', line_clean, re.IGNORECASE)
            if not m:
                raise QASMParseError(f"第{line_no}行：无法解析 creg 声明: {line}")
            name = m.group(1)
            size = int(m.group(2))
            if len(creg_map) >= 1:
                raise QASMParseError("当前适配器暂不支持多个经典寄存器")
            creg_map[name] = size
            creg_size = size
            continue

        if first == 'measure':
            m = re.match(r'measure\s+(.+?)\s*->\s*(.+)', line_clean, re.IGNORECASE)
            if not m:
                raise QASMParseError(f"第{line_no}行：无法解析测量语句: {line}")
            qubit_part = m.group(1).strip()
            clbit_part = m.group(2).strip()
            try:
                qubits = _parse_index_list_expand(qubit_part, qreg_map)
                clbits = _parse_index_list_expand(clbit_part, creg_map)
            except QASMParseError as e:
                raise QASMParseError(f"第{line_no}行：{e}") from e
            if len(qubits) != len(clbits):
                raise QASMParseError(f"第{line_no}行：测量语句中量子位和经典位数量不匹配: {line}")
            for q, c in zip(qubits, clbits):
                operations.append({
                    'name': 'measure',
                    'params': [],
                    'qubits': [q],
                    'clbits': [c],
                })
            continue

        gate_match = re.match(r'([a-z][a-z0-9]*)\s*(?:\(([^)]*)\))?\s+(.+)', line_clean, re.IGNORECASE)
        if not gate_match:
            raise QASMParseError(f"第{line_no}行：无法解析的语句: {line}")

        gate_name = gate_match.group(1).lower()
        params_str = gate_match.group(2)
        qubit_part = gate_match.group(3).strip()

        try:
            qubits = _parse_index_list_expand(qubit_part, qreg_map)
        except QASMParseError as e:
            raise QASMParseError(f"第{line_no}行：{e}") from e

        if not qubits:
            raise QASMParseError(f"第{line_no}行：量子位列表为空: {line}")

        params = []
        if params_str:
            try:
                params = _parse_param_list(params_str)
            except QASMParseError as e:
                raise QASMParseError(f"第{line_no}行：{e}") from e

        operations.append({
            'name': gate_name,
            'params': params,
            'qubits': qubits,
            'clbits': [],
        })

    return {
        'qreg_size': qreg_size,
        'creg_size': creg_size,
        'qreg_map': qreg_map,
        'creg_map': creg_map,
        'operations': operations,
    }

def _parse_index_list_expand(s: str, reg_sizes: Dict[str, int]) -> List[int]:
    """解析索引列表，支持裸寄存器名自动展开为所有索引。"""
    s = s.strip()
    if not s:
        return []
    if s.lower() in reg_sizes:
        return list(range(reg_sizes[s.lower()]))
    indices = []
    for part in s.split(','):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'[qc]\[(\d+)\]', part, re.IGNORECASE)
        if m:
            indices.append(int(m.group(1)))
        else:
            try:
                indices.append(int(part))
            except ValueError:
                raise QASMParseError(f"无法解析索引: {part}")
    return indices

def _parse_param_list(params_str: str) -> List[float]:
    """解析参数表达式，使用安全求值器。"""
    params_str = params_str.strip()
    if not params_str:
        return []
    param_parts = [p.strip() for p in params_str.split(',')]
    result = []
    for p in param_parts:
        if not p:
            continue
        try:
            val = _safe_eval_math(p)
            result.append(float(val))
        except Exception as e:
            raise QASMParseError(f"参数表达式求值失败: {p}，错误: {e}")
    return result

# ============================================================================
# OriginIR 转译
# ============================================================================
def _generate_originir(parsed: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"QINIT {parsed['qreg_size']}")
    lines.append(f"CREG {parsed['creg_size']}")

    for op in parsed['operations']:
        name = op['name']
        qubits = op['qubits']
        if name == 'measure':
            clbits = op['clbits']
            for q, c in zip(qubits, clbits):
                lines.append(f"MEASURE q[{q}],c[{c}]")
            continue

        originir_name = GATE_MAP.get(name)
        if not originir_name:
            raise QASMParseError(f"不支持的门: {name}")

        params = op['params']
        if params:
            param_str = ",".join(_format_param(p) for p in params)
            qubit_str = ",".join(f"q[{i}]" for i in qubits)
            lines.append(f"{originir_name}({param_str}) {qubit_str}")
        else:
            if len(qubits) == 1:
                lines.append(f"{originir_name} q[{qubits[0]}]")
            elif len(qubits) == 2:
                lines.append(f"{originir_name} q[{qubits[0]}],q[{qubits[1]}]")
            elif len(qubits) == 3:
                lines.append(f"{originir_name} q[{qubits[0]}],q[{qubits[1]}],q[{qubits[2]}]")
            else:
                raise QASMParseError(f"门 {name} 的量子位数量不支持: {len(qubits)}")

    return "\n".join(lines)

def _format_param(value: float) -> str:
    pi_ratio = value / math.pi
    if abs(pi_ratio - round(pi_ratio)) < 1e-9:
        n = int(round(pi_ratio))
        if n == 0:
            return "0"
        elif n == 1:
            return "pi"
        elif n == -1:
            return "-pi"
        else:
            return f"{n}*pi"
    return f"{value:.15g}"

# ============================================================================
# 门分解应用到操作列表（统一分解路径）
# ============================================================================
def _apply_decompositions(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将高级门替换为基础门分解序列，并修正 cnot 为 cx。"""
    new_ops = []
    for op in operations:
        name = op['name']
        if name == 'measure':
            new_ops.append(op)
            continue
        if name in DECOMPOSITION_REGISTRY:
            qubits = op['qubits']
            params = op['params']
            decompose_func = DECOMPOSITION_REGISTRY[name]
            if name == 'swap':
                decomposed = decompose_func(qubits[0], qubits[1])
            elif name == 'cu1':
                theta = params[0] if params else 0.0
                decomposed = decompose_func(theta, qubits[0], qubits[1])
            elif name == 'ccx':
                decomposed = decompose_func(qubits[0], qubits[1], qubits[2])
            elif name == 'ry':
                theta = params[0] if params else 0.0
                decomposed = decompose_func(theta, qubits[0])
            else:
                decomposed = []
            for g_name, g_params, g_qubits in decomposed:
                lower_gate = g_name.lower()
                if lower_gate == "cnot":
                    lower_gate = "cx"
                new_ops.append({
                    'name': lower_gate,
                    'params': g_params,
                    'qubits': g_qubits,
                    'clbits': [],
                })
        else:
            new_ops.append(op)
    return new_ops

# ============================================================================
# transpile 函数（应用分解后生成 OriginIR）
# ============================================================================
def transpile(qasm_str: str, target: str) -> str:
    if target != TARGET_ORIGINQ:
        raise ValueError(f"Unsupported target: {target}. Only '{TARGET_ORIGINQ}' is supported.")
    parsed = _parse_qasm(qasm_str)
    parsed['operations'] = _apply_decompositions(parsed['operations'])
    return _generate_originir(parsed)

# ============================================================================
# pyqpanda 线路构建与执行
# ============================================================================
def _build_qprog_from_parsed(parsed: Dict[str, Any]):
    """根据解析结果构建 pyqpanda QProg，返回 (QProg, CVec, QVec)。"""
    if not PYQPANDA_AVAILABLE:
        raise PyQPandaError("pyqpanda is not available")

    _ensure_qm_initialized()

    qreg_size = parsed['qreg_size']
    creg_size = parsed['creg_size']
    operations = parsed['operations']
    # === 关键：统一门分解，与 transpile 路径一致 ===
    operations = _apply_decompositions(operations)

    q_vec = None
    c_reg = None
    try:
        q_vec = pyqpanda.qAlloc_many(qreg_size)
        c_reg = pyqpanda.cAlloc_many(creg_size)
        prog = pyqpanda.QProg()

        for op in operations:
            name = op['name']
            qubits = op['qubits']
            if name == 'measure':
                for qidx, cidx in zip(qubits, op['clbits']):
                    prog << pyqpanda.Measure(q_vec[qidx], c_reg[cidx])
                continue

            pyqpanda_gate = _get_pyqpanda_gate(name)
            if pyqpanda_gate is not None:
                _apply_gate_direct(prog, pyqpanda_gate, name, op['params'], qubits, q_vec)
                continue

            # 理论上分解后不会走到这里，但保留运行时分解作为兜底
            decomposed = _decompose_gate(name, op['params'], qubits)
            if decomposed is None:
                raise RuntimeError(f"无法应用门 {name}，且无可用分解")
            for g_name, g_params, g_qubits in decomposed:
                lower_gate = g_name.lower()
                if lower_gate == "cnot":
                    lower_gate = "cx"
                gate_func_name = _get_pyqpanda_gate(lower_gate)
                if gate_func_name is None:
                    raise RuntimeError(f"无法找到门 {lower_gate} 的 PyQPanda 实现")
                _apply_gate_direct(prog, gate_func_name, lower_gate, g_params, g_qubits, q_vec)

    except Exception:
        # 安全释放已分配资源
        if q_vec is not None:
            for qb in q_vec:
                try:
                    pyqpanda.qFree(qb)
                except Exception as e:
                    logging.warning(f"释放量子比特失败: {e}")
        if c_reg is not None:
            for cb in c_reg:
                try:
                    pyqpanda.cFree(cb)
                except Exception as e:
                    logging.warning(f"释放经典比特失败: {e}")
        raise

    return prog, c_reg, q_vec

def _get_pyqpanda_gate(qasm_gate: str) -> Optional[str]:
    """获取 pyqpanda 中对应的门函数名（输入为小写 QASM 门名）。"""
    mapping = {
        'h': ['H', 'HGate'],
        'x': ['X', 'XGate'],
        's': ['S', 'SGate'],
        'sdg': ['SDG', 'Sdg', 'S_DAGGER'],
        't': ['T', 'TGate'],
        'tdg': ['TDG', 'Tdg', 'T_DAGGER'],
        'rz': ['RZ', 'RZGate'],
        'ry': ['RY', 'RYGate'],
        'rx': ['RX', 'RXGate'],
        'cx': ['CNOT', 'CNOTGate'],
        'cu1': ['CU1', 'CU1Gate', 'CR'],
        'swap': ['SWAP', 'SwapGate'],
        'ccx': ['Toffoli', 'CCX', 'CCXGate', 'ToffoliGate'],
    }
    candidates = mapping.get(qasm_gate, [])
    for candidate in candidates:
        if hasattr(pyqpanda, candidate):
            attr = getattr(pyqpanda, candidate)
            if callable(attr):
                return candidate
    return None

def _apply_gate_direct(prog, gate_name: str, original_name: str, params: List[float], qubits: List[int], q_reg):
    """
    直接应用门到 QProg。
    根据门类型明确参数顺序：
    - 单量子比特旋转门 (rz/ry/rx)：gate(qubit, angle)
    - 两量子比特相位门 (cu1)：gate(angle, control, target)
    - 其他无参数门直接按顺序传递量子比特
    """
    gate_func = getattr(pyqpanda, gate_name)
    q_args = [q_reg[idx] for idx in qubits]

    if not params:
        prog << gate_func(*q_args)
        return

    # 根据门名处理参数顺序
    if original_name in ('rz', 'ry', 'rx'):
        # 旋转门：单个量子比特 + 一个角度参数
        if len(q_args) != 1 or len(params) != 1:
            raise ValueError(f"旋转门 {original_name} 需要 1 个量子比特和 1 个参数")
        prog << gate_func(q_args[0], params[0])
    elif original_name == 'cu1':
        # CU1 相位门：两个量子比特 + 一个角度参数
        if len(q_args) != 2 or len(params) != 1:
            raise ValueError(f"CU1 门需要 2 个量子比特和 1 个参数")
        prog << gate_func(params[0], q_args[0], q_args[1])
    else:
        # 未明确处理的其他参数门，尝试通用顺序（参数在前）
        try:
            prog << gate_func(*params, *q_args)
        except TypeError:
            # 若失败，尝试量子比特在前
            try:
                prog << gate_func(*q_args, *params)
            except TypeError as e:
                raise TypeError(f"无法应用参数门 {original_name}，参数顺序不匹配: {e}")

def _decompose_gate(name: str, params: List[float], qubits: List[int]) -> Optional[List[Tuple[str, List[float], List[int]]]]:
    """根据门名返回分解后的操作列表（运行时兜底用）。"""
    if name not in DECOMPOSITION_REGISTRY:
        return None
    decompose_func = DECOMPOSITION_REGISTRY[name]
    if name == 'swap':
        return decompose_func(qubits[0], qubits[1])
    elif name == 'cu1':
        theta = params[0] if params else 0.0
        return decompose_func(theta, qubits[0], qubits[1])
    elif name == 'ccx':
        return decompose_func(qubits[0], qubits[1], qubits[2])
    elif name == 'ry':
        theta = params[0] if params else 0.0
        return decompose_func(theta, qubits[0])
    return None

# ============================================================================
# 执行函数
# ============================================================================
def execute_circuit(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """执行 OpenQASM 2.0 电路，返回统一结果 Schema。"""
    result_template = {
        "backend": BACKEND_NAME,
        "job_id": str(uuid.uuid4()),
        "shots": shots,
        "counts": {},
        "bit_order": BIT_ORDER,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "meta": {},
    }

    if target != TARGET_ORIGINQ:
        result_template["error"] = f"Unsupported target: {target}"
        return result_template

    if not PYQPANDA_AVAILABLE:
        result_template["error"] = "pyqpanda is not installed. Please install pyqpanda to run on originq backend."
        return result_template

    if shots <= 0:
        result_template["error"] = "shots must be a positive integer"
        return result_template

    try:
        parsed = _parse_qasm(qasm_str)
    except QASMParseError as e:
        result_template["error"] = f"QASM parsing error: {e}"
        return result_template

    result_template["meta"]["qreg_size"] = parsed['qreg_size']
    result_template["meta"]["creg_size"] = parsed['creg_size']
    result_template["meta"]["optimization_level"] = 0

    q_vec = None
    c_reg = None
    qprog = None

    try:
        qprog, c_reg, q_vec = _build_qprog_from_parsed(parsed)
    except Exception as e:
        logging.error(f"Failed to build quantum program: {e}", exc_info=True)
        result_template["error"] = f"Failed to build quantum program: {e}"
        return result_template

    try:
        _ensure_qm_initialized()
        # 注意：不调用 reset，避免破坏已分配量子比特

        # 执行采样，兼容不同版本的函数名
        if hasattr(pyqpanda, 'run_with_configuration'):
            raw_counts = pyqpanda.run_with_configuration(qprog, c_reg, shots)
        elif hasattr(pyqpanda, 'run_with_config'):
            raw_counts = pyqpanda.run_with_config(qprog, c_reg, shots)
        elif hasattr(pyqpanda, 'direct_run'):
            raw_counts = pyqpanda.direct_run(qprog, shots)
        elif hasattr(pyqpanda, 'run'):
            raw_counts = pyqpanda.run(qprog, c_reg, shots)
        else:
            raise RuntimeError("No suitable pyqpanda run function found")
    except Exception as e:
        logging.error(f"Execution error: {e}", exc_info=True)
        result_template["error"] = f"Execution error: {e}"
        return result_template
    finally:
        # 释放资源（优先使用 *_many 函数）
        if q_vec is not None:
            try:
                if hasattr(pyqpanda, 'qFree_many'):
                    pyqpanda.qFree_many(q_vec)
                else:
                    for qb in q_vec:
                        pyqpanda.qFree(qb)
            except Exception as e:
                logging.warning(f"Failed to free q_vec: {e}")
        if c_reg is not None:
            try:
                if hasattr(pyqpanda, 'cFree_many'):
                    pyqpanda.cFree_many(c_reg)
                else:
                    for cb in c_reg:
                        pyqpanda.cFree(cb)
            except Exception as e:
                logging.warning(f"Failed to free c_reg: {e}")

    counts = _process_counts(raw_counts, parsed['creg_size'])
    result_template["counts"] = counts
    return result_template

# 兼容外部调用 run
run = execute_circuit

def _process_counts(raw_counts: Dict[str, int], creg_size: int) -> Dict[str, int]:
    """
    将 pyqpanda 返回的 counts 转换为统一格式（小端序）。
    实测（pyqpanda 3.8.5）：返回的 key 是 str，且本身就是小端显示（'01' 的右字符 = c[0]），
    无需反转（早期代码反转了，变回大端——已修）。
    """
    processed = {}
    for key, value in raw_counts.items():
        if isinstance(key, int):
            # pyqpanda 的 int 键已是小端（bit0=c[0]），直接格式化
            key_str = format(key, f'0{creg_size}b')
        else:
            key_str = str(key).strip().replace(' ', '')
            if len(key_str) < creg_size:
                key_str = key_str.zfill(creg_size)
            elif len(key_str) > creg_size:
                key_str = key_str[-creg_size:]
            # pyqpanda 的 str 键本身就是小端显示（实测 '01' = c[0]在右），不反转
        processed[key_str] = processed.get(key_str, 0) + value
    return processed

# ============================================================================
# 测试入口
# ============================================================================
if __name__ == "__main__":
    # 测试贝尔态
    qasm_bell = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[2];
    creg c[2];
    h q[0];
    cx q[0],q[1];
    measure q[0] -> c[0];
    measure q[1] -> c[1];
    """
    print("Bell state OriginIR:")
    print(transpile(qasm_bell, TARGET_ORIGINQ))
    print("\nBell state counts:")
    result = execute_circuit(qasm_bell, TARGET_ORIGINQ, shots=8192)
    print(json.dumps(result, indent=2))

    # 测试 Toffoli
    qasm_toffoli = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[3];
    creg c[3];
    x q[0];
    x q[1];
    ccx q[0],q[1],q[2];
    measure q[0] -> c[0];
    measure q[1] -> c[1];
    measure q[2] -> c[2];
    """
    print("\nToffoli state OriginIR (decomposed):")
    print(transpile(qasm_toffoli, TARGET_ORIGINQ))
    print("\nToffoli state counts:")
    result = execute_circuit(qasm_toffoli, TARGET_ORIGINQ, shots=8192)
    print(json.dumps(result, indent=2))
