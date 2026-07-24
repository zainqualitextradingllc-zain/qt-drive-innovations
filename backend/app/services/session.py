"""In-memory session store (swap for Redis/Supabase in production)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SessionState:
    session_id: str
    language: str = "en"
    messages: list[dict[str, str]] = field(default_factory=list)
    vehicle: dict[str, Any] | None = None
    questions_asked_count: int = 0
    # Last strong RAG hits for this session (cost hard-quote + grounding carry-over)
    last_strong_rag_hits: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str | None, language: str = "en") -> SessionState:
        if session_id and session_id in self._sessions:
            state = self._sessions[session_id]
            state.language = language
            state.updated_at = datetime.now(timezone.utc).isoformat()
            return state
        new_id = session_id or str(uuid.uuid4())
        state = SessionState(session_id=new_id, language=language)
        self._sessions[new_id] = state
        return state

    def save(self, state: SessionState) -> None:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        self._sessions[state.session_id] = state


session_store = SessionStore()
