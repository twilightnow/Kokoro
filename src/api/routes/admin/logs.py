"""
会话日志 API。

GET    /admin/logs               会话文件列表（分页，按 mtime 倒序）
GET    /admin/logs/{filename}    单个会话文件内容（JSONL → JSON 数组）
DELETE /admin/logs               清空所有会话日志（危险操作）
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/logs")


def _log_dir() -> Path:
    return Path(os.environ.get("KOKORO_DATA_DIR", "./data")) / "logs"


class LogFileSummary(BaseModel):
    filename: str
    mtime: float
    size: int
    turn_count: int


class LogListResponse(BaseModel):
    items: List[LogFileSummary]
    total: int
    offset: int
    limit: int


def _count_turns(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


@router.get("", response_model=LogListResponse)
async def list_logs(
    offset: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
) -> LogListResponse:
    log_dir = _log_dir()
    if not log_dir.exists():
        return LogListResponse(items=[], total=0, offset=offset, limit=limit)

    files = sorted(
        (f for f in log_dir.iterdir() if f.suffix == ".jsonl" and f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    total = len(files)
    page = files[offset: offset + limit]
    items = [
        LogFileSummary(
            filename=f.name,
            mtime=f.stat().st_mtime,
            size=f.stat().st_size,
            turn_count=_count_turns(f),
        )
        for f in page
    ]
    return LogListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{filename}", response_model=List[Dict[str, Any]])
async def get_log(filename: str) -> List[Dict[str, Any]]:
    # 安全检查：防止路径穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    path = _log_dir() / filename
    if not path.exists() or path.suffix != ".jsonl":
        raise HTTPException(status_code=404, detail=f"日志文件不存在: {filename}")
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


@router.delete("", status_code=200)
async def clear_logs() -> Dict[str, Any]:
    log_dir = _log_dir()
    if not log_dir.exists():
        return {"status": "ok", "deleted": 0}
    count = 0
    for f in log_dir.iterdir():
        if f.suffix == ".jsonl" and f.is_file():
            f.unlink()
            count += 1
    return {"status": "ok", "deleted": count}
