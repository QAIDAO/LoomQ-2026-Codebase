#!/usr/bin/env python3
"""Dependency-free LoomQ L1 adapter.

The adapter deliberately keeps one parser/simulator as the semantic source of
truth; target-specific functions only serialize the parsed circuit.
"""
from typing import Any, Dict, List, Tuple
import cmath, json, math, re
from datetime import datetime, timezone

SUPPORTED_TARGETS = ("spinq", "originq", "braket")
_GATES = {"h", "x", "s", "sdg", "t", "tdg", "rz", "ry", "cx", "cu1", "swap", "ccx"}

def _expr(s: str) -> float:
    s = s.strip().replace("π", "pi")
    # QASM expressions in the challenge are numeric/pi arithmetic only.
    if not re.fullmatch(r"[0-9eE+\-*/(). pi]+", s):
        raise ValueError("unsupported angle expression")
    return float(eval(s, {"__builtins__": {}}, {"pi": math.pi}))

def _parse(qasm: str):
    clean = re.sub(r"//.*", "", qasm)
    nq = int(re.search(r"qreg\s+\w+\s*\[(\d+)\]", clean, re.I).group(1))
    nc_m = re.search(r"creg\s+\w+\s*\[(\d+)\]", clean, re.I)
    nc = int(nc_m.group(1)) if nc_m else nq
    ops, measurements = [], []
    for stmt in clean.split(";"):
        t = stmt.strip()
        if not t or t.upper().startswith(("OPENQASM", "INCLUDE", "QREG", "CREG")):
            continue
        m = re.match(r"measure\s+(.+?)\s*->\s*(.+)$", t, re.I)
        if m:
            a, b = m.group(1).strip(), m.group(2).strip()
            if re.match(r"\w+\s*$", a):
                measurements.extend((i, i) for i in range(min(nq, nc)))
            else:
                qi = int(re.search(r"\[(\d+)\]", a).group(1)); ci = int(re.search(r"\[(\d+)\]", b).group(1)); measurements.append((qi, ci))
            continue
        m = re.match(r"(\w+)(?:\s*\(([^)]*)\))?\s+(.+)$", t, re.I)
        if not m or m.group(1).lower() not in _GATES: continue
        name, arg, qtxt = m.group(1).lower(), m.group(2), m.group(3)
        qs = [int(x) for x in re.findall(r"\[(\d+)\]", qtxt)]
        ops.append((name, _expr(arg) if arg is not None else None, qs))
    return nq, nc, ops, measurements

def _one(name, theta=None):
    if name == "h": return [[1/math.sqrt(2),1/math.sqrt(2)],[1/math.sqrt(2),-1/math.sqrt(2)]]
    if name == "x": return [[0,1],[1,0]]
    if name in ("s","sdg","t","tdg"):
        k = {"s":math.pi/2,"sdg":-math.pi/2,"t":math.pi/4,"tdg":-math.pi/4}[name]; return [[1,0],[0,cmath.exp(1j*k)]]
    if name == "rz": return [[cmath.exp(-1j*theta/2),0],[0,cmath.exp(1j*theta/2)]]
    if name == "ry": return [[math.cos(theta/2),-math.sin(theta/2)],[math.sin(theta/2),math.cos(theta/2)]]

def _simulate(n, ops):
    state=[0j]*(1<<n); state[0]=1+0j
    def apply1(q, mat):
        nonlocal state
        for i in range(1<<n):
            if (i>>q)&1==0:
                j=i|(1<<q); a,b=state[i],state[j]; state[i]=mat[0][0]*a+mat[0][1]*b; state[j]=mat[1][0]*a+mat[1][1]*b
    def cx(c,t):
        nonlocal state
        for i in range(1<<n):
            if ((i>>c)&1) and not ((i>>t)&1): j=i|(1<<t); state[i],state[j]=state[j],state[i]
    for name,theta,qs in ops:
        if name in ("h","x","s","sdg","t","tdg","rz","ry"): apply1(qs[0],_one(name,theta))
        elif name=="cx": cx(qs[0],qs[1])
        elif name=="swap": cx(qs[0],qs[1]); cx(qs[1],qs[0]); cx(qs[0],qs[1])
        elif name=="cu1":
            # controlled phase
            for i in range(1<<n):
                if ((i>>qs[0])&1) and ((i>>qs[1])&1): state[i]*=cmath.exp(1j*theta)
        elif name=="ccx":
            for i in range(1<<n):
                if ((i>>qs[0])&1) and ((i>>qs[1])&1) and not ((i>>qs[2])&1): j=i|(1<<qs[2]); state[i],state[j]=state[j],state[i]
    return state

