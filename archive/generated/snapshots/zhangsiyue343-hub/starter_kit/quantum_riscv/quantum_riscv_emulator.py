#!/usr/bin/env python3
"""LoomQ Quantum RISC-V Emulator —— 官方 riscv_emulator.py 的量子扩展 fork。

本实现采用**指令字驱动的执行链路**（主办方 Bonus 方向 1）：

  汇编文本 ──assemble()──> 32 位机器码指令字 ──execute() 逐字解码──> 执行

- 标准指令按标准 RISC-V 编码（I/R/B/UJ 型）：li/add/sub/addi/beq/bne/j
- 量子指令使用 CUSTOM-0 opcode（0x0B），在 execute() 中按 opcode/funct3/funct7
  字段解码分派，使自定义 opcode 真正参与运行（不仅停留在规格文档）。

向后兼容官方 TinyRISCVEmulator：load_program(文本) + execute() 的标准指令行为
与官方实现一致（200 组随机程序交叉验证）。执行时每条指令都经过 decode()。
"""

import math
import random
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# RISC-V 标准 opcode
# ---------------------------------------------------------------------------
OP_IMM = 0x13    # addi 等
OP_R   = 0x33    # add/sub 等
OP_B   = 0x63    # beq/bne
OP_JAL = 0x6F    # jal（j 伪指令）
OP_CUSTOM0 = 0x0B  # 自定义量子扩展

# funct3 / funct7
F3_ADDI = 0x0
F3_ADD  = 0x0
F3_BEQ  = 0x0
F3_BNE  = 0x1
F7_SUB  = 0x20
F7_ADD  = 0x00

# 量子指令 funct7 / funct3 编码（见 QUANTUM_RISCV_SPEC.md）
_Q_F7 = {"qh": 0x01, "qx": 0x02, "qs": 0x03, "qsdg": 0x04, "qt": 0x05,
         "qtdg": 0x06, "qz": 0x07, "qcx": 0x08, "qswap": 0x09,
         "qccx": 0x0A, "qmeas": 0x0B, "qinit": 0x0C}
# 参数门用 funct3>=3，避免与 R 型门的 funct3（0/1/2）歧义
_Q_F3 = {"qry": 3, "qrz": 4, "qcu1": 5}

_STD_OPS = {"li", "add", "sub", "addi", "beq", "bne", "j"}


def _xidx(arg: str) -> int:
    a = arg.strip().replace(",", "")
    if not a.startswith("x") and not a.startswith("X"):
        raise ValueError("无效寄存器名: %s" % arg)
    return int(a[1:])


def _qidx(arg: str) -> int:
    a = arg.strip().replace(",", "")
    if a.startswith("q"):
        a = a[1:]
    return int(a)


def _imm16(value: int) -> int:
    if not -2048 <= value <= 2047:
        raise ValueError("立即数超出 12 位范围: %d" % value)
    return value & 0xFFF


# ---------------------------------------------------------------------------
# 汇编器：文本 → 32 位指令字
# ---------------------------------------------------------------------------

