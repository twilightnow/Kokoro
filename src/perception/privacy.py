from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..config import get_data_dir
from .context import PerceptionContext


_DEFAULT_SENSITIVE_PATTERNS = [
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^ \t]+",
    r"https?://\S+\?\S+",
    r"\b\d{12,}\b",
    r"[A-Za-z]:\\Users\\[^\\]+\\[^\s]+",
]


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_int(value: object, default: int, minimum: int = 0, maximum: int = 200) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _matches_any(value: str, patterns: list[str]) -> str | None:
    if not value:
        return None
    for pattern in patterns:
        if not pattern:
            continue
        try:
            if re.search(pattern, value, flags=re.IGNORECASE):
                return pattern
        except re.error:
            if pattern.lower() in value.lower():
                return pattern
    return None


@dataclass
class PrivacySettings:
    enabled: bool = True
    blocked_apps: list[str] = field(default_factory=list)
    blocked_title_patterns: list[str] = field(default_factory=list)
    sensitive_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_SENSITIVE_PATTERNS))
    max_title_length: int = 40
    audit_enabled: bool = True
    dnd_app_patterns: list[str] = field(default_factory=list)
    dnd_title_patterns: list[str] = field(default_factory=list)
    dnd_fullscreen: bool = False
    dnd_meeting_patterns: list[str] = field(default_factory=lambda: ["Zoom", "Teams", "腾讯会议", "会议"])

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "PrivacySettings":
        default = cls()
        return cls(
            enabled=_coerce_bool(raw.get("enabled"), default.enabled),
            blocked_apps=_coerce_list(raw.get("blocked_apps")),
            blocked_title_patterns=_coerce_list(raw.get("blocked_title_patterns")),
            sensitive_patterns=_coerce_list(raw.get("sensitive_patterns")) or default.sensitive_patterns,
            max_title_length=_coerce_int(raw.get("max_title_length"), default.max_title_length, 1, 200),
            audit_enabled=_coerce_bool(raw.get("audit_enabled"), default.audit_enabled),
            dnd_app_patterns=_coerce_list(raw.get("dnd_app_patterns")),
            dnd_title_patterns=_coerce_list(raw.get("dnd_title_patterns")),
            dnd_fullscreen=_coerce_bool(raw.get("dnd_fullscreen"), default.dnd_fullscreen),
            dnd_meeting_patterns=_coerce_list(raw.get("dnd_meeting_patterns")) or default.dnd_meeting_patterns,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrivacySettingsRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or get_data_dir())
        self._path = self._data_dir / "runtime" / "perception" / "privacy_settings.json"

    def load(self) -> PrivacySettings:
        defaults = PrivacySettings()
        if not self._path.exists():
            return defaults
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return defaults
        if not isinstance(raw, dict):
            return defaults
        merged = defaults.to_dict()
        merged.update(raw)
        return PrivacySettings.from_mapping(merged)

    def save(self, settings: PrivacySettings) -> PrivacySettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return settings


class PerceptionAuditRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or get_data_dir())
        self._path = self._data_dir / "runtime" / "perception" / "audit.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, ctx: PerceptionContext) -> None:
        entry = {
            "timestamp": ctx.timestamp.isoformat(),
            "active_app_name": ctx.active_app_name,
            "active_window_title": ctx.active_window_title,
            "time_of_day": ctx.time_of_day,
            "is_user_active": ctx.is_user_active,
            "idle_seconds": int(ctx.idle_seconds),
            "switches_per_minute": round(ctx.switches_per_minute, 2),
            "is_gaming": ctx.is_gaming,
            "is_fullscreen": ctx.is_fullscreen,
            "blocked_reason": ctx.blocked_reason,
            "dnd_reason": ctx.dnd_reason,
            "redactions": list(ctx.redactions),
        }
        with self._path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list(self, limit: int = 50) -> list[dict[str, object]]:
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
        items.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        return items[: max(1, min(limit, 200))]


class PrivacyFilter:
    def __init__(self, settings: PrivacySettings | None = None) -> None:
        self._settings = settings or PrivacySettings()

    def apply(self, ctx: PerceptionContext) -> PerceptionContext:
        settings = self._settings
        if not settings.enabled:
            return ctx

        app_match = _matches_any(ctx.active_app_name, settings.blocked_apps)
        title_match = _matches_any(ctx.active_window_title, settings.blocked_title_patterns)
        if app_match or title_match:
            return PerceptionContext(
                timestamp=ctx.timestamp,
                active_window_title="",
                active_app_name=ctx.active_app_name,
                is_user_active=ctx.is_user_active,
                hour=ctx.hour,
                idle_seconds=ctx.idle_seconds,
                switches_per_minute=ctx.switches_per_minute,
                is_gaming=False,
                is_fullscreen=ctx.is_fullscreen,
                blocked_reason=f"blocked:{'app' if app_match else 'title'}",
                dnd_reason="privacy_blocked",
            )

        safe_title = ctx.active_window_title
        redactions: list[str] = []
        for index, pattern in enumerate(settings.sensitive_patterns):
            try:
                next_title, count = re.subn(pattern, "[已脱敏]", safe_title, flags=re.IGNORECASE)
            except re.error:
                continue
            if count:
                safe_title = next_title
                redactions.append(f"sensitive_pattern_{index + 1}")

        max_len = max(1, settings.max_title_length)
        if len(safe_title) > max_len:
            safe_title = safe_title[:max_len]
            redactions.append("title_truncated")

        dnd_reason = self._dnd_reason(ctx, settings)
        return PerceptionContext(
            timestamp=ctx.timestamp,
            active_window_title=safe_title,
            active_app_name=ctx.active_app_name,
            is_user_active=ctx.is_user_active,
            hour=ctx.hour,
            idle_seconds=ctx.idle_seconds,
            switches_per_minute=ctx.switches_per_minute,
            is_gaming=ctx.is_gaming,
            is_fullscreen=ctx.is_fullscreen,
            blocked_reason="",
            dnd_reason=dnd_reason,
            redactions=redactions,
        )

    def _dnd_reason(self, ctx: PerceptionContext, settings: PrivacySettings) -> str:
        if settings.dnd_fullscreen and ctx.is_fullscreen:
            return "fullscreen"
        if _matches_any(ctx.active_app_name, settings.dnd_app_patterns):
            return "app"
        if _matches_any(ctx.active_window_title, settings.dnd_title_patterns):
            return "title"
        if _matches_any(ctx.active_window_title, settings.dnd_meeting_patterns):
            return "meeting"
        return ""
