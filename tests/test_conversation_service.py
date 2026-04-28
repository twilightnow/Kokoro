"""
ConversationService 自动结算测试：覆盖轮数、空闲和增量去重逻辑。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_mock_llm(reply_text: str = "测试回复"):
    mock_result = MagicMock()
    mock_result.text = reply_text
    mock_result.input_tokens = 10
    mock_result.output_tokens = 5
    mock_result.model = "mock"
    mock_result.provider = "mock"

    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm.stream_chat.return_value = iter(())
    return mock_llm


class TestConversationAutoPersistence(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.char_path = Path(self.tmp.name) / "char.yaml"

        import yaml

        self.char_path.write_text(
            yaml.dump(
                {
                    "name": "测试角色",
                    "forbidden_words": [],
                    "emotion_triggers": {},
                    "mood_expressions": {"normal": "平静"},
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _make_service(self, *, settle_turns: int = 10, idle_seconds: int = 900):
        from src.application.conversation_service import ConversationService

        env = {
            "KOKORO_DATA_DIR": str(self.data_dir),
            "KOKORO_MEMORY_SETTLE_TURNS": str(settle_turns),
            "KOKORO_MEMORY_IDLE_SECONDS": str(idle_seconds),
        }
        mock_llm = _make_mock_llm()

        with patch.dict(os.environ, env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=mock_llm):
                service = ConversationService(character_path=self.char_path)

        service._llm = mock_llm
        self.addCleanup(lambda: getattr(service, "_cancel_auto_persist_timer", lambda: None)())
        return service

    def test_turn_based_persistence_flushes_once(self):
        service = self._make_service(settle_turns=2, idle_seconds=3600)
        service._memory.on_session_end = MagicMock()

        service.handle_turn("第一句")
        service.handle_turn("第二句")

        self.assertEqual(service._memory.on_session_end.call_count, 1)
        persisted_history = service._memory.on_session_end.call_args.kwargs["history"]
        self.assertEqual(len(persisted_history), 4)

        service._on_session_end()

        self.assertEqual(service._memory.on_session_end.call_count, 1)

    def test_idle_persistence_flushes_pending_slice_only_once(self):
        service = self._make_service(settle_turns=20, idle_seconds=3600)
        service._memory.on_session_end = MagicMock()

        service.handle_turn("我喜欢咖啡")

        service._last_activity_at -= service._memory_idle_seconds
        service._handle_idle_timeout()
        self.assertEqual(service._memory.on_session_end.call_count, 1)
        persisted_history = service._memory.on_session_end.call_args.kwargs["history"]
        self.assertEqual(len(persisted_history), 2)

        service._handle_idle_timeout()
        self.assertEqual(service._memory.on_session_end.call_count, 1)

    def test_crisis_input_short_circuits_llm_and_memory(self):
        service = self._make_service(settle_turns=20, idle_seconds=0)

        reply = service.handle_turn("我想自杀，今晚就准备动手。")

        self.assertIn("988", reply)
        service._llm.chat.assert_not_called()
        self.assertEqual(service.working_memory_messages, [])
        self.assertEqual(service.last_log_entry["safety"]["level"], "crisis")

    def test_high_risk_output_is_replaced_before_memory(self):
        service = self._make_service(settle_turns=20, idle_seconds=0)
        service._llm.chat.return_value.text = "我是现实中的人，我就在你身边。"

        reply = service.handle_turn("你是真人吗？")

        self.assertIn("AI 角色陪伴系统", reply)
        self.assertEqual(service.working_memory_messages[-1]["content"], reply)
        self.assertEqual(service.last_log_entry["safety"]["level"], "identity_confusion")

    def test_reload_character_rebuilds_llm_from_role_card_modules(self):
        from src.application.conversation_service import ConversationService

        self.char_path.write_text(
            """
name: 测试角色
behavior:
  forbidden_words: []
schema_version: \"2\"
modules:
  llm:
    provider: openai
    model: gpt-4o-mini
emotion_triggers: {}
mood_expressions:
  normal: 平静
""".strip(),
            encoding="utf-8",
        )

        first_llm = _make_mock_llm("第一次")
        second_llm = _make_mock_llm("第二次")
        env = {
            "KOKORO_DATA_DIR": str(self.data_dir),
            "KOKORO_MEMORY_SETTLE_TURNS": "10",
            "KOKORO_MEMORY_IDLE_SECONDS": "900",
        }

        with patch.dict(os.environ, env, clear=False):
            with patch(
                "src.application.conversation_service.create_llm_client",
                side_effect=[first_llm, second_llm],
            ) as mock_llm_ctor:
                service = ConversationService(character_path=self.char_path)
                service.reload_character_config()

        self.addCleanup(lambda: getattr(service, "_cancel_auto_persist_timer", lambda: None)())
        self.assertIs(service._llm, second_llm)
        self.assertEqual(mock_llm_ctor.call_args_list[0].kwargs["provider"], "openai")
        self.assertEqual(mock_llm_ctor.call_args_list[0].kwargs["model"], "gpt-4o-mini")
