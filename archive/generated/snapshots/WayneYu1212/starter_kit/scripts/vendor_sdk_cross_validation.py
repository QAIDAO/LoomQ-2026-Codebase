#!/usr/bin/env python3
"""Run 40 fixed-seed circuits through all vendor local SDK runners."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from starter_kit.evaluator import calculate_hellinger_fidelity
from starter_kit.loomq.compiler.parser import parse_qasm
from starter_kit.loomq.runners import run_circuit
from starter_kit.loomq.simulator import probabilities
from starter_kit.tests.fixtures import GHZ5_QASM,GROVER_LIKE_QASM,QFT_LIKE_QASM,random_qasm
OUT=ROOT/'starter_kit'/'evidence'/'files'/'vendor-sdk-cross-validation-summary.json'
def main():
    corpus=[('ghz5',GHZ5_QASM),('qft',QFT_LIKE_QASM),('grover',GROVER_LIKE_QASM)]+[(f'random-{i}',random_qasm(1000+i)) for i in range(37)]
    rows=[]; shots=2048
    for name,src in corpus:
        circuit=parse_qasm(src); expected=probabilities(circuit)
        for target in ('spinq','originq','braket'):
            result=run_circuit(circuit,target,shots); observed={s:c/shots for s,c in result['counts'].items()}; fidelity=calculate_hellinger_fidelity(observed,expected)
            rows.append({'circuit':name,'target':target,'fidelity':fidelity,'pass':fidelity>=0.95})
    out={'seed':1000,'circuits':len(corpus),'targets':['spinq','originq','braket'],'total':len(rows),'passed':sum(x['pass'] for x in rows),'failed':sum(not x['pass'] for x in rows),'rows':rows}
    OUT.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:out[k] for k in ('circuits','total','passed','failed')}))
if __name__=='__main__':main()
