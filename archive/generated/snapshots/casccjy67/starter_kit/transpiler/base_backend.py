"""Abstract base class for quantum backend adapters."""
from abc import ABC, abstractmethod
from .ir import Circuit


class BaseBackend(ABC):
    name: str = "base"

    @abstractmethod
    def transpile(self, circuit: Circuit) -> str:
        """Convert Circuit IR to native instruction string."""
        ...

    @abstractmethod
    def run(self, circuit: Circuit, shots: int = 8192) -> dict:
        """Execute circuit and return unified result dict."""
        ...

    @staticmethod
    def _normalize_counts_little(counts: dict, num_clbits: int) -> dict:
        """Ensure counts keys are little-endian: rightmost char = c[0]."""
        normalized = {}
        for key, val in counts.items():
            key_str = key.replace(" ", "")
            if len(key_str) < num_clbits:
                key_str = key_str.zfill(num_clbits)
            elif len(key_str) > num_clbits:
                key_str = key_str[-num_clbits:]
            normalized[key_str] = normalized.get(key_str, 0) + val
        return normalized

    @staticmethod
    def _build_result(
        backend_name: str, job_id: str, shots: int,
        counts: dict, num_clbits: int, meta: dict = None,
    ) -> dict:
        from datetime import datetime, timezone
        normalized = BaseBackend._normalize_counts_little(counts, num_clbits)
        return {
            "backend": backend_name,
            "job_id": job_id,
            "shots": shots,
            "counts": normalized,
            "bit_order": "little",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": meta or {},
        }


def expand_cu1(control: int, target: int, lam: float):
    """Decompose cu1(λ) into rz + cx gates (standard Qiskit decomposition).

    cu1(λ) q[c],q[t]  →
        rz(λ/2) q[c]
        cx q[c], q[t]
        rz(-λ/2) q[t]
        cx q[c], q[t]
        rz(λ/2) q[t]
    """
    from .ir import Gate
    half = lam / 2.0
    return [
        Gate("rz", [control], [half]),
        Gate("cx", [control, target]),
        Gate("rz", [target], [-half]),
        Gate("cx", [control, target]),
        Gate("rz", [target], [half]),
    ]
