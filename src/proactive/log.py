from __future__ import annotations

import json
from pathlib import Path

from ..config import get_data_dir
from .action import ProactiveAction


class ProactiveLogRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or get_data_dir())
        self._path = self._data_dir / "runtime" / "proactive" / "events.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, action: ProactiveAction) -> None:
        with self._path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(action.to_dict(), ensure_ascii=False) + "\n")

    def list(self, limit: int = 50, character_id: str | None = None) -> list[dict[str, object]]:
        items = self._read_all()
        if character_id is not None:
            items = [item for item in items if item.get("character_id") == character_id]
        items.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        return items[:limit]

    def get(self, event_id: str) -> dict[str, object] | None:
        for item in self._read_all():
            if item.get("id") == event_id:
                return item
        return None

    def update_feedback(self, event_id: str, feedback: str | None, responded: bool) -> bool:
        items = self._read_all()
        updated = False
        for item in items:
            if item.get("id") != event_id:
                continue
            item["user_responded"] = responded
            item["feedback"] = feedback
            updated = True
            break

        if updated:
            self._write_all(items)
        return updated

    def _read_all(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []

        items: list[dict[str, object]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                items.append(raw)
        return items

    def _write_all(self, items: list[dict[str, object]]) -> None:
        self._path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + ("\n" if items else ""),
            encoding="utf-8",
        )