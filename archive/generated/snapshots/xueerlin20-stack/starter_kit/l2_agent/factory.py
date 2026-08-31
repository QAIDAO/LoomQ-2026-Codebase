"""Production construction of the LoomQ L2 agent."""

from .agent import AgentEngine
from .context import AgentContext
from .gateway import OpenAICompatibleLLMGateway
from .registry import default_registry
from .tools import (
    CapabilityBackendSelector,
    QASMValidator,
)


def create_agent() -> AgentEngine:
    context = AgentContext(
        llm=OpenAICompatibleLLMGateway(),
        backend_selector=CapabilityBackendSelector(),
        validator=QASMValidator(target="spinq", shots=4096),
    )
    return AgentEngine(context, default_registry())
