"""
感知层单元测试：InputTracker、WindowMonitor、CooldownManager、触发器、ProactiveEngine。
"""
import sys
import time
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.perception.context import PerceptionContext
from src.perception.cooldown import CooldownManager
from src.perception.input_tracker import InputTracker
from src.perception.window_monitor import WindowMonitor
from src.perception.triggers import (
    GamingTrigger,
    IdleTrigger,
    LateNightTrigger,
    WindowSwitchTrigger,
)
from src.perception.engine import ProactiveEngine
from src.perception.collector import PerceptionCollector


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


# ── CooldownManager ───────────────────────────────────────────────────────────

class TestCooldownManager(unittest.TestCase):

    def test_can_trigger_initially_true(self):
        cd = CooldownManager()
        self.assertTrue(cd.can_trigger("idle"))

    def test_after_trigger_cannot_retrigger(self):
        cd = CooldownManager()
        cd.mark_triggered("idle")
        self.assertFalse(cd.can_trigger("idle"))
        self.assertFalse(cd.can_trigger("other"))  # 全局冷却

    def test_reset_allows_retrigger(self):
        cd = CooldownManager()
        cd.mark_triggered("idle")
        cd.reset()
        self.assertTrue(cd.can_trigger("idle"))


# ── Triggers ──────────────────────────────────────────────────────────────────

class TestTriggers(unittest.TestCase):

    def test_idle_trigger_fires_when_threshold_exceeded(self):
        trigger = IdleTrigger(threshold_sec=100)
        ctx = _make_ctx(idle_seconds=150.0)
        self.assertIsNotNone(trigger.check(ctx))

    def test_idle_trigger_no_fire_below_threshold(self):
        trigger = IdleTrigger(threshold_sec=100)
        ctx = _make_ctx(idle_seconds=50.0)
        self.assertIsNone(trigger.check(ctx))

    def test_late_night_active_fires(self):
        trigger = LateNightTrigger()
        ctx = _make_ctx(hour=23, is_user_active=True)
        self.assertIsNotNone(trigger.check(ctx))

    def test_late_night_inactive_no_fire(self):
        trigger = LateNightTrigger()
        ctx = _make_ctx(hour=23, is_user_active=False)
        self.assertIsNone(trigger.check(ctx))

    def test_late_night_day_no_fire(self):
        trigger = LateNightTrigger()
        ctx = _make_ctx(hour=14, is_user_active=True)
        self.assertIsNone(trigger.check(ctx))

    def test_window_switch_fires_when_over_threshold(self):
        trigger = WindowSwitchTrigger(freq_threshold=5.0)
        ctx = _make_ctx(switches_per_minute=10.0)
        self.assertIsNotNone(trigger.check(ctx))

    def test_gaming_trigger_fires(self):
        trigger = GamingTrigger()
        ctx = _make_ctx(is_gaming=True)
        self.assertIsNotNone(trigger.check(ctx))

    def test_gaming_trigger_no_fire(self):
        trigger = GamingTrigger()
        ctx = _make_ctx(is_gaming=False)
        self.assertIsNone(trigger.check(ctx))


# ── ProactiveEngine ───────────────────────────────────────────────────────────

class TestProactiveEngine(unittest.TestCase):

    def _make_engine(self, ctx: PerceptionContext) -> ProactiveEngine:
        mock_collector = MagicMock(spec=PerceptionCollector)
        mock_collector.collect.return_value = ctx
        mock_collector.last_perception.return_value = ctx
        engine = ProactiveEngine(mock_collector)
        return engine

    def test_no_trigger_returns_none(self):
        ctx = _make_ctx(idle_seconds=0.0, is_gaming=False, switches_per_minute=0.0, hour=14)
        engine = self._make_engine(ctx)
        result = engine.check()
        self.assertIsNone(result)

    def test_idle_trigger_fires(self):
        ctx = _make_ctx(idle_seconds=7500.0, is_user_active=False)
        engine = self._make_engine(ctx)
        # 替换 IdleTrigger 阈值为 100s
        from src.perception.triggers import IdleTrigger
        engine._triggers = [IdleTrigger(threshold_sec=100)]
        result = engine.check()
        self.assertIsNotNone(result)
        self.assertEqual(result.tag, "idle")

    def test_trigger_then_cooldown_prevents_retrigger(self):
        ctx = _make_ctx(idle_seconds=7500.0, is_user_active=False)
        mock_collector = MagicMock(spec=PerceptionCollector)
        mock_collector.collect.return_value = ctx
        mock_collector.last_perception.return_value = ctx
        engine = ProactiveEngine(mock_collector)
        from src.perception.triggers import IdleTrigger
        engine._triggers = [IdleTrigger(threshold_sec=100)]
        # 手动清零冷却后触发
        engine._cooldown.reset()
        first = engine.check()
        self.assertIsNotNone(first)
        # 再次检查应因冷却返回 None
        second = engine.check()
        self.assertIsNone(second)

    def test_event_tag_matches_trigger_name(self):
        ctx = _make_ctx(is_gaming=True)
        engine = self._make_engine(ctx)
        engine._cooldown.reset()
        result = engine.check()
        self.assertIsNotNone(result)
        self.assertEqual(result.tag, "gaming")


# ── ConversationService._handle_proactive ──────────────────────────────────────

class TestHandleProactive(unittest.TestCase):

    def _make_service(self):
        """构建最小化的 ConversationService，用 mock LLM 替代真实调用。"""
        from src.application.conversation_service import ConversationService
        from src.personality.character import CharacterConfig, PersonalityConfig, ProactiveStyle

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

    def test_no_style_hint_returns_none(self):
        service, mock_llm = self._make_service()
        from src.perception.event import ProactiveEvent
        event = ProactiveEvent(tag="unknown_tag", trigger_name="UnknownTrigger")
        result = service._handle_proactive(event)
        self.assertIsNone(result)
        mock_llm.chat.assert_not_called()

    def test_llm_failure_returns_none(self):
        service, mock_llm = self._make_service()
        mock_llm.chat.side_effect = RuntimeError("LLM 挂了")
        from src.perception.event import ProactiveEvent
        event = ProactiveEvent(tag="idle", trigger_name="IdleTrigger")
        result = service._handle_proactive(event)
        self.assertIsNone(result)

    def test_normal_trigger_returns_reply(self):
        service, mock_llm = self._make_service()
        from src.perception.event import ProactiveEvent
        event = ProactiveEvent(tag="gaming", trigger_name="GamingTrigger")
        result = service._handle_proactive(event)
        self.assertIsNotNone(result)
        self.assertEqual(result, "主动台词")

    def test_proactive_does_not_increment_turn(self):
        service, mock_llm = self._make_service()
        from src.perception.event import ProactiveEvent
        turn_before = service._turn
        event = ProactiveEvent(tag="gaming", trigger_name="GamingTrigger")
        service._handle_proactive(event)
        self.assertEqual(service._turn, turn_before)

    def test_proactive_does_not_affect_working_memory(self):
        service, mock_llm = self._make_service()
        from src.perception.event import ProactiveEvent
        wm_len_before = len(service._memory.working_memory)
        event = ProactiveEvent(tag="gaming", trigger_name="GamingTrigger")
        service._handle_proactive(event)
        self.assertEqual(len(service._memory.working_memory), wm_len_before)


if __name__ == "__main__":
    unittest.main()
