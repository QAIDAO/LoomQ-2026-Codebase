"""Windows-safe hard deadline for one killable campaign child."""
from __future__ import annotations

import multiprocessing as mp
import queue as queue_module
import traceback


def _bootstrap(target, args, result_queue):
    try:
        target(*args, result_queue)
    except BaseException as exc:
        result_queue.put(
            {
                "status": "child_exception",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)[:500],
                "traceback_tail": traceback.format_exc(limit=4)[-1500:],
            }
        )


def run(target, args, timeout_seconds: float):
    context = mp.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(target=_bootstrap, args=(target, args, result_queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
        return {"status": "timeout"}
    try:
        return result_queue.get(timeout=1)
    except queue_module.Empty:
        return {
            "status": "child_exception",
            "exception_type": "ProcessExit",
            "exception_message": f"campaign child exited without a result (exitcode={process.exitcode})",
        }