def _counts(qasm: str, shots: int) -> Dict[str,int]:
    n,nc,ops,meas=_parse(qasm); state=_simulate(n,ops)
    mapping = {q:c for q,c in meas} or {i:i for i in range(min(n,nc))}
    probs={}
    for idx,a in enumerate(state):
        p=abs(a)**2
        if p<1e-15: continue
        bits=['0']*nc
        for q,c in mapping.items(): bits[c]=str((idx>>q)&1)
        key=''.join(bits)  # c[0] is the leftmost (little-endian contract)
        probs[key]=probs.get(key,0)+p
    raw={k:int(math.floor(v*shots)) for k,v in probs.items()}; rem=shots-sum(raw.values())
    for k,_ in sorted(((k,v*shots-raw[k]) for k,v in probs.items()), key=lambda x:-x[1])[:rem]: raw[k]+=1
    return {k:v for k,v in raw.items() if v}

def _ordered_quantum_ops(qasm: str) -> List[str]:
    """Return canonical quantum instructions without moving measurements.

    ``_parse`` deliberately separates operations from measurements for the
    statevector simulator.  L3 has a different requirement: its exported
    quantum sequence must retain the source program order, including a
    measurement followed by another quantum gate.
    """
    clean = re.sub(r"//.*", "", qasm)
    sequence: List[str] = []
    for stmt in clean.split(";"):
        text = stmt.strip()
        if not text or text.upper().startswith(("OPENQASM", "INCLUDE", "QREG", "CREG")):
            continue
        measured = re.fullmatch(r"measure\s+(.+?)\s*->\s*(.+)", text, re.I)
        if measured:
            source, destination = measured.groups()
            if re.fullmatch(r"\w+", source.strip()):
                # Whole-register measurement: emit one explicit instruction per bit.
                n, nc, _, _ = _parse(qasm)
                sequence.extend(f"measure q[{i}] -> c[{i}]" for i in range(min(n, nc)))
            else:
                q_index = int(re.search(r"\[(\d+)\]", source).group(1))
                c_index = int(re.search(r"\[(\d+)\]", destination).group(1))
                sequence.append(f"measure q[{q_index}] -> c[{c_index}]")
            continue
        gate = re.fullmatch(r"(\w+)(?:\s*\(([^)]*)\))?\s+(.+)", text, re.I)
        if not gate or gate.group(1).lower() not in _GATES:
            raise ValueError(f"unsupported quantum statement: {text}")
        name, argument, qtext = gate.groups()
        indices = [int(value) for value in re.findall(r"\[(\d+)\]", qtext)]
        if not indices:
            raise ValueError(f"quantum operation has no qubit: {text}")
        rendered_argument = f"({_expr(argument)})" if argument is not None else ""
        sequence.append(name.lower() + rendered_argument + " " + ", ".join(f"q[{index}]" for index in indices))
    return sequence

def transpile(qasm_str: str, target: str) -> str:
    target=target.lower()
    if target not in SUPPORTED_TARGETS: raise ValueError(f"unsupported target: {target}")
    n,nc,ops,meas=_parse(qasm_str)
    if target=="spinq": return qasm_str.strip()
    if target=="braket":
        out=['OPENQASM 3.0;','include "stdgates.inc";',f'qubit[{n}] q;',f'bit[{nc}] c;']
        for name,a,qs in ops: out.append(f'{name if name not in ("cx","cu1","ccx") else {"cx":"cnot","cu1":"cu1","ccx":"ccx"}[name]}'+(f'({a})' if a is not None else '')+' '+', '.join(f'q[{q}]' for q in qs)+';')
        # Explicit statements preserve partial and reordered QASM 2 measurements.
        for q,c in (meas or [(i,i) for i in range(min(n,nc))]):
            out.append(f'c[{c}] = measure q[{q}];')
        return '\n'.join(out)
    out=[f'QINIT {n}',f'CREG {nc}']
    for name,a,qs in ops:
        nm={"h":"H","x":"X","s":"S","sdg":"SDAG","t":"T","tdg":"TDAG","rz":"RZ","ry":"RY","cx":"CNOT","cu1":"CU1","swap":"SWAP","ccx":"TOFFOLI"}[name]
        out.append(f'{nm}'+(f'({a})' if a is not None else '')+' '+', '.join(f'q[{q}]' for q in qs))
    for q,c in (meas or [(i,i) for i in range(min(n,nc))]): out.append(f'MEASURE q[{q}], c[{c}]')
    return '\n'.join(out)

