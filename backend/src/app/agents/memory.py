from __future__ import annotations

import threading
from collections import OrderedDict

from app.agents.contracts import ConversationTurn

_MAX_CONVERSATIONS = 200
_MAX_TURNS_PER_CONVERSATION = 12


class ConversationMemory:
    """Thread-safe in-memory conversation buffer keyed by conversation_id."""

    def __init__(
        self,
        max_conversations: int = _MAX_CONVERSATIONS,
        max_turns: int = _MAX_TURNS_PER_CONVERSATION,
    ) -> None:
        self._max_conversations = max_conversations
        self._max_turns = max_turns
        self._store: OrderedDict[str, list[ConversationTurn]] = OrderedDict()
        self._lock = threading.Lock()

    def get_history(self, conversation_id: str) -> list[ConversationTurn]:
        with self._lock:
            turns = self._store.get(conversation_id, [])
            return list(turns)

    def add_turn(self, conversation_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            if conversation_id not in self._store:
                if len(self._store) >= self._max_conversations:
                    self._store.popitem(last=False)
                self._store[conversation_id] = []
            else:
                self._store.move_to_end(conversation_id)

            turns = self._store[conversation_id]
            turns.append(turn)
            if len(turns) > self._max_turns:
                self._store[conversation_id] = turns[-self._max_turns :]

    def format_history_for_prompt(self, conversation_id: str) -> str:
        turns = self.get_history(conversation_id)
        if not turns:
            return ""

        lines = ["=== CONVERSATION HISTORY (most recent last) ==="]
        for turn in turns[-6:]:
            prefix = "USER" if turn.role == "user" else "ASSISTANT"
            line = f"[{prefix}]: {turn.message[:300]}"
            if turn.sql:
                line += f"\n  SQL: {turn.sql[:200]}"
            if turn.row_count is not None:
                line += f"\n  Rows: {turn.row_count}"
            lines.append(line)
        lines.append("=== END HISTORY ===")
        return "\n".join(lines)
