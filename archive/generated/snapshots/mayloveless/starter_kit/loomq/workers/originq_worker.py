"""pyQPanda 独立 Python 环境的 stdin/stdout JSON Worker。"""

import contextlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

from ..results import validate_shots


@contextlib.contextmanager
def _redirect_native_stdout_to_stderr():  # type: ignore[no-untyped-def]
    """同时重定向 Python stdout 与原生库使用的文件描述符 1。"""
    try:
        stdout_fd = sys.stdout.fileno()
        stderr_fd = sys.stderr.fileno()
    except (AttributeError, OSError):
        # StringIO 单测没有文件描述符，仍验证 Python 层日志不会污染协议。
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


def _read_request() -> Dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("OriginQ worker request must be a JSON object")
    originir = payload.get("originir")
    shots = payload.get("shots")
    if not isinstance(originir, str) or not originir.strip():
        raise ValueError("OriginQ worker originir must be a non-empty string")
    validate_shots(shots)
    return {"originir": originir, "shots": shots}


def _execute_originir(originir: str, shots: int) -> Mapping[str, int]:
    """在临时 UTF-8 文件中转换 OriginIR，并确保释放 CPUQVM。"""
    try:
        pyqpanda = importlib.import_module("pyqpanda")
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "pyQPanda SDK is not installed; install requirements-originq.txt "
            "in the isolated OriginQ environment"
        ) from exc

    machine = pyqpanda.CPUQVM()
    initialized = False
    try:
        machine.init_qvm()
        initialized = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.originir"
            path.write_text(originir, encoding="utf-8")
            converted = pyqpanda.convert_originir_to_qprog(str(path), machine)
            if not isinstance(converted, (list, tuple)) or len(converted) != 3:
                raise RuntimeError(
                    "pyQPanda convert_originir_to_qprog returned an unexpected value"
                )
            prog, _qvec, cvec = converted
            return machine.run_with_configuration(prog, cvec, shots)
    finally:
        if initialized:
            machine.finalize()


def main() -> int:
    """读取一次请求，SDK 日志进 stderr，stdout 只写最终 JSON。"""
    try:
        request = _read_request()
        with _redirect_native_stdout_to_stderr():
            counts = _execute_originir(request["originir"], request["shots"])
        json.dump({"counts": dict(counts)}, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
