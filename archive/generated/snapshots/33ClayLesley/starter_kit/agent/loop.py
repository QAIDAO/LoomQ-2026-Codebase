# starter_kit/agent/loop.py
import os, json, subprocess, time
from qiskit.qasm2 import loads
from qiskit import QuantumCircuit
from qiskit_aer import Aer

def run_qasm_and_get_counts(qasm_str: str, shots: int = 1024):
    """本地快速验证 QASM 能否运行并返回 counts"""
    try:
        circuit = loads(qasm_str)
        backend = Aer.get_backend('qasm_simulator')
        job = backend.run(circuit, shots=shots)
        return job.result().get_counts()
    except Exception as e:
        return {"error": str(e)}

def agent_with_self_healing(user_prompt: str, llm_generate_func, max_retries=2):
    """
    核心闭环逻辑：
    1. LLM 生成 QASM
    2. 本地模拟器跑一下
    3. 如果报错或结果不理想，把报错喂给 LLM 让它修
    """
    current_qasm = ""
    history = []
    
    for attempt in range(max_retries + 1):
        # 调用 LLM（需要你传入 client 的调用方法）
        if attempt == 0:
            response = llm_generate_func(user_prompt, error_feedback=None)
        else:
            response = llm_generate_func(user_prompt, error_feedback=history[-1])
        
        current_qasm = extract_qasm(response)  # 提取代码块
        
        # 本地跑一下验证
        counts = run_qasm_and_get_counts(current_qasm)
        
        if "error" in counts:
            # 出错了，记录错误，进入下一轮重试
            history.append(f"上一版代码运行报错: {counts['error']}")
            continue
        else:
            # 跑通了！返回结果
            return current_qasm, counts
    
    # 重试次数用完，返回最后生成的版本（即使可能报错，但至少交差了）
    return current_qasm, {"error": "Max retries exceeded, but returning last generated code"}

def extract_qasm(text: str) -> str:
    """从 LLM 回复中提取 QASM 代码块"""
    import re
    match = re.search(r"```(?:qasm)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 如果没有 markdown 包裹，尝试直接找 OPENQASM
    if "OPENQASM" in text:
        return text.strip()
    return text