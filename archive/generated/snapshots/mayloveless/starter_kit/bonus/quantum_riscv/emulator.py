"""官方 TinyRISCVEmulator 的隔离式 Quantum custom-word 扩展。"""

from typing import Dict, Iterable, List, Protocol

try:
    from ...riscv_emulator import TinyRISCVEmulator
except ImportError:  # 支持从 starter_kit 目录直接运行。
    from riscv_emulator import TinyRISCVEmulator

from .encoding import QuantumInstruction, decode_quantum_instruction


class QuantumCoprocessor(Protocol):
    """量子命令派发边界；本接口不承诺或模拟量子态。"""

    def apply_gate(self, command: QuantumInstruction) -> None:
        ...

    def measure(self, command: QuantumInstruction) -> int:
        ...


class TraceCoprocessor:
    """确定性控制流测试后端：记录命令并消费预置测量位。"""

    def __init__(self, measurements: Iterable[int] = ()) -> None:
        values = list(measurements)
        if any(type(value) is not int or value not in (0, 1) for value in values):
            raise ValueError("deterministic measurements must contain only 0 or 1")
        self._measurements = values
        self._measurement_index = 0
        self.trace: List[QuantumInstruction] = []

    def apply_gate(self, command: QuantumInstruction) -> None:
        self.trace.append(command)

    def measure(self, command: QuantumInstruction) -> int:
        if self._measurement_index >= len(self._measurements):
            raise RuntimeError("no deterministic measurement remains")
        value = self._measurements[self._measurement_index]
        self._measurement_index += 1
        self.trace.append(command)
        return value


class QuantumRISCVEmulator(TinyRISCVEmulator):
    """执行官方经典子集，并将 `.word` custom-0 指令派发给协处理器。"""

    def __init__(self, coprocessor: QuantumCoprocessor) -> None:
        super().__init__()
        self.coprocessor = coprocessor
        self.quantum_trace: List[QuantumInstruction] = []

    def load_program(self, asm_code: str) -> None:
        # 复用官方 parser；它会把 `.word 0x...` 保留为普通 token。
        super().load_program(asm_code)
        self.quantum_trace = []

    def execute(self) -> Dict[str, int]:
        """保持官方 PC/分支语义，在同一取指循环中增加 custom dispatch。"""
        steps = 0
        num_instr = len(self.instructions)

        while 0 <= self.pc < num_instr:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")

            op, args = self.instructions[self.pc]
            next_pc = self.pc + 1
            if op == ".word":
                if len(args) != 1:
                    raise ValueError(".word requires exactly one 32-bit value")
                word = int(args[0], 0)
                self._dispatch_quantum(word)
            else:
                next_pc = self._execute_classical(op, args, next_pc)
            self.pc = next_pc

        return {
            "x%d" % index: value
            for index, value in enumerate(self.registers)
            if value != 0
        }

    def _dispatch_quantum(self, word: int) -> None:
        # 每个 custom word 必须先经过严格 decoder，禁止 pseudo-mnemonic 旁路。
        command = decode_quantum_instruction(word)
        if command.operation == "QMEAS":
            result = self.coprocessor.measure(command)
            if type(result) is not int or result not in (0, 1):
                raise ValueError("quantum measurement must return 0 or 1")
            assert command.rd is not None
            self.set_register("x%d" % command.rd, result)
        else:
            self.coprocessor.apply_gate(command)
        self.quantum_trace.append(command)

    def _execute_classical(self, op: str, args: List[str], next_pc: int) -> int:
        """与官方 TinyRISCVEmulator 支持的七条经典指令保持同义。"""
        if op == "li":
            self.set_register(args[0], int(args[1]))
        elif op == "add":
            self.set_register(
                args[0], self.get_register(args[1]) + self.get_register(args[2])
            )
        elif op == "sub":
            self.set_register(
                args[0], self.get_register(args[1]) - self.get_register(args[2])
            )
        elif op == "addi":
            self.set_register(args[0], self.get_register(args[1]) + int(args[2]))
        elif op in ("beq", "bne"):
            equal = self.get_register(args[0]) == self.get_register(args[1])
            should_branch = equal if op == "beq" else not equal
            if should_branch:
                label = args[2]
                if label not in self.labels:
                    raise ValueError("未定义的跳转标签: %s" % label)
                next_pc = self.labels[label]
        elif op == "j":
            label = args[0]
            if label not in self.labels:
                raise ValueError("未定义的跳转标签: %s" % label)
            next_pc = self.labels[label]
        else:
            raise ValueError("不支持的指令操作: %s" % op)
        return next_pc
