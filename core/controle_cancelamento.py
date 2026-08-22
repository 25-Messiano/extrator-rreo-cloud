from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event


@dataclass
class CancellationToken:
    _event: Event = field(default_factory=Event)

    def request(self) -> None:
        self._event.set()

    def clear(self) -> None:
        self._event.clear()

    @property
    def requested(self) -> bool:
        return self._event.is_set()


class ProcessingCancelled(RuntimeError):
    pass
