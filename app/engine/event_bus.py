from __future__ import annotations

from typing import Callable


class EventBus:
    """Minimal synchronous pub/sub. The dashboard subscribes to push updates
    to the browser; the engine emits status/positions/trade/log events."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable]] = {}

    def on(self, event: str, callback: Callable) -> None:
        self._subs.setdefault(event, []).append(callback)

    def emit(self, event: str, payload=None) -> None:
        for cb in list(self._subs.get(event, [])):
            cb(payload)
