"""An append-only record store.

Deliberately small. The point is the ownership contract, not persistence: a
record is written once, never mutated, and a correction is a new record that
points at the one it supersedes. A deployment would back this with an append-only
table; the behaviour it has to preserve is here.

Audit events carry no prompt or transcript content. sec:design's audit
record is specified as "Actor, action, object version, time" and explicitly not
the student's words - an audit trail that quoted the prompts would recreate, in a
log file, exactly the named diagnostic history the framework forbids.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


class OverwriteRejected(RuntimeError):
    """Raised when an identifier is reused. Records are written once."""


@dataclass(frozen=True)
class AuditEvent:
    actor: str
    action: str
    object_type: str
    object_id: str

    #: No prompt_text, no stated_intent, no transcript. Not an oversight.
    def __str__(self) -> str:
        return f"{self.actor} {self.action} {self.object_type}:{self.object_id}"


@dataclass
class Store:
    _records: dict[str, Any] = field(default_factory=dict)
    _scores: dict[str, dict] = field(default_factory=dict)
    _superseded_by: dict[str, str] = field(default_factory=dict)
    audit: list[AuditEvent] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def append(self, key: str, record: Any, actor: str = "system") -> None:
        with self._lock:
            if key in self._records:
                raise OverwriteRejected(
                    f"{key} already exists. A correction is a new record that "
                    "supersedes the old one, not an edit to it."
                )
            self._records[key] = record
            self.audit.append(
                AuditEvent(
                    actor=actor,
                    action="append",
                    object_type=type(record).__name__,
                    object_id=key,
                )
            )

    def supersede(self, old_key: str, new_key: str, record: Any) -> None:
        with self._lock:
            self.append(new_key, record)
            self._superseded_by[old_key] = new_key

    def current(self, key: str) -> Any:
        seen: set[str] = set()
        while key in self._superseded_by and key not in seen:
            seen.add(key)
            key = self._superseded_by[key]
        return self._records.get(key)

    def get(self, key: str) -> Any:
        return self._records.get(key)

    def remember_scores(self, attempt_id: str, scores: dict) -> None:
        with self._lock:
            self._scores[attempt_id] = scores

    def scores_for(self, attempt_id: str) -> dict | None:
        return self._scores.get(attempt_id)

    def __len__(self) -> int:
        return len(self._records)
