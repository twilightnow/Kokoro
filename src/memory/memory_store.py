from __future__ import annotations

from typing import Optional, Protocol

from .record import MemoryMutationResult, MemoryRecord


class MemoryStore(Protocol):
    def read_records(self, character_id: str) -> dict[str, MemoryRecord]:
        ...

    def write_record(
        self,
        character_id: str,
        key: str,
        value: str,
        *,
        source: str = "user",
        memory_type: str = "fact",
        status: str = "confirmed",
        evidence: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[dict[str, object]] = None,
    ) -> MemoryMutationResult:
        ...

    def resolve_candidate(
        self,
        character_id: str,
        key: str,
        adopt_new: bool,
    ) -> MemoryMutationResult:
        ...

    def archive_records(
        self,
        character_id: str,
        *,
        key: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> int:
        ...