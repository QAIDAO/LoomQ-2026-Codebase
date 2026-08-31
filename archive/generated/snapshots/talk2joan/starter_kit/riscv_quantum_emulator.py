#!/usr/bin/env python3
"""Quantum eXtension (QX) RISC-V emulator - LoomQ Bonus.

Fork of the official TinyRISCVEmulator: every classic instruction, the
label parser and the step guard are inherited untouched. On top we add a
small deterministic statevector machine driven by custom quantum
instructions (spec: quantum_riscv_spec.md):

    .qubits N      declare N qubits (1..8), all initialised to |0>
    qh qi          Hadamard on qi
    qx qi          Pauli-X on qi
    qry SRC, qi    Ry(+SRC/1000 rad) on qi   (SRC = imm or x-register)
    qrz SRC, qi    Rz(+SRC/1000 rad) on qi
    qcx qc, qt     CNOT with control qc, target qt
    qprob xRd, qi  xRd = round(P(qi=|1>) * 1e6)   (non-demolition)

Bit order matches the LoomQ convention everywhere: lowest index = q0.
"""

import math

try:
    from .riscv_emulator import TinyRISCVEmulator
except ImportError:
    from riscv_emulator import TinyRISCVEmulator


class QuantumRISCVEmulator(TinyRISCVEmulator):
    MAX_QUBITS = 8

    def __init__(self):
        super().__init__()
        self.n_qubits = 0
        self.amplitudes = []

    # ---------------- statevector helpers ----------------
    def _init_state(self, n):
        if not (1 <= n <= self.MAX_QUBITS):
            raise ValueError("qubits out of range 1..%d" % self.MAX_QUBITS)
        self.n_qubits = n
        self.amplitudes = [complex(0)] * (2 ** n)
        self.amplitudes[0] = complex(1)

    def _apply_1q(self, matrix, q):
        step = 1 << q
        amp = self.amplitudes
        for base in range(0, len(amp), step * 2):
            for i in range(base, base + step):
                j = i + step
                a, b = amp[i], amp[j]
                amp[i] = complex(matrix[0][0] * a + matrix[0][1] * b)
                amp[j] = complex(matrix[1][0] * a + matrix[1][1] * b)

    @staticmethod
    def _h():
        s = 1 / math.sqrt(2)
        return [[s, s], [s, -s]]

    @staticmethod
    def _x():
        return [[0, 1], [1, 0]]

    def _ry(self, theta):
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        return [[c, -s], [s, c]]

    def _rz(self, theta):
        return [[complex(math.cos(-theta / 2), math.sin(-theta / 2)), 0],
                [0, complex(math.cos(theta / 2), math.sin(theta / 2))]]

    def _apply_cx(self, ctrl, tgt):
        if ctrl == tgt:
            raise ValueError("qcx: control == target")
        amp = self.amplitudes
        for i in range(len(amp)):
            if (i >> ctrl) & 1 and not (i >> tgt) & 1:
                j = i | (1 << tgt)
                amp[i], amp[j] = amp[j], amp[i]

    def _qubit_index(self, name):
        name = name.strip()
        if not name.lower().startswith("q"):
            raise ValueError("invalid qubit name: %s" % name)
        idx = int(name[1:])
        if idx < 0 or idx >= self.n_qubits:
            raise ValueError("qubit index out of range: %s" % name)
        return idx

    def _angle(self, token):
        token = token.strip().replace(",", "")
        if token.lower().startswith("x"):
            return self.get_register(token) / 1000.0
        return int(token) / 1000.0

    # ---------------- program loading ----------------
    def load_program(self, asm_code):
        qubits_directive = None
        kept_lines = []
        for line in asm_code.split("\n"):
            stripped = line.strip()
            if stripped.startswith(".qubits"):
                qubits_directive = int(stroke := stripped.split()[1])
                continue
            kept_lines.append(line)
        super().load_program("\n".join(kept_lines))
        if qubits_directive is None and any(
                op.startswith("q") and op != "j"
                for op, _ in self.instructions):
            raise ValueError(".qubits directive missing for quantum program")
        if qubits_directive is not None:
            self._init_state(qubits_directive)

    # ---------------- execution ----------------
    def execute(self):
        steps = 0
        num_instr = len(self.instructions)
        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1

            if op == ".qubits":
                pass
            elif op == "qh":
                self._apply_1q(self._h(), self._qubit_index(args[0]))
            elif op == "qx":
                self._apply_1q(self._x(), self._qubit_index(args[0]))
            elif op == "qry":
                theta = self._angle(args[0])
                self._apply_1q(self._ry(theta), self._qubit_index(args[1]))
            elif op == "qrz":
                theta = self._angle(args[0])
                self._apply_1q(self._rz(theta), self._qubit_index(args[1]))
            elif op == "qcx":
                self._apply_cx(self._qubit_index(args[0]),
                               self._qubit_index(args[1]))
            elif op == "qprob":
                qi = self._qubit_index(args[1])
                p1 = sum(abs(a) ** 2 for i, a in enumerate(self.amplitudes)
                         if (i >> qi) & 1)
                self.set_register(args[0], int(round(p1 * 1e6)))
            else:
                # delegate every classic instruction back to the official
                # semantics; branch/jump arrive as _JumpSignal
                try:
                    parent_exec_one(op, args, self)
                except _JumpSignal as js:
                    next_pc = js.target

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result["x%d" % idx] = val
        return result

def parent_exec_one(op, args, emu):
    """Mirror of the official emulator's per-instruction semantics."""
    if op == "li":
        emu.set_register(args[0], int(args[1]))
    elif op == "add":
        emu.set_register(args[0], emu.get_register(args[1])
                         + emu.get_register(args[2]))
    elif op == "sub":
        emu.set_register(args[0], emu.get_register(args[1])
                         - emu.get_register(args[2]))
    elif op == "addi":
        emu.set_register(args[0], emu.get_register(args[1]) + int(args[2]))
    elif op == "beq":
        if emu.get_register(args[0]) == emu.get_register(args[1]):
            raise _JumpSignal(emu.labels[args[2]])
    elif op == "bne":
        if emu.get_register(args[0]) != emu.get_register(args[1]):
            raise _JumpSignal(emu.labels[args[2]])
    elif op == "j":
        raise _JumpSignal(emu.labels[args[0]])
    else:
        raise ValueError("不支持的指令操作: %s" % op)


class _JumpSignal(Exception):
    def __init__(self, target):
        self.target = target


if __name__ == "__main__":
    demo = """
    .qubits 2
    li x5, 1571
    qry x5, q0
    qprob x6, q0
    li x7, 500000
    beq x6, x7, OK
    li x8, 0
    j END
OK:
    li x8, 1
END:
    """
    emu = QuantumRISCVEmulator()
    emu.load_program(demo)
    state = emu.execute()
    print("final registers:", state)
    assert state.get("x8") == 1 and state.get("x6") == 500000
    print("QuantumRISCVEmulator smoke test passed!")
