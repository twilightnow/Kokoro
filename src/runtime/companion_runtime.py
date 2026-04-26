import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from ..config import get_data_dir
from ..perception.collector import PerceptionCollector
from ..perception.input_tracker import InputTracker
from ..perception.privacy import PerceptionAuditRepository, PrivacySettings, PrivacySettingsRepository
from ..perception.window_monitor import WindowMonitor
from ..proactive.action import ProactiveAction, ProactiveSignal
from ..proactive.log import ProactiveLogRepository
from ..proactive.policy import ProactivePolicy
from ..proactive.profile import ProactiveSettings, ProactiveSettingsRepository
from ..proactive.scheduler import ProactiveScheduler
from ..proactive.signal_detector import ProactiveSignalDetector
from ..proactive.templates import style_hint_for_scene
from ..reminder.repository import ReminderRepository
from ..reminder.service import RoutineReminderService

if TYPE_CHECKING:
    from ..application.conversation_service import ConversationService


class CompanionRuntime:
    def __init__(
        self,
        get_service: Callable[[], "ConversationService"],
        publish: Callable[[ProactiveAction], Awaitable[None]],
        data_dir: Path | None = None,
        interval_seconds: int = 30,
        llm_timeout_seconds: float = 10.0,
    ) -> None:
        self._get_service = get_service
        self._publish = publish
        self._data_dir = Path(data_dir or get_data_dir())
        self._interval_seconds = max(5, interval_seconds)
        self._llm_timeout_seconds = max(1.0, llm_timeout_seconds)
        self._settings_repo = ProactiveSettingsRepository(self._data_dir)
        self._privacy_settings_repo = PrivacySettingsRepository(self._data_dir)
        self._perception_audit_repo = PerceptionAuditRepository(self._data_dir)
        self._log_repo = ProactiveLogRepository(self._data_dir)
        self._policy = ProactivePolicy()
        self._scheduler = ProactiveScheduler(self._policy)
        self._detector = ProactiveSignalDetector()
        self._reminder_service = RoutineReminderService(ReminderRepository(self._data_dir))
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._input_tracker: InputTracker | None = None
        self._collector: PerceptionCollector | None = None
        self._status: dict[str, object] = {
            "running": False,
            "today_count": 0,
            "cooldown_remaining_seconds": 0,
            "last_reason": "",
            "last_scene": "",
            "last_decision": "",
        }

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return

        self._stop_event = asyncio.Event()
        self._ensure_collector()
        self._status["running"] = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        self._task = None
        if task is not None:
            await task
        if self._input_tracker is not None:
            try:
                self._input_tracker.stop()
            except Exception:
                pass
        self._status["running"] = False

    def get_settings(self) -> ProactiveSettings:
        return self._settings_repo.load()

    def update_settings(self, settings: ProactiveSettings) -> ProactiveSettings:
        saved = self._settings_repo.save(settings)
        self._refresh_status(saved)
        return saved

    def get_status(self) -> dict[str, object]:
        self._refresh_status(self.get_settings())
        return dict(self._status)

    def get_logs(self, limit: int = 50, character_id: str | None = None) -> list[dict[str, object]]:
        return self._log_repo.list(limit=limit, character_id=character_id)

    def get_privacy_settings(self) -> PrivacySettings:
        return self._privacy_settings_repo.load()

    def update_privacy_settings(self, settings: PrivacySettings) -> PrivacySettings:
        return self._privacy_settings_repo.save(settings)

    def get_perception_audit(self, limit: int = 50) -> list[dict[str, object]]:
        return self._perception_audit_repo.list(limit=limit)

    def get_perception_status(self) -> dict[str, object]:
        ctx = self._collector.last_perception() if self._collector is not None else None
        return {
            "collector_available": self._collector is not None,
            "last_perception": {
                "timestamp": ctx.timestamp.isoformat(),
                "active_app_name": ctx.active_app_name,
                "active_window_title": ctx.active_window_title,
                "time_of_day": ctx.time_of_day,
                "is_user_active": ctx.is_user_active,
                "is_gaming": ctx.is_gaming,
                "blocked_reason": ctx.blocked_reason,
                "dnd_reason": ctx.dnd_reason,
                "redactions": ctx.redactions,
            } if ctx is not None else None,
        }

    def list_reminders(self, character_id: str, include_completed: bool = True) -> list[dict[str, object]]:
        return [
            reminder.to_dict()
            for reminder in self._reminder_service.list(character_id, include_completed=include_completed)
        ]

    def create_reminder(
        self,
        character_id: str,
        title: str,
        due_at: datetime,
        note: str = "",
        repeat_rule: str = "once",
        source: str = "admin",
    ) -> dict[str, object]:
        reminder = self._reminder_service.create(
            character_id,
            title,
            due_at,
            note=note,
            repeat_rule=repeat_rule,
            source=source,
        )
        return reminder.to_dict()

    def update_reminder(
        self,
        character_id: str,
        reminder_id: str,
        *,
        title: str | None = None,
        note: str | None = None,
        due_at: datetime | None = None,
        repeat_rule: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        reminder = self._reminder_service.update(
            character_id,
            reminder_id,
            title=title,
            note=note,
            due_at=due_at,
            repeat_rule=repeat_rule,
            status=status,
        )
        return reminder.to_dict()

    def complete_reminder(self, character_id: str, reminder_id: str) -> dict[str, object]:
        return self._reminder_service.complete(character_id, reminder_id).to_dict()

    def snooze_reminder(self, character_id: str, reminder_id: str, until: datetime) -> dict[str, object]:
        return self._reminder_service.snooze(character_id, reminder_id, until).to_dict()

    def delete_reminder(self, character_id: str, reminder_id: str) -> bool:
        return self._reminder_service.delete(character_id, reminder_id)

    def record_feedback(self, event_id: str, feedback: str | None, responded: bool = True) -> bool:
        event = self._log_repo.get(event_id)
        updated = self._log_repo.update_feedback(event_id, feedback, responded)
        if not updated or event is None:
            return updated

        if event.get("scene") == "reminder":
            self._apply_reminder_feedback(event, feedback)
        return True

    async def send_test_action(self) -> ProactiveAction:
        service = self._get_service()
        settings = self.get_settings()
        recent_entries = self._log_repo.list(limit=200, character_id=service.character_id)
        action = ProactiveAction(
            id="evt_test_manual",
            timestamp=datetime.now().isoformat(),
            character_id=service.character_id,
            scene="reminder",
            level="short",
            decision="sent",
            reason="manual_test",
            content="这是主动陪伴测试气泡。",
            expression="happy",
            actions=["知道了", "稍后提醒", "今天别提醒"],
            settings_mode=settings.mode,
            daily_count_before=self._policy.daily_count(recent_entries, service.character_id, datetime.now()),
            generated_by="template",
        )
        self._log_repo.append(action)
        await self._publish(action)
        self._refresh_status(settings, action)
        return action

    async def run_once(self) -> ProactiveAction | None:
        self._ensure_collector()
        settings = self._settings_repo.load()
        service = self._get_service()
        current_time = datetime.now()

        reminder_signals = self._collect_reminder_signals(service.character_id, current_time)
        ctx = None
        if self._collector is not None:
            ctx = await asyncio.to_thread(self._collector.collect)
        service.set_perception_context(ctx)

        recent_entries = self._log_repo.list(limit=200, character_id=service.character_id)
        signals = reminder_signals
        if ctx is not None:
            signals.extend(self._detector.detect(ctx))
        emotion_summary = getattr(service, "current_emotion_summary", None)
        action = self._scheduler.plan(
            signals,
            settings,
            service.character,
            service.character_id,
            recent_entries,
            current_time,
            emotion_summary=getattr(emotion_summary, "__dict__", {}) if emotion_summary is not None else {},
            privacy_dnd_reason=ctx.dnd_reason if ctx is not None else "",
        )
        if action is None:
            self._refresh_status(settings)
            return None

        if action.decision == "suppressed":
            self._log_repo.append(action)
            self._refresh_status(settings, action)
            return action

        action = await self._finalize_action(action, service)
        self._log_repo.append(action)
        self._refresh_status(settings, action)
        if action.decision == "sent" and action.level != "silent":
            await self._publish(action)
        return action

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                self._status["running"] = False
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _finalize_action(
        self,
        action: ProactiveAction,
        service: "ConversationService",
    ) -> ProactiveAction:
        if action.level == "full":
            style_hint = style_hint_for_scene(service.character, action.scene)
            scene_context = str(action.metadata.get("summary") or action.metadata.get("title") or action.content or "")
            try:
                content = await asyncio.wait_for(
                    asyncio.to_thread(service.generate_proactive_reply, action.scene, style_hint, scene_context),
                    timeout=self._llm_timeout_seconds,
                )
            except (RuntimeError, asyncio.TimeoutError):
                content = None

            if content:
                action.content = content
                action.generated_by = "llm"
                return action

            if action.content:
                action.level = "short"
                action.generated_by = "template"
                return action

            if action.expression:
                action.level = "expression"
                action.actions = []
                action.generated_by = "expression"
                return action

            action.level = "silent"
            action.decision = "suppressed"
            action.suppressed_by = "degraded_to_silent"
            action.generated_by = "silent"
            return action

        if action.level == "short" and not action.content:
            if action.expression:
                action.level = "expression"
                action.actions = []
                action.generated_by = "expression"
            else:
                action.level = "silent"
                action.decision = "suppressed"
                action.suppressed_by = "missing_template"
                action.generated_by = "silent"
        return action

    def _collect_reminder_signals(self, character_id: str, now: datetime) -> list[ProactiveSignal]:
        signals: list[ProactiveSignal] = []
        for reminder in self._reminder_service.due(character_id, now):
            signals.append(
                ProactiveSignal(
                    scene="reminder",
                    reason=f"reminder_due:{reminder.id}",
                    trigger_name="RoutineReminderTrigger",
                    detected_at=now,
                    priority=95,
                    metadata={
                        "reminder_id": reminder.id,
                        "title": reminder.title,
                        "summary": reminder.title,
                    },
                )
            )
        return signals

    def _apply_reminder_feedback(self, event: dict[str, object], feedback: str | None) -> None:
        character_id = str(event.get("character_id") or "")
        reminder_id = self._resolve_reminder_id(event)
        if not character_id or not reminder_id:
            return

        try:
            if feedback == "知道了":
                self._reminder_service.complete(character_id, reminder_id)
            elif feedback == "稍后提醒":
                self._reminder_service.snooze(
                    character_id,
                    reminder_id,
                    datetime.now() + timedelta(minutes=30),
                )
        except KeyError:
            return

    def _resolve_reminder_id(self, event: dict[str, object]) -> str | None:
        metadata = event.get("metadata")
        if isinstance(metadata, dict):
            reminder_id = metadata.get("reminder_id")
            if isinstance(reminder_id, str) and reminder_id:
                return reminder_id

        reason = event.get("reason")
        if isinstance(reason, str) and reason.startswith("reminder_due:"):
            _, _, reminder_id = reason.partition(":")
            return reminder_id or None
        return None

    def _ensure_collector(self) -> None:
        if self._collector is not None:
            return
        try:
            tracker = InputTracker()
            tracker.start()
            self._input_tracker = tracker
            self._collector = PerceptionCollector(
                tracker,
                WindowMonitor(),
                privacy_settings_repo=self._privacy_settings_repo,
                audit_repo=self._perception_audit_repo,
            )
        except Exception:
            self._collector = None

    def _refresh_status(self, settings: ProactiveSettings, action: ProactiveAction | None = None) -> None:
        service = self._get_service()
        now = datetime.now()
        recent_entries = self._log_repo.list(limit=200, character_id=service.character_id)
        today_count = self._policy.daily_count(recent_entries, service.character_id, now)
        cooldown_remaining = self._policy.cooldown_remaining_seconds(recent_entries, service.character_id, now, settings)
        latest = action.to_dict() if action is not None else (recent_entries[0] if recent_entries else {})
        self._status = {
            "running": self._task is not None and not self._task.done(),
            "enabled": settings.enabled,
            "mode": settings.mode,
            "today_count": today_count,
            "cooldown_remaining_seconds": cooldown_remaining,
            "last_reason": latest.get("reason", ""),
            "last_scene": latest.get("scene", ""),
            "last_decision": latest.get("decision", ""),
            "last_event_id": latest.get("id", ""),
        }
