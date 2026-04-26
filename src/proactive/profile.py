import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from ..config import get_data_dir
from .action import InterventionLevel

ProactiveMode = Literal["off", "low", "normal", "high"]


def _env_flag_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_optional_int(value: object) -> int | None:
    if value in {None, "", "null"}:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _coerce_mode(value: object, default: ProactiveMode) -> ProactiveMode:
    if isinstance(value, str) and value in {"off", "low", "normal", "high"}:
        return value
    return default


def _coerce_level(value: object, default: InterventionLevel) -> InterventionLevel:
    if isinstance(value, str) and value in {"silent", "expression", "short", "full"}:
        return value  # type: ignore[return-value]
    return default


@dataclass
class ProactiveSettings:
    enabled: bool = True
    mode: ProactiveMode = "normal"
    dnd_enabled: bool = True
    dnd_start: str = "23:30"
    dnd_end: str = "08:00"
    allow_late_night: bool = True
    allow_long_work: bool = True
    allow_idle_return: bool = True
    allow_window_switch: bool = True
    allow_gaming: bool = True
    allow_reminders: bool = True
    gaming_level: InterventionLevel = "expression"
    max_per_day: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "ProactiveSettings":
        default = cls()
        return cls(
            enabled=_coerce_bool(raw.get("enabled"), default.enabled),
            mode=_coerce_mode(raw.get("mode"), default.mode),
            dnd_enabled=_coerce_bool(raw.get("dnd_enabled"), default.dnd_enabled),
            dnd_start=str(raw.get("dnd_start", default.dnd_start) or default.dnd_start),
            dnd_end=str(raw.get("dnd_end", default.dnd_end) or default.dnd_end),
            allow_late_night=_coerce_bool(raw.get("allow_late_night"), default.allow_late_night),
            allow_long_work=_coerce_bool(raw.get("allow_long_work"), default.allow_long_work),
            allow_idle_return=_coerce_bool(raw.get("allow_idle_return"), default.allow_idle_return),
            allow_window_switch=_coerce_bool(raw.get("allow_window_switch"), default.allow_window_switch),
            allow_gaming=_coerce_bool(raw.get("allow_gaming"), default.allow_gaming),
            allow_reminders=_coerce_bool(raw.get("allow_reminders"), default.allow_reminders),
            gaming_level=_coerce_level(raw.get("gaming_level"), default.gaming_level),
            max_per_day=_coerce_optional_int(raw.get("max_per_day")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProactiveSettingsRepository:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or get_data_dir())
        self._path = self._data_dir / "runtime" / "proactive" / "settings.json"

    @property
    def path(self) -> Path:
        return self._path

    def _default_settings(self) -> ProactiveSettings:
        enabled = _env_flag_enabled("KOKORO_ENABLE_PERCEPTION")
        return ProactiveSettings(
            enabled=enabled,
            mode="normal" if enabled else "off",
        )

    def load(self) -> ProactiveSettings:
        defaults = self._default_settings()
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
        return ProactiveSettings.from_mapping(merged)

    def save(self, settings: ProactiveSettings) -> ProactiveSettings:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(settings.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return settings