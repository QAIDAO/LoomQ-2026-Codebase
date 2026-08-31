#!/usr/bin/env python3
"""Validate Wukong 180 access and build a no-submit execution plan."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


STARTER_KIT = Path(__file__).resolve().parents[1]
REPOSITORY = STARTER_KIT.parent
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.hardware import (  # noqa: E402
    assert_no_secret_values,
    load_env_file,
    positive_int,
    redact_text,
    require_config,
    sha256_text,
    top_k_states,
)
from loomq.qasm import parse_openqasm2  # noqa: E402


REQUIRED_CONFIG = ("LOOMQ_ORIGINQ_API_TOKEN", "LOOMQ_ORIGINQ_BACKEND")
SECRET_CONFIG = (
    "LOOMQ_ORIGINQ_API_TOKEN",
    "LOOMQ_SPINQ_USERNAME",
    "LOOMQ_SPINQ_KEYFILE",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Wukong 180 access without submitting a cloud task."
    )
    parser.add_argument(
        "--env-file", type=Path, default=REPOSITORY / ".env.hardware.local"
    )
    parser.add_argument(
        "--circuit", type=Path, default=STARTER_KIT / "circuits" / "bell.qasm"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY / "local_docs" / "hardware_preflight" / "originq",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_preflight(args: argparse.Namespace) -> dict[str, object]:
    import pyqpanda3
    from pyqpanda3.core import CPUQVM
    from pyqpanda3.intermediate_compiler import convert_originir_string_to_qprog
    from pyqpanda3.qcloud import QCloudOptions, QCloudService

    config = load_env_file(args.env_file)
    require_config(config, REQUIRED_CONFIG)
    shots = positive_int(config.get("LOOMQ_HARDWARE_SHOTS", "1024"), "shots")
    backend_name = config["LOOMQ_ORIGINQ_BACKEND"].strip()

    source_qasm = args.circuit.read_text(encoding="utf-8")
    executed_originir = adapter.transpile(source_qasm, "originq")
    program = parse_openqasm2(source_qasm)
    qprog = convert_originir_string_to_qprog(executed_originir)

    local_qvm = CPUQVM()
    local_qvm.run(qprog, shots)
    local_counts = dict(local_qvm.result().get_counts())
    if set(top_k_states(local_counts, 2)) != {"00", "11"}:
        raise RuntimeError("local pyqpanda3 Bell validation did not match the ideal states")

    service = QCloudService(config["LOOMQ_ORIGINQ_API_TOKEN"])
    visible_backends = service.backends()
    if backend_name not in visible_backends:
        raise ValueError("configured OriginQ backend is not visible to this account")
    if not visible_backends[backend_name]:
        raise RuntimeError("configured OriginQ backend is currently unavailable")
    backend = service.backend(backend_name)
    chip_info = backend.chip_info()
    if chip_info.qubits_num() != 180:
        raise ValueError("configured OriginQ backend is not a Wukong 180 QPU")
    available_qubits = list(chip_info.available_qubits())
    topology = [list(edge) for edge in chip_info.get_chip_topology()]
    if len(available_qubits) < program.quantum_register.size:
        raise RuntimeError("Wukong 180 does not have enough available qubits")

    blocks = backend.best_qubit_blocks(
        qubit_num=program.quantum_register.size,
        label=1,
        qubit_block_num=1,
    )
    if blocks.empty():
        raise RuntimeError("Wukong 180 did not return a usable qubit block")
    selected_block = list(blocks.block(0))
    if len(selected_block) != program.quantum_register.size:
        raise RuntimeError("Wukong 180 returned an invalid qubit block")

    options = QCloudOptions()
    options.set_mapping(True)
    options.set_optimization(True)
    options.set_amend(True)
    options.set_specified_block(selected_block)

    plan: dict[str, object] = {
        "mode": "online-read-only-preflight",
        "submitted": False,
        "timestamp": utc_now(),
        "sdk": {"name": "pyqpanda3", "version": pyqpanda3.__version__},
        "platform": {
            "name": "Origin Quantum Cloud",
            "backend": backend_name,
            "is_qpu": True,
            "available_now": True,
            "total_qubits": chip_info.qubits_num(),
            "available_qubits": len(available_qubits),
            "basic_gates": list(chip_info.get_basic_gates()),
            "topology_edges": len(topology),
            "selected_block": selected_block,
        },
        "circuit": {
            "source": args.circuit.name,
            "qubits": program.quantum_register.size,
            "classical_bits": program.classical_register.size,
            "shots": shots,
            "source_sha256": sha256_text(source_qasm),
            "executed_sha256": sha256_text(executed_originir),
            "local_counts": local_counts,
        },
        "execution_options": {
            "mapping": True,
            "optimization": True,
            "amend": True,
            "specified_block": selected_block,
        },
        "artifacts": {
            "source_qasm": "source.qasm",
            "executed_originir": "executed.originir",
            "execution_plan": "execution-plan.json",
        },
    }
    serialized = "\n".join(
        (
            source_qasm,
            executed_originir,
            json.dumps(plan, ensure_ascii=False, sort_keys=True),
        )
    )
    assert_no_secret_values(serialized, config, SECRET_CONFIG)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source.qasm").write_text(source_qasm, encoding="utf-8")
    (args.output_dir / "executed.originir").write_text(
        executed_originir, encoding="utf-8"
    )
    (args.output_dir / "execution-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return plan


def main() -> int:
    args = parse_args()
    config: dict[str, str] = {}
    try:
        if args.env_file.is_file():
            config = load_env_file(args.env_file)
        plan = build_preflight(args)
    except Exception as exc:
        print(
            "OriginQ preflight failed: " + redact_text(str(exc), config, SECRET_CONFIG),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