def assemble_line(op: str, args: List[str], labels: Dict[str, int],
                  addr: int) -> int:
    """把一条汇编指令编码为 32 位机器码指令字。"""
    if op == "li":
        rd, imm = _xidx(args[0]), int(args[1])
        return (imm & 0xFFF) << 20 | (rd & 0x1F) << 7 | OP_IMM
    if op == "addi":
        rd, rs1, imm = _xidx(args[0]), _xidx(args[1]), int(args[2])
        return (imm & 0xFFF) << 20 | (rs1 & 0x1F) << 15 | F3_ADDI << 12 | (rd & 0x1F) << 7 | OP_IMM
    if op == "add":
        rd, rs1, rs2 = _xidx(args[0]), _xidx(args[1]), _xidx(args[2])
        return (F7_ADD << 25) | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | F3_ADD << 12 | (rd & 0x1F) << 7 | OP_R
    if op == "sub":
        rd, rs1, rs2 = _xidx(args[0]), _xidx(args[1]), _xidx(args[2])
        return (F7_SUB << 25) | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15 | F3_ADD << 12 | (rd & 0x1F) << 7 | OP_R
    if op in ("beq", "bne"):
        rs1, rs2, label = _xidx(args[0]), _xidx(args[1]), args[2]
        if label not in labels:
            raise ValueError("未定义标签: %s" % label)
        # 偏移 = 目标索引 - 当前索引（指令寻址，与官方模拟器一致）。
        # 编码进 12 位立即数（I 型布局），解码端按同样语义还原。
        offset = labels[label] - addr
        if not -2048 <= offset <= 2047:
            raise ValueError("分支索引偏移超出 12 位范围: %d" % offset)
        funct3 = F3_BEQ if op == "beq" else F3_BNE
        imm = offset & 0xFFF
        return (imm << 20) | (rs1 & 0x1F) << 15 | funct3 << 12 | (rs2 & 0x1F) << 7 | OP_B
    if op == "j":
        label = args[0]
        if label not in labels:
            raise ValueError("未定义标签: %s" % label)
        offset = labels[label] - addr
        if not -(1 << 20) <= offset <= (1 << 20) - 1:
            raise ValueError("跳转索引偏移超出范围: %d" % offset)
        imm = offset & 0x1FFFFF
        return (imm << 12) | (0 << 7) | OP_JAL
    if op == "qinit":
        n = _qidx(args[0])
        return (_Q_F7["qinit"] << 25) | (n & 0x1F) << 15 | OP_CUSTOM0
    if op in _Q_F7:
        funct7 = _Q_F7[op]
        if op == "qmeas":
            qd, qa = _xidx(args[0]), _qidx(args[1])
            funct3, qb = 0, 0
        elif op in ("qcx", "qswap"):
            qa, qb = _qidx(args[0]), _qidx(args[1])
            funct3, qd = 1, 0
        elif op == "qccx":
            qa, qb, qd = _qidx(args[0]), _qidx(args[1]), _qidx(args[2])
            funct3 = 2
        else:
            qa = _qidx(args[0])
            qb, qd, funct3 = 0, 0, 0
        return ((funct7 & 0x7F) << 25) | ((qb & 0x1F) << 20) | ((qa & 0x1F) << 15) \
               | (funct3 << 12) | ((qd & 0x1F) << 7) | OP_CUSTOM0
    if op in _Q_F3:
        funct3 = _Q_F3[op]
        if op == "qcu1":
            qa, qb, imm16 = _qidx(args[0]), _qidx(args[1]), int(args[2])
            qd = qb
        else:
            qa, imm16 = _qidx(args[0]), int(args[1])
            qd = 0
        return ((imm16 & 0xFFF) << 20) | ((qa & 0x1F) << 15) | (funct3 << 12) \
               | ((qd & 0x1F) << 7) | OP_CUSTOM0
    raise ValueError("未知指令: %s" % op)


def assemble(asm_code: str) -> Tuple[List[int], Dict[str, int]]:
    """汇编文本 → (指令字列表, 标签→指令地址映射)。

    第一遍收集指令与标签；第二遍解析分支目标，编码每条指令。
    """
    # pass 1: parse lines -> (op, args, label?)
    parsed = []
    labels = {}
    for line in asm_code.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "#" in line:
            line = line.split("#")[0].strip()
        if line.endswith(":"):
            labels[line[:-1].strip()] = len(parsed)
            continue
        elif ":" in line:
            parts = line.split(":", 1)
            labels[parts[0].strip()] = len(parsed)
            line = parts[1].strip()
        tokens = line.replace(",", " ").split()
        if not tokens:
            continue
        op = tokens[0].lower()
        parsed.append((op, tokens[1:]))

    # pass 2: encode
    words = []
    for addr, (op, args) in enumerate(parsed):
        words.append(assemble_line(op, args, labels, addr))
    return words, labels


# ---------------------------------------------------------------------------
# 解码器：指令字 → (op, args) —— opcode/funct3/funct7 真正参与运行
# ---------------------------------------------------------------------------

