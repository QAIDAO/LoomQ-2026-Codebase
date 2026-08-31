#!/usr/bin/env python3
"""Validate SpinQ real-hardware access and build a no-submit task preview."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile


STARTER_KIT = Path(__file__).resolve().parents[1]
REPOSITORY = STARTER_KIT.parent
if str(STARTER_KIT) not in sys.path:
    sys.path.insert(0, str(STARTER_KIT))

import adapter  # noqa: E402
from loomq.hardware import (  # noqa: E402
    assert_no_secret_values,
    load_env_file,
    positive_int,
    prepare_spinq_cloud_qasm,
    redact_text,
    require_config,
    sha256_text,
)
from loomq.qasm import parse_openqasm2  # noqa: E402


REQUIRED_CONFIG = (
    "LOOMQ_SPINQ_USERNAME",
    "LOOMQ_SPINQ_KEYFILE",
    "LOOMQ_SPINQ_HOST",
    "LOOMQ_SPINQ_PLATFORM_CODE",
)
SECRET_CONFIG = (
    "LOOMQ_SPINQ_USERNAME",
    "LOOMQ_SPINQ_KEYFILE",
    "LOOMQ_ORIGINQ_API_TOKEN",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log in to SpinQ, validate a real platform, and create a local task preview."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPOSITORY / ".env.hardware.local",
    )
    parser.add_argument(
        "--circuit",
        type=Path,
        default=STARTER_KIT / "circuits" / "bell.qasm",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPOSITORY / "local_docs" / "hardware_preflight" / "spinq",
    )
    return parser.parse_args()


def compile_spinq_ir(qasm: str):
    from spinqit import get_compiler

    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".qasm", delete=False, encoding="utf-8"
        ) as temporary:
            temporary.write(qasm)
            temporary_path = temporary.name
        return get_compiler("qasm").compile(temporary_path, 0)
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


def build_preflight(args: argparse.Namespace) -> dict[str, object]:
    from spinqit import SpinQCloudConfig, get_spinq_cloud

    config = load_env_file(args.env_file)
    require_config(config, REQUIRED_CONFIG)
    shots = positive_int(config.get("LOOMQ_HARDWARE_SHOTS", "1024"), "shots")

    keyfile = Path(config["LOOMQ_SPINQ_KEYFILE"]).expanduser()
    if not keyfile.is_file():
        raise ValueError("SpinQ private key file does not exist or is unreadable")

    source_qasm = args.circuit.read_text(encoding="utf-8")
    transpiled_qasm = adapter.transpile(source_qasm, "spinq")
    executed_qasm = prepare_spinq_cloud_qasm(transpiled_qasm)
    program = parse_openqasm2(transpiled_qasm)
    ir = compile_spinq_ir(executed_qasm)

    backend = get_spinq_cloud(
        config["LOOMQ_SPINQ_USERNAME"],
        str(keyfile),
        config["LOOMQ_SPINQ_HOST"],
    )
    platform = backend.get_platform(config["LOOMQ_SPINQ_PLATFORM_CODE"])
    if platform.simu:
        raise ValueError("configured SpinQ platform is a simulator, not real hardware")
    if program.quantum_register.size > platform.max_bitnum:
        raise ValueError("circuit exceeds the configured SpinQ platform qubit limit")

    task_prefix = config.get("LOOMQ_HARDWARE_TASK_PREFIX", "LoomQ-L1")
    cloud_config = SpinQCloudConfig()
    cloud_config.configure_platform(platform.code)
    cloud_config.configure_shots(shots)
    cloud_config.configure_task(f"{task_prefix}-spinq-preflight", "LoomQ L1 Bell evidence preflight")

    captured = io.StringIO()
    with redirect_stdout(captured):
        backend.submit_task(ir, cloud_config, debug=True)
    preview_lines = [line for line in captured.getvalue().splitlines() if line.strip()]
    if not preview_lines:
        raise RuntimeError("SpinQ SDK did not produce a task preview")
    task_payload = json.loads(preview_lines[-1])
    if task_payload.get("platformCode") != platform.code:
        raise RuntimeError("SpinQ task preview selected an unexpected platform")
    if int(task_payload.get("shots", 0)) != shots:
        raise RuntimeError("SpinQ task preview selected an unexpected shot count")

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest: dict[str, object] = {
        "mode": "dry-run",
        "submitted": False,
        "timestamp": timestamp,
        "platform": {
            "code": platform.code,
            "name": platform.name,
            "is_simulator": platform.simu,
            "available_now": platform.available(),
            "online_machines": platform.machine_count,
            "max_qubits": platform.max_bitnum,
        },
        "circuit": {
            "source": args.circuit.name,
            "qubits": program.quantum_register.size,
            "classical_bits": program.classical_register.size,
            "shots": shots,
            "source_sha256": sha256_text(source_qasm),
            "transpiled_sha256": sha256_text(transpiled_qasm),
            "executed_sha256": sha256_text(executed_qasm),
        },
        "task_payload_sha256": sha256_text(
            json.dumps(task_payload, ensure_ascii=False, sort_keys=True)
        ),
        "artifacts": {
            "source_qasm": "source.qasm",
            "transpiled_qasm": "transpiled.qasm",
            "executed_qasm": "executed.qasm",
            "task_preview": "task-preview.json",
        },
    }

    serialized = "\n".join(
        (
            source_qasm,
            transpiled_qasm,
            executed_qasm,
            json.dumps(task_payload, ensure_ascii=False, sort_keys=True),
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
        )
    )
    assert_no_secret_values(serialized, config, SECRET_CONFIG)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source.qasm").write_text(source_qasm, encoding="utf-8")
    (args.output_dir / "transpiled.qasm").write_text(transpiled_qasm, encoding="utf-8")
    (args.output_dir / "executed.qasm").write_text(executed_qasm, encoding="utf-8")
    (args.output_dir / "task-preview.json").write_text(
        json.dumps(task_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "preflight.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    args = parse_args()
    config: dict[str, str] = {}
    try:
        if args.env_file.is_file():
            config = load_env_file(args.env_file)
        manifest = build_preflight(args)
    except Exception as exc:
        message = redact_text(str(exc), config, SECRET_CONFIG)
        print(f"SpinQ preflight failed: {message}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
