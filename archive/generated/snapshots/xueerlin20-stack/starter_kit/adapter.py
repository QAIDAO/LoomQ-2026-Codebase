#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

Thin facade over the translation pipeline:

    qasm_L1/parser.py   OpenQASM 2.0 text -> Circuit IR
    qasm_L1/emitter.py  Translator -> target-native text
    qasm_L1/runners.py  SDK execution backends (spinq / braket / originq)

The contract functions below never re-parse or re-implement platform logic;
they only parse once and dispatch to a target.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from .qasm_L1 import runners
    from .qasm_L1.emitter import Translator
    from .qasm_L1.execution import save_hardware_evidence, save_local_artifacts
    from .qasm_L1.parser import parse_qasm
except ImportError:
    from qasm_L1 import runners
    from qasm_L1.emitter import Translator
    from qasm_L1.execution import save_hardware_evidence, save_local_artifacts
    from qasm_L1.parser import parse_qasm

SUPPORTED_TARGETS = ("spinq", "originq", "braket")
CREDENTIALS_DIRECTORY = Path(__file__).resolve().parent / "qasm_L1" / "credentials"

RUNNERS = {
    "spinq": runners.run_spinq,
    "braket": runners.run_braket,
    "originq": runners.run_originq,
}

REAL_RUNNERS = {
    "spinq": runners.run_spinq_real,
    "braket": runners.run_braket_real,
    "originq": runners.run_originq_real,
}

PROGRAM_SUFFIXES = {"spinq": "qasm", "braket": "qasm", "originq": "originir"}


def _normalize_target(target: str) -> str:
    return (target or "").strip().lower()


def _read_credential(filename: str) -> str:
    return (CREDENTIALS_DIRECTORY / filename).read_text(encoding="utf-8").strip()


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    circuit = parse_qasm(qasm_str)
    return Translator(circuit).dispatch(target_name)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")

    native_qasm = transpile(qasm_str, target_name)
    execution = RUNNERS[target_name](native_qasm, shots)
    return execution.to_contract_dict()


def run_and_save(
    qasm_str: str,
    target: str,
    shots: int,
    output_directory: str,
) -> Dict[str, Any]:
    """Run a local backend once and export its native program and result JSON."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if not output_directory:
        raise ValueError("output_directory is required")

    native_program = transpile(qasm_str, target_name)
    execution = RUNNERS[target_name](native_program, shots)
    execution.metadata["artifact_files"] = save_local_artifacts(
        execution,
        native_program,
        output_directory,
        program_suffix=PROGRAM_SUFFIXES[target_name],
    )
    return execution.to_contract_dict()


def run_real(
    qasm_str: str,
    target: str,
    shots: int,
    **backend_options: Any,
) -> Dict[str, Any]:
    """Submit to a physical QPU and return a traceable, evidence-ready result.

    Credentials and device selection are target-specific keyword arguments.
    Pass ``evidence_directory`` to also export the native program, normalized
    result, and sanitized platform response.
    """
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")

    evidence_directory = backend_options.pop("evidence_directory", None)
    native_program = transpile(qasm_str, target_name)
    execution = REAL_RUNNERS[target_name](native_program, shots, **backend_options)
    if evidence_directory:
        execution.metadata["evidence_files"] = save_hardware_evidence(
            execution,
            native_program,
            evidence_directory,
            program_suffix=PROGRAM_SUFFIXES[target_name],
        )
    return execution.to_contract_dict(include_raw=True)


def main(argv: List[str] = None) -> int:
    """Run one or more local circuits and save their native IR and results."""
    parser = argparse.ArgumentParser(
        description="Run LoomQ OpenQASM 2 circuits locally or on a real QPU and save results."
    )
    parser.add_argument("input", help="a .qasm file or a directory of .qasm files")
    parser.add_argument("--target", choices=SUPPORTED_TARGETS, required=True)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--real", action="store_true", help="submit to a real QPU")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "evidence" / "files"),
        help="artifact output directory (default: starter_kit/evidence/files)",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    circuits = sorted(input_path.glob("*.qasm")) if input_path.is_dir() else [input_path]
    if not circuits:
        parser.error("no .qasm circuits found")

    output_root = Path(args.output)
    batch_mode = len(circuits) > 1
    for circuit_path in circuits:
        output_directory = output_root / circuit_path.stem if batch_mode else output_root
        qasm_str = circuit_path.read_text(encoding="utf-8")
        if args.real:
            if args.target == "spinq":
                options = {
                    "username": os.environ["SPINQ_USERNAME"],
                    "keyfile": str(CREDENTIALS_DIRECTORY / "spinq_private_key.pem"),
                    "platform": os.environ.get("SPINQ_PLATFORM", "triangulum_vp"),
                }
            elif args.target == "braket":
                options = {"device_arn": os.environ["BRAKET_DEVICE_ARN"]}
            else:
                options = {"token": _read_credential("originq_token.txt")}
            result = run_real(
                qasm_str,
                args.target,
                args.shots,
                evidence_directory=str(output_directory),
                **options,
            )
        else:
            result = run_and_save(
                qasm_str,
                args.target,
                args.shots,
                str(output_directory),
            )
        print(f"{circuit_path.name}: {result['counts']}")
        files_key = "evidence_files" if args.real else "artifact_files"
        print(f"files: {result['meta'][files_key]}")
    return 0


def agent_chat(prompt: str) -> str:
    """Run the L2 agent using the documented LOOMQ_LLM_* environment."""
    try:
        from .l2_agent.factory import create_agent
    except ImportError:
        from l2_agent.factory import create_agent

    return create_agent().respond(prompt)


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Compile Hybrid-QASM into quantum operations and RISC-V assembly."""
    try:
        from .L3 import compile_hybrid as compile_l3_hybrid
    except ImportError:
        from L3 import compile_hybrid as compile_l3_hybrid

    return compile_l3_hybrid(hybrid_qasm_str)


if __name__ == "__main__":
    sys.exit(main())
