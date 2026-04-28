import asyncio
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.personality.character import CharacterConfig, ProactiveStyle
from src.proactive.action import ProactiveAction, ProactiveSignal
from src.proactive.notify import (
    NotifyEvent,
    perception_signal_to_notify_event,
    reminder_to_notify_event,
    validate_external_notify_params,
)
from src.proactive.policy import ProactivePolicy
from src.proactive.profile import ProactiveSettings, ProactiveSettingsRepository
from src.proactive.scheduler import ProactiveScheduler
from src.runtime.companion_runtime import CompanionRuntime


class TestProactiveSettingsRepository(unittest.TestCase):

    def test_missing_file_uses_env_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            with unittest.mock.patch.dict("os.environ", {"KOKORO_ENABLE_PERCEPTION": "1"}, clear=False):
                repo = ProactiveSettingsRepository(Path(tmp))
                settings = repo.load()

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.mode, "normal")


class TestProactivePolicy(unittest.TestCase):

    def test_dnd_window_suppresses_action(self):
        policy = ProactivePolicy()
        settings = ProactiveSettings(
            enabled=True,
            mode="normal",
            dnd_enabled=True,
            dnd_start="23:00",
            dnd_end="08:00",
        )
        decision = policy.evaluate(
            "late_night",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 23, 30, 0),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.suppressed_by, "dnd")

    def test_privacy_dnd_suppresses_before_normal_policy(self):
        policy = ProactivePolicy()
        settings = ProactiveSettings(enabled=True, mode="high", dnd_enabled=False)

        decision = policy.evaluate(
            "long_work",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 14, 0, 0),
            privacy_dnd_reason="meeting",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.suppressed_by, "privacy_dnd:meeting")


class TestProactiveScheduler(unittest.TestCase):

    def test_gaming_level_override_is_applied(self):
        scheduler = ProactiveScheduler()
        settings = ProactiveSettings(enabled=True, mode="high", gaming_level="expression")
        character = CharacterConfig(name="测试角色", proactive_style=ProactiveStyle())
        action = scheduler.plan(
            [ProactiveSignal(scene="gaming", reason="game_window_detected", trigger_name="GamingTrigger", priority=1)],
            settings,
            character,
            "firefly",
            [],
            datetime(2026, 4, 26, 20, 0, 0),
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.level, "expression")
        self.assertEqual(action.decision, "sent")

    def test_strong_emotion_downgrades_low_priority_scene_and_merges_expression(self):
        scheduler = ProactiveScheduler()
        settings = ProactiveSettings(enabled=True, mode="high")
        character = CharacterConfig(name="测试角色", proactive_style=ProactiveStyle())

        action = scheduler.plan(
            [ProactiveSignal(scene="idle_return", reason="idle_returned", trigger_name="IdleReturnTrigger", priority=1)],
            settings,
            character,
            "firefly",
            [],
            datetime(2026, 4, 26, 20, 0, 0),
            emotion_summary={"mood": "angry", "intensity": 0.9},
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.level, "expression")
        self.assertEqual(action.expression, "angry")
        self.assertEqual(action.metadata["emotion"]["mood"], "angry")


class _FakeService:
    def __init__(self, response: str | None) -> None:
        self.character_id = "firefly"
        self.character = CharacterConfig(name="测试角色", proactive_style=ProactiveStyle())
        self._response = response
        self.perception_context = None

    def set_perception_context(self, _ctx) -> None:
        self.perception_context = _ctx

    def generate_proactive_reply(
        self,
        _scene: str,
        _style_hint: str,
        _scene_context: str | None = None,
    ) -> str | None:
        if self._response is None:
            raise RuntimeError("llm unavailable")
        return self._response


