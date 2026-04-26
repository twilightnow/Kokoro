from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from .model import Reminder, ReminderRepeatRule
from .repository import ReminderRepository


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class RoutineReminderService:
    def __init__(self, repository: ReminderRepository) -> None:
        self._repository = repository

    def create(
        self,
        character_id: str,
        title: str,
        due_at: datetime,
        note: str = "",
        repeat_rule: ReminderRepeatRule = "once",
        source: str = "admin",
    ) -> Reminder:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("title is required")
        if repeat_rule not in {"once", "daily", "weekly"}:
            raise ValueError("invalid repeat_rule")

        now = datetime.now().isoformat()
        reminder = Reminder(
            id=f"rem_{uuid4().hex[:12]}",
            character_id=character_id,
            title=clean_title,
            note=note.strip(),
            due_at=due_at.isoformat(),
            repeat_rule=repeat_rule,
            status="scheduled",
            created_at=now,
            updated_at=now,
            completed_at=None,
            source=source,
            last_triggered_at=None,
        )
        reminders = self._repository.list(character_id)
        reminders.append(reminder)
        self._repository.save_all(character_id, reminders)
        return reminder

    def list(self, character_id: str, include_completed: bool = True) -> list[Reminder]:
        reminders = self._repository.list(character_id)
        if include_completed:
            return reminders
        return [item for item in reminders if item.status != "completed"]

    def get(self, character_id: str, reminder_id: str) -> Reminder | None:
        for item in self._repository.list(character_id):
            if item.id == reminder_id:
                return item
        return None

    def update(
        self,
        character_id: str,
        reminder_id: str,
        *,
        title: str | None = None,
        note: str | None = None,
        due_at: datetime | None = None,
        repeat_rule: ReminderRepeatRule | None = None,
        status: str | None = None,
    ) -> Reminder:
        reminders = self._repository.list(character_id)
        now = datetime.now().isoformat()

        for index, item in enumerate(reminders):
            if item.id != reminder_id:
                continue
            if title is not None:
                clean_title = title.strip()
                if not clean_title:
                    raise ValueError("title is required")
                item.title = clean_title
            if note is not None:
                item.note = note.strip()
            if due_at is not None:
                item.due_at = due_at.isoformat()
            if repeat_rule is not None:
                if repeat_rule not in {"once", "daily", "weekly"}:
                    raise ValueError("invalid repeat_rule")
                item.repeat_rule = repeat_rule
            if status is not None:
                if status not in {"scheduled", "pending_ack", "completed"}:
                    raise ValueError("invalid status")
                item.status = status
                if status != "completed":
                    item.completed_at = None
            item.updated_at = now
            reminders[index] = item
            self._repository.save_all(character_id, reminders)
            return item

        raise KeyError(reminder_id)

    def complete(
        self,
        character_id: str,
        reminder_id: str,
        completed_at: datetime | None = None,
    ) -> Reminder:
        reminders = self._repository.list(character_id)
        resolved_at = (completed_at or datetime.now()).isoformat()

        for index, item in enumerate(reminders):
            if item.id != reminder_id:
                continue
            item.status = "completed"
            item.completed_at = resolved_at
            item.updated_at = resolved_at
            reminders[index] = item
            self._repository.save_all(character_id, reminders)
            return item

        raise KeyError(reminder_id)

    def delete(self, character_id: str, reminder_id: str) -> bool:
        reminders = self._repository.list(character_id)
        filtered = [item for item in reminders if item.id != reminder_id]
        if len(filtered) == len(reminders):
            return False
        self._repository.save_all(character_id, filtered)
        return True

    def snooze(
        self,
        character_id: str,
        reminder_id: str,
        until: datetime,
    ) -> Reminder:
        reminders = self._repository.list(character_id)
        updated_at = datetime.now().isoformat()

        for index, item in enumerate(reminders):
            if item.id != reminder_id:
                continue
            item.due_at = until.isoformat()
            item.status = "scheduled"
            item.completed_at = None
            item.updated_at = updated_at
            reminders[index] = item
            self._repository.save_all(character_id, reminders)
            return item

        raise KeyError(reminder_id)

    def due(self, character_id: str, now: datetime | None = None) -> list[Reminder]:
        current_time = now or datetime.now()
        reminders = self._repository.list(character_id)
        due_items: list[Reminder] = []
        changed = False

        for item in reminders:
            if item.status != "scheduled":
                continue
            try:
                due_at = _parse_datetime(item.due_at)
            except ValueError:
                continue
            if due_at > current_time:
                continue

            item.last_triggered_at = current_time.isoformat()
            item.updated_at = current_time.isoformat()
            due_items.append(Reminder.from_dict(item.to_dict()))
            changed = True

            if item.repeat_rule == "once":
                item.status = "pending_ack"
            else:
                item.due_at = self._next_due_at(due_at, item.repeat_rule).isoformat()

        if changed:
            self._repository.save_all(character_id, reminders)

        due_items.sort(key=lambda item: (item.due_at, item.created_at, item.id))
        return due_items

    def _next_due_at(self, due_at: datetime, repeat_rule: ReminderRepeatRule) -> datetime:
        if repeat_rule == "daily":
            return due_at + timedelta(days=1)
        if repeat_rule == "weekly":
            return due_at + timedelta(days=7)
        return due_at