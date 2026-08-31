"""Server-side stores for puzzles whose answer must stay hidden.

The Deutsch walkthrough only works if the secret is genuinely unknown to the
page: if the browser ever held the answer, the whole "you only get to ask
once" premise would be theatre. So the secret lives here and the client only
ever gets an opaque id back.

Sessions are deliberately in-memory and bounded.  This is a single-user demo
served from `python web_chat.py`, not a multi-tenant service, and losing a
session on restart is the correct behaviour: the user just starts a new round.
"""

from __future__ import annotations

import secrets
import threading
from collections import OrderedDict
from typing import Any, Dict


class SessionStore:
    """A bounded, thread-safe map of opaque id -> secret state."""

    def __init__(self, max_sessions: int = 256) -> None:
        self._lock = threading.Lock()
        self._items: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max = max_sessions

    @property
    def lock(self) -> threading.Lock:
        """Callers mutating counters need the same lock the store uses."""
        return self._lock

    def create(self, state: Dict[str, Any]) -> str:
        session_id = secrets.token_urlsafe(12)
        with self._lock:
            self._items[session_id] = state
            while len(self._items) > self._max:
                self._items.popitem(last=False)
        return session_id

    def get(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            state = self._items.get(session_id)
        if state is None:
            raise KeyError("这一局已经过期了，请重新开始一局。")
        return state
