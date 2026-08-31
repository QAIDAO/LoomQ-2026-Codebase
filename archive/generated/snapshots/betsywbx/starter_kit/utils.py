from typing import Any, Dict, List, Tuple
import re

def checker_reg(qasm_str: str) -> str:
    """
    General checker for reg: perform defensive check and add declaration of 
    qreg and creg if missing using the maximum indexing. 
    """
    res = qasm_str.strip()

    # 1. analyse declared qreg / creg names
    declared_qregs = set(re.findall(r"\bqreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\d+\];", res))
    declared_cregs = set(re.findall(r"\bcreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[\d+\];", res))

    # 2. scan used reg from quantum gate
    used_q_matches = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\[(\d+)\]", res)

    # filter key words and collect undeclared creg / qreg
    undeclared_q = {}
    for name, idx in used_q_matches:
        if name not in declared_qregs and name not in declared_cregs and name not in ["creg", "qreg", "measure"]:
            idx = int(idx)
            undeclared_q[name] = max(undeclared_q.get(name, -1), idx)

    # 3. add undeclared qreg
    if undeclared_q:
        q_decls = "\n".join([f"qreg {reg_name}[{max_idx + 1}];" for reg_name, max_idx in undeclared_q.items()])
        # insert after "include"; if no "inclide", insert after "OPENQASM 2.0;"
        if 'include "qelib1.inc";' in res:
            res = re.sub(r'(include "qelib1.inc";)', r'\1\n' + q_decls, res)
        elif "OPENQASM 2.0;" in res:
            res = re.sub(r'(OPENQASM\s+2\.0;)', r'\1\n' + q_decls, res)
        else:
            res = q_decls + "\n" + res

    # 4. check creg and add them if missing
    if not declared_cregs:
        # find the largest qubit as default reg length
        all_q_sizes = [max_idx + 1 for max_idx in undeclared_q.values()]
        # count the size of declared qreg
        qreg_sizes = [int(s) for s in re.findall(r"\bqreg\s+\w+\s*\[(\d+)\];", res)]
        max_size = max(all_q_sizes + qreg_sizes) if (all_q_sizes + qreg_sizes) else 2

        c_decl = f"creg c[{max_size}];"
        # insert after the last qreg declaration
        if re.search(r"\bqreg\s+.*?;", res):
            res = re.sub(r"(\bqreg\s+.*?;)", r"\1\n" + c_decl, res, count=1)
        else:
            res = res + "\n" + c_decl

    return res


def checker_measure(qasm_str: str) -> str:
    """
    General checker for measure: if missing, read current qreg and creg, 
    then add "measure q[i] -> c[i];"
    """
    res = qasm_str.strip()

    if "measure" in res:
        return res

    # extract the name and size of the first qreg and creg
    qreg_match = re.search(r"\bqreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[(\d+)\];", res)
    creg_match = re.search(r"\bcreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\[(\d+)\];", res)

    if qreg_match and creg_match:
        q_name, q_size = qreg_match.group(1), int(qreg_match.group(2))
        c_name, c_size = creg_match.group(1), int(creg_match.group(2))
        
        num_measures = min(q_size, c_size)
        measures = "\n" + "\n".join([f"measure {q_name}[{i}] -> {c_name}[{i}];" for i in range(num_measures)])
        res = res + measures

    return res