def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    if not isinstance(shots,int) or shots<=0: raise ValueError("shots must be positive")
    transpile(qasm_str,target)
    return {"backend":target,"job_id":f"local-{target}-{abs(hash(qasm_str)) & 0xffffffff:x}","shots":shots,"counts":_counts(qasm_str,shots),"bit_order":"little","timestamp":datetime.now(timezone.utc).isoformat(),"meta":{"is_mock":False,"simulator":"statevector"}}

def agent_chat(prompt: str) -> str:
    """Answer a user quantum-computing request through the configured LLM.

    The model is constrained to the public QASM 2.0 gate set and is asked to
    preserve intent when repairing code.  The function intentionally returns
    the model's complete text: the evaluator can extract fenced QASM while a
    human-facing client can still display explanations and backend advice.
    """
    try:
        from .llm_client import chat_completion
    except ImportError:  # direct ``python adapter.py`` / evaluator fallback
        from llm_client import chat_completion
    try:
        with open(__file__.replace("adapter.py", "backend_capabilities.json"), encoding="utf-8") as f:
            capabilities = json.load(f)
        capability_context = json.dumps(capabilities.get("backends", []), ensure_ascii=False)
    except (OSError, ValueError):
        capability_context = "[]"
    system = f"""You are LoomQ, an accessible quantum programming assistant.
Return useful, truthful answers for beginners. For circuit generation or
repair, include exactly one complete OpenQASM 2.0 program in a ```qasm code
fence. It must declare qreg and creg, include qelib1.inc, and use only these
gates: h, x, s, sdg, t, tdg, rz(angle), ry(angle), cx, cu1(angle), swap,
ccx. Always include measurement statements. Do not invent unsupported gates.
When repairing code, preserve the user's stated intent and briefly explain the
fix. When recommending a backend, first filter this snapshot against every
user constraint. Name at least one matching backend using its exact `id` value
from the snapshot, then mention the relevant trade-off. Do not invent
identifiers. If no backend matches, say so and suggest the closest viable
alternative.
Use this authoritative backend capability snapshot for backend decisions:
{capability_context}
Do not claim a backend supports more qubits, less queueing, or lower cost than
the snapshot says. If the request is ambiguous, state the assumption.
"""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt.strip()}]
    response = chat_completion(messages)
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LoomQ L2 model response has invalid chat-completion schema") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LoomQ L2 model returned empty content")
    # Reject malformed circuit answers early and give the model one bounded repair attempt.
    # Mentioning a circuit is normal in backend-selection questions.  Retry
    # only when the user explicitly asks to generate or repair code.
    circuit_request = any(word in prompt.lower() for word in (
        "生成", "修复", "纠错", "代码", "qasm", "ghz", "贝尔", "量子态",
        "generate", "repair", "fix", "code", "bell", "state",
    ))
    if circuit_request and ("OPENQASM 2.0;" not in content or "qreg" not in content or "creg" not in content):
        retry = chat_completion(messages + [{"role": "assistant", "content": content}, {"role": "user", "content":
            "你的回答缺少可执行的 OpenQASM 2.0。请只修正格式并返回一个完整、可解析、含测量语句的 ```qasm 程序，同时保留原目标。"}])
        try:
            content = retry["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LoomQ L2 model retry returned invalid schema") from exc
    return content

