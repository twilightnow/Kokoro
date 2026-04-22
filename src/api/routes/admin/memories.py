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


class FactItem(BaseModel):
    key: str
    value: str
    source: str = "user"
    updated_at: str = ""
    pending_confirm: bool = False
    pending_value: Optional[str] = None


class FactUpsertRequest(BaseModel):
    value: str
    source: str = "user"


class FactResolveRequest(BaseModel):
    """处理冲突事实：adopt_new=True 采用新值，否则保留旧值。"""
    adopt_new: bool


class SummaryItem(BaseModel):
    index: int
    summary: str
    created_at: str


class SummaryListResponse(BaseModel):
    items: List[SummaryItem]
    total: int
    offset: int
    limit: int


@router.get("/{character_id}/facts", response_model=List[FactItem])
async def list_facts(character_id: str) -> List[FactItem]:
    raw = _load_facts(character_id)
    result = []
    for key, d in raw.items():
        result.append(FactItem(
            key=d.get("key", key),
            value=d.get("value", ""),
            source=d.get("source", "user"),
            updated_at=d.get("updated_at", ""),
            pending_confirm=d.get("pending_confirm", False),
            pending_value=d.get("pending_value"),
        ))
    return result


@router.post("/{character_id}/facts", status_code=201)
async def create_fact(
    character_id: str,
    body: FactUpsertRequest,
    key: str = Query(..., description="事实键名"),
) -> Dict[str, str]:
    from datetime import datetime
    raw = _load_facts(character_id)
    raw[key] = {
        "key": key,
        "value": body.value,
        "source": body.source,
        "updated_at": datetime.now().isoformat(),
        "pending_confirm": False,
        "pending_value": None,
    }
    _save_facts(character_id, raw)
    return {"status": "created", "key": key}


@router.put("/{character_id}/facts/{key}", status_code=200)
async def update_fact(
    character_id: str,
    key: str,
    body: FactUpsertRequest,
) -> Dict[str, str]:
    from datetime import datetime
    raw = _load_facts(character_id)
    if key not in raw:
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    raw[key].update({
        "value": body.value,
        "source": body.source,
        "updated_at": datetime.now().isoformat(),
        "pending_confirm": False,
        "pending_value": None,
    })
    _save_facts(character_id, raw)
    return {"status": "updated", "key": key}


@router.post("/{character_id}/facts/{key}/resolve", status_code=200)
async def resolve_conflict(
    character_id: str,
    key: str,
    body: FactResolveRequest,
) -> Dict[str, str]:
    from datetime import datetime
    raw = _load_facts(character_id)
    if key not in raw:
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    record = raw[key]
    if body.adopt_new and record.get("pending_value"):
        record["value"] = record["pending_value"]
        record["updated_at"] = datetime.now().isoformat()
    record["pending_confirm"] = False
    record["pending_value"] = None
    _save_facts(character_id, raw)
    return {"status": "resolved", "key": key, "action": "adopted" if body.adopt_new else "kept"}


@router.delete("/{character_id}/facts/{key}", status_code=200)
async def delete_fact(character_id: str, key: str) -> Dict[str, str]:
    raw = _load_facts(character_id)
    if key not in raw:
        raise HTTPException(status_code=404, detail=f"事实不存在: {key}")
    del raw[key]
    _save_facts(character_id, raw)
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


@router.delete("/{character_id}", status_code=200)
async def clear_memories(character_id: str) -> Dict[str, str]:
    """清空角色全部记忆（facts.json + summaries.jsonl）。危险操作。"""
    deleted = []
    for fname in ["facts.json", "summaries.jsonl", "truncation.log"]:
        p = _data_dir() / "memories" / character_id / fname
        if p.exists():
            p.unlink()
            deleted.append(fname)
    return {"status": "cleared", "deleted": deleted}
