"""
长期记忆：存储用户明确说出的已确认事实。

存储格式：memories/<character_id>/facts.json
写入原则：
  - 用户明确说出的事实才进入长期记忆
  - 同一 key 出现不同值时，标记 pending_confirm=True，不直接覆盖
"""
import json
from pathlib import Path
from typing import Dict, Optional

from .memory_store import MemoryStore
from .record import (
    MemoryMutationResult,
    MemoryRecord,
    new_memory_record_id,
    normalize_memory_status,
    normalize_memory_type,
)


def normalize_fact_category(value: Optional[str]) -> str:
    return normalize_memory_type(value)


class JsonMemoryStore:
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

    def _serialize_record(self, record: MemoryRecord) -> dict:
        return {
            "record_id": record.record_id,
            "character_id": record.character_id,
            "key": record.key,
            "value": record.value,
            "memory_type": normalize_memory_type(record.memory_type),
            "source": record.source,
            "status": normalize_memory_status(record.status),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "evidence": record.evidence,
            "confidence": record.confidence,
            "supersedes_record_id": record.supersedes_record_id,
            "metadata": record.metadata,
        }

    def _record_from_new_dict(
        self,
        character_id: str,
        raw_key: str,
        data: dict,
    ) -> MemoryRecord:
        record_id = str(data.get("record_id") or raw_key)
        created_at = str(data.get("created_at") or data.get("updated_at") or "")
        updated_at = str(data.get("updated_at") or created_at)
        return MemoryRecord(
            record_id=record_id,
            character_id=str(data.get("character_id") or character_id),
            key=str(data.get("key") or raw_key),
            value=str(data.get("value") or ""),
            memory_type=normalize_memory_type(data.get("memory_type") or data.get("category")),
            source=str(data.get("source") or "user"),
            status=normalize_memory_status(data.get("status") or "confirmed"),
            created_at=created_at,
            updated_at=updated_at,
            evidence=data.get("evidence") if isinstance(data.get("evidence"), str) else None,
            confidence=float(data["confidence"]) if isinstance(data.get("confidence"), (int, float)) else None,
            supersedes_record_id=(
                str(data.get("supersedes_record_id"))
                if data.get("supersedes_record_id")
                else None
            ),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )

    def _records_from_legacy_entry(
        self,
        character_id: str,
        raw_key: str,
        data: dict,
    ) -> list[MemoryRecord]:
        key = str(data.get("key") or raw_key)
        base_record_id = str(data.get("record_id") or f"legacy:{key}")
        updated_at = str(data.get("updated_at") or "")
        category = normalize_memory_type(data.get("category"))
        records = [
            MemoryRecord(
                record_id=base_record_id,
                character_id=character_id,
                key=key,
                value=str(data.get("value") or ""),
                memory_type=category,
                source=str(data.get("source") or "user"),
                status="confirmed",
                created_at=updated_at,
                updated_at=updated_at,
            )
        ]
        pending_value = data.get("pending_value")
        if data.get("pending_confirm") and isinstance(pending_value, str) and pending_value.strip():
            records.append(
                MemoryRecord(
                    record_id=f"{base_record_id}:candidate",
                    character_id=character_id,
                    key=key,
                    value=pending_value.strip(),
                    memory_type=normalize_memory_type(data.get("pending_category") or category),
                    source="llm_extract",
                    status="candidate",
                    created_at=updated_at,
                    updated_at=updated_at,
                    supersedes_record_id=base_record_id,
                )
            )
        return records

    def _save_records(self, character_id: str, records: Dict[str, MemoryRecord]) -> None:
        raw = {
            record_id: self._serialize_record(record)
            for record_id, record in sorted(records.items(), key=lambda item: item[0])
        }
        self._save_raw(character_id, raw)

    def read_records(self, character_id: str) -> Dict[str, MemoryRecord]:
        """读取所有结构化记忆记录。"""
        raw = self._load_raw(character_id)
        result: Dict[str, MemoryRecord] = {}
        for key, d in raw.items():
            if not isinstance(d, dict):
                continue
            if "status" in d or "memory_type" in d or "record_id" in d:
                record = self._record_from_new_dict(character_id, key, d)
                result[record.record_id] = record
                continue
            for record in self._records_from_legacy_entry(character_id, key, d):
                result[record.record_id] = record
        return result

    def _active_records_for_key(
        self,
        records: Dict[str, MemoryRecord],
        key: str,
        *,
        status: Optional[str] = None,
    ) -> list[MemoryRecord]:
        matches = [
            record
            for record in records.values()
            if record.key == key and record.status not in {"archived", "rejected"}
        ]
        if status is not None:
            normalized_status = normalize_memory_status(status)
            matches = [record for record in matches if record.status == normalized_status]
        matches.sort(key=lambda record: (record.updated_at, record.created_at, record.record_id), reverse=True)
        return matches

    def _archive_competing_records(
        self,
        records: Dict[str, MemoryRecord],
        key: str,
        *,
        exclude_record_id: Optional[str] = None,
        statuses: tuple[str, ...] = ("candidate",),
    ) -> None:
        for record in records.values():
            if record.key != key or record.record_id == exclude_record_id:
                continue
            if record.status not in statuses:
                continue
            record.status = "archived"

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
        records = self.read_records(character_id)
        normalized_type = normalize_memory_type(memory_type)
        normalized_status = normalize_memory_status(status)
        now = new_memory_record_id()
        active_confirmed = self._active_records_for_key(records, key, status="confirmed")
        current_confirmed = active_confirmed[0] if active_confirmed else None
        if normalized_status == "candidate":
            existing_candidates = self._active_records_for_key(records, key, status="candidate")
            for candidate in existing_candidates:
                if candidate.value == value and candidate.memory_type == normalized_type:
                    return MemoryMutationResult(action="noop", record=candidate)
            record = MemoryRecord(
                record_id=now,
                character_id=character_id,
                key=key,
                value=value,
                memory_type=normalized_type,
                source=source,
                status="candidate",
                evidence=evidence,
                confidence=confidence,
                supersedes_record_id=current_confirmed.record_id if current_confirmed else None,
                metadata=dict(metadata or {}),
            )
            records[record.record_id] = record
            self._save_records(character_id, records)
            return MemoryMutationResult(
                action="candidate_created",
                record=record,
                related_record_id=current_confirmed.record_id if current_confirmed else None,
            )

        if current_confirmed and current_confirmed.value == value and current_confirmed.memory_type == normalized_type:
            current_confirmed.updated_at = current_confirmed.updated_at or current_confirmed.created_at
            records[current_confirmed.record_id] = current_confirmed
            self._save_records(character_id, records)
            return MemoryMutationResult(action="noop", record=current_confirmed)

        if current_confirmed and normalized_type != "event":
            current_confirmed.status = "archived"
            records[current_confirmed.record_id] = current_confirmed

        record = MemoryRecord(
            record_id=now,
            character_id=character_id,
            key=key,
            value=value,
            memory_type=normalized_type,
            source=source,
            status="confirmed",
            evidence=evidence,
            confidence=confidence,
            supersedes_record_id=current_confirmed.record_id if current_confirmed else None,
            metadata=dict(metadata or {}),
        )
        records[record.record_id] = record
        self._archive_competing_records(records, key, exclude_record_id=record.record_id)
        self._save_records(character_id, records)
        return MemoryMutationResult(
            action="confirmed_replaced" if current_confirmed else "created",
            record=record,
            related_record_id=current_confirmed.record_id if current_confirmed else None,
        )

    def resolve_candidate(
        self,
        character_id: str,
        key: str,
        adopt_new: bool,
    ) -> MemoryMutationResult:
        records = self.read_records(character_id)
        candidates = self._active_records_for_key(records, key, status="candidate")
        if not candidates:
            raise KeyError(key)
        candidate = candidates[0]
        if adopt_new:
            confirmed = self._active_records_for_key(records, key, status="confirmed")
            if confirmed:
                confirmed[0].status = "archived"
                records[confirmed[0].record_id] = confirmed[0]
            candidate.status = "confirmed"
            records[candidate.record_id] = candidate
            self._archive_competing_records(records, key, exclude_record_id=candidate.record_id)
            self._save_records(character_id, records)
            return MemoryMutationResult(
                action="candidate_adopted",
                record=candidate,
                related_record_id=candidate.supersedes_record_id,
            )

        candidate.status = "rejected"
        records[candidate.record_id] = candidate
        self._save_records(character_id, records)
        return MemoryMutationResult(
            action="candidate_rejected",
            record=candidate,
            related_record_id=candidate.supersedes_record_id,
        )

    def archive_records(
        self,
        character_id: str,
        *,
        key: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> int:
        records = self.read_records(character_id)
        removed = 0
        normalized_type = normalize_memory_type(memory_type) if memory_type else None
        for record in records.values():
            if key and record.key != key:
                continue
            if normalized_type and record.memory_type != normalized_type:
                continue
            if record.status in {"archived", "rejected"}:
                continue
            record.status = "archived"
            removed += 1
        if removed:
            self._save_records(character_id, records)
        return removed

    def read_facts(self, character_id: str) -> Dict[str, MemoryRecord]:
        """兼容接口：按 key 返回当前活跃记录，优先 confirmed，其次 candidate。"""
        records = self.read_records(character_id)
        result: Dict[str, MemoryRecord] = {}
        for record in sorted(
            records.values(),
            key=lambda item: (
                item.status != "confirmed",
                item.updated_at,
                item.created_at,
                item.record_id,
            ),
        ):
            if record.status in {"archived", "rejected"}:
                continue
            result[record.key] = record
        return result

    def write_fact(
        self,
        character_id: str,
        key: str,
        value: str,
        source: str = "user",
        category: str = "fact",
        status: str = "confirmed",
    ) -> None:
        normalized_category = normalize_fact_category(category)
        normalized_status = normalize_memory_status(status)
        if normalized_status == "confirmed" and normalized_category != "event":
            records = self.read_records(character_id)
            confirmed = self._active_records_for_key(records, key, status="confirmed")
            if confirmed:
                current = confirmed[0]
                if current.value != value or current.memory_type != normalized_category:
                    self.write_record(
                        character_id,
                        key,
                        value,
                        source=source,
                        memory_type=normalized_category,
                        status="candidate",
                    )
                    return

        self.write_record(
            character_id,
            key,
            value,
            source=source,
            memory_type=normalized_category,
            status=normalized_status,
        )

    def flag_conflict(
        self,
        character_id: str,
        key: str,
        new_value: str,
        new_category: str = "fact",
    ) -> None:
        self.write_record(
            character_id,
            key,
            new_value,
            source="llm_extract",
            memory_type=new_category,
            status="candidate",
        )

    def get_confirmed_facts(self, character_id: str) -> Dict[str, str]:
        """返回所有已确认事实的 key→value 字典。"""
        records = self.read_records(character_id)
        return {
            record.key: record.value
            for record in records.values()
            if record.status == "confirmed"
        }


LongTermMemory = JsonMemoryStore
FactRecord = MemoryRecord
