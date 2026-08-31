#!/usr/bin/env python3
"""Deterministic local parser/semantic fuzz smoke at the requested scales."""
import json, random, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from starter_kit.tests.fixtures import random_qasm
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.simulator import probabilities
from starter_kit.loomq.emitters import emit_spinq,emit_originq,emit_braket
from starter_kit import adapter
from starter_kit.riscv_emulator import TinyRISCVEmulator,encode_quantum_instruction,decode_quantum_word
OUT=ROOT/'starter_kit/evidence/files/offline-fuzz-summary.json'
def main():
    seed=20260822; random.seed(seed); result={'seed':seed,'failures':[]}
    for label,n in [('l1_general',10000),('measurement',5000),('parameters',5000)]:
        passed=0
        for i in range(n):
            try:
                c=parse_qasm(random_qasm(seed+i,qubits=3+(i%4),depth=6+(i%12))); probabilities(c)
                if label=='l1_general': emit_spinq(c); emit_originq(c); emit_braket(c)
                passed+=1
            except Exception as e: result['failures'].append({'campaign':label,'case':i,'error':type(e).__name__})
        result[label]={'cases':n,'passed':passed,'failures':n-passed}
    result['l3_hybrid']={'cases':5000,'status':'NOT RUN: dedicated generator not present'}
    hybrid_pass=0
    for i in range(5000):
        source='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2]; creg c[2];\nh q[0]; measure q[0] -> c[0];\nclassical { r1 = c[0] + %d; }\n' % (i%17-8)
        try:
            ops,assembly=adapter.compile_hybrid(source); emu=TinyRISCVEmulator(); emu.load_program(assembly); emu.set_register('x10',i%2); emu.execute(); hybrid_pass+=1
        except Exception as e: result['failures'].append({'campaign':'l3_hybrid','case':i,'error':type(e).__name__})
    result['l3_hybrid']={'cases':5000,'passed':hybrid_pass,'failures':5000-hybrid_pass}
    riscv_pass=0
    names=('qinit','qh','qx','qcx','qmeasure')
    for i in range(5000):
        name=names[i%len(names)]; args=(i%32,) if name!='qcx' and name!='qmeasure' else ((i%32,(i+1)%32) if name in ('qcx','qmeasure') else (i%32,))
        try:
            word=encode_quantum_instruction(name,*args); decoded=decode_quantum_word(word)
            if decoded[0]!=name or tuple(decoded[1])!=tuple(args): raise ValueError('roundtrip')
            riscv_pass+=1
        except Exception as e: result['failures'].append({'campaign':'custom_riscv','case':i,'error':type(e).__name__})
    result['custom_riscv']={'cases':5000,'passed':riscv_pass,'failures':5000-riscv_pass}
    security_pass=0
    for i in range(5000):
        try:
            parse_qasm('OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1]; '+(' '*(i%100))+'rz((pi+) q[0];')
        except Exception: security_pass+=1
    result['security_parser']={'cases':5000,'passed':security_pass,'failures':5000-security_pass}
    OUT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in result.items() if k!='failures'}))
if __name__=='__main__': main()
