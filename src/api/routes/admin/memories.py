"""
记忆管理 API。

GET    /admin/memories/{id}/facts          长期事实列表
POST   /admin/memories/{id}/facts          新增事实
PUT    /admin/memories/{id}/facts/{key}    修改事实（采用新值 / 保留旧值）
DELETE /admin/memories/{id}/facts/{key}    删除事实

GET    /admin/memories/{id}/summaries      摘要列表（分页）
DELETE /admin/memories/{id}/summaries/{idx} 删除单条摘要
DELETE /admin/memories/{id}               清空角色全部记忆（危险）
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...service_registry import get_service
from ....memory.long_term_memory import LongTermMemory, normalize_fact_category
from ....memory.record import MemoryRecord

router = APIRouter(prefix="/memories")


def _data_dir() -> Path:
    return Path(os.environ.get("KOKORO_DATA_DIR", "./data"))


def _facts_path(character_id: str) -> Path:
    return _data_dir() / "memories" / character_id / "facts.json"


def _summaries_path(character_id: str) -> Path:
    return _data_dir() / "memories" / character_id / "summaries.jsonl"


def _load_facts(character_id: str) -> Dict[str, Any]:
    path = _facts_path(character_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_facts(character_id: str, data: Dict[str, Any]) -> None:
    path = _facts_path(character_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _memory_store() -> LongTermMemory:
    return LongTermMemory(_data_dir())


class FactItem(BaseModel):
    record_id: str
    key: str
    value: str
    category: str = "fact"
    source: str = "user"
    status: str = "confirmed"
    updated_at: str = ""
    pending_confirm: bool = False
    pending_value: Optional[str] = None
    pending_category: Optional[str] = None
    evidence: Optional[str] = None
    confidence: Optional[float] = None
    supersedes_record_id: Optional[str] = None


class FactUpsertRequest(BaseModel):
    value: str
    source: str = "user"
    category: Optional[str] = None


class FactResolveRequest(BaseModel):
    """处理冲突事实：adopt_new=True 采用新值，否则保留旧值。"""
    adopt_new: bool


class SummaryItem(BaseModel):
    index: int
    summary: str
    created_at: str


class SummaryUpdateRequest(BaseModel):
    summary: str


class MemoryExportResponse(BaseModel):
    character_id: str
    exported_at: str
    facts: List[FactItem]
    summaries: List[SummaryItem]


class SummaryListResponse(BaseModel):
    items: List[SummaryItem]
    total: int
    offset: int
    limit: int


async def _list_facts_impl(
    character_id: str,
    category: Optional[str] = None,
    query: str = "",
) -> List[FactItem]:
    store = _memory_store()
    records = store.read_records(character_id)
    result: List[FactItem] = []
    normalized_category = normalize_fact_category(category) if category else None
    search = query.strip().lower()
    grouped: Dict[str, Dict[str, Optional[MemoryRecord]]] = {}
    for record in records.values():
        if record.status in {"archived", "rejected"}:
            continue
        slot = grouped.setdefault(record.key, {"confirmed": None, "candidate": None})
        current = slot.get(record.status)
        if record.status in {"confirmed", "candidate"} and (
            current is None or (current.updated_at, current.record_id) < (record.updated_at, record.record_id)
        ):
            slot[record.status] = record

    for key, slot in grouped.items():
        confirmed = slot.get("confirmed")
        candidate = slot.get("candidate")
        primary = confirmed or candidate
        if primary is None:
            continue
        item = FactItem(
            record_id=primary.record_id,
            key=primary.key,
            value=primary.value,
            category=normalize_fact_category(primary.memory_type),
            source=primary.source,
            status=primary.status,
            updated_at=primary.updated_at,
            pending_confirm=candidate is not None,
            pending_value=(candidate.value if confirmed and candidate else None),
            pending_category=(candidate.memory_type if confirmed and candidate else None),
            evidence=primary.evidence,
            confidence=primary.confidence,
            supersedes_record_id=primary.supersedes_record_id,
        )
        if normalized_category and item.category != normalized_category:
            continue
        if search and search not in item.key.lower() and search not in item.value.lower():
            continue
        result.append(item)
    result.sort(key=lambda item: item.updated_at, reverse=True)
    return result


@router.get("/{character_id}/facts", response_model=List[FactItem])
async def list_facts(
    character_id: str,
    category: Optional[str] = Query(default=None),
    query: str = Query(default=""),
) -> List[FactItem]:
    return await _list_facts_impl(character_id, category=category, query=query)


@router.post("/{character_id}/facts", status_code=201)
async def create_fact(
    character_id: str,
    body: FactUpsertRequest,
    key: str = Query(..., description="事实键名"),
) -> Dict[str, str]:
    normalized_category = normalize_fact_category(body.category)
    mutation = _memory_store().write_record(
        character_id,
        key,
        body.value,
        source=body.source,
        memory_type=normalized_category,
        status="confirmed",
    )
    return {
        "status": mutation.action,
        "key": key,
        "category": normalized_category,
        "record_id": mutation.record.record_id,
    }


@router.put("/{character_id}/facts/{key}", status_code=200)
async def update_fact(
    character_id: str,
    key: str,
    body: FactUpsertRequest,
) -> Dict[str, str]:
    existing = await _list_facts_impl(character_id, query=key)
    if not any(item.key == key for item in existing):
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    current_category = next((item.category for item in existing if item.key == key), "fact")
    next_category = normalize_fact_category(body.category or current_category)
    mutation = _memory_store().write_record(
        character_id,
        key,
        body.value,
        source=body.source,
        memory_type=next_category,
        status="confirmed",
    )
    return {
        "status": mutation.action,
        "key": key,
        "category": next_category,
        "record_id": mutation.record.record_id,
    }


@router.post("/{character_id}/facts/{key}/resolve", status_code=200)
async def resolve_conflict(
    character_id: str,
    key: str,
    body: FactResolveRequest,
) -> Dict[str, str]:
    try:
        mutation = _memory_store().resolve_candidate(character_id, key, body.adopt_new)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    return {
        "status": mutation.action,
        "key": key,
        "action": "adopted" if body.adopt_new else "kept",
        "record_id": mutation.record.record_id,
    }


@router.delete("/{character_id}/facts/{key}", status_code=200)
async def delete_fact(character_id: str, key: str) -> Dict[str, str]:
    removed = _memory_store().archive_records(character_id, key=key)
    if not removed:
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    return {"status": "deleted", "key": key}


@router.get("/{character_id}/summaries", response_model=SummaryListResponse)
async def list_summaries(
    character_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> SummaryListResponse:
    path = _summaries_path(character_id)
    if not path.exists():
        return SummaryListResponse(items=[], total=0, offset=offset, limit=limit)

    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = len(lines)
    # 倒序（最新在前）
    lines_reversed = list(reversed(lines))
    page = lines_reversed[offset: offset + limit]
    items = []
    for idx, line in enumerate(page):
        try:
            record = json.loads(line)
            items.append(SummaryItem(
                index=total - 1 - (offset + idx),  # 原始文件中的行号
                summary=record.get("summary", ""),
                created_at=record.get("created_at", ""),
            ))
        except (json.JSONDecodeError, KeyError):
            pass
    return SummaryListResponse(items=items, total=total, offset=offset, limit=limit)


@router.put("/{character_id}/summaries/{index}", status_code=200)
async def update_summary(character_id: str, index: int, body: SummaryUpdateRequest) -> Dict[str, Any]:
    summary = body.summary.strip()
    if not summary:
        raise HTTPException(status_code=422, detail="摘要不能为空")

    path = _summaries_path(character_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="摘要文件不存在")

    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if index < 0 or index >= len(lines):
        raise HTTPException(status_code=404, detail=f"摘要索引越界: {index}")

    try:
        record = json.loads(lines[index])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"摘要记录损坏: {exc}")

    record["summary"] = summary[:100]
    lines[index] = json.dumps(record, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": "updated", "index": index}


@router.delete("/{character_id}/summaries/{index}", status_code=200)
async def delete_summary(character_id: str, index: int) -> Dict[str, str]:
    path = _summaries_path(character_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="摘要文件不存在")
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if index < 0 or index >= len(lines):
        raise HTTPException(status_code=404, detail=f"摘要索引越界: {index}")
    lines.pop(index)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return {"status": "deleted", "index": index}


@router.get("/{character_id}/export", response_model=MemoryExportResponse)
async def export_memories(character_id: str) -> MemoryExportResponse:
    from datetime import datetime, timezone

    facts = await _list_facts_impl(character_id)
    summaries_path = _summaries_path(character_id)
    summary_items: List[SummaryItem] = []
    if summaries_path.exists():
        lines = [line.strip() for line in summaries_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for index, line in enumerate(lines):
            try:
                record = json.loads(line)
                summary_items.append(SummaryItem(
                    index=index,
                    summary=record.get("summary", ""),
                    created_at=record.get("created_at", ""),
                ))
            except json.JSONDecodeError:
                continue
    return MemoryExportResponse(
        character_id=character_id,
        exported_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        facts=facts,
        summaries=summary_items,
    )


@router.delete("/{character_id}", status_code=200)
async def clear_memories(
    character_id: str,
    kind: str = Query(default="all"),
) -> Dict[str, Any]:
    """清空角色全部或指定类型记忆。"""
    normalized_kind = kind.strip().lower()
    if normalized_kind not in {"all", "summaries", "facts", "preferences", "boundaries", "events"}:
        raise HTTPException(status_code=422, detail=f"不支持的清空类型: {kind}")

    deleted = []

    if normalized_kind in {"all", "summaries"}:
        summary_path = _data_dir() / "memories" / character_id / "summaries.jsonl"
        if summary_path.exists():
            summary_path.unlink()
            deleted.append("summaries.jsonl")

    if normalized_kind == "all":
        truncation_path = _data_dir() / "memories" / character_id / "truncation.log"
        if truncation_path.exists():
            truncation_path.unlink()
            deleted.append("truncation.log")

    if normalized_kind in {"all", "facts", "preferences", "boundaries", "events"}:
        if normalized_kind == "all":
            if _facts_path(character_id).exists():
                _facts_path(character_id).unlink()
                deleted.append("facts.json")
        else:
            category_map = {
                "facts": "fact",
                "preferences": "preference",
                "boundaries": "boundary",
                "events": "event",
            }
            target_category = category_map[normalized_kind]
            removed = _memory_store().archive_records(
                character_id,
                memory_type=target_category,
            )
            if removed:
                deleted.append(f"facts:{target_category}:{removed}")

    return {"status": "cleared", "kind": normalized_kind, "deleted": deleted}
