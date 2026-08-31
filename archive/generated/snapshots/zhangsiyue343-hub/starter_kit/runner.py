#!/usr/bin/env python3
"""Asyncio orchestration for multi-backend submission and aggregation.

The runner owns the concurrency policy: parse once, fan a circuit out to
several plugin backends concurrently (native SDK calls are blocking, so they
execute in the default thread-pool executor), then fold every outcome into
the unified result schema. Failures are isolated per target — one platform
error never poisons the others.

Public sync surface (adapter.py contract) is a thin wrapper over these
coroutines; async callers can `await run_many_async` directly.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

try:
    from .gates import GATES
    from .ir import Circuit, lower
    from .parser import parse_source
    from .simulator import circuit_depth
except ImportError:
    from gates import GATES
    from ir import Circuit, lower
    from parser import parse_source
    from simulator import circuit_depth


class TranspileError(ValueError):
    pass


@dataclass(frozen=True)
class TargetResult:
    target: str
    ok: bool
    payload: dict = field(default_factory=dict)
    error: str = ""
    native_ir: str = ""


@dataclass
class CircuitRunner:
    config: Any                       # LoomqConfig (kept loose to avoid cycles)
    registry: Any                     # PluginRegistry

    # ---- single-target primitives -----------------------------------------

    def compile(self, qasm_str: str) -> Circuit:
        program = parse_source(qasm_str, GATES)
        circuit = lower(program)
        if circuit.n_qubits <= 0:
            raise TranspileError("circuit declares no qubits")
        return circuit

    def transpile(self, qasm_str: str, target: str) -> str:
        circuit = self.compile(qasm_str)
        plugin = self.registry.get(target)
        return plugin.emit(circuit)

    def execute(self, circuit: Circuit, target: str, shots: int):
        return self.registry.get(target).run(circuit, shots, self.config)

    def run_one(self, qasm_str: str, target: str, shots: int,
                include_native_ir: bool = True) -> dict[str, Any]:
        """Sync single-target execution returning the unified schema."""
        circuit = self.compile(qasm_str)
        outcome = self.execute(circuit, target, shots)
        payload = _unified_payload(target, outcome, shots, circuit)
        if include_native_ir:
            payload["native_ir"] = self.registry.get(target).emit(circuit)
        return payload

    # ---- concurrent fan-out -------------------------------------------------

    async def transpile_async(self, qasm_str: str, target: str) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.transpile, qasm_str, target)

    async def run_target_async(self, circuit: Circuit, target: str,
                               shots: int, include_native_ir: bool = True) -> TargetResult:
        loop = asyncio.get_running_loop()
        try:
            plugin = self.registry.get(target)
            outcome = await loop.run_in_executor(
                None, lambda: plugin.run(circuit, shots, self.config))
            payload = _unified_payload(target, outcome, shots, circuit)
            native_ir = plugin.emit(circuit)
            if include_native_ir:
                payload["native_ir"] = native_ir
            return TargetResult(target, True, payload, "", native_ir)
        except Exception as exc:
            return TargetResult(target, False, {}, "%s: %s" % (type(exc).__name__, exc))

    async def run_many_async(self, qasm_str: str, targets: Iterable[str],
                             shots: int, concurrency: int = 0,
                             include_native_ir: bool = False) -> list[TargetResult]:
        """Submit one circuit to several backends concurrently and aggregate."""
        circuit = self.compile(qasm_str)
        requested = list(dict.fromkeys(targets))
        unknown = [t for t in requested if t not in self.registry.plugins]
        limit = max(concurrency or getattr(self.config.engine, "concurrency", 4), 1)
        semaphore = asyncio.Semaphore(limit)

        async def guarded(task_target: str) -> TargetResult:
            async with semaphore:
                return await self.run_target_async(circuit, task_target, shots,
                                                   include_native_ir)

        gathered = await asyncio.gather(*(guarded(t) for t in requested))
        results = list(gathered)
        results.extend(TargetResult(t, False, {}, "unknown target %r" % t)
                       for t in unknown)
        return results

    def run_many(self, qasm_str: str, targets: Iterable[str], shots: int,
                 concurrency: int = 0, include_native_ir: bool = False) -> list[TargetResult]:
        return _run_coroutine(self.run_many_async(qasm_str, targets, shots,
                                                  concurrency, include_native_ir))


# --------------------------------------------------------------------------
# unified schema assembly + event-loop plumbing
# --------------------------------------------------------------------------

def _unified_payload(target: str, outcome, shots: int,
                     circuit: Circuit) -> dict[str, Any]:
    total = sum(outcome.counts.values())
    if total != shots:
        raise ValueError("backend %s returned %d of %d shots"
                         % (outcome.backend_id, total, shots))
    return {
        "backend": outcome.backend_id,
        "target": target,
        "engine": outcome.engine_label,
        "job_id": uuid.uuid4().hex[:16],
        "shots": shots,
        "counts": dict(sorted(outcome.counts.items())),
        "bit_order": "little",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "transpiled_gates": len(circuit.ops),
            "depth": circuit_depth(circuit),
        },
    }


def _run_coroutine(coroutine):
    """Run a coroutine on a fresh loop; reusable from any sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        raise RuntimeError("call the *_async variant from inside a running loop")
    return asyncio.run(coroutine)
