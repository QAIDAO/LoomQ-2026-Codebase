"""Stable application facade shared by HTTP and unit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .chat import ChatService
from .configuration import ConfigurationService

try:
    from ..run_l2 import DEFAULT_ENV_FILE
except ImportError:
    from run_l2 import DEFAULT_ENV_FILE  # type: ignore


class WebApplication:
    """Coordinate independently replaceable configuration and chat services."""

    def __init__(
        self,
        env_file: Path = DEFAULT_ENV_FILE,
        *,
        configuration: Optional[ConfigurationService] = None,
        chat: Optional[ChatService] = None,
    ):
        self.configuration = configuration or ConfigurationService(env_file)
        self.chat = chat or ChatService()

    @property
    def env_file(self) -> Path:
        return self.configuration.env_file

    def configuration_status(self) -> Dict[str, Any]:
        return self.configuration.status()

    def save_configuration(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.configuration.save(payload)

    def handle_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.chat.execute(payload)

    def run_current_circuit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.chat.run_local(payload)

    def reset_conversation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.chat.reset(payload)

    @staticmethod
    def _display_text(result: Dict[str, Any]) -> str:
        return ChatService._display_text(result)
