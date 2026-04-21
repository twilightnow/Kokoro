"""
长期记忆：存储用户明确说出的已确认事实。

存储格式：memories/<character_id>/facts.json
写入原则：
  - 用户明确说出的事实才进入长期记忆
  - 同一 key 出现不同值时，标记 pending_confirm=True，不直接覆盖
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


@dataclass
class FactRecord:
    """长期记忆中的单条事实记录。"""

    key: str
    value: str
    source: str = "user"
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    pending_confirm: bool = False
    pending_value: Optional[str] = None


class LongTermMemory:
    """长期记忆：存储用户明确说出的已确认事实。

    按角色隔离存储，不同角色不共享 facts.json。
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _facts_path(self, character_id: str) -> Path:
        path = self._data_dir / "memories" / character_id / "facts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _load_raw(self, character_id: str) -> Dict[str, dict]:
        path = self._facts_path(character_id)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_raw(self, character_id: str, data: Dict[str, dict]) -> None:
        path = self._facts_path(character_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def read_facts(self, character_id: str) -> Dict[str, FactRecord]:
        """读取所有事实记录（含待确认）。"""
        raw = self._load_raw(character_id)
        result: Dict[str, FactRecord] = {}
        for key, d in raw.items():
            result[key] = FactRecord(
                key=d.get("key", key),
                value=d.get("value", ""),
                source=d.get("source", "user"),
                updated_at=d.get("updated_at", ""),
                pending_confirm=d.get("pending_confirm", False),
                pending_value=d.get("pending_value"),
            )
        return result

    def write_fact(
        self,
        character_id: str,
        key: str,
        value: str,
        source: str = "user",
    ) -> None:
        """写入一条事实。如果 key 已存在且值不同，触发冲突标记。"""
        raw = self._load_raw(character_id)
        existing = raw.get(key)
        if existing and existing.get("value") != value:
            self.flag_conflict(character_id, key, value)
            return
        raw[key] = asdict(FactRecord(key=key, value=value, source=source))
        self._save_raw(character_id, raw)

    def flag_conflict(
        self,
        character_id: str,
        key: str,
        new_value: str,
    ) -> None:
        """标记冲突：保留旧值，标记 pending_confirm=True，不直接覆盖。"""
        raw = self._load_raw(character_id)
        if key in raw:
            raw[key]["pending_confirm"] = True
            raw[key]["pending_value"] = new_value
        else:
            rec = FactRecord(
                key=key,
                value=new_value,
                source="conflict",
                pending_confirm=True,
            )
            raw[key] = asdict(rec)
        self._save_raw(character_id, raw)

    def get_confirmed_facts(self, character_id: str) -> Dict[str, str]:
        """返回所有已确认事实（pending_confirm=False）的 key→value 字典。"""
        facts = self.read_facts(character_id)
        return {k: v.value for k, v in facts.items() if not v.pending_confirm}
