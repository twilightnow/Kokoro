import time

from ..perception.context import PerceptionContext
from .action import ProactiveSignal


class ProactiveSignalDetector:
    _LONG_WORK_THRESHOLD_SEC = 3600
    _IDLE_RETURN_THRESHOLD_SEC = 1800

    def __init__(self) -> None:
        self._session_active_since = time.monotonic()
        self._last_was_active = True
        self._last_ctx: PerceptionContext | None = None

    def detect(self, ctx: PerceptionContext) -> list[ProactiveSignal]:
        signals: list[ProactiveSignal] = []
        now = time.monotonic()

        if ctx.is_user_active:
            if not self._last_was_active:
                if self._last_ctx and self._last_ctx.idle_seconds >= self._IDLE_RETURN_THRESHOLD_SEC:
                    signals.append(
                        ProactiveSignal(
                            scene="idle_return",
                            reason=f"returned_after_{int(self._last_ctx.idle_seconds)}_seconds_idle",
                            trigger_name="IdleReturnTrigger",
                            priority=85,
                        )
                    )
                self._session_active_since = now
            self._last_was_active = True
        else:
            self._last_was_active = False

        if ctx.is_user_active and now - self._session_active_since >= self._LONG_WORK_THRESHOLD_SEC:
            signals.append(
                ProactiveSignal(
                    scene="long_work",
                    reason=f"active_for_{int(now - self._session_active_since)}_seconds",
                    trigger_name="LongWorkTrigger",
                    priority=90,
                )
            )

        if ctx.is_late_night and ctx.is_user_active:
            signals.append(
                ProactiveSignal(
                    scene="late_night",
                    reason=f"late_night_active_at_{ctx.hour:02d}",
                    trigger_name="LateNightTrigger",
                    priority=80,
                )
            )

        if ctx.switches_per_minute >= 10.0:
            signals.append(
                ProactiveSignal(
                    scene="window_switch",
                    reason=f"switches_per_minute_{ctx.switches_per_minute:.2f}",
                    trigger_name="WindowSwitchTrigger",
                    priority=70,
                )
            )

        if ctx.is_gaming:
            signals.append(
                ProactiveSignal(
                    scene="gaming",
                    reason="game_window_detected",
                    trigger_name="GamingTrigger",
                    priority=60,
                )
            )

        self._last_ctx = ctx
        return signals