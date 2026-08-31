"""SpinQit 独立 Python 环境的 stdin/stdout JSON Worker。"""

import contextlib
import json
import sys
from typing import Any, Dict

from ..parser import parse_qasm
from ..results import validate_shots
from ..runners.spinq import run_spinq_native


def _read_request() -> Dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("SpinQ worker request must be a JSON object")
    qasm = payload.get("qasm")
    shots = payload.get("shots")
    if not isinstance(qasm, str) or not qasm.strip():
        raise ValueError("SpinQ worker qasm must be a non-empty string")
    validate_shots(shots)
    return {"qasm": qasm, "shots": shots}


def main() -> int:
    """读取一个请求并仅向 stdout 写出最终结果 JSON。"""
    try:
        request = _read_request()
        circuit = parse_qasm(request["qasm"])
        # SpinQit 的普通输出转到 stderr，避免破坏 stdout JSON 协议。
        with contextlib.redirect_stdout(sys.stderr):
            result = run_spinq_native(circuit, request["shots"])
        json.dump(result, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except Exception as exc:
        print("%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
