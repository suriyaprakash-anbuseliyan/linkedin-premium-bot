"""
utils/states.py
───────────────
Simple in-memory state machine for multi-step forms (admin product
creation, payment UTR/Order-ID input, admin credit management, etc.).

States are stored per-user in a dict and cleared after completion
or cancellation.  This keeps the codebase dependency-free and
Railway-friendly (no Redis needed for a single-process bot).
"""


class UserStates:
    """Thread-unsafe per-user state store (fine for polling mode)."""

    def __init__(self):
        self._states: dict[int, dict] = {}

    # ── getters / setters ────────────────────────────────────────────────
    def get(self, user_id: int) -> dict | None:
        return self._states.get(user_id)

    def get_field(self, user_id: int, field: str, default=None):
        state = self._states.get(user_id)
        if state is None:
            return default
        return state.get(field, default)

    def set(self, user_id: int, state: dict) -> None:
        self._states[user_id] = state

    def update(self, user_id: int, **kwargs) -> None:
        if user_id not in self._states:
            self._states[user_id] = {}
        self._states[user_id].update(kwargs)

    def clear(self, user_id: int) -> None:
        self._states.pop(user_id, None)

    def has(self, user_id: int) -> bool:
        return user_id in self._states


# ── Global singleton ─────────────────────────────────────────────────────
user_states = UserStates()
