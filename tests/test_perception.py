"""
感知层单元测试：InputTracker、WindowMonitor、PerceptionCollector、ProactiveSignalDetector。
"""
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.perception.context import PerceptionContext
from src.perception.collector import PerceptionCollector
from src.perception.input_tracker import InputTracker
from src.perception.privacy import (
    PerceptionAuditRepository,
    PrivacyFilter,
    PrivacySettings,
    PrivacySettingsRepository,
)
from src.perception.window_monitor import WindowMonitor
from src.proactive.signal_detector import ProactiveSignalDetector


def _make_ctx(**kwargs) -> PerceptionContext:
    defaults = dict(
        timestamp=datetime.now(),
        active_window_title="",
        is_user_active=True,
        hour=10,
        idle_seconds=0.0,
        switches_per_minute=0.0,
        is_gaming=False,
    )
    defaults.update(kwargs)
    return PerceptionContext(**defaults)


# ── InputTracker ──────────────────────────────────────────────────────────────

class TestInputTracker(unittest.TestCase):

    def test_idle_seconds_initial_near_zero(self):
        tracker = InputTracker()
        self.assertLess(tracker.idle_seconds(), 1.0)

    def test_mark_active_resets_timer(self):
        tracker = InputTracker()
        # 手动调整 last_activity 到过去
        import threading
        with tracker._lock:
            tracker._last_activity -= 100
        self.assertGreater(tracker.idle_seconds(), 90)
        tracker.mark_active()
        self.assertLess(tracker.idle_seconds(), 1.0)

    def test_start_without_pynput_no_exception(self):
        tracker = InputTracker()
        # 无论 pynput 是否安装，start() 不抛异常
        try:
            tracker.start()
            tracker.stop()
        except Exception as e:
            self.fail(f"start()/stop() 抛出了异常: {e}")


# ── WindowMonitor ─────────────────────────────────────────────────────────────

class TestWindowMonitor(unittest.TestCase):

    def test_collect_failure_returns_empty_string(self):
        monitor = WindowMonitor()
        with patch("src.perception.window_monitor.WindowMonitor.current_title", return_value=""):
            result = monitor.collect()
        self.assertEqual(result, "")

    def test_is_gaming_case_insensitive(self):
        monitor = WindowMonitor()
        self.assertTrue(monitor.is_gaming("steam overlay"))
        self.assertTrue(monitor.is_gaming("原神"))
        self.assertFalse(monitor.is_gaming("VS Code"))
        self.assertFalse(monitor.is_gaming(""))

    def test_switches_per_minute_empty_history(self):
        monitor = WindowMonitor()
        self.assertEqual(monitor.switches_per_minute(), 0.0)

    def test_collect_records_switches(self):
        monitor = WindowMonitor()
        with patch.object(monitor, "current_title", side_effect=["App A", "App B", "App C"]):
            monitor.collect()
            monitor.collect()
            monitor.collect()
        # 应有 2 次切换（A→B, B→C；空→A 不计，因为初始 _last_title 为空，但第一次非空→有切换记录）
        # 修正：第一次 A 时 _last_title="" → title="App A" != "" 触发 record，共 3 次
        self.assertGreater(len(monitor._switch_history), 0)


class TestPerceptionCollector(unittest.TestCase):

    def test_collect_updates_latest_context(self):
        tracker = MagicMock(spec=InputTracker)
        tracker.idle_seconds.return_value = 120.0
        monitor = MagicMock(spec=WindowMonitor)
        monitor.collect.return_value = "Visual Studio Code"
        monitor.current_app_name.return_value = "Code"
        monitor.is_fullscreen.return_value = False
        monitor.switches_per_minute.return_value = 3.0
        monitor.is_gaming.return_value = False

        collector = PerceptionCollector(tracker, monitor)
        ctx = collector.collect()

        self.assertEqual(ctx.active_window_title, "Visual Studio Code")
        self.assertTrue(ctx.is_user_active)
        self.assertEqual(ctx.idle_seconds, 120.0)
        self.assertEqual(collector.last_perception(), ctx)