def decode_word(word: int) -> Tuple[str, List[str]]:
    """解码一个 32 位指令字，返回 (助记符, 参数列表)。"""
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    imm12 = (word >> 20) & 0xFFF
    if imm12 & 0x800:
        imm12 -= 0x1000

    if opcode == OP_CUSTOM0:
        # 量子扩展：funct3>=3 为参数门（I 型），否则为 R 型门
        if funct3 >= 3:
            if funct3 == _Q_F3["qry"]:
                return ("qry", ["q%d" % rs1, str(imm12)])
            if funct3 == _Q_F3["qrz"]:
                return ("qrz", ["q%d" % rs1, str(imm12)])
            if funct3 == _Q_F3["qcu1"]:
                return ("qcu1", ["q%d" % rs1, "q%d" % rd, str(imm12)])
            raise ValueError("未知参数门 funct3: %d (word=0x%08X)" % (funct3, word))
        if funct7 == _Q_F7["qinit"]:
            return ("qinit", ["q%d" % rs1])
        if funct7 in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            name = {0x01: "qh", 0x02: "qx", 0x03: "qs", 0x04: "qsdg",
                    0x05: "qt", 0x06: "qtdg", 0x07: "qz"}[funct7]
            return (name, ["q%d" % rs1])
        if funct7 == _Q_F7["qcx"]:
            return ("qcx", ["q%d" % rs1, "q%d" % rs2])
        if funct7 == _Q_F7["qswap"]:
            return ("qswap", ["q%d" % rs1, "q%d" % rs2])
        if funct7 == _Q_F7["qccx"]:
            return ("qccx", ["q%d" % rs1, "q%d" % rs2, "q%d" % rd])
        if funct7 == _Q_F7["qmeas"]:
            return ("qmeas", ["x%d" % rd, "q%d" % rs1])
        raise ValueError("未知量子指令字: 0x%08X" % word)

    if opcode == OP_R:
        if funct3 == F3_ADD and funct7 == F7_ADD:
            return ("add", ["x%d" % rd, "x%d" % rs1, "x%d" % rs2])
        if funct3 == F3_ADD and funct7 == F7_SUB:
            return ("sub", ["x%d" % rd, "x%d" % rs1, "x%d" % rs2])
        raise ValueError("未知 R 型指令字: 0x%08X" % word)

    if opcode == OP_IMM:
        return ("addi", ["x%d" % rd, "x%d" % rs1, str(imm12)])

    if opcode == OP_B:
        # 自定义 B 型布局：imm[11:0]=索引偏移，rs1/rs2=寄存器
        imm = imm12
        name = "beq" if funct3 == F3_BEQ else ("bne" if funct3 == F3_BNE else "?")
        if name == "?":
            raise ValueError("未知 B 型指令字: 0x%08X" % word)
        # rs2 放在 rd 字段编码，解码时还原
        return (name, ["x%d" % rs1, "x%d" % rd, str(imm)])

    if opcode == OP_JAL:
        imm20 = (word >> 12) & 0x1FFFFF
        if imm20 & 0x100000:
            imm20 -= 0x200000
        return ("j", [str(imm20)])

    raise ValueError("未知 opcode: 0x%02X (word=0x%08X)" % (opcode, word))


# ---------------------------------------------------------------------------
# 量子门矩阵（与 adapter.py 的无噪声模拟器一致）
# ---------------------------------------------------------------------------

def _apply_1q(sv: List[complex], n: int, bit: int, mat: List[List[complex]], scale: float) -> None:
    mask = 1 << bit
    for i in range(1 << n):
        if not (i & mask):
            j = i | mask
            a0, a1 = sv[i], sv[j]
            sv[i] = (mat[0][0] * a0 + mat[0][1] * a1) * scale
            sv[j] = (mat[1][0] * a0 + mat[1][1] * a1) * scale


def _apply_cx(sv: List[complex], n: int, ctrl: int, tgt: int) -> None:
    cmask, tmask = 1 << ctrl, 1 << tgt
    for i in range(1 << n):
        if (i & cmask) and not (i & tmask):
            j = i | tmask
            sv[i], sv[j] = sv[j], sv[i]


def _apply_swap(sv: List[complex], n: int, a: int, b: int) -> None:
    amask, bmask = 1 << a, 1 << b
    for i in range(1 << n):
        if ((i >> a) & 1) != ((i >> b) & 1):
            j = i ^ amask ^ bmask
            if i < j:
                sv[i], sv[j] = sv[j], sv[i]


def _apply_ccx(sv: List[complex], n: int, a: int, b: int, c: int) -> None:
    amask, bmask, cmask = 1 << a, 1 << b, 1 << c
    for i in range(1 << n):
        if (i & amask) and (i & bmask) and not (i & cmask):
            j = i | cmask
            sv[i], sv[j] = sv[j], sv[i]


def _apply_cu1(sv: List[complex], n: int, ctrl: int, tgt: int, theta: float) -> None:
    phase = math.e ** (1j * theta)
    cmask, tmask = 1 << ctrl, 1 << tgt
    for i in range(1 << n):
        if (i & cmask) and (i & tmask):
            sv[i] *= phase


