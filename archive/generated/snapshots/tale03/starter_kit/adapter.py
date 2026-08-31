#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple

import os
import tempfile

from datetime import datetime, timezone

SUPPORTED_TARGETS = ("spinq", "originq", "braket")


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""

    if target == "braket":
        new_lines = []
        lines = qasm_str.split("\n")
        for line in lines:
            if line.strip().startswith("OPENQASM"):
                line = line.replace("2.0", "3.0")

            if line.strip().startswith("include"):
                continue

            if "qreg" in line:
                parts = line.split("[")
                number = parts[1].split("]")
                line = f"qubit[{number[0]}] q;"

            if "creg" in line:
                parts = line.split("[")
                number = parts[1].split("]")
                line = f"bit[{number[0]}] c;"

            if line.strip().startswith("cx "):
                line = line.replace("cx", "cnot")

            if line.strip().startswith("measure") and "->" in line:
                parts = line.strip().rstrip(";").split(" -> ")
                line = f"{parts[1]} = {parts[0]};"

            if line.strip().startswith("ccx "):
                line = line.replace("ccx ", "ccnot ")

            if line.strip().startswith("cu1("):
                angle = line.split("(")[1].split(")")[0]
                qubits = line.split(")")[1].strip().rstrip(";")
                qa = qubits.split(",")[0].strip()
                qb = qubits.split(",")[1].strip()

                new_lines.append(f"rz({angle}/2) {qa};")
                new_lines.append(f"cnot {qa}, {qb};")
                new_lines.append(f"rz(-{angle}/2) {qb};")
                new_lines.append(f"cnot {qa}, {qb};")
                new_lines.append(f"rz({angle}/2) {qb};")
                continue

            if line.strip().startswith("sdg "):
                qubit = line.strip().replace("sdg ", "").rstrip(";")
                line = f"rz(-pi/2) {qubit};"

            if line.strip().startswith("s "):
                qubit = line.strip().replace("s ", "").rstrip(";")
                line = f"rz(pi/2) {qubit};"

            if line.strip().startswith("tdg "):
                qubit = line.strip().replace("tdg ", "").rstrip(";")
                line = f"rz(-pi/4) {qubit};"

            if line.strip().startswith("t "):
                qubit = line.strip().replace("t ", "").rstrip(";")
                line = f"rz(pi/4) {qubit};"

            new_lines.append(line)

        result = "\n".join(new_lines)
        return result

    elif target == "spinq":
        new_lines = []
        lines = qasm_str.split("\n")

        for line in lines:
            if line.strip().startswith("cu1("):
                angle = line.split("(")[1].split(")")[0]
                qubits = line.split(")")[1].strip().rstrip(";")
                qa = qubits.split(",")[0].strip()
                qb = qubits.split(",")[1].strip()
                
                new_lines.append(f"u1({angle}/2) {qa};")
                new_lines.append(f"cx {qa}, {qb};")
                new_lines.append(f"u1(-{angle}/2) {qb};")
                new_lines.append(f"cx {qa}, {qb};")
                new_lines.append(f"u1({angle}/2) {qb};")
                continue
            
            new_lines.append(line)
    
        results = "\n".join(new_lines)
        return results

    elif target == "originq":
        new_lines = []
        lines = qasm_str.split("\n")
        for line in lines:
            line = line.replace(";", "")

            if line.strip().startswith("OPENQASM"):
                continue

            if line.strip().startswith("include"):
                continue

            if "qreg" in line:
                parts = line.split("[")
                number = parts[1].split("]")
                line = f"QINIT {number[0]}"

            if "creg" in line:
                parts = line.split("[")
                number = parts[1].split("]")
                line = f"CREG {number[0]}"

            if line.strip().startswith("h "):
                line = line.replace("h ", "H ")

            if line.strip().startswith("cx "):
                line = line.replace("cx ", "CNOT ")

            if line.strip().startswith("measure "):
                line = line.replace("measure ", "MEASURE ")
                line = line.replace(" -> ", ",")

            if line.strip().startswith("x "):
                line = line.replace("x ", "X ")

            if line.strip().startswith("swap "):
                line = line.replace("swap ", "SWAP ")

            if line.strip().startswith("sdg "):
                line = line.replace("sdg ", "SDAG ")

            if line.strip().startswith("s "):
                line = line.replace("s ", "S ")

            if line.strip().startswith("tdg "):
                line = line.replace("tdg ", "TDAG ")

            if line.strip().startswith("t "):
                line = line.replace("t ", "T ")

            if line.strip().startswith("ccx "):
                line = line.replace("ccx ", "TOFFOLI ")

            if "rz(" in line:
                line = line.replace("rz(", "RZ(")

            if "ry(" in line:
                line = line.replace("ry(", "RY(")

            if "cu1(" in line:
                line = line.replace("cu1(", "CU1(")

            new_lines.append(line)

        result = "\n".join(new_lines)   
        return result
        

