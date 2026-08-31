"""在隔离 SDK 解释器中直接解析并执行公开 target-native artifact。"""

import contextlib
import importlib
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping

from loomq.results import validate_shots


@contextlib.contextmanager
def _redirect_native_stdout_to_stderr() -> Iterator[None]:
    """避免厂商原生库日志污染 stdout 上的 JSON 协议。"""
    try:
        stdout_fd = sys.stdout.fileno()
        stderr_fd = sys.stderr.fileno()
    except (AttributeError, OSError):
        with contextlib.redirect_stdout(sys.stderr):
            yield
        return

    sys.stdout.flush()
    saved_stdout = os.dup(stdout_fd)
    try:
        os.dup2(stderr_fd, stdout_fd)
        with contextlib.redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stderr.flush()
        os.dup2(saved_stdout, stdout_fd)
        os.close(saved_stdout)


def _package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _execute_spinq_qasm(qasm: str, shots: int) -> Mapping[str, int]:
    """使用 SpinQit 自带 QASMCompiler，而不是 LoomQ Parser。"""
    spinqit = importlib.import_module("spinqit")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "program.qasm"
        path.write_text(qasm, encoding="utf-8")
        executable = spinqit.get_compiler("qasm").compile(str(path), 0)
        if executable is None:
            raise RuntimeError("SpinQit QASM compiler rejected target artifact")
        config = spinqit.BasicSimulatorConfig()
        config.configure_shots(shots)
        result = spinqit.get_basic_simulator().execute(executable, config)
    counts = getattr(result, "counts", None)
    if not isinstance(counts, dict) or not counts:
        raise RuntimeError("SpinQit QASM execution returned no counts")
    return counts


def _execute_originir(originir: str, shots: int) -> Mapping[str, int]:
    """复用已验证的 pyQPanda convert_originir_to_qprog + CPUQVM helper。"""
    from loomq.workers.originq_worker import _execute_originir as execute

    return execute(originir, shots)


def _read_request() -> Dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("native worker request must be a JSON object")
    target = payload.get("target")
    artifact = payload.get("artifact")
    shots = payload.get("shots")
    if target not in ("spinq", "originq"):
        raise ValueError("native worker target must be spinq or originq")
    if not isinstance(artifact, str) or not artifact.strip():
        raise ValueError("native worker artifact must be a non-empty string")
    validate_shots(shots)
    return {"target": target, "artifact": artifact, "shots": shots}


def main() -> int:
    try:
        request = _read_request()
        target = request["target"]
        with _redirect_native_stdout_to_stderr():
            if target == "spinq":
                counts = _execute_spinq_qasm(
                    request["artifact"], request["shots"]
                )
                version = _package_version("spinqit")
            else:
                counts = _execute_originir(
                    request["artifact"], request["shots"]
                )
                version = _package_version("pyqpanda")
        payload = {"counts": dict(counts), "sdk_version": version}
        if target == "spinq":
            # QASMCompiler counts 的首字符对应 q0，与 LoomQ key 顺序相反。
            payload["count_key_order"] = "q0_to_qn"
        json.dump(
            payload,
            sys.stdout,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
