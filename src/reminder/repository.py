from __future__ import annotations

import json
from pathlib import Path

from ..config import get_data_dir
from .model import Reminder


class ReminderRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or get_data_dir())
        self._root = self._data_dir / "runtime" / "reminders"
        self._root.mkdir(parents=True, exist_ok=True)

    def path_for_character(self, character_id: str) -> Path:
        return self._root / f"{character_id}.json"

    def list(self, character_id: str) -> list[Reminder]:
        path = self.path_for_character(character_id)
        if not path.exists():
            return []

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(raw, list):
            return []

        reminders: list[Reminder] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            reminder = Reminder.from_dict(item)
            if reminder.id and reminder.character_id == character_id and reminder.title and reminder.due_at:
                reminders.append(reminder)

        reminders.sort(key=lambda item: (item.due_at, item.created_at, item.id))
        return reminders

    def save_all(self, character_id: str, reminders: list[Reminder]) -> None:
        path = self.path_for_character(character_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.to_dict() for item in sorted(reminders, key=lambda reminder: (reminder.due_at, reminder.created_at, reminder.id))]
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )