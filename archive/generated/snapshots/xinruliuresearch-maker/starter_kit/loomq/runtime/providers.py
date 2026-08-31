"""Uniform provider boundary for target emission and local execution.

The three providers currently share the audited reference state-vector engine.
Metadata states that fact explicitly; no provider pretends that an optional
vendor SDK or cloud QPU was used.
"""

from dataclasses import dataclass
from typing import Any, Dict, Type

from ..errors import UnsupportedTargetError
from ..targets import emit_target_ir
from ..targets.roundtrip import admit_target_artifact
from .reference_simulator import simulate_counts
from .result_normalizer import build_result


@dataclass(frozen=True)
class ProviderCapabilities:
    target: str
    execution_mode: str = "local_simulator"
    execution_engine: str = "loomq_reference_statevector"
    native_sdk_used: bool = False


class BaseProvider:
    """Narrow provider interface used by the stateless adapter path."""

    target = ""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(target=self.target)

    def transpile(self, circuit: Any) -> str:
        artifact = emit_target_ir(circuit, self.target)
        return admit_target_artifact(circuit, artifact, self.target)

    def run(self, circuit: Any, shots: int, seed: int, digest: str) -> Dict[str, Any]:
        counts = simulate_counts(circuit, shots, seed)
        return build_result(self.target, shots, counts, digest, circuit)


class SpinQProvider(BaseProvider):
    target = "spinq"


class OriginQProvider(BaseProvider):
    target = "originq"


class BraketProvider(BaseProvider):
    target = "braket"


PROVIDERS: Dict[str, Type[BaseProvider]] = {
    "spinq": SpinQProvider,
    "originq": OriginQProvider,
    "braket": BraketProvider,
}


def get_provider(target: str) -> BaseProvider:
    try:
        provider_type = PROVIDERS[target]
    except KeyError as exc:
        raise UnsupportedTargetError("no provider registered for target %r" % target) from exc
    return provider_type()