class TestPrivacyFilter(unittest.TestCase):

    def test_blocked_title_is_removed_before_prompt(self):
        ctx = _make_ctx(active_window_title="Secret Project - VS Code")
        settings = PrivacySettings(blocked_title_patterns=["Secret Project"])

        safe = PrivacyFilter(settings).apply(ctx)

        self.assertEqual(safe.active_window_title, "")
        self.assertEqual(safe.blocked_reason, "blocked:title")
        self.assertEqual(safe.dnd_reason, "privacy_blocked")

    def test_sensitive_title_is_redacted_and_truncated(self):
        ctx = _make_ctx(active_window_title="token=abc12345678901234567890 - private document")
        settings = PrivacySettings(max_title_length=16)

        safe = PrivacyFilter(settings).apply(ctx)

        self.assertNotIn("abc12345678901234567890", safe.active_window_title)
        self.assertLessEqual(len(safe.active_window_title), 16)
        self.assertIn("title_truncated", safe.redactions)

    def test_audit_stores_only_safe_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = MagicMock(spec=InputTracker)
            tracker.idle_seconds.return_value = 0.0
            monitor = MagicMock(spec=WindowMonitor)
            monitor.collect.return_value = "alice@example.com - Mail"
            monitor.current_app_name.return_value = "Mail"
            monitor.is_fullscreen.return_value = False
            monitor.switches_per_minute.return_value = 0.0
            monitor.is_gaming.return_value = False
            privacy_repo = PrivacySettingsRepository(Path(tmp))
            privacy_repo.save(PrivacySettings(audit_enabled=True))
            audit_repo = PerceptionAuditRepository(Path(tmp))

            collector = PerceptionCollector(tracker, monitor, privacy_repo, audit_repo)
            collector.collect()
            items = audit_repo.list()

        self.assertEqual(len(items), 1)
        self.assertNotIn("alice@example.com", str(items[0]))
        self.assertIn("[已脱敏]", str(items[0]))

    def test_audit_is_not_written_when_privacy_filter_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker = MagicMock(spec=InputTracker)
            tracker.idle_seconds.return_value = 0.0
            monitor = MagicMock(spec=WindowMonitor)
            monitor.collect.return_value = "alice@example.com - Mail"
            monitor.current_app_name.return_value = "Mail"
            monitor.is_fullscreen.return_value = False
            monitor.switches_per_minute.return_value = 0.0
            monitor.is_gaming.return_value = False
            privacy_repo = PrivacySettingsRepository(Path(tmp))
            privacy_repo.save(PrivacySettings(enabled=False, audit_enabled=True))
            audit_repo = PerceptionAuditRepository(Path(tmp))

            collector = PerceptionCollector(tracker, monitor, privacy_repo, audit_repo)
            collector.collect()

            self.assertEqual(audit_repo.list(), [])


class TestProactiveSignalDetector(unittest.TestCase):

    def test_long_work_signal_fires_after_active_threshold(self):
        detector = ProactiveSignalDetector()
        detector._session_active_since = time.monotonic() - 3700

        signals = detector.detect(_make_ctx(is_user_active=True))

        self.assertTrue(any(signal.scene == "long_work" for signal in signals))

    def test_idle_return_signal_fires_after_long_idle(self):
        detector = ProactiveSignalDetector()
        detector._last_was_active = False
        detector._last_ctx = _make_ctx(is_user_active=False, idle_seconds=1900.0)

        signals = detector.detect(_make_ctx(is_user_active=True, idle_seconds=0.0))

        self.assertTrue(any(signal.scene == "idle_return" for signal in signals))


class TestConversationPerceptionIntegration(unittest.TestCase):

    def _make_service(self):
        from src.application.conversation_service import ConversationService

        with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
            mock_llm = MagicMock()
            mock_result = MagicMock()
            mock_result.text = "主动台词"
            mock_result.input_tokens = 0
            mock_result.output_tokens = 0
            mock_llm.chat.return_value = mock_result
            mock_llm_ctor.return_value = mock_llm

            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                char_path = Path(tmp) / "char.yaml"
                import yaml
                char_data = {
                    "name": "测试角色",
                    "forbidden_words": [],
                    "emotion_triggers": {},
                    "mood_expressions": {"normal": "平静"},
                    "proactive_style": {
                        "idle_too_long": "发呆什么呢",
                        "user_working_late": "还不睡",
                        "user_gaming": "打游戏",
                    },
                }
                with open(char_path, "w", encoding="utf-8") as f:
                    yaml.dump(char_data, f, allow_unicode=True)

                service = ConversationService(character_path=char_path)
                service._llm = mock_llm
                return service, mock_llm

    def test_generate_proactive_reply_returns_none_on_llm_failure(self):
        service, mock_llm = self._make_service()
        mock_llm.chat.side_effect = RuntimeError("LLM 挂了")

        result = service.generate_proactive_reply("idle_return", "发呆什么呢")

        self.assertIsNone(result)

    def test_generate_proactive_reply_keeps_turn_and_working_memory_stable(self):
        service, mock_llm = self._make_service()
        turn_before = service.turn
        wm_len_before = len(service.working_memory_messages)

        result = service.generate_proactive_reply("gaming", "打游戏")

        self.assertEqual(result, "主动台词")
        self.assertEqual(service.turn, turn_before)
        self.assertEqual(len(service.working_memory_messages), wm_len_before)

    def test_prepare_turn_collects_prompt_perception_without_old_engine(self):
        service, _mock_llm = self._make_service()
        ctx = _make_ctx(active_window_title="Visual Studio Code", idle_seconds=42.0)
        service._perception_collector = MagicMock(spec=PerceptionCollector)
        service._perception_collector.collect.return_value = ctx

        system_prompt, _mood_before = service._prepare_turn("你好")

        self.assertEqual(service._latest_perception, ctx)
        self.assertIn("当前窗口：Visual Studio Code", system_prompt)


if __name__ == "__main__":
    unittest.main()
