from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

ReminderRepeatRule = Literal["once", "daily", "weekly"]
ReminderStatus = Literal["scheduled", "pending_ack", "completed"]


@dataclass
class Reminder:
    id: str
    character_id: str
    title: str
    note: str
    due_at: str
    repeat_rule: ReminderRepeatRule
    status: ReminderStatus
    created_at: str
    updated_at: str
    completed_at: str | None = None
    source: str = "admin"
    last_triggered_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "Reminder":
        repeat_rule = str(raw.get("repeat_rule") or "once")
        if repeat_rule not in {"once", "daily", "weekly"}:
            repeat_rule = "once"

        status = str(raw.get("status") or "scheduled")
        if status not in {"scheduled", "pending_ack", "completed"}:
            status = "scheduled"

        return cls(
            id=str(raw.get("id") or ""),
            character_id=str(raw.get("character_id") or ""),
            title=str(raw.get("title") or "").strip(),
            note=str(raw.get("note") or ""),
            due_at=str(raw.get("due_at") or ""),
            repeat_rule=repeat_rule,
            status=status,
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            completed_at=str(raw.get("completed_at")) if raw.get("completed_at") else None,
            source=str(raw.get("source") or "admin"),
            last_triggered_at=(
                str(raw.get("last_triggered_at"))
                if raw.get("last_triggered_at")
                else None
            ),
        )