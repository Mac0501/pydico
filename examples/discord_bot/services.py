from collections import deque
from threading import RLock

from examples.discord_bot.resources import CommandSession


class AuditLog:
    def __init__(self) -> None:
        self._entries: deque[str] = deque(maxlen=20)
        self._lock = RLock()

    def record(self, entry: str) -> None:
        with self._lock:
            self._entries.append(entry)

    def recent(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._entries)


class GreetingService:
    def __init__(self, session: CommandSession, audit_log: AuditLog) -> None:
        self._session = session
        self._audit_log = audit_log

    def greet(self, display_name: str) -> str:
        self._audit_log.record(f"{self._session.id}: greeted {display_name}")
        return f"Hello {display_name}! Command session: {self._session.id}"
