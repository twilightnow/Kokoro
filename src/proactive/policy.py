from dataclasses import dataclass
from datetime import datetime

from .action import InterventionLevel, ProactiveScene
from .profile import ProactiveSettings

_MODE_MIN_INTERVAL_SECONDS = {
    "off": 0,
    "low": 3 * 60 * 60,
    "normal": 60 * 60,
    "high": 25 * 60,
}
_MODE_MAX_PER_DAY = {
    "off": 0,
    "low": 2,
    "normal": 5,
    "high": 10,
}
_MODE_DEFAULT_LEVEL: dict[str, dict[ProactiveScene, InterventionLevel]] = {
    "off": {
        "late_night": "silent",
        "long_work": "silent",
        "idle_return": "silent",
        "window_switch": "silent",
        "gaming": "silent",
        "reminder": "silent",
    },
    "low": {
        "late_night": "short",
        "long_work": "short",
        "idle_return": "expression",
        "window_switch": "expression",
        "gaming": "expression",
        "reminder": "short",
    },
    "normal": {
        "late_night": "short",
        "long_work": "short",
        "idle_return": "short",
        "window_switch": "short",
        "gaming": "expression",
        "reminder": "short",
    },
    "high": {
        "late_night": "full",
        "long_work": "full",
        "idle_return": "short",
        "window_switch": "short",
        "gaming": "short",
        "reminder": "full",
    },
}


@dataclass
class PolicyDecision:
    allowed: bool
    level: InterventionLevel
    suppressed_by: str | None
    daily_count_before: int
    cooldown_remaining_seconds: int


class ProactivePolicy:
    def daily_count(
        self,
        entries: list[dict[str, object]],
        character_id: str,
        now: datetime,
    ) -> int:
        count = 0
        for entry in entries:
            if entry.get("character_id") != character_id:
                continue
            if entry.get("decision") != "sent":
                continue
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if timestamp.date() == now.date():
                count += 1
        return count

    def cooldown_remaining_seconds(
        self,
        entries: list[dict[str, object]],
        character_id: str,
        now: datetime,
        settings: ProactiveSettings,
    ) -> int:
        min_interval = self._min_interval_seconds(settings)
        if min_interval <= 0:
            return 0

        last_sent_at: datetime | None = None
        for entry in entries:
            if entry.get("character_id") != character_id:
                continue
            if entry.get("decision") != "sent":
                continue
            timestamp = self._parse_timestamp(entry.get("timestamp"))
            if timestamp is None:
                continue
            if last_sent_at is None or timestamp > last_sent_at:
                last_sent_at = timestamp

        if last_sent_at is None:
            return 0

        elapsed = int((now - last_sent_at).total_seconds())
        return max(0, min_interval - elapsed)

    def evaluate(
        self,
        scene: ProactiveScene,
        settings: ProactiveSettings,
        entries: list[dict[str, object]],
        character_id: str,
        now: datetime,
        privacy_dnd_reason: str = "",
    ) -> PolicyDecision:
        base_level = self._base_level(scene, settings)
        daily_count_before = self.daily_count(entries, character_id, now)
        cooldown_remaining = self.cooldown_remaining_seconds(entries, character_id, now, settings)

        if not settings.enabled or settings.mode == "off":
            return PolicyDecision(False, "silent", "disabled", daily_count_before, cooldown_remaining)

        if not self._scene_enabled(scene, settings):
            return PolicyDecision(False, "silent", "scene_disabled", daily_count_before, cooldown_remaining)

        if privacy_dnd_reason:
            return PolicyDecision(
                False,
                "silent",
                f"privacy_dnd:{privacy_dnd_reason}",
                daily_count_before,
                cooldown_remaining,
            )

        if settings.dnd_enabled and self._is_in_dnd(now, settings):
            return PolicyDecision(False, "silent", "dnd", daily_count_before, cooldown_remaining)

        max_per_day = settings.max_per_day
        if max_per_day is None:
            max_per_day = _MODE_MAX_PER_DAY.get(settings.mode, 0)
        if max_per_day <= 0:
            return PolicyDecision(False, "silent", "daily_limit", daily_count_before, cooldown_remaining)
        if daily_count_before >= max_per_day:
            return PolicyDecision(False, "silent", "daily_limit", daily_count_before, cooldown_remaining)

        if cooldown_remaining > 0:
            return PolicyDecision(False, "silent", "cooldown", daily_count_before, cooldown_remaining)

        return PolicyDecision(True, base_level, None, daily_count_before, 0)

    def _base_level(self, scene: ProactiveScene, settings: ProactiveSettings) -> InterventionLevel:
        if scene == "gaming":
            return settings.gaming_level
        return _MODE_DEFAULT_LEVEL.get(settings.mode, _MODE_DEFAULT_LEVEL["normal"])[scene]

    def _min_interval_seconds(self, settings: ProactiveSettings) -> int:
        return _MODE_MIN_INTERVAL_SECONDS.get(settings.mode, _MODE_MIN_INTERVAL_SECONDS["normal"])

    def _scene_enabled(self, scene: ProactiveScene, settings: ProactiveSettings) -> bool:
        flags = {
            "late_night": settings.allow_late_night,
            "long_work": settings.allow_long_work,
            "idle_return": settings.allow_idle_return,
            "window_switch": settings.allow_window_switch,
            "gaming": settings.allow_gaming,
            "reminder": settings.allow_reminders,
        }
        return flags.get(scene, True)

    def _is_in_dnd(self, now: datetime, settings: ProactiveSettings) -> bool:
        try:
            start_hour, start_minute = [int(part) for part in settings.dnd_start.split(":", 1)]
            end_hour, end_minute = [int(part) for part in settings.dnd_end.split(":", 1)]
        except ValueError:
            return False

        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute

        if start_minutes == end_minutes:
            return True
        if start_minutes < end_minutes:
            return start_minutes <= current_minutes < end_minutes
        return current_minutes >= start_minutes or current_minutes < end_minutes

    def _parse_timestamp(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