def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    # Strip // comments (LLM sometimes adds them)
    qasm_str = "\n".join(line.split("//")[0] for line in qasm_str.split("\n"))

    qasm3 = transpile(qasm_str, target) # call transpile() to get QASM 3.0

    gate_lines = [l for l in qasm_str.split('\n') 
              if l.strip() 
              and not l.strip().startswith(('OPENQASM', 'include', 'qreg', 'creg', 'measure', '//'))]
              
    meta = {
        "transpiled_gates": len(gate_lines),
        "depth": len(gate_lines)  # 简单近似，不精确但够用
    }

    if target == "braket":
        from braket.devices import LocalSimulator
        from braket.ir.openqasm import Program

        device = LocalSimulator()
        program = Program(source=qasm3)
        task = device.run(program, shots=shots)

        result = task.result()

        counts = result.measurement_counts

        return {
            "backend": "braket_local_simulator",
            "job_id": "braket-local",
            "shots": shots,
            "counts": dict(counts),
            "bit_order": "little",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": meta
        }

    elif target == "spinq":
        from spinqit import BasicSimulatorConfig, get_basic_simulator, get_compiler

        tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".qasm", delete=False, encoding="utf-8"
            )
        try:
            tmp.write(qasm_str)
            tmp.close()
            compiler = get_compiler("qasm")
            ir = compiler.compile(tmp.name, 0)
        finally:
            os.unlink(tmp.name)

        engine = get_basic_simulator()
        config = BasicSimulatorConfig()
        config.configure_shots(shots)

        result = engine.execute(ir, config)

        counts = result.counts

        return {
            "backend": "spinq_taurus_simulator",
            "job_id": "spinq-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "shots": shots,
            "counts": dict(counts),
            "bit_order": "little",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": meta
        }

    elif target == "originq":
        import pyqpanda as pq

        machine = pq.CPUQVM()
        machine.init_qvm()

        try:
            # 兼容不同版本 pyqpanda 接口
            if hasattr(pq, 'convert_qasm_string_to_qprog'):
                prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
            else:
                prog = pq.convert_qasm_to_qprog(qasm_str, machine)
                # 如果接口只返回 prog，需要从机器获取比特列表
                qreg = machine.get_allocate_qubits()
                creg = machine.get_allocate_cbits()
        except Exception as e:
            raise RuntimeError(f"QASM 转译失败，请检查语法兼容性: {e}")

        # 3. 运行线路
        # 使用 run_with_configuration 进行多次测量采样 (shots)
        result = machine.run_with_configuration(prog, creg, shots)
        
        # 4. 统计结果
        # pyqpanda 返回的 counts 是以十进制或二进制字符串作为 key
        # 我们确保将其标准化为二进制 key，如 "00", "11"
        raw_counts = result
        formatted_counts = {}
        
        # 获取比特总数，以便将十进制格式化为对应长度的二进制串
        num_bits = len(creg)
        for key, val in raw_counts.items():
            trimmed = key[-num_bits:]  
            reversed_key = trimmed[::-1]
            formatted_counts[reversed_key] = val

        # 5. 释放量子虚拟机器资源
        machine.finalize()

        return {
            "backend": "originq_local_simulator",
            "job_id": "originq-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "shots": shots,
            "counts": formatted_counts,
            "bit_order": "little",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta": meta
        }


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""

    from llm_client import chat_completion
    import re

    system_prompt = """You are a quantum computing assistant. You help users by:
    1. Generating valid OpenQASM 2.0 circuits
    2. Fixing broken QASM code  
    3. Recommending quantum backends

    You are 喵子/Qat (use the Chinese or English version of the name depending on the user's language: use 喵子 when the user uses Chinese, Qat when the user uses English), a friendly quantum computing assistant. When replying in Chinese, refer to yourself as 喵子. When replying in English, refer to yourself as Qat. Never use "I" or "an AI assistant".
    IMPORTANT: Always reply in the SAME language the user writes in. If the user writes in English, reply entirely in English. If the user writes in Chinese, reply entirely in Chinese. Never mix languages. English speakers won't understand your Chinese name.
    Keep a warm, approachable tone. Occasionally use a subtle cat metaphor at the end of an explanation, but maximum one per response. Stay professional — cute but not childish.
    Occasionally use cat-related kaomoji, but maximum one per response. Use them at the end of a sentence, never in the middle of technical explanations.

    If the user greets in "hi" or use some casual greeting in English that's used internationally, answer your full answer in Chinses once, then full in English once.

    Rules for generating QASM:
    - Always start with: OPENQASM 2.0;  and  include "qelib1.inc";
    - Declare qreg and creg before using them
    - Only use these 12 gates: h, x, s, sdg, t, tdg, rz(θ), ry(θ), cx, cu1(θ), swap, ccx
    - Always end with measure statements
    - ALWAYS return the complete QASM code in a ```qasm code block
    - If asked to generate a circuit, output ONLY ONE final circuit — do not include alternative or intermediate versions. If your first attempt is wrong, correct it before outputting.

    When writing QASM code, always use lowercase gate names: h, x, y, z, s, t, cx, cz, ccx, swap. Never use uppercase like H, CX, X.
    When you generate QASM code, always remind the user to click the "run"/"运行" (depends on user's language) button below the code block to execute it and see the result.

    Rules for fixing QASM:
    - Fix syntax errors (wrong case, missing semicolons, undeclared registers)
    - Preserve the user's intended circuit purpose
    - Return the corrected complete QASM code

    Backend capabilities (use ONLY this data for backend selection):
    - spinq_taurus_simulator: max 24 qubits, no queue, free, no account needed, local
    - spinq_cloud_qpu: max 8 qubits, queue minutes to hours, free quota, account needed
    - originq_local_simulator: max 30 qubits, no queue, free, no account needed, local
    - originq_wukong: max 72 qubits, queue hours, free quota, account needed
    - braket_local_simulator: max 25 qubits, no queue, free, no account needed, local
    - braket_cloud: max 34 qubits, queue minutes to hours, paid, account needed

    When recommending a backend, return the exact backend identifier from the capability table, such as braket_local_simulator, spinq_cloud, originq_cloud.
    
    Reply in the same language the user uses.

    If the user's question is unrelated to quantum computing, gently guide them back. Reply in the same language they used. 
    For example: "I'm not sure about that, but I can help you run a quantum experiment! Try asking me to generate a Bell state circuit."
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    for attempt in range(3):
        result = chat_completion(messages)
        reply = result["choices"][0]["message"]["content"]

        match = re.search(r"```(?:qasm|openqasm)?\s*\n(.*?)```", reply, re.DOTALL | re.IGNORECASE)
        if not match:
            # Fallback: find QASM code without backticks
            match = re.search(r"(OPENQASM\s+2\.0;.*?(?:measure\s+.*?;))", reply, re.DOTALL | re.IGNORECASE)
            if match:
                # Wrap bare code in backticks so frontend can detect it
                reply = reply.replace(match.group(1), "\n```qasm\n" + match.group(1) + "\n```\n")
        if not match:
            return reply
        qasm_code = match.group(1).strip()

        try:
            transpile(qasm_code, "spinq")  
            return reply  
        except Exception as e:
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": f"QASM error: {e}. Please fix the code. Reply in the same language as my original question."})

    return reply 


# Helper functions for L3
def convert_var(var):
    if var.startswith("r"):
        return var.replace("r", "x")
    elif var.startswith("c["):
        number = int(var.split("[")[1].rstrip("]")) + 10
        return f"x{number}"
    else:
        return var

def translate_assignment(line):
    line = line.strip().rstrip(";")
    left, right = line.split("=")
    left = left.strip()
    right = right.strip()    

    rd = convert_var(left)

    if right.isdigit() or (right.startswith("-") and right[1:].isdigit()):
        return f"li {rd}, {right}"

    elif "+" in right:
        parts = right.split("+")
        a = parts[0].strip()
        b = parts[1].strip()

        a_is_num = a.isdigit() or (a.startswith("-") and a[1:].isdigit())
        b_is_num = b.isdigit() or (b.startswith("-") and b[1:].isdigit())

        if a_is_num and b_is_num:
            return f"li {rd}, {int(a) + int(b)}"
        elif a_is_num:
            return f"addi {rd}, {convert_var(b)}, {a}"
        elif b_is_num:
            return f"addi {rd}, {convert_var(a)}, {b}"
        else:
            return f"add {rd}, {convert_var(a)}, {convert_var(b)}"

    elif "-" in right:
        parts = right.split("-")
        a = parts[0].strip()
        b = parts[1].strip()
        
        a_is_num = a.isdigit() or (a.startswith("-") and a[1:].isdigit())
        b_is_num = b.isdigit() or (b.startswith("-") and b[1:].isdigit())
        
        if a_is_num and b_is_num:
            return f"li {rd}, {int(a) - int(b)}"
        elif b_is_num:
            return f"addi {rd}, {convert_var(a)}, -{b}"
        elif a_is_num:
            raise ValueError(f"Cannot compile: {line}")
        else:
            return f"sub {rd}, {convert_var(a)}, {convert_var(b)}"

def translate_classical(classical_lines):
    output = []
    label_counter = 0
    i = 0

    while i < len(classical_lines):
        line = classical_lines[i].strip()

        if line.startswith("if"):
            condition = line[line.index("(")+1 : line.rindex(")")]

            if "==" in condition:
                left, right = condition.split("==")
                branch = "bne"  # jump if NOT equal
            else:
                left, right = condition.split("!=")
                branch = "beq"  # jump if equal

            left = left.strip()
            right = right.strip()

            end_label = f"END_{label_counter}"

            output.append(f"li x20, {right}")
            branch_line_idx = len(output)
            output.append(f"{branch} {convert_var(left)}, x20, PLACEHOLDER")

            # process "if true" body:
            i += 1
            while i < len(classical_lines):
                inner = classical_lines[i].strip()

                if inner.startswith("}"):
                    break
                output.append(translate_assignment(inner))
                i += 1

            # check for else
            if i < len(classical_lines) and "else" in classical_lines[i]:
                else_label = f"ELSE_{label_counter}"
                output[branch_line_idx] = output[branch_line_idx].replace("PLACEHOLDER", else_label)
                output.append(f"j {end_label}")
                output.append(f"{else_label}:")
                i += 1

                while i < len(classical_lines):
                    inner = classical_lines[i].strip()

                    if inner == "}":
                        break

                    output.append(translate_assignment(inner))
                    i += 1
            else:
                output[branch_line_idx] = output[branch_line_idx].replace("PLACEHOLDER", end_label)

            output.append(f"{end_label}:")
            label_counter += 1
            i += 1

        else:
            output.append(translate_assignment(line))
            i += 1

    return "\n".join(output)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    hybrid_qasm_str = hybrid_qasm_str.replace("{", "{\n")
    hybrid_qasm_str = hybrid_qasm_str.replace("}", "\n}\n")
    hybrid_qasm_str = hybrid_qasm_str.replace(";", ";\n")


    hybrid_qasm_str = hybrid_qasm_str.replace("}\n else", "} else")
    hybrid_qasm_str = hybrid_qasm_str.replace("}\nelse", "} else")

    quantum_ops = []
    classical_lines = []
    inside_classical = False
    brace_count = 0

    for line in hybrid_qasm_str.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("OPENQASM") or stripped.startswith("include") or stripped.startswith("qreg") or stripped.startswith("creg"):
            continue  

        if stripped.startswith("classical"):
            inside_classical = True
            brace_count = 1
            continue

        if inside_classical:
            brace_count += stripped.count("{") - stripped.count("}")
            if brace_count <= 0:
                inside_classical = False
                continue
            classical_lines.append(stripped)
        else:
            if stripped:
                quantum_ops.append(stripped.rstrip(";"))

    riscv_asm = translate_classical(classical_lines)

    return(quantum_ops, riscv_asm)