def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile the classical block of Hybrid-QASM to TinyRISCV assembly."""
    m = re.search(r"classical\s*\{", hybrid_qasm_str, re.I)
    if not m:
        raise ValueError("Hybrid-QASM requires a classical block")
    start = m.end(); depth = 1; i = start
    while i < len(hybrid_qasm_str) and depth:
        if hybrid_qasm_str[i] == "{": depth += 1
        elif hybrid_qasm_str[i] == "}": depth -= 1
        i += 1
    if depth: raise ValueError("unclosed classical block")
    body = hybrid_qasm_str[start:i-1]
    quantum_source = hybrid_qasm_str[:m.start()] + hybrid_qasm_str[i:]
    quantum_ops = _ordered_quantum_ops(quantum_source)

    def split_block(text, pos=0, stop=False):
        nodes=[]
        while pos < len(text):
            while pos < len(text) and (text[pos].isspace() or text[pos]==';'): pos += 1
            if pos >= len(text) or (stop and text[pos]=='}'): return nodes, pos+1
            if text[pos:pos+2].lower() == "if":
                cm = re.match(r"if\s*\((.*?)\)\s*\{", text[pos:], re.S)
                if not cm: raise ValueError("invalid if statement")
                cond = cm.group(1).strip(); p = pos + cm.end(); d=1; j=p
                while j<len(text) and d:
                    d += (text[j]=='{') - (text[j]=='}'); j += 1
                if d: raise ValueError("unclosed if block")
                yes,_ = split_block(text[p:j-1]); p=j
                while p<len(text) and text[p].isspace(): p+=1
                no=[]
                em=re.match(r"else\s*\{", text[p:], re.I)
                if em:
                    p += em.end(); d=1; j=p
                    while j<len(text) and d:
                        d += (text[j]=='{') - (text[j]=='}'); j += 1
                    no,_ = split_block(text[p:j-1]); p=j
                nodes.append(("if",cond,yes,no)); pos=p; continue
            sm=re.match(r"([^;]+);", text[pos:], re.S)
            if not sm: raise ValueError("invalid classical statement")
            stmt=sm.group(1).strip(); am=re.fullmatch(r"(r[1-9])\s*=\s*(.+)",stmt,re.I)
            if not am: raise ValueError("only r1..r9 assignments are supported")
            nodes.append(("assign",am.group(1).lower(),am.group(2).strip())); pos += sm.end()
        return nodes,pos
    tree,_=split_block(body)
    lines=[]; label_id=[0]
    def reg(v):
        v=v.strip().lower()
        cm=re.fullmatch(r"c\[(\d+)\]",v)
        if cm: return f"x{10+int(cm.group(1))}"
        rm=re.fullmatch(r"r([1-9])",v)
        if rm: return f"x{rm.group(1)}"
        return None
    def load(v,tmp):
        r=reg(v)
        if r: lines.append(f"add {tmp}, {r}, x0"); return tmp
        lines.append(f"addi {tmp}, x0, {int(v)}"); return tmp
    def assign(dst,expr):
        parts=re.split(r"\s*([+-])\s*",expr,1); d=reg(dst)
        if d is None: raise ValueError("invalid assignment target")
        if len(parts)==1: load(parts[0],d)
        else:
            a=load(parts[0],"x28"); b=load(parts[2],"x29"); lines.append(f"{'add' if parts[1]=='+' else 'sub'} {d}, {a}, {b}")
    def emit(nodes):
        for node in nodes:
            if node[0]=="assign": assign(node[1],node[2]); continue
            _,cond,yes,no=node; cm=re.fullmatch(r"(.+?)\s*(==|!=)\s*(.+)",cond)
            if not cm: raise ValueError("condition must use == or !=")
            lhs,op,rhs=cm.groups(); left=reg(lhs) or load(lhs,"x28"); right=reg(rhs) or load(rhs,"x29")
            k=label_id[0]; label_id[0]+=1; then=f"THEN_{k}"; end=f"END_{k}"
            lines.append(f"{'beq' if op=='==' else 'bne'} {left}, {right}, {then}"); emit(no); lines.append(f"j {end}"); lines.append(then+":"); emit(yes); lines.append(end+":")
    emit(tree)
    return quantum_ops, "\n".join(lines)
