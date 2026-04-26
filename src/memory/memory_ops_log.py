from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class MemoryOpsLog:
    """Append-only operation log for memory ingestion and persistence events."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _log_path(self, character_id: str) -> Path:
        path = self._data_dir / "memories" / character_id / "memory_ops.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def record(self, character_id: str, event: str, **details: Any) -> None:
        payload = {
            "time": datetime.now().isoformat(),
            "event": event,
            "details": details,
        }
        with open(self._log_path(character_id), "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")