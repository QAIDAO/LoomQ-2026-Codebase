#!/usr/bin/env python3
"""L3 compile_hybrid 随机化模糊测试（本地开发用）。

按赛题迷你文法随机生成 Hybrid-QASM 用例，把编译出的 RISC-V 汇编载入官方
TinyRISCVEmulator，穷举注入所有测量值组合，与参考解释器逐组比对寄存器终态。

运行：python3 starter_kit/test_hybrid_fuzz.py [--cases N] [--seed S]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapter  # noqa: E402
from riscv_emulator import TinyRISCVEmulator  # noqa: E402

PASSED = 0
FAILED = 0


# --- 参考解释器（与赛题文法一致） --------------------------------------------

class RefInterpreter:
    """按赛题迷你文法解释 classical {} 块。r1..r9 -> 变量表，c[k] -> 注入值。"""

    def __init__(self, measured: dict):
        self.regs = {i: 0 for i in range(1, 10)}
        self.measured = measured  # {bit_index: value}

    def eval_expr(self, tokens):
        # tokens: [operand] 或 [a, op, b]（a/b 为 int 字面量或变量/测量引用）
        if len(tokens) == 1:
            return self.operand(tokens[0])
        a, op, b = self.operand(tokens[0]), tokens[1], self.operand(tokens[2])
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        raise ValueError(f"未知运算符 {op}")

    def operand(self, tok):
        if tok.startswith("r") and tok[1:].isdigit() and 1 <= int(tok[1:]) <= 9:
            return self.regs[int(tok[1:])]
        if tok.startswith("c[") and tok.endswith("]"):
            return self.measured[int(tok[2:-1])]
        if tok.lstrip("-").isdigit():
            return int(tok)
        raise ValueError(f"未知操作数 {tok}")

    def run(self, statements):
        i = 0
        while i < len(statements):
            stmt = statements[i]
            if stmt["kind"] == "assign":
                self.regs[stmt["var"]] = self.eval_expr(stmt["expr"])
            elif stmt["kind"] == "if":
                a, op, b = self.operand(stmt["cond"][0]), stmt["cond"][1], self.operand(stmt["cond"][2])
                truth = (a == b) if op == "==" else (a != b)
                if truth:
                    self.run(stmt["then"])
                elif stmt["else"] is not None:
                    self.run(stmt["else"])
            i += 1


def parse_classical_for_ref(code: str):
    """把 classical 块解析为语句树（独立实现，不复用 compile 路径）。"""
    import re
    raw = []
    for m in re.finditer(r"if|else|c\[\d+\]|r[1-9]|==|!=|\d+|[(){};=+\-]", code):
        raw.append(m.group(0))
    # 合并一元符号与数字（与 adapter 的分词规则一致）
    tokens = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if tok in ("+", "-") and i + 1 < len(raw) and raw[i + 1].isdigit():
            prev = tokens[-1] if tokens else None
            is_binary = prev is not None and (
                re.fullmatch(r"r[1-9]", prev) or re.fullmatch(r"c\[\d+\]", prev)
                or prev.lstrip("-").isdigit()
            )
            if not is_binary:
                tokens.append(tok + raw[i + 1])
                i += 2
                continue
        tokens.append(tok)
        i += 1

    def parse_block(idx):
        stmts = []
        while idx < len(tokens):
            t = tokens[idx]
            if t == "}":
                return stmts, idx + 1
            if t == "if":
                # if ( cond ) { ... } [else { ... }]
                assert tokens[idx + 1] == "("
                j = idx + 2
                cond = []
                while tokens[j] != ")":
                    cond.append(tokens[j]); j += 1
                j += 1
                assert tokens[j] == "{"
                then_stmts, j = parse_block(j + 1)
                else_stmts = None
                if j < len(tokens) and tokens[j] == "else":
                    j += 1
                    assert tokens[j] == "{"
                    else_stmts, j = parse_block(j + 1)
                stmts.append({"kind": "if", "cond": cond, "then": then_stmts, "else": else_stmts})
                idx = j
            elif t in ("r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"):
                var = int(t[1])
                assert tokens[idx + 1] == "="
                j = idx + 2
                expr = []
                while tokens[j] != ";":
                    expr.append(tokens[j]); j += 1
                stmts.append({"kind": "assign", "var": var, "expr": expr})
                idx = j + 1
            else:
                idx += 1
        return stmts, idx

    stmts, _ = parse_block(0)
    return stmts


def ref_final_state(code: str, measured: dict) -> dict:
    ref = RefInterpreter(measured)
    ref.run(parse_classical_for_ref(code))
    return {f"x{i}": v for i, v in ref.regs.items() if v != 0}


# --- 随机用例生成 ------------------------------------------------------------

def gen_code(rng: random.Random, n_meas: int, n_statements: int, depth: int = 0) -> str:
    lines = [f"r{x} = {rng.randint(-50, 200)};" for x in (1, 2, 3)]
    for _ in range(n_statements):
        if depth >= 2 or rng.random() < 0.45:
            var = rng.randint(1, 9)
            expr = gen_expr(rng, n_meas)
            lines.append(f"r{var} = {expr};")
        else:
            lines.append(gen_if(rng, n_meas, depth))
    return "\n".join(lines)


def gen_operand(rng, n_meas) -> str:
    pick = rng.random()
    if pick < 0.4:
        return str(rng.randint(-20, 100))
    if pick < 0.8:
        return f"r{rng.randint(1, 9)}"
    return f"c[{rng.randrange(n_meas)}]"


def gen_expr(rng, n_meas) -> str:
    pick = rng.random()
    if pick < 0.4:
        return gen_operand(rng, n_meas)
    a = gen_operand(rng, n_meas)
    op = rng.choice(["+", "-"])
    b = gen_operand(rng, n_meas)
    return f"{a} {op} {b}"


def gen_if(rng, n_meas, depth: int = 0) -> str:
    a = gen_operand(rng, n_meas)
    op = rng.choice(["==", "!="])
    b = gen_operand(rng, n_meas)
    inner = gen_code(rng, n_meas, 2, depth + 1)
    if rng.random() < 0.6:
        other = gen_code(rng, n_meas, 2, depth + 1)
        return f"if ({a} {op} {b}) {{\n{inner}\n}} else {{\n{other}\n}}"
    return f"if ({a} {op} {b}) {{\n{inner}\n}}"


def gen_hybrid_qasm(rng, n_q, n_meas, n_statements) -> str:
    header = f"""OPENQASM 2.0;
