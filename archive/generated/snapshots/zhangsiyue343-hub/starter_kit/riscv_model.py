#!/usr/bin/env python3
"""Immutable RISC-V subset model: instructions, machine state, pure stepping.

Every instruction is a frozen dataclass; the machine state is immutable and
`step`/`execute` are pure functions returning new states — decoding is a
dict dispatch, execution is a fold. Rendering to assembly text and parsing
text back are inverse views over the same instruction objects, so compiled
artifacts can be verified by construction instead of string surgery.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Optional


# --------------------------------------------------------------------------
# instruction set (frozen dataclasses)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Instruction:
    pass


@dataclass(frozen=True)
class Label(Instruction):
    name: str

    def render(self) -> str:
        return "%s:" % self.name


@dataclass(frozen=True)
class Li(Instruction):
    rd: str
    imm: int

    def render(self) -> str:
        return "li %s, %d" % (self.rd, self.imm)


@dataclass(frozen=True)
class Add(Instruction):
    rd: str
    rs1: str
    rs2: str

    def render(self) -> str:
        return "add %s, %s, %s" % (self.rd, self.rs1, self.rs2)


@dataclass(frozen=True)
class Sub(Instruction):
    rd: str
    rs1: str
    rs2: str

    def render(self) -> str:
        return "sub %s, %s, %s" % (self.rd, self.rs1, self.rs2)


@dataclass(frozen=True)
class Addi(Instruction):
    rd: str
    rs1: str
    imm: int

    def render(self) -> str:
        return "addi %s, %s, %d" % (self.rd, self.rs1, self.imm)


@dataclass(frozen=True)
class Beq(Instruction):
    rs1: str
    rs2: str
    target: str

    def render(self) -> str:
        return "beq %s, %s, %s" % (self.rs1, self.rs2, self.target)


@dataclass(frozen=True)
class Bne(Instruction):
    rs1: str
    rs2: str
    target: str

    def render(self) -> str:
        return "bne %s, %s, %s" % (self.rs1, self.rs2, self.target)


@dataclass(frozen=True)
class Jmp(Instruction):
    target: str

    def render(self) -> str:
        return "j %s" % self.target


def render_program(instructions: tuple[Instruction, ...]) -> str:
    return "\n".join(instr.render() for instr in instructions) + "\n"


# --------------------------------------------------------------------------
# parsing assembly text back into instructions (verification round-trip)
# --------------------------------------------------------------------------

_PARSERS = {
    "li": lambda a: Li(a[0], int(a[1])),
    "add": lambda a: Add(*a),
    "sub": lambda a: Sub(*a),
    "addi": lambda a: Addi(a[0], a[1], int(a[2])),
    "beq": lambda a: Beq(*a),
    "bne": lambda a: Bne(*a),
    "j": lambda a: Jmp(a[0]),
}


def parse_program(text: str) -> tuple[Instruction, ...]:
    instructions: list[Instruction] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        while True:
            colon = line.find(":")
            head = line[:colon].strip()
            if colon >= 0 and " " not in head and "," not in head:
                instructions.append(Label(head))
                line = line[colon + 1:].strip()
                if not line:
                    break
            else:
                break
        if not line:
            continue
        parts = [t for t in line.replace(",", " ").split() if t]
        op, args = parts[0].lower(), parts[1:]
        builder = _PARSERS.get(op)
        if builder is None:
            raise ValueError("unsupported RISC-V mnemonic %r" % op)
        instructions.append(builder(args))
    return tuple(instructions)


# --------------------------------------------------------------------------
# pure machine semantics
# --------------------------------------------------------------------------

XLEN_MASK = (1 << 64) - 1
MAX_STEPS = 10_000


@dataclass(frozen=True)
class MachineState:
    registers: tuple[int, ...] = (0,) * 32
    pc: int = 0

    def read(self, reg: str) -> int:
        index = _reg_index(reg)
        return 0 if index == 0 else self.registers[index]

    def write(self, reg: str, value: int) -> "MachineState":
        index = _reg_index(reg)
        if index == 0:
            return self
        masked = value & XLEN_MASK
        if masked >= 1 << 63:
            masked -= 1 << 64
        registers = list(self.registers)
        registers[index] = masked
        return replace(self, registers=tuple(registers))


@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]
    labels: Mapping[str, int]


def link(instructions: tuple[Instruction, ...]) -> Program:
    """Resolve label names to instruction indices."""
    labels: dict[str, int] = {}
    executable: list[Instruction] = []
    for instr in instructions:
        if isinstance(instr, Label):
            labels[instr.name] = len(executable)
        else:
            executable.append(instr)
    return Program(tuple(executable), labels)


def step(state: MachineState, program: Program) -> MachineState:
    """Execute exactly one instruction; returns the successor state."""
    if not 0 <= state.pc < len(program.instructions):
        return replace(state, pc=-1)
    instr = program.instructions[state.pc]
    nxt = state.pc + 1
    if isinstance(instr, Li):
        return _bump(state.write(instr.rd, instr.imm), nxt)
    if isinstance(instr, Add):
        return _bump(state.write(
            instr.rd, state.read(instr.rs1) + state.read(instr.rs2)), nxt)
    if isinstance(instr, Sub):
        return _bump(state.write(
            instr.rd, state.read(instr.rs1) - state.read(instr.rs2)), nxt)
    if isinstance(instr, Addi):
        return _bump(state.write(
            instr.rd, state.read(instr.rs1) + instr.imm), nxt)
    if isinstance(instr, (Beq, Bne)):
        equal = state.read(instr.rs1) == state.read(instr.rs2)
        taken = equal if isinstance(instr, Beq) else not equal
        if taken:
            if instr.target not in program.labels:
                raise ValueError("undefined jump label %r" % instr.target)
            return replace(state, pc=program.labels[instr.target])
        return _bump(state, nxt)
    if isinstance(instr, Jmp):
        if instr.target not in program.labels:
            raise ValueError("undefined jump label %r" % instr.target)
        return replace(state, pc=program.labels[instr.target])
    raise ValueError("undecodable instruction %r" % (instr,))


def _bump(state: MachineState, pc: int) -> MachineState:
    return replace(state, pc=pc)


def execute(program: Program, injections: Optional[Mapping[str, int]] = None,
            max_steps: int = MAX_STEPS) -> tuple[int, ...]:
    """Run until PC leaves the program; returns the final register file."""
    state = MachineState()
    for reg, value in (injections or {}).items():
        state = state.write(reg, value)
    for _ in range(max_steps):
        if not 0 <= state.pc < len(program.instructions):
            return state.registers
        state = step(state, program)
    raise RuntimeError("program exceeded %d steps (infinite loop?)" % max_steps)


def _reg_index(reg: str) -> int:
    name = reg.strip().lower()
    if not name.startswith("x") or not name[1:].isdigit():
        raise ValueError("invalid register %r" % reg)
    index = int(name[1:])
    if not 0 <= index <= 31:
        raise ValueError("register index out of range: %r" % reg)
    return index
