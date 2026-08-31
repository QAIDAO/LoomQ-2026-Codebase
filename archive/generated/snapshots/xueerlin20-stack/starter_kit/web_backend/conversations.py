"""In-memory conversation and active-circuit state for the local web UI."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class ConversationTurn:
    """One compact turn retained for bounded conversational context."""

    user_text: str
    assistant_text: str
    action: str


@dataclass(frozen=True)
class CircuitArtifact:
    """The circuit currently discussed by a conversation."""

    artifact_id: str
    version: int
    qasm: str
    goal: str
    explanation: str = ""

    def public_metadata(self) -> Dict[str, object]:
        return {
            "id": self.artifact_id,
            "version": self.version,
            "goal": self.goal,
        }


@dataclass
class Conversation:
    """Mutable server-side session; access is synchronized by the store."""

    conversation_id: str
    updated_at: float
    turns: List[ConversationTurn] = field(default_factory=list)
    active_artifact: Optional[CircuitArtifact] = None


class ConversationStore:
    """Thread-safe, expiring conversation store for a single local process."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 2 * 60 * 60,
        max_turns: int = 5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("conversation TTL must be positive")
        if max_turns <= 0:
            raise ValueError("conversation max_turns must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._clock = clock
        self._items: Dict[str, Conversation] = {}
        self._lock = threading.RLock()

    def get_or_create(self, conversation_id: Optional[str]) -> Conversation:
        with self._lock:
            now = self._clock()
            self._discard_expired(now)
            conversation = (
                self._items.get(conversation_id) if conversation_id else None
            )
            if conversation is None:
                conversation = Conversation(
                    conversation_id="conv_" + secrets.token_urlsafe(12),
                    updated_at=now,
                )
                self._items[conversation.conversation_id] = conversation
            conversation.updated_at = now
            return conversation

    def get(self, conversation_id: str) -> Optional[Conversation]:
        """Return an existing live conversation without creating a new one."""
        with self._lock:
            now = self._clock()
            self._discard_expired(now)
            conversation = self._items.get(conversation_id)
            if conversation is not None:
                conversation.updated_at = now
            return conversation

    def record(
        self,
        conversation: Conversation,
        *,
        user_text: str,
        assistant_text: str,
        action: str,
        qasm: Optional[str] = None,
    ) -> Optional[CircuitArtifact]:
        with self._lock:
            if qasm and action in {"new_circuit", "modify_current"}:
                previous = conversation.active_artifact
                if action == "modify_current" and previous is not None:
                    artifact_id = previous.artifact_id
                    version = previous.version + 1
                else:
                    artifact_id = "circuit_" + secrets.token_urlsafe(10)
                    version = 1
                conversation.active_artifact = CircuitArtifact(
                    artifact_id=artifact_id,
                    version=version,
                    qasm=qasm,
                    goal=(
                        previous.goal
                        if action == "modify_current" and previous is not None
                        else user_text
                    ),
                    explanation=assistant_text,
                )
            conversation.turns.append(
                ConversationTurn(
                    user_text=user_text,
                    assistant_text=assistant_text,
                    action=action,
                )
            )
            del conversation.turns[:-self.max_turns]
            conversation.updated_at = self._clock()
            return conversation.active_artifact

    def delete(self, conversation_id: str) -> bool:
        """Immediately remove all turns and circuit state for one session."""
        with self._lock:
            return self._items.pop(conversation_id, None) is not None

    def _discard_expired(self, now: float) -> None:
        expired = [
            key
            for key, value in self._items.items()
            if now - value.updated_at > self.ttl_seconds
        ]
        for key in expired:
            del self._items[key]