class TestCompanionRuntime(unittest.TestCase):

    def test_full_action_degrades_to_short_template_on_llm_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _FakeService(None)

            async def publish(_action: ProactiveAction) -> None:
                return None

            runtime = CompanionRuntime(lambda: service, publish, data_dir=Path(tmp))
            action = ProactiveAction(
                id="evt_test",
                timestamp=datetime.now().isoformat(),
                character_id="firefly",
                scene="long_work",
                level="full",
                decision="sent",
                reason="active_for_3600_seconds",
                content="你已经忙了很久，要不要起来活动一下？",
                expression="cold",
                actions=["知道了"],
                settings_mode="high",
            )

            finalized = asyncio.run(runtime._finalize_action(action, service))

        self.assertEqual(finalized.level, "short")
        self.assertEqual(finalized.generated_by, "template")
        self.assertEqual(finalized.content, "你已经忙了很久，要不要起来活动一下？")

    def test_due_reminder_generates_signal_without_perception_collector(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = _FakeService("提醒你去做约好的事。")
            published: list[ProactiveAction] = []

            async def publish(action: ProactiveAction) -> None:
                published.append(action)

            runtime = CompanionRuntime(lambda: service, publish, data_dir=Path(tmp))
            runtime.update_settings(ProactiveSettings(enabled=True, mode="high", dnd_enabled=False))
            reminder = runtime.create_reminder(
                service.character_id,
                "站起来活动一下",
                datetime(2026, 4, 26, 9, 0, 0),
            )

            action = asyncio.run(runtime.run_once())

        self.assertIsNotNone(action)
        self.assertEqual(action.scene, "reminder")
        self.assertIn("reminder:", action.reason)  # 新格式："reminder:ntf_xxx"
        self.assertEqual(action.metadata["reminder_id"], reminder["id"])
        self.assertEqual(action.content, "提醒你去做约好的事。")
        self.assertEqual(len(published), 1)
        # 来源应标注为 reminder
        self.assertEqual(action.notify_source, "reminder")


class TestNotifyEvent(unittest.TestCase):

    def test_reminder_to_notify_event_defaults(self):
        evt = reminder_to_notify_event("rem_abc", "站起来活动一下")
        self.assertEqual(evt.source, "reminder")
        self.assertEqual(evt.scene, "reminder")
        self.assertEqual(evt.urgency, "high")
        self.assertEqual(evt.payload["reminder_id"], "rem_abc")
        self.assertEqual(evt.payload["title"], "站起来活动一下")
        self.assertEqual(evt.privacy_level, "public")

    def test_notify_event_to_signal_priority_mapping(self):
        evt_critical = NotifyEvent(source="external", scene="reminder", urgency="critical")
        self.assertEqual(evt_critical.to_signal().priority, 99)

        evt_high = NotifyEvent(source="reminder", scene="reminder", urgency="high")
        self.assertEqual(evt_high.to_signal().priority, 90)

        evt_normal = NotifyEvent(source="perception", scene="idle_return", urgency="normal")
        self.assertEqual(evt_normal.to_signal().priority, 70)

        evt_low = NotifyEvent(source="perception", scene="gaming", urgency="low")
        self.assertEqual(evt_low.to_signal().priority, 50)

    def test_notify_event_to_signal_preserves_source(self):
        evt = NotifyEvent(source="external", scene="long_work", urgency="high")
        signal = evt.to_signal()
        self.assertEqual(signal.notify_source, "external")
        self.assertEqual(signal.urgency, "high")
        self.assertEqual(signal.scene, "long_work")

    def test_perception_signal_to_notify_event_privacy_level(self):
        signal = ProactiveSignal(
            scene="gaming",
            reason="game_window_detected",
            trigger_name="GamingTrigger",
            priority=60,
        )
        evt = perception_signal_to_notify_event(signal)
        self.assertEqual(evt.source, "perception")
        self.assertEqual(evt.privacy_level, "private")
        self.assertEqual(evt.urgency, "normal")

    def test_validate_external_notify_params_valid(self):
        scene, urgency, privacy = validate_external_notify_params("reminder", "critical", "public")
        self.assertEqual(scene, "reminder")
        self.assertEqual(urgency, "critical")
        self.assertEqual(privacy, "public")

    def test_validate_external_notify_params_invalid_scene(self):
        with self.assertRaises(ValueError):
            validate_external_notify_params("unknown_scene", "normal", "public")

    def test_validate_external_notify_params_invalid_urgency(self):
        with self.assertRaises(ValueError):
            validate_external_notify_params("reminder", "extreme", "public")

    def test_validate_external_notify_params_invalid_privacy(self):
        with self.assertRaises(ValueError):
            validate_external_notify_params("reminder", "normal", "classified")


class TestCriticalUrgencyBypassesDnd(unittest.TestCase):

    def test_critical_urgency_bypasses_dnd_time_window(self):
        policy = ProactivePolicy()
        settings = ProactiveSettings(
            enabled=True,
            mode="normal",
            dnd_enabled=True,
            dnd_start="23:00",
            dnd_end="08:00",
        )
        # 处于 DND 时间窗口内，但 urgency=critical 应跳过
        decision = policy.evaluate(
            "reminder",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 23, 30, 0),
            urgency="critical",
        )
        self.assertTrue(decision.allowed)

    def test_normal_urgency_still_blocked_by_dnd(self):
        policy = ProactivePolicy()
        settings = ProactiveSettings(
            enabled=True,
            mode="normal",
            dnd_enabled=True,
            dnd_start="23:00",
            dnd_end="08:00",
        )
        decision = policy.evaluate(
            "reminder",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 23, 30, 0),
            urgency="normal",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.suppressed_by, "dnd")

    def test_critical_urgency_still_blocked_by_mode_off(self):
        policy = ProactivePolicy()
        settings = ProactiveSettings(enabled=True, mode="off")
        decision = policy.evaluate(
            "reminder",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 23, 30, 0),
            urgency="critical",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.suppressed_by, "disabled")

    def test_critical_urgency_does_not_bypass_privacy_dnd(self):
        """critical urgency 绕过时间窗口 DND，但不绕过感知 privacy_dnd_reason。"""
        policy = ProactivePolicy()
        settings = ProactiveSettings(enabled=True, mode="normal", dnd_enabled=False)
        decision = policy.evaluate(
            "reminder",
            settings,
            [],
            "firefly",
            datetime(2026, 4, 26, 14, 0, 0),
            privacy_dnd_reason="meeting",
            urgency="critical",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.suppressed_by, "privacy_dnd:meeting")


class TestExternalNotifyQueue(unittest.TestCase):

    def test_external_notify_event_is_processed_in_run_once(self):
        """推入外部 NotifyEvent 后，run_once 能将其转换为 action 并发布。"""
        with tempfile.TemporaryDirectory() as tmp:
            service = _FakeService("提醒你休息一下。")
            published: list[ProactiveAction] = []

            async def publish(action: ProactiveAction) -> None:
                published.append(action)

            runtime = CompanionRuntime(lambda: service, publish, data_dir=Path(tmp))
            runtime.update_settings(ProactiveSettings(enabled=True, mode="high", dnd_enabled=False))

            evt = NotifyEvent(
                source="external",
                scene="reminder",
                urgency="high",
                payload={"title": "去喝水", "reminder_id": "rem_external_001"},
            )
            runtime.push_notify_event(evt)

            action = asyncio.run(runtime.run_once())

        self.assertIsNotNone(action)
        self.assertEqual(action.scene, "reminder")
        self.assertEqual(action.notify_source, "external")
        self.assertEqual(action.urgency, "high")
        self.assertEqual(len(published), 1)
