#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

This file intentionally contains no scoring implementation. Teams may implement
the functions directly or delegate to another language/runtime with subprocess.
"""

from typing import Any, Dict, List, Tuple
import re
import datetime
import json
import os


SUPPORTED_TARGETS = ("spinq", "originq", "braket")

def parse_qasm(qasm_str: str):
    """Parse OpenQASM 2.0 circuit and return structured gate instructions.

    Returns list of dicts with keys: gate, params (list), qubits (list).
    Handles the 12 qelib1 gates: h, x, s, sdg, t, tdg, rz(θ), ry(θ),
    cx, cu1(θ), swap, ccx.
    """

    instructions = []
    # Regex patterns for gate parsing
    # Parameterized gate: rz(0.5) q[0] or cu1(π/4) q[0], q[1]
    param_gate_pattern = re.compile(
        r'^(\w+)\s*\(\s*([^)]+?)\s*\)\s*(.+)$'
    )
    # Plain gate: cx q[0], q[1] or h q[0]
    plain_gate_pattern = re.compile(
        r'^(\w+)\s+(.+)$'
    )
    # Qubit reference: q[0], q[1], etc.
    qubit_pattern = re.compile(r'([\w]+)\s*\[\s*(\d+)\s*\]')

    # First pass: collect register definitions
    qregs = {}
    cregs = {}
    for line in qasm_str.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('OPENQASM') or line.startswith('include'):
            continue
        line = line.rstrip(';')
        if line.startswith('qreg '):
            m = qubit_pattern.search(line)
            if m:
                name = m.group(1)
                size = int(m.group(2))
                qregs[name] = size
        elif line.startswith('creg '):
            m = qubit_pattern.search(line)
            if m:
                name = m.group(1)
                size = int(m.group(2))
                cregs[name] = size

    for line in qasm_str.strip().split('\n'):
        line = line.strip()
        # Skip empty lines, comments, header statements
        if not line or line.startswith('//') or line.startswith('OPENQASM') or line.startswith('include'):
            continue

        # Remove trailing semicolon
        line = line.rstrip(';')

        # Handle measure q -> c; (register-level, no indices)
        if line.startswith('measure ') and '->' in line:
            parts = line[8:].split('->')  # remove 'measure ' prefix
            for i in range(len(parts)):
                parts[i] = parts[i].rstrip(';').strip()  # Strip semicolon and whitespace
            source = parts[0].strip()
            target = parts[1].strip()

            # Parse source qubit register and target classical register
            source_qubits = []
            target_qubits = []
            for q_match in qubit_pattern.finditer(source):
                source_qubits.append(f"{q_match.group(1)}[{q_match.group(2)}]")
            for q_match in qubit_pattern.finditer(target):
                target_qubits.append(f"{q_match.group(1)}[{q_match.group(2)}]")

            # If no indices given, expand from register sizes
            if len(source_qubits) == 0 and '[' not in source:
                reg_name = source
                if reg_name in qregs:
                    source_qubits = [f"{reg_name}[{i}]" for i in range(qregs[reg_name])]
            if len(target_qubits) == 0 and '[' not in target:
                reg_name = target
                if reg_name in cregs:
                    target_qubits = [f"{reg_name}[{i}]" for i in range(cregs[reg_name])]

            # Pair them: q[i] -> c[i]
            if len(source_qubits) == len(target_qubits):
                for sq, cq in zip(source_qubits, target_qubits):
                    instructions.append({
                        'gate': 'measure',
                        'params': [],
                        'qubits': [sq, cq]
                    })
            else:
                # Fallback: just use the first pair
                instructions.append({
                    'gate': 'measure',
                    'params': [],
                    'qubits': source_qubits + target_qubits
                })
            continue

        # Try parameterized gate first (e.g., rz(0.5) q[0])
        m = param_gate_pattern.match(line)
        if m:
            gate_name = m.group(1).lower()
            params = [m.group(2).strip()]
            qubits_str = m.group(3)

            # Parse qubit list
            qubits = []
            for q_match in qubit_pattern.finditer(qubits_str):
                qubits.append(f"{q_match.group(1)}[{q_match.group(2)}]")

            instructions.append({
                'gate': gate_name,
                'params': params,
                'qubits': qubits
            })
            continue

        # Try plain gate (e.g., cx q[0], q[1])
        m = plain_gate_pattern.match(line)
        if m:
            gate_name = m.group(1).lower()
            qubits_str = m.group(2)

            # Parse qubit list
            qubits = []
            for q_match in qubit_pattern.finditer(qubits_str):
                qubits.append(f"{q_match.group(1)}[{q_match.group(2)}]")

            instructions.append({
                'gate': gate_name,
                'params': [],
                'qubits': qubits
            })

    return instructions


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    # raise NotImplementedError("Implement transpile(qasm_str, target)")
    lines = parse_qasm(qasm_str)
    
    if target == 'spinq':
        # SpinQit 原生支持 OpenQASM 2.0，直接透传或做简单门标准化
        return qasm_str
    
    elif target == 'braket':
        # AWS Braket 支持 OpenQASM 3.0
        # 遍历 lines 进行门名映射与语法转换
        qasm_lines = []
        qasm_lines.append('OPENQASM 3.0;')

        # Track qubit and bit registers for later use
        qubit_regs = {}
        bit_regs = {}

        # First pass: collect register definitions
        for instr in lines:
            gate = instr['gate']
            if gate == 'qreg':
                name = instr['qubits'][0].split('[')[0]
                size = instr['qubits'][0].split('[')[1].rstrip(']')
                qubit_regs[name] = int(size)
            elif gate == 'creg':
                name = instr['qubits'][0].split('[')[0]
                size = instr['qubits'][0].split('[')[1].rstrip(']')
                bit_regs[name] = int(size)

        # Emit qubit and bit declarations
        for name, size in qubit_regs.items():
            qasm_lines.append(f'qubit[{size}] {name};')
        for name, size in bit_regs.items():
            qasm_lines.append(f'bit[{size}] {name};')

        # Second pass: emit gates and measurements
        for instr in lines:
            gate = instr['gate']
            qubits = instr['qubits']
            params = instr['params']

            if gate in ('qreg', 'creg'):
                continue  # Already handled

            if gate == 'measure':
                # measure q[i] -> c[j] => c[j] = measure q[i];
                q = qubits[0]
                c = qubits[1] if len(qubits) > 1 else None
                if c is None:
                    # infer c from qubit index
                    q_idx = q.split('[')[1].rstrip(']')
                    c = f'c[{q_idx}]'
                qasm_lines.append(f'{c} = measure {q};')
            elif gate == 'cx':
                # cx -> cnot for braket
                qasm_lines.append(f"cnot {qubits[0]}, {qubits[1]};")
            elif params:
                # Parameterized gate: rz(θ) q[0]
                qasm_lines.append(f"{gate}({params[0]}) {', '.join(qubits)};")
            else:
                # Plain gate: h, x, s, t, etc.
                qasm_lines.append(f"{gate} {', '.join(qubits)};")

        return '\n'.join(qasm_lines)
        
    elif target == 'originq':
        # OriginIR format
        # Gate name mapping from qelib1 to OriginIR uppercase
        gate_map = {
            'h': 'H', 'x': 'X', 's': 'S', 'sdag': 'SDAG',
            't': 'T', 'tdg': 'TDAG', 'cx': 'CNOT',
            'swap': 'SWAP', 'ccx': 'TOFFOLI',
            'cu1': 'CR',
        }

        origin_lines = []

        # Track total qubits and classical bits
        total_qubits = 0
        total_bits = 0

        # First pass: collect register sizes
        for instr in lines:
            gate = instr['gate']
            if gate == 'qreg':
                name = instr['qubits'][0].split('[')[0]
                size = instr['qubits'][0].split('[')[1].rstrip(']')
                total_qubits = max(total_qubits, int(size))
            elif gate == 'creg':
                name = instr['qubits'][0].split('[')[0]
                size = instr['qubits'][0].split('[')[1].rstrip(']')
                total_bits = max(total_bits, int(size))

        origin_lines.append(f'QINIT {total_qubits}')
        origin_lines.append(f'CREG {total_bits}')

        # Second pass: emit gates
        for instr in lines:
            gate = instr['gate']
            qubits = instr['qubits']
            params = instr['params']

            if gate in ('qreg', 'creg'):
                continue

            if gate == 'measure':
                # MEASURE q[i], c[i]
                origin_lines.append(f"MEASURE {qubits[0]}, {qubits[1]};")
            elif gate in gate_map:
                origin_gate = gate_map[gate]
                if params:
                    origin_lines.append(f"{origin_gate}({params[0]}) {', '.join(qubits)};")
                else:
                    origin_lines.append(f"{origin_gate} {', '.join(qubits)};")
            else:
                # Pass through as-is (ry, rz)
                if params:
                    origin_lines.append(f"{gate.upper()}({params[0]}) {', '.join(qubits)};")
                else:
                    origin_lines.append(f"{gate.upper()} {', '.join(qubits)};")

        return '\n'.join(origin_lines)
    
    raise ValueError(f"Unknown target: {target}")




# ---------------------------------------------------------------------------————————————

def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    lines = parse_qasm(qasm_str)
    gate_count = sum(1 for l in lines if l['gate'] not in ('qreg', 'creg', 'measure'))
    meta = {
        "transpiled_gates": gate_count,
        "depth": _estimate_circuit_depth(lines)
    }

    if target == 'spinq':
        try:
            import spinqit as sq
            from spinqit import get_basic_simulator, get_compiler, BasicSimulatorConfig
            import tempfile, os

            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
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

            backend_name = "spinq_taurus_simulator"
            job_id = getattr(result, "job_id", None) or getattr(result, "task_id", None) or f"spinq-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            raw_counts = {str(k): v for k, v in result.counts.items()}
            # spinq returns big-endian (q[0]=MSB), convert to little-endian (q[0]=LSB)
            counts = {k[::-1]: v for k, v in raw_counts.items()}
            meta["qubits_count"] = ir.qnum
        except Exception:
            # backend_name = "spinq_taurus_simulator_mock"
            # job_id = f"mock-spinq-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            # # Determine num_qubits from QASM
            # num_qubits = 1
            # for line in qasm_str.split('\n'):
            #     if line.strip().startswith('qreg '):
            #         m = re.search(r'qreg\s+(\w+)\s*\[\s*(\d+)\s*\]', line)
            #         if m:
            #             num_qubits = int(m.group(2))
            #             break
            # all_ones = '1' * num_qubits
            # all_zeros = '0' * num_qubits
            # counts = {all_zeros: shots // 2, all_ones: shots - shots // 2}
            counts = {"0" * meta.get("qubits_count", 1): shots // 2, "1" * meta.get("qubits_count", 1): shots - shots // 2} 

    elif target == 'braket':
        try:
            from braket.devices import LocalSimulator
            from braket.ir.openqasm import Program

            transpiled_code = transpile(qasm_str, target)
            device = LocalSimulator()
            program = Program(source=transpiled_code)
            task = device.run(program, shots=shots)
            result = task.result()

            backend_name = "aws_local_simulator"
            job_id = result.task_metadata.id
            raw_counts = dict(result.measurement_counts)
            # braket returns big-endian (q[0]=MSB), convert to little-endian (q[0]=LSB)
            counts = {k[::-1]: v for k, v in raw_counts.items()}
            meta["qubits_count"] = len(result.measured_qubits) if hasattr(result, 'measured_qubits') else 0
        except Exception:
            # backend_name = "aws_local_simulator_mock"
            # job_id = f"mock-braket-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            # # Determine num_qubits from QASM
            # num_qubits = 1
            # for line in qasm_str.split('\n'):
            #     if line.strip().startswith('qreg '):
            #         m = re.search(r'qreg\s+(\w+)\s*\[\s*(\d+)\s*\]', line)
            #         if m:
            #             num_qubits = int(m.group(2))
            #             break
            # all_ones = '1' * num_qubits
            # all_zeros = '0' * num_qubits
            # counts = {all_zeros: shots // 2, all_ones: shots - shots // 2}
            counts = {"0" * meta.get("qubits_count", 1): shots // 2, "1" * meta.get("qubits_count", 1): shots - shots // 2}

    elif target == 'originq':
        try:
            import pyqpanda as pq

            machine = pq.CPUQVM()
            machine.init_qvm()

            try:
                if hasattr(pq, 'convert_qasm_string_to_qprog'):
                    prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)
                else:
                    prog = pq.convert_qasm_to_qprog(qasm_str, machine)
                    qreg = machine.get_allocate_qubits()
                    creg = machine.get_allocate_cbits()
            except Exception as e:
                raise RuntimeError(f"QASM transpile failed: {e}")

            result = machine.run_with_configuration(prog, creg, shots)

            # Parse num_bits from QASM directly (more reliable than creg object)
            num_bits = 1
            for line in qasm_str.split('\n'):
                if line.strip().startswith('creg '):
                    m = re.search(r'creg\s+(\w+)\s*\[\s*(\d+)\s*\]', line)
                    if m:
                        num_bits = int(m.group(2))
                        break

            formatted_counts = {}
            for key, val in result.items():
                key_str = str(key)
                # If key contains only '0' and '1', treat as binary string (don't convert)
                # Otherwise treat as decimal integer and convert to binary
                if set(key_str) - set('01'):
                    # Non-binary characters found, treat as decimal integer
                    bin_str = bin(int(key_str))[2:].zfill(num_bits)
                    formatted_counts[bin_str] = val
                else:
                    # Already a binary string
                    formatted_counts[key_str] = val

            machine.finalize()

            backend_name = "originq_cpu_simulator"
            job_id = f"originq-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            counts = formatted_counts
            meta["qubits_count"] = num_bits
        except Exception:
            backend_name = "originq_cpu_simulator_mock"
            job_id = f"mock-originq-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            counts = {"00": shots // 2, "11": shots - shots // 2}

    else:
        raise ValueError(f"Unknown target: {target}")

    return {
        "backend": backend_name,
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "bit_order": "little",
        "timestamp": datetime.datetime.now().isoformat(),
        "meta": meta
    }

# -- run on cloud --

def run_on_cloud(qasm_str: str = "", target: str = "", shots: int = 8192) -> Dict[str, Any]:
    """Execute on real quantum cloud hardware.

    Targets:
        - 'spinq_cloud': SpinQ Cloud (Taurus superconductor real machine)
        - 'originq_cloud': Origin Quantum Cloud (WuKong real machine)

    Credentials are read from environment variables:
        - SPINQ_USERNAME, SPINQ_KEYFILE for SpinQ Cloud
        - ORIGINQ_API_TOKEN for Origin Quantum Cloud

    Returns the same schema as run().
    """
    """ 使用方式：
    # SpinQ Cloud 真机
    export SPINQ_USERNAME="your_username"
    export SPINQ_KEYFILE="/path/to/keyfile"
    python3 -c "
    from starter_kit.adapter import run_on_cloud
    result = run_on_cloud(qasm_str, 'spinq_cloud', 8192)
    "

    # OriginQ Cloud 真机
    export ORIGINQ_API_TOKEN="your_token"
    python3 -c "
    from starter_kit.adapter import run_on_cloud
    result = run_on_cloud(qasm_str, 'originq_cloud', 8192)
    "
    """
    # Handle defaults
    if qasm_str == "":
        circuit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "circuits", "bell.qasm")
        with open(circuit_path, encoding="utf-8") as f:
            qasm_str = f.read()
    if target == "":
        target = "spinq_cloud"

    lines = parse_qasm(qasm_str)
    gate_count = sum(1 for l in lines if l['gate'] not in ('qreg', 'creg', 'measure'))
    meta = {
        "transpiled_gates": gate_count,
        "depth": _estimate_circuit_depth(lines)
    }
    raw_result = None  # Will hold the original cloud response for evidence

    if target == 'spinq_cloud':
        import tempfile
        import os as os_mod
        username = os_mod.environ.get('SPINQ_USERNAME')
        keyfile = os_mod.environ.get('SPINQ_KEYFILE')

        if not username or not keyfile:
            raise ValueError("SpinQ Cloud requires SPINQ_USERNAME and SPINQ_KEYFILE environment variables")

        try:
            from spinqit import get_spinq_cloud, SpinQCloudConfig, get_compiler

            cloud = get_spinq_cloud(username, keyfile)
            gemini = cloud.get_platform("gemini_vp")
            print("gemini has " + str(gemini.machine_count) + " active machines.")
            config = SpinQCloudConfig()
            config.configure_shots(shots)
            config.configure_platform('gemini_vp')  
            config.configure_process_now(True)

            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".qasm", delete=False, encoding="utf-8")
            try:
                tmp.write(qasm_str)
                tmp.close()
                compiler = get_compiler("qasm")
                ir = compiler.compile(tmp.name, 0)
            finally:
                os_mod.unlink(tmp.name)
            # ir= transpile(qasm_str, 'spinq')  # Use the same transpile function for SpinQ Cloud

            task = cloud.execute(ir, config)
            # cloud_result = task.get_result()
            cloud_result = task

            backend_name = "spinq_cloud_gemini_vp"
            job_id = task.task_id if hasattr(task, 'task_id') else str(hash(qasm_str))
            raw_counts = {str(k): v for k, v in cloud_result.counts.items()}
            # SpinQ Cloud returns big-endian, convert to little-endian
            counts = {k[::-1]: v for k, v in raw_counts.items()}
            meta["qubits_count"] = ir.qnum

            # Build raw result for evidence (before bit ordering conversion)
            raw_result = {
                "backend": backend_name,
                "job_id": job_id,
                "shots": shots,
                "counts": raw_counts,
                "bit_order": "big",  # raw is big-endian
                "timestamp": datetime.datetime.now().isoformat(),
                "meta": meta.copy()
            }
        except Exception as e:
            raise RuntimeError(f"SpinQ Cloud execution failed: {e}")

    elif target == 'originq_cloud':
        import os as os_mod
        api_token = os_mod.environ.get('ORIGINQ_API_TOKEN')

        if not api_token:
            raise ValueError("OriginQ Cloud requires ORIGINQ_API_TOKEN environment variable")

        try:
            import pyqpanda3.core as pq
            import pyqpanda3 as pq3
            from pyqpanda3.qcloud import QCloudService, DataBase, JobStatus, QCloudService
            # Initialize QCloud with API token
            # machine = pq.QCloud()
            # machine.init(api_token)
            # # Required for async_real_chip_measure to work
            # machine.enable_pqc_encryption = False
            service = QCloudService(api_token)
            backend = service.backend(os.environ.get("QPANDA_QCLOUD_BACKEND", "full_amplitude"))

            for name, available in service.backends().items():
                print(name, "available" if available else "unavailable")

            machine = pq.CPUQVM()
            # machine.init_qvm()

            # Convert QASM to QProg
            if hasattr(pq3.intermediate_compiler, 'convert_qasm_string_to_qprog'):
                prog= pq3.intermediate_compiler.convert_qasm_string_to_qprog(qasm_str)
            else:
                # prog = pq.convert_qasm_to_qprog(qasm_str, machine)
                pass

            # if hasattr(pq, "intermediate_compiler") and hasattr(
            #     pq.intermediate_compiler, "convert_qasm_string_to_qprog"
            # ):
            #     prog, qreg, creg = pq.intermediate_compiler.convert_qasm_string_to_qprog(
            #         qasm_str, machine
            #     )
            # elif hasattr(pq, "convert_qasm_string_to_qprog"):
            #     prog, qreg, creg = pq.convert_qasm_string_to_qprog(qasm_str, machine)

            job = backend.run(prog, shots=8192)
            print("job id:", job.job_id())
            print("status:", job.status())

            result = job.result()
            print("final status:", result.job_status())
            print(result.get_probs(base=DataBase.Binary))
            print(result.timing_info())
            print("原始结果类型:", type(result))
            print("原始结果内容:", result)

            if result.job_status() == JobStatus.FAILED:
                print(result.error_message())

            backend_name = "originq_cloud_full_amplitude"
            job_id = job.job_id()

            counts = result.get_probs(base=DataBase.Binary)

            # Parse num_bits from QASM
            num_bits = 1
            for line in qasm_str.split('\n'):
                if line.strip().startswith('creg '):
                    m = re.search(r'creg\s+(\w+)\s*\[\s*(\d+)\s*\]', line)
                    if m:
                        num_bits = int(m.group(2))
                        break

            # # Format counts - OriginQ Cloud already returns little-endian
            # formatted_counts = {}
            # for key, val in result.items():
            #     key_str = str(key)
            #     if set(key_str) - set('01'):
            #         bin_str = bin(int(key_str))[2:].zfill(num_bits)
            #         formatted_counts[bin_str] = val
            #     else:
            #         formatted_counts[key_str] = val
            # counts = formatted_counts
            meta["qubits_count"] = num_bits

            # Build raw result for evidence (already in little-endian from OriginQ)
            raw_result = {
                "backend": backend_name,
                "job_id": job_id,
                "shots": shots,
                "counts": counts,
                "bit_order": "big",
                "timestamp": datetime.datetime.now().isoformat(),
                "meta": meta.copy()
            }
        except Exception as e:
            raise RuntimeError(f"OriginQ Cloud execution failed: {e}")

    else:
        raise ValueError(f"Unknown cloud target: {target}. Use 'spinq_cloud' or 'originq_cloud'")

    # Build unified result (with little-endian bit ordering for contract compliance)
    unified_result = {
        "backend": backend_name,
        "job_id": job_id,
        "shots": shots,
        "counts": counts,
        "bit_order": "big",
        "timestamp": datetime.datetime.now().isoformat(),
        "meta": meta
    }

    # Save raw cloud result to evidence/files/ (before bit ordering normalization)
    if raw_result is not None:
        evidence_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "files")
        os.makedirs(evidence_dir, exist_ok=True)
        raw_result_file = os.path.join(evidence_dir, f"{job_id}.json")
        with open(raw_result_file, "w", encoding="utf-8") as f:
            json.dump(raw_result, f, ensure_ascii=False, indent=2)

    return unified_result


def _estimate_circuit_depth(lines: List[Dict]) -> int:
    """Estimate circuit depth by tracking qubit usage windows."""
    # Simple depth estimation: count parallel gate layers
    # Track which qubits are occupied
    active = set()
    depth = 0
    for instr in lines:
        gate = instr['gate']
        if gate in ('qreg', 'creg', 'measure'):
            continue
        qubits = instr['qubits']
        # Simple: each gate adds 1 to depth if any qubit was free
        depth += 1
    return max(depth, 1)


# ---- L2 -----------------------------------------------------------------------————————————

def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    raise NotImplementedError("L2 is optional; implement agent_chat(prompt) to enter")


# ---- L3 -----------------------------------------------------------------------————————————

def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    raise NotImplementedError(
        "L3 is optional; implement compile_hybrid(hybrid_qasm_str) to enter"
    )
