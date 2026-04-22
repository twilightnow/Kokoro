"""
情绪统计 API（带内存缓存，60 秒过期）。

GET /admin/stats/emotion?days=30   时序数据（按日期聚合各情绪出现次数）
GET /admin/stats/triggers?top=10   触发词频率排行（mood_before != mood_after 时统计）
"""
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from ...service_registry import get_service

router = APIRouter(prefix="/stats")

_CACHE_TTL = 60  # 秒

# 简单的内存缓存结构: {cache_key: (timestamp, data)}
_cache: Dict[str, tuple] = {}


def _log_dir() -> Path:
    return Path(os.environ.get("KOKORO_DATA_DIR", "./data")) / "logs"


def _cache_get(key: str) -> Optional[Any]:
    if key in _cache:
        ts, data = _cache[key]
        if time.monotonic() - ts < _CACHE_TTL:
            return data
    return None


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (time.monotonic(), data)


def _scan_log_records(days: int) -> List[Dict[str, Any]]:
    """扫描最近 days 天的日志文件，返回所有记录。"""
    cutoff = datetime.now() - timedelta(days=days)
    log_dir = _log_dir()
    if not log_dir.exists():
        return []
    records = []
    for f in log_dir.iterdir():
        if f.suffix != ".jsonl" or not f.is_file():
            continue
        # 快速过滤：文件修改时间早于截止日期则跳过
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            continue
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ts_str = rec.get("timestamp", "")
                    if ts_str:
                        # ISO 格式时间，可能带时区
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        cutoff_aware = cutoff.replace(tzinfo=timezone.utc)
                        if ts >= cutoff_aware:
                            records.append(rec)
                except (ValueError, KeyError):
                    pass
        except OSError:
            pass
    return records


from pydantic import BaseModel


class EmotionSeriesItem(BaseModel):
    date: str
    normal: int = 0
    happy: int = 0
    angry: int = 0
    shy: int = 0
    cold: int = 0


class EmotionStatsResponse(BaseModel):
    days: int
    series: List[EmotionSeriesItem]


class TriggerItem(BaseModel):
    word: str
    emotion: str
    count: int


class TriggerStatsResponse(BaseModel):
    top: int
    items: List[TriggerItem]


@router.get("/emotion", response_model=EmotionStatsResponse)
async def emotion_stats(
    days: int = Query(30, ge=1, le=365),
    service=Depends(get_service),
) -> EmotionStatsResponse:
    cache_key = f"emotion:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    records = _scan_log_records(days)
    # 按日期聚合 mood_after
    daily: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rec in records:
        ts_str = rec.get("timestamp", "")
        mood = rec.get("mood_after", "normal")
        if not ts_str:
            continue
        try:
            date_key = ts_str[:10]  # "YYYY-MM-DD"
            daily[date_key][mood] += 1
        except Exception:
            pass

    # 填充连续日期
    series = []
    for i in range(days - 1, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        counts = daily.get(date, {})
        series.append(EmotionSeriesItem(
            date=date,
            normal=counts.get("normal", 0),
            happy=counts.get("happy", 0),
            angry=counts.get("angry", 0),
            shy=counts.get("shy", 0),
            cold=counts.get("cold", 0),
        ))

    result = EmotionStatsResponse(days=days, series=series)
    _cache_set(cache_key, result)
    return result


@router.get("/triggers", response_model=TriggerStatsResponse)
async def trigger_stats(
    top: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365),
    service=Depends(get_service),
) -> TriggerStatsResponse:
    cache_key = f"triggers:{top}:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    records = _scan_log_records(days)
    emotion_triggers = service.character.emotion_triggers  # 当前角色的触发词

    word_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for rec in records:
        mood_before = rec.get("mood_before", "normal")
        mood_after = rec.get("mood_after", "normal")
        if mood_before == mood_after:
            continue  # 无情绪变化，跳过
        user_input = rec.get("user_input", "")
        # 找出匹配的触发词
        for emotion, keywords in emotion_triggers.items():
            if emotion != mood_after:
                continue
            for kw in keywords:
                if kw in user_input:
                    word_counts[kw][emotion] += 1
                    break  # 一个输入只计一次

    # 展平并排序
    flat = []
    for word, emotion_map in word_counts.items():
        for emotion, count in emotion_map.items():
            flat.append(TriggerItem(word=word, emotion=emotion, count=count))
    flat.sort(key=lambda x: x.count, reverse=True)

    result = TriggerStatsResponse(top=top, items=flat[:top])
    _cache_set(cache_key, result)
    return result
