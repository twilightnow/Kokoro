from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

DEFAULT_MEMORY_TYPE = "fact"
ALLOWED_MEMORY_TYPES = {"fact", "preference", "boundary", "event"}

DEFAULT_MEMORY_STATUS = "confirmed"
ALLOWED_MEMORY_STATUSES = {"candidate", "confirmed", "rejected", "archived"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def new_memory_record_id() -> str:
    return uuid.uuid4().hex


def normalize_memory_type(value: Optional[str]) -> str:
    normalized = (value or DEFAULT_MEMORY_TYPE).strip().lower()
    if normalized not in ALLOWED_MEMORY_TYPES:
        return DEFAULT_MEMORY_TYPE
    return normalized


def normalize_memory_status(value: Optional[str]) -> str:
    normalized = (value or DEFAULT_MEMORY_STATUS).strip().lower()
    if normalized not in ALLOWED_MEMORY_STATUSES:
        return DEFAULT_MEMORY_STATUS
    return normalized


@dataclass
class MemoryRecord:
    """Canonical memory record used by the current JSON repository backend."""

    record_id: str
    character_id: str
    key: str
    value: str
    memory_type: str = DEFAULT_MEMORY_TYPE
    source: str = "user"
    status: str = DEFAULT_MEMORY_STATUS
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    supersedes_record_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def category(self) -> str:
        return self.memory_type

    @property
    def pending_confirm(self) -> bool:
        return self.status == "candidate"

    @property
    def pending_value(self) -> Optional[str]:
        if self.status != "candidate":
            return None
        return self.value

    @property
    def pending_category(self) -> Optional[str]:
        if self.status != "candidate":
            return None
        return self.memory_type


@dataclass
class MemoryMutationResult:
    action: str
    record: MemoryRecord
    related_record_id: Optional[str] = None