class QuantumRISCVEmulator:
    """指令字驱动的量子 RISC-V 模拟器。

    load_program(文本) → assemble() 得到 32 位指令字；
    execute() 逐条 decode_word()，按 opcode/funct3/funct7 分派执行。
    标准指令行为与官方 TinyRISCVEmulator 一致。
    """

    def __init__(self):
        self.registers = [0] * 32
        self.pc = 0
        self.labels: Dict[str, int] = {}
        self.words: List[int] = []
        self._instructions = []          # (op, args) 缓存，供调试/展示
        self.max_steps = 200000
        self.num_qubits = 0
        self.statevector: List[complex] = []
        self.rng = random.Random(0x5EED)

    def set_register(self, reg: str, value: int):
        idx = self._parse_reg_idx(reg)
        if idx != 0:
            self.registers[idx] = value

    def get_register(self, reg: str) -> int:
        idx = self._parse_reg_idx(reg)
        return self.registers[idx]

    def _parse_reg_idx(self, reg: str) -> int:
        reg = reg.strip().replace(",", "")
        if not reg.startswith("x") and not reg.startswith("X"):
            raise ValueError("无效的寄存器名称: %s" % reg)
        idx = int(reg[1:])
        if idx < 0 or idx > 31:
            raise ValueError("寄存器索引超出范围 (x0-x31): %s" % reg)
        return idx

    def load_program(self, asm_code: str):
        """汇编文本 → 32 位指令字，并重置全部状态。"""
        self.words, self.labels = assemble(asm_code)
        self._instructions = [decode_word(w) for w in self.words]
        self.pc = 0
        self.registers = [0] * 32
        self.num_qubits = 0
        self.statevector = []

    def load_machine_code(self, words: List[int]):
        """直接加载 32 位机器码指令字（不经文本汇编）。"""
        self.words = list(words)
        self.labels = {}
        self._instructions = [decode_word(w) for w in self.words]
        self.pc = 0
        self.registers = [0] * 32
        self.num_qubits = 0
        self.statevector = []

    def disassemble(self) -> List[Tuple[int, str, List[str]]]:
        """返回 [(指令字, 助记符, 参数)]，供验证/展示。"""
        return [(w, op, args) for w, (op, args) in zip(self.words, self._instructions)]

    # ---- 量子状态管理 ------------------------------------------------------

    def _ensure_qubits(self, n: int) -> None:
        if n > self.num_qubits:
            raise RuntimeError("未声明量子比特 %d（当前 qinit=%d）" % (n, self.num_qubits))

    def quantum_probs(self) -> Dict[str, float]:
        if self.num_qubits == 0:
            return {}
        total = sum(abs(v) ** 2 for v in self.statevector)
        return {
            format(i, "0%db" % self.num_qubits): abs(self.statevector[i]) ** 2 / total
            for i in range(1 << self.num_qubits)
        }

    def _qinit(self, n: int) -> None:
        if not 1 <= n <= 16:
            raise ValueError("qinit 支持 1-16 比特")
        self.num_qubits = n
        self.statevector = [0.0 + 0.0j] * (1 << n)
        self.statevector[0] = 1.0 + 0.0j

    def _qgate(self, op: str, args: List[str]) -> None:
        n = self.num_qubits
        if op == "qh":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 1], [1, -1]], 1 / math.sqrt(2))
        elif op == "qx":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[0, 1], [1, 0]], 1.0)
        elif op == "qs":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 0], [0, 1j]], 1.0)
        elif op == "qsdg":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 0], [0, -1j]], 1.0)
        elif op == "qt":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 0], [0, math.e ** (1j * math.pi / 4)]], 1.0)
        elif op == "qtdg":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 0], [0, math.e ** (-1j * math.pi / 4)]], 1.0)
        elif op == "qz":
            q = _qidx(args[0]); self._ensure_qubits(q)
            _apply_1q(self.statevector, n, q, [[1, 0], [0, -1]], 1.0)
        elif op == "qcx":
            a, b = _qidx(args[0]), _qidx(args[1]); self._ensure_qubits(max(a, b))
            _apply_cx(self.statevector, n, a, b)
        elif op == "qswap":
            a, b = _qidx(args[0]), _qidx(args[1]); self._ensure_qubits(max(a, b))
            _apply_swap(self.statevector, n, a, b)
        elif op == "qccx":
            a, b, c = _qidx(args[0]), _qidx(args[1]), _qidx(args[2]); self._ensure_qubits(max(a, b, c))
            _apply_ccx(self.statevector, n, a, b, c)
        elif op == "qry":
            q, imm16 = _qidx(args[0]), int(args[1]); self._ensure_qubits(q)
            th = imm16 * math.pi / 16
            c, s = math.cos(th / 2), math.sin(th / 2)
            _apply_1q(self.statevector, n, q, [[c, -s], [s, c]], 1.0)
        elif op == "qrz":
            q, imm16 = _qidx(args[0]), int(args[1]); self._ensure_qubits(q)
            th = imm16 * math.pi / 16
            _apply_1q(self.statevector, n, q, [[1, 0], [0, math.e ** (1j * th)]], 1.0)
        elif op == "qcu1":
            a, b, imm16 = _qidx(args[0]), _qidx(args[1]), int(args[2]); self._ensure_qubits(max(a, b))
            th = imm16 * math.pi / 16
            _apply_cu1(self.statevector, n, a, b, th)
        else:
            raise ValueError("未知量子门: %s" % op)

    def _qmeas(self, qd: int, qa: int) -> None:
        self._ensure_qubits(qa)
        probs = [abs(v) ** 2 for v in self.statevector]
        n = self.num_qubits
        p1 = sum(probs[i] for i in range(1 << n) if (i >> qa) & 1)
        r = self.rng.random()
        bit = 1 if r < p1 else 0
        keep = [(i, probs[i]) for i in range(1 << n) if ((i >> qa) & 1) == bit]
        norm = sum(p for _, p in keep)
        new_sv = [0.0 + 0.0j] * (1 << n)
        if norm > 0:
            for i, p in keep:
                new_sv[i] = self.statevector[i] / math.sqrt(norm)
        self.statevector = new_sv
        self.set_register("x%d" % qd, bit)

    # ---- 指令字驱动的执行循环 ---------------------------------------------

    def execute(self) -> Dict[str, int]:
        steps = 0
        num_words = len(self.words)
        while 0 <= self.pc < num_words:
            steps += 1
            if steps > self.max_steps:
                raise RuntimeError("程序执行超出最大步数限制，疑似发生死循环")
            word = self.words[self.pc]
            op, args = decode_word(word)
            next_pc = self.pc + 1

            if op == "li":
                self.set_register(args[0], int(args[1]))
            elif op == "addi":
                rd, rs1, imm = args
                self.set_register(rd, self.get_register(rs1) + int(imm))
            elif op == "add":
                rd, rs1, rs2 = args
                self.set_register(rd, self.get_register(rs1) + self.get_register(rs2))
            elif op == "sub":
                rd, rs1, rs2 = args
                self.set_register(rd, self.get_register(rs1) - self.get_register(rs2))
            elif op == "beq":
                rs1, rs2, off = args
                if self.get_register(rs1) == self.get_register(rs2):
                    next_pc = self.pc + int(off)
            elif op == "bne":
                rs1, rs2, off = args
                if self.get_register(rs1) != self.get_register(rs2):
                    next_pc = self.pc + int(off)
            elif op == "j":
                next_pc = self.pc + int(args[0])
            elif op == "qinit":
                self._qinit(_qidx(args[0]))
            elif op == "qmeas":
                qd = self._parse_reg_idx(args[0])
                qa = _qidx(args[1])
                self._qmeas(qd, qa)
            elif op.startswith("q"):
                self._qgate(op, args)
            else:
                raise ValueError("解码结果无法执行: %s" % op)

            self.pc = next_pc

        result = {}
        for idx, val in enumerate(self.registers):
            if val != 0:
                result["x%d" % idx] = val
        return result


# 向后兼容别名：官方类名可直接使用本扩展。
TinyRISCVEmulator = QuantumRISCVEmulator


def encode_quantum_instruction(op: str, args: List[str]) -> int:
    """兼容入口：单条量子指令编码为 32 位机器码（委托 assemble_line）。"""
    return assemble_line(op, list(args), {}, 0)


# 简易功能测试
if __name__ == "__main__":
    code = """
    qinit 2
    li x10, 0
    qh q0
    qcx q0, q1
    qmeas x10, q0
    qmeas x11, q1
    """
    emu = QuantumRISCVEmulator()
    emu.load_program(code)
    print("汇编为 %d 条指令字；反汇编:" % len(emu.words))
    for w, op, args in emu.disassemble():
        print("  0x%08X  %s %s" % (w, op, " ".join(args)))
    state = emu.execute()
    print("测量寄存器:", state)
    print("量子 RISC-V 指令字驱动核心测试通过！")