include "qelib1.inc";
qreg q[{n_q}];
creg c[{n_meas}];
"""
    meas = "\n".join(f"measure q[{i}] -> c[{i}];" for i in range(n_meas))
    body = gen_code(rng, n_meas, n_statements)
    return f"""{header}{meas}
classical {{
{body}
}}
h q[0];
"""


# --- 验证 --------------------------------------------------------------------

def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f"  [FAIL] {label} — {detail}")


def run_case(case_id: int, qasm: str, n_meas: int) -> None:
    try:
        quantum_ops, assembly = adapter.compile_hybrid(qasm)
    except Exception as exc:
        check(f"case{case_id}:compile", False, f"{type(exc).__name__}: {exc}")
        return
    if not assembly.strip():
        check(f"case{case_id}:compile", False, "空汇编输出")
        return

    # 提取 classical 代码用于参考解释（从 qasm 原文提取）
    start = qasm.find("classical")
    brace = qasm.find("{", start)
    depth = 0
    end = -1
    for i in range(brace, len(qasm)):
        if qasm[i] == "{":
            depth += 1
        elif qasm[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    classical_code = qasm[brace + 1:end]

    # 穷举注入所有测量值组合
    for mask in range(1 << n_meas):
        measured = {i: (mask >> i) & 1 for i in range(n_meas)}
        emu = TinyRISCVEmulator()
        try:
            emu.load_program(assembly)
            for i in range(n_meas):
                emu.set_register(f"x{10 + i}", measured[i])
            state = emu.execute()
        except Exception as exc:
            check(f"case{case_id}:mask{mask:0{n_meas}b}", False,
                  f"{type(exc).__name__}: {exc}\n---asm---\n{assembly}")
            return
        expected = ref_final_state(classical_code, measured)
        # 按赛题规范只比对程序变量寄存器 x1..x9（r1..r9 的映射）
        got_vars = {k: v for k, v in state.items() if k in {f"x{i}" for i in range(1, 10)}}
        if got_vars != expected:
            check(f"case{case_id}:mask{mask:0{n_meas}b}", False,
                  f"got={state} want={expected}\n---asm---\n{assembly}\n---classical---\n{classical_code}")
            return
    check(f"case{case_id}:all-masks({1 << n_meas})", True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260825)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    print("=" * 66)
    print(f"L3 compile_hybrid 随机模糊测试：{args.cases} 用例，种子 {args.seed}")
    print("=" * 66)
    for case_id in range(args.cases):
        n_q = rng.randint(1, 5)
        n_meas = rng.randint(1, 3)
        n_stmts = rng.randint(1, 6)
        qasm = gen_hybrid_qasm(rng, n_q, n_meas, n_stmts)
        run_case(case_id, qasm, n_meas)
    print("=" * 66)
    print(f"结果：{PASSED} passed, {FAILED} failed")
    print("=" * 66)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
