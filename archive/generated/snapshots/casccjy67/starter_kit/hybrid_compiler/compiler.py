"""Hybrid-QASM compiler entry point."""
from .lexer import Lexer
from .parser import HybridQASMParser
from .codegen import RiscVCodeGen


def compile_hybrid_qasm(hybrid_qasm_str: str):
    """Compile Hybrid-QASM to (quantum_ops, riscv_assembly).

    Args:
        hybrid_qasm_str: Hybrid-QASM source string

    Returns:
        Tuple of (list of quantum operation dicts, RISC-V assembly text)
    """
    lexer = Lexer(hybrid_qasm_str)
    tokens = lexer.tokenize()

    parser = HybridQASMParser(tokens)
    quantum_ops_ast, classical_stmts = parser.parse()

    quantum_ops = []
    for op in quantum_ops_ast:
        quantum_ops.append({
            "name": op.name,
            "qubits": op.qubits,
            "params": op.params,
            "is_measure": op.is_measure,
            "measure_clbit": op.measure_clbit if op.is_measure else -1,
        })

    codegen = RiscVCodeGen()
    riscv_text = codegen.generate(classical_stmts)

    return quantum_ops, riscv_text
