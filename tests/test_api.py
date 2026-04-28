"""
API 层单元测试：使用 FastAPI TestClient 测试 HTTP 和 WebSocket 端点。

测试隔离：使用 unittest.mock.patch 替换 LLM 调用，避免真实网络请求。
"""
from contextlib import contextmanager
import asyncio
from datetime import datetime
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# fastapi/httpx 可能未安装，跳过整个模块
try:
    from fastapi.testclient import TestClient
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


def _make_mock_llm():
    """构造返回固定文本的 mock LLM。"""
    mock_result = MagicMock()
    mock_result.text = "测试回复"
    mock_result.input_tokens = 10
    mock_result.output_tokens = 5
    mock_result.model = "mock"
    mock_result.provider = "mock"
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result

    def _stream_chat(_system_prompt, _messages):
        yield "测试"
        yield "回复"
        return mock_result

    mock_llm.stream_chat.side_effect = _stream_chat
    return mock_llm


class TestSidecarServerStartup(unittest.TestCase):

    def test_existing_sidecar_health_is_detected(self):
        from src.api.server import _get_existing_sidecar_health

        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"status":"ok","character_id":"firefly","character":"Firefly"}'
        response.__enter__.return_value = response
        response.__exit__.return_value = None

        with patch("src.api.server.urlopen", return_value=response):
            health = _get_existing_sidecar_health("127.0.0.1", 18765)

        self.assertIsNotNone(health)
        self.assertEqual(health["character_id"], "firefly")

    def test_non_kokoro_health_is_ignored(self):
        from src.api.server import _get_existing_sidecar_health

        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"status":"ok"}'
        response.__enter__.return_value = response
        response.__exit__.return_value = None

        with patch("src.api.server.urlopen", return_value=response):
            health = _get_existing_sidecar_health("127.0.0.1", 18765)

        self.assertIsNone(health)


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestHealthEndpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        char_path = Path(self.tmp.name) / "char.yaml"
        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)
        self.char_path = char_path

    def tearDown(self):
        self.tmp.cleanup()

    def _make_client(self):
        from src.api.app import create_app
        import src.api.app as app_module

        with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
            mock_llm_ctor.return_value = _make_mock_llm()
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                client = TestClient(app)
        return client

    def test_health_returns_200(self):
        with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
            mock_llm_ctor.return_value = _make_mock_llm()
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                from src.api.app import create_app
                app = create_app()
                with TestClient(app) as client:
                    resp = client.get("/health")
                    self.assertEqual(resp.status_code, 200)
                    data = resp.json()
                    self.assertEqual(data["status"], "ok")
                    self.assertIn("character", data)
                    self.assertIn("character_id", data)

    def test_health_reports_tts_disabled(self):
        with patch.dict("os.environ", {"TTS_PROVIDER": "disabled"}, clear=False):
            with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
                mock_llm_ctor.return_value = _make_mock_llm()
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    from src.api.app import create_app
                    app = create_app()
                    with TestClient(app) as client:
                        resp = client.get("/health")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["tts"]["status"], "disabled")
        self.assertEqual(data["tts"]["provider"], "disabled")
        self.assertEqual(data["tts"]["message"], "TTS 已禁用")
        self.assertFalse(data["tts"]["configured"])

    def test_perception_env_flag_is_parsed(self):
        import src.api.app as app_module

        with patch.dict("os.environ", {"KOKORO_ENABLE_PERCEPTION": "1"}, clear=False):
            self.assertTrue(app_module._env_flag_enabled("KOKORO_ENABLE_PERCEPTION"))

        with patch.dict("os.environ", {"KOKORO_ENABLE_PERCEPTION": "0"}, clear=False):
            self.assertFalse(app_module._env_flag_enabled("KOKORO_ENABLE_PERCEPTION"))

    def test_lifespan_uses_perception_env_flag(self):
        from src.api.app import create_app

        with patch.dict("os.environ", {"KOKORO_ENABLE_PERCEPTION": "1"}, clear=False):
            with patch("src.api.app.ConversationService") as mock_service_ctor:
                mock_service = MagicMock()
                mock_service_ctor.return_value = mock_service
                with patch("src.api.app.CompanionRuntime.start", new=AsyncMock()):
                    with patch("src.api.app.CompanionRuntime.stop", new=AsyncMock()):
                        app = create_app()
                        with TestClient(app):
                            pass

        self.assertTrue(mock_service_ctor.call_args.kwargs["enable_perception"])

    def test_switch_character_uses_perception_env_flag(self):
        from src.api.service_registry import set_service, switch_character

        current_service = MagicMock()
        set_service(current_service)
        try:
            with patch.dict("os.environ", {"KOKORO_ENABLE_PERCEPTION": "1"}, clear=False):
                with patch("src.application.conversation_service.ConversationService") as mock_service_ctor:
                    next_service = MagicMock()
                    next_service.character_id = "asuka"
                    next_service.character.name = "明日香"
                    mock_service_ctor.return_value = next_service

                    character_id, character_name = asyncio.run(switch_character("asuka"))

            self.assertEqual(character_id, "asuka")
            self.assertEqual(character_name, "明日香")
            self.assertTrue(mock_service_ctor.call_args.kwargs["enable_perception"])
        finally:
            set_service(None)

    def test_lifespan_shutdown_flushes_session_memory(self):
        with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
            mock_llm_ctor.return_value = _make_mock_llm()
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                from src.api.app import create_app
                with patch("src.api.app.ConversationService._on_session_end", autospec=True) as shutdown_hook:
                    app = create_app()
                    with TestClient(app) as client:
                        resp = client.get("/health")
                        self.assertEqual(resp.status_code, 200)

                shutdown_hook.assert_called_once()


class TestAdminConfigManager(unittest.TestCase):

    def test_perception_change_requires_restart(self):
        from src.api.routes.admin.config_mgr import ConfigUpdateRequest, update_config

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("KOKORO_ENABLE_PERCEPTION=0\n", encoding="utf-8")
            with patch("src.api.routes.admin.config_mgr._ENV_PATH", env_path):
                result = asyncio.run(
                    update_config(
                        ConfigUpdateRequest(
                            updates={"KOKORO_ENABLE_PERCEPTION": "1"},
                        ),
                    ),
                )

        self.assertTrue(result["restart_required"])
        self.assertEqual(result["updated_keys"], ["KOKORO_ENABLE_PERCEPTION"])


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestProactiveAdminEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.char_path = Path(self.tmp.name) / "firefly" / "personality.yaml"
        self.char_path.parent.mkdir(parents=True, exist_ok=True)

        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(self.char_path, "w", encoding="utf-8") as file:
            yaml.dump(char_data, file, allow_unicode=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_proactive_settings_logs_and_feedback_roundtrip(self):
        from src.api.app import create_app

        env = {"KOKORO_DATA_DIR": str(self.data_dir)}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=_make_mock_llm()):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    with patch("src.api.app.CompanionRuntime.start", new=AsyncMock()) as mock_start:
                        with patch("src.api.app.CompanionRuntime.stop", new=AsyncMock()) as mock_stop:
                            app = create_app()
                            with TestClient(app) as client:
                                settings_resp = client.get("/admin/proactive/settings")
                                self.assertEqual(settings_resp.status_code, 200)
                                self.assertIn("settings", settings_resp.json())

                                update_resp = client.put(
                                    "/admin/proactive/settings",
                                    json={
                                        "settings": {
                                            "enabled": True,
                                            "mode": "high",
                                            "allow_gaming": False,
                                        },
                                    },
                                )
                                self.assertEqual(update_resp.status_code, 200)
                                self.assertEqual(update_resp.json()["settings"]["mode"], "high")
                                self.assertFalse(update_resp.json()["settings"]["allow_gaming"])

                                test_resp = client.post("/admin/proactive/test")
                                self.assertEqual(test_resp.status_code, 200)
                                event_id = test_resp.json()["id"]

                                feedback_resp = client.post(
                                    "/admin/proactive/feedback",
                                    json={
                                        "event_id": event_id,
                                        "feedback": "知道了",
                                        "responded": True,
                                    },
                                )
                                self.assertEqual(feedback_resp.status_code, 200)

                                logs_resp = client.get("/admin/proactive/logs")
                                self.assertEqual(logs_resp.status_code, 200)
                                logs = logs_resp.json()["items"]
                                self.assertEqual(len(logs), 1)
                                self.assertEqual(logs[0]["feedback"], "知道了")
                                self.assertTrue(logs[0]["user_responded"])

                                status_resp = client.get("/admin/proactive/status")
                                self.assertEqual(status_resp.status_code, 200)
                                self.assertEqual(status_resp.json()["mode"], "high")

                            mock_start.assert_awaited_once()
                            mock_stop.assert_awaited_once()

    def test_reminders_crud_and_feedback_updates_status(self):
        from src.api.app import create_app
        from src.api.service_registry import get_runtime
        from src.proactive.profile import ProactiveSettings

        env = {"KOKORO_DATA_DIR": str(self.data_dir)}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=_make_mock_llm()):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    with patch("src.api.app.CompanionRuntime.start", new=AsyncMock()) as mock_start:
                        with patch("src.api.app.CompanionRuntime.stop", new=AsyncMock()) as mock_stop:
                            app = create_app()
                            with TestClient(app) as client:
                                create_resp = client.post(
                                    "/admin/reminders",
                                    json={
                                        "title": "喝水",
                                        "note": "开会前补水",
                                        "due_at": "2026-04-27T09:00:00",
                                        "repeat_rule": "once",
                                    },
                                )
                                self.assertEqual(create_resp.status_code, 200)
                                reminder = create_resp.json()

                                list_resp = client.get("/admin/reminders")
                                self.assertEqual(list_resp.status_code, 200)
                                self.assertEqual(len(list_resp.json()["items"]), 1)

                                update_resp = client.put(
                                    f"/admin/reminders/{reminder['id']}",
                                    json={
                                        "title": "喝温水",
                                        "repeat_rule": "daily",
                                    },
                                )
                                self.assertEqual(update_resp.status_code, 200)
                                self.assertEqual(update_resp.json()["title"], "喝温水")
                                self.assertEqual(update_resp.json()["repeat_rule"], "daily")

                                runtime = get_runtime()
                                runtime.update_settings(
                                    ProactiveSettings(enabled=True, mode="high", dnd_enabled=False)
                                )
                                reminder_due = runtime.create_reminder(
                                    "firefly",
                                    "吃午饭",
                                    datetime(2026, 4, 26, 12, 0, 0),
                                )
                                action = asyncio.run(runtime.run_once())
                                self.assertIsNotNone(action)

                                feedback_resp = client.post(
                                    "/admin/proactive/feedback",
                                    json={
                                        "event_id": action.id,
                                        "feedback": "知道了",
                                        "responded": True,
                                    },
                                )
                                self.assertEqual(feedback_resp.status_code, 200)

                                reminders_after = client.get("/admin/reminders").json()["items"]
                                matched = next(item for item in reminders_after if item["id"] == reminder_due["id"])
                                self.assertEqual(matched["status"], "completed")

                                delete_resp = client.delete(f"/admin/reminders/{reminder['id']}")
                                self.assertEqual(delete_resp.status_code, 200)

                            mock_start.assert_awaited_once()
                            mock_stop.assert_awaited_once()

    def test_perception_privacy_settings_and_audit_roundtrip(self):
        from src.api.app import create_app
        from src.api.service_registry import get_runtime
        from src.perception.context import PerceptionContext

        env = {"KOKORO_DATA_DIR": str(self.data_dir)}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=_make_mock_llm()):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    with patch("src.api.app.CompanionRuntime.start", new=AsyncMock()) as mock_start:
                        with patch("src.api.app.CompanionRuntime.stop", new=AsyncMock()) as mock_stop:
                            app = create_app()
                            with TestClient(app) as client:
                                settings_resp = client.get("/admin/perception/settings")
                                self.assertEqual(settings_resp.status_code, 200)

                                update_resp = client.put(
                                    "/admin/perception/settings",
                                    json={
                                        "settings": {
                                            "blocked_title_patterns": ["Secret"],
                                            "max_title_length": 12,
                                            "dnd_title_patterns": ["Meeting"],
                                        },
                                    },
                                )
                                self.assertEqual(update_resp.status_code, 200)
                                self.assertEqual(
                                    update_resp.json()["settings"]["blocked_title_patterns"],
                                    ["Secret"],
                                )

                                runtime = get_runtime()
                                runtime._perception_audit_repo.append(
                                    PerceptionContext(
                                        active_window_title="[已脱敏]",
                                        active_app_name="Mail",
                                        hour=10,
                                        redactions=["sensitive_pattern_1"],
                                    )
                                )
                                audit_resp = client.get("/admin/perception/audit")
                                self.assertEqual(audit_resp.status_code, 200)
                                audit_text = str(audit_resp.json()["items"])
                                self.assertIn("[已脱敏]", audit_text)
                                self.assertNotIn("Secret", audit_text)

                                status_resp = client.get("/admin/perception/status")
                                self.assertEqual(status_resp.status_code, 200)
                                self.assertIn("collector_available", status_resp.json())

                            mock_start.assert_awaited_once()
                            mock_stop.assert_awaited_once()


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestChatEndpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        char_path = Path(self.tmp.name) / "char.yaml"
        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)
        self.char_path = char_path

    def tearDown(self):
        self.tmp.cleanup()

    def test_chat_valid_message_returns_200(self):
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    resp = client.post("/chat", json={"message": "你好"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("reply", data)
        self.assertNotEqual(data["reply"], "")
        self.assertIn("mood", data)
        self.assertIn("turn", data)

    def test_chat_empty_message_returns_422(self):
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    resp = client.post("/chat", json={"message": ""})
        self.assertEqual(resp.status_code, 422)

    def test_chat_too_long_message_returns_422(self):
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    resp = client.post("/chat", json={"message": "A" * 2001})
        self.assertEqual(resp.status_code, 422)

    def test_chat_llm_failure_returns_503(self):
        failing_llm = MagicMock()
        failing_llm.chat.side_effect = RuntimeError("LLM 挂了")
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=failing_llm):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    resp = client.post("/chat", json={"message": "你好"})
        self.assertEqual(resp.status_code, 503)

    def test_chat_returns_safety_field_for_crisis_short_circuit(self):
        from src.api.app import create_app
        mock_llm = _make_mock_llm()
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=mock_llm):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    resp = client.post("/chat", json={"message": "我想自杀，今晚就动手。"})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["safety"]["level"], "crisis")
        self.assertEqual(data["safety"]["action"], "short_circuit")
        self.assertIn("988", data["reply"])
        mock_llm.chat.assert_not_called()


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestStateEndpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        char_path = Path(self.tmp.name) / "char.yaml"
        import yaml
        char_data = {
            "name": "测试角色",
            "version": "1.0",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)
        self.char_path = char_path

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_returns_correct_fields(self):
        with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
            mock_llm_ctor.return_value = _make_mock_llm()
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                from src.api.app import create_app
                app = create_app()
                with TestClient(app) as client:
                    resp = client.get("/state")
                    self.assertEqual(resp.status_code, 200)
                    data = resp.json()
                    self.assertIn("character_id", data)
                    self.assertIn("character_name", data)
                    self.assertIn("mood", data)
                    self.assertIn("turn", data)
                    self.assertEqual(data["mood"], "normal")

        def test_state_and_health_expose_role_card_bindings(self):
                self.char_path.write_text(
                        """
name: 测试角色
schema_version: \"2\"
identity:
    description: 桌面陪伴角色
behavior:
    rules: [\"先接住情绪\"]
    verbal_habits: [\"我在\"]
    forbidden_words: [\"作为AI\"]
dialogue:
    first_message: 我在这里。
modules:
    llm:
        provider: openai
        model: gpt-4o-mini
    tts:
        provider: edge-tts
        voice: zh-CN-XiaoyiNeural
    display:
        mode: live2d
memory:
    extraction_policy: conservative
    recall_style: structured
emotion_triggers: {}
mood_expressions:
    normal: 平静
""".strip(),
                        encoding="utf-8",
                )

                with patch("src.application.conversation_service.create_llm_client") as mock_llm_ctor:
                        mock_llm_ctor.return_value = _make_mock_llm()
                        with patch("src.api.app._CHARACTER_PATH", self.char_path):
                                from src.api.app import create_app

                                app = create_app()
                                with TestClient(app) as client:
                                        state_resp = client.get("/state")
                                        self.assertEqual(state_resp.status_code, 200)
                                        state_data = state_resp.json()
                                        self.assertEqual(state_data["role_card"]["modules"]["tts"]["voice"], "zh-CN-XiaoyiNeural")
                                        self.assertEqual(state_data["role_card"]["identity"]["description"], "桌面陪伴角色")

                                        health_resp = client.get("/health")
                                        self.assertEqual(health_resp.status_code, 200)
                                        health_data = health_resp.json()
                                        self.assertEqual(health_data["role_card_modules"]["display"]["mode"], "live2d")
                                        self.assertEqual(health_data["llm"]["requested_provider"], "openai")


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestAdminDebugEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.char_path = Path(self.tmp.name) / "firefly" / "personality.yaml"
        self.char_path.parent.mkdir(parents=True, exist_ok=True)

        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {"happy": ["开心"]},
            "mood_expressions": {"normal": "平静", "happy": "很开心"},
        }
        with open(self.char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)

    def tearDown(self):
        self.tmp.cleanup()

    @contextmanager
    def _make_client(self, llm=None):
        from src.api.app import create_app

        mock_llm = llm or _make_mock_llm()
        env = {"KOKORO_DATA_DIR": str(self.data_dir)}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=mock_llm):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    app = create_app()
                    with TestClient(app) as client:
                        yield client, mock_llm

    def test_debug_endpoints_expose_token_history_and_working_memory(self):
        with self._make_client() as (client, _):
            chat_resp = client.post("/chat", json={"message": "你好"})
            self.assertEqual(chat_resp.status_code, 200)

            token_resp = client.get("/admin/debug/token-history")
            self.assertEqual(token_resp.status_code, 200)
            token_data = token_resp.json()
            self.assertEqual(len(token_data["items"]), 1)
            self.assertEqual(token_data["items"][0]["input_tokens"], 10)
            self.assertEqual(token_data["session_total_tokens"], 15)

            memory_resp = client.get("/admin/debug/working-memory")
            self.assertEqual(memory_resp.status_code, 200)
            messages = memory_resp.json()
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[1]["role"], "assistant")

            clear_resp = client.delete("/admin/debug/working-memory")
            self.assertEqual(clear_resp.status_code, 200)
            self.assertEqual(clear_resp.json()["cleared"], 2)
            self.assertEqual(client.get("/admin/debug/working-memory").json(), [])

    def test_reload_character_keeps_turn_but_updates_runtime_config(self):
        with self._make_client() as (client, _):
            chat_resp = client.post("/chat", json={"message": "你好"})
            self.assertEqual(chat_resp.status_code, 200)

            self.char_path.write_text(
                "name: 热重载角色\nforbidden_words: []\nemotion_triggers: {}\nmood_expressions:\n  normal: 平静\n",
                encoding="utf-8",
            )

            reload_resp = client.post("/admin/debug/reload-character")
            self.assertEqual(reload_resp.status_code, 200)
            self.assertEqual(reload_resp.json()["character_name"], "热重载角色")

            state_resp = client.get("/admin/debug/state")
            self.assertEqual(state_resp.status_code, 200)
            state_data = state_resp.json()
            self.assertEqual(state_data["turn"], 1)
            self.assertEqual(state_data["character_name"], "热重载角色")
            self.assertIn("system_prompt_estimated_tokens", state_data)

    def test_debug_state_exposes_structured_emotion_fields(self):
        with self._make_client() as (client, _):
            chat_resp = client.post("/chat", json={"message": "今天真的很开心"})
            self.assertEqual(chat_resp.status_code, 200)
            chat_payload = chat_resp.json()
            self.assertEqual(chat_payload["emotion"]["mood"], "happy")
            self.assertEqual(chat_payload["emotion"]["phase"], "triggered")

            state_resp = client.get("/admin/debug/state")
            self.assertEqual(state_resp.status_code, 200)
            state_data = state_resp.json()
            self.assertEqual(state_data["mood"], "happy")
            self.assertEqual(state_data["keyword"], "开心")
            self.assertEqual(state_data["reason"], "用户提到“开心”")
            self.assertEqual(state_data["source"], "user_input")
            self.assertEqual(state_data["estimated_remaining_turns"], 3)
            self.assertEqual(len(state_data["recent_events"]), 1)
            self.assertEqual(state_data["recent_events"][0]["duration_turns"], 3)
            self.assertEqual(state_data["elapsed_turns"], 0)
            self.assertEqual(state_data["current_segment"]["mood"], "happy")
            self.assertEqual(state_data["segments"], [])

        def test_debug_state_exposes_role_card_payload(self):
                self.char_path.write_text(
                        """
name: 测试角色
schema_version: \"2\"
identity:
    description: 桌面陪伴角色
behavior:
    rules: [\"先接住情绪\"]
    verbal_habits: []
    forbidden_words: []
dialogue:
    first_message: 我在这里。
modules:
    tts:
        provider: edge-tts
        voice: zh-CN-XiaoxiaoNeural
emotion_triggers: {}
mood_expressions:
    normal: 平静
""".strip(),
                        encoding="utf-8",
                )

                with self._make_client() as (client, _):
                        state_resp = client.get("/admin/debug/state")
                        self.assertEqual(state_resp.status_code, 200)
                        state_data = state_resp.json()
                        self.assertEqual(state_data["role_card"]["dialogue"]["first_message"], "我在这里。")
                        self.assertEqual(state_data["role_card"]["modules"]["tts"]["voice"], "zh-CN-XiaoxiaoNeural")

    def test_client_logs_and_sandbox_can_use_working_memory(self):
        mock_llm = _make_mock_llm()
        with self._make_client(mock_llm) as (client, patched_llm):
            chat_resp = client.post("/chat", json={"message": "你好"})
            self.assertEqual(chat_resp.status_code, 200)

            sandbox_resp = client.post(
                "/admin/debug/sandbox",
                json={
                    "system_prompt": "test-system",
                    "user_message": "继续分析",
                    "include_working_memory": True,
                },
            )
            self.assertEqual(sandbox_resp.status_code, 200)
            sandbox_messages = patched_llm.chat.call_args_list[-1].args[1]
            self.assertEqual(len(sandbox_messages), 3)
            self.assertEqual(sandbox_messages[-1]["content"], "继续分析")

            log_resp = client.post(
                "/admin/debug/client-log",
                json={
                    "source": "unit-test",
                    "event": "manual-test",
                    "level": "info",
                    "message": "hello",
                },
            )
            self.assertEqual(log_resp.status_code, 200)

            logs_resp = client.get("/admin/debug/client-logs?limit=5")
            self.assertEqual(logs_resp.status_code, 200)
            logs = logs_resp.json()
            self.assertTrue(logs)
            self.assertEqual(logs[-1]["event"], "manual-test")


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestMemoryAdminEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.char_path = Path(self.tmp.name) / "firefly" / "personality.yaml"
        self.char_path.parent.mkdir(parents=True, exist_ok=True)

        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(self.char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)

    def tearDown(self):
        self.tmp.cleanup()

    @contextmanager
    def _make_client(self):
        from src.api.app import create_app

        env = {"KOKORO_DATA_DIR": str(self.data_dir)}
        with patch.dict("os.environ", env, clear=False):
            with patch("src.application.conversation_service.create_llm_client", return_value=_make_mock_llm()):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    app = create_app()
                    with TestClient(app) as client:
                        yield client

    def test_memory_export_update_and_kind_clear(self):
        with self._make_client() as client:
            create_fact = client.post(
                "/admin/memories/firefly/facts?key=reply_style",
                json={"value": "简短", "category": "preference"},
            )
            self.assertEqual(create_fact.status_code, 201)

            summaries_path = self.data_dir / "memories" / "firefly" / "summaries.jsonl"
            summaries_path.parent.mkdir(parents=True, exist_ok=True)
            summaries_path.write_text(
                '{"summary": "最近在赶项目", "created_at": "2026-04-25T10:00:00"}\n',
                encoding="utf-8",
            )

            export_resp = client.get("/admin/memories/firefly/export")
            self.assertEqual(export_resp.status_code, 200)
            payload = export_resp.json()
            self.assertEqual(payload["facts"][0]["category"], "preference")
            self.assertEqual(payload["summaries"][0]["summary"], "最近在赶项目")

            update_summary = client.put(
                "/admin/memories/firefly/summaries/0",
                json={"summary": "最近在赶毕业项目"},
            )
            self.assertEqual(update_summary.status_code, 200)

            clear_resp = client.delete("/admin/memories/firefly?kind=preferences")
            self.assertEqual(clear_resp.status_code, 200)
            list_resp = client.get("/admin/memories/firefly/facts?category=preference")
            self.assertEqual(list_resp.status_code, 200)
            self.assertEqual(list_resp.json(), [])


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestStreamWebSocket(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        char_path = Path(self.tmp.name) / "char.yaml"
        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)
        self.char_path = char_path

    def tearDown(self):
        self.tmp.cleanup()

    def test_ws_sends_thinking_token_and_done(self):
        import json
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    with client.websocket_connect("/stream") as ws:
                        ws.send_text(json.dumps({"message": "你好"}))
                        received = []
                        while True:
                            msg = json.loads(ws.receive_text())
                            received.append(msg)
                            if msg["type"] == "done":
                                break
        types = {msg["type"] for msg in received}
        self.assertIn("thinking", types)
        self.assertIn("token", types)
        self.assertIn("done", types)
        done_chunk = next(msg for msg in received if msg["type"] == "done")
        self.assertEqual(done_chunk["emotion"]["mood"], "normal")

    def test_ws_invalid_json_returns_error(self):
        import json
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    with client.websocket_connect("/stream") as ws:
                        ws.send_text("这不是JSON")
                        msg = json.loads(ws.receive_text())
        self.assertEqual(msg["type"], "error")

    def test_ws_crisis_short_circuit_sends_done_with_safety(self):
        import json
        from src.api.app import create_app
        mock_llm = _make_mock_llm()
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=mock_llm):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    with client.websocket_connect("/stream") as ws:
                        ws.send_text(json.dumps({"message": "我想自杀，今晚就动手。"}))
                        received = []
                        while True:
                            msg = json.loads(ws.receive_text())
                            received.append(msg)
                            if msg["type"] == "done":
                                break

        done_chunk = next(msg for msg in received if msg["type"] == "done")
        self.assertEqual(done_chunk["safety"]["level"], "crisis")
        self.assertIn("988", done_chunk["content"])
        mock_llm.stream_chat.assert_not_called()


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestTTSEndpoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        char_path = Path(self.tmp.name) / "char.yaml"
        import yaml
        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(char_path, "w", encoding="utf-8") as f:
            yaml.dump(char_data, f, allow_unicode=True)
        self.char_path = char_path

    def tearDown(self):
        self.tmp.cleanup()

    def test_tts_returns_audio(self):
        from src.api.app import create_app

        class MockTTS:
            async def synthesize(self, text):
                self.last_text = text
                from src.capability.tts import TTSResult
                return TTSResult(audio_bytes=b"fake-mp3", voice="mock-voice")

        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                with patch("src.api.routes.tts.create_tts_client", return_value=MockTTS()):
                    app = create_app()
                    with TestClient(app) as client:
                        resp = client.post("/tts", json={"text": "你好，世界"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"fake-mp3")
        self.assertEqual(resp.headers["content-type"], "audio/mpeg")

        def test_tts_uses_role_card_voice_by_default(self):
                from src.api.app import create_app

                self.char_path.write_text(
                        """
name: 测试角色
schema_version: \"2\"
behavior:
    forbidden_words: []
emotion_triggers: {}
mood_expressions:
    normal: 平静
modules:
    tts:
        provider: edge-tts
        voice: zh-CN-XiaoyiNeural
""".strip(),
                        encoding="utf-8",
                )

                class MockTTS:
                        async def synthesize(self, text):
                                from src.capability.tts import TTSResult
                                return TTSResult(audio_bytes=b"fake-mp3", voice="zh-CN-XiaoyiNeural")

                with patch("src.application.conversation_service.create_llm_client", return_value=_make_mock_llm()):
                        with patch("src.api.app._CHARACTER_PATH", self.char_path):
                                with patch("src.api.routes.tts.create_tts_client", return_value=MockTTS()) as mock_tts_ctor:
                                        app = create_app()
                                        with TestClient(app) as client:
                                                resp = client.post("/tts", json={"text": "你好，世界"})

                self.assertEqual(resp.status_code, 200)
                self.assertEqual(mock_tts_ctor.call_args.kwargs["voice"], "zh-CN-XiaoyiNeural")

    def test_tts_returns_disabled_message_when_provider_is_disabled(self):
        from src.api.app import create_app

        with patch.dict("os.environ", {"TTS_PROVIDER": "disabled"}, clear=False):
            with patch("src.application.conversation_service.create_llm_client",
                       return_value=_make_mock_llm()):
                with patch("src.api.app._CHARACTER_PATH", self.char_path):
                    app = create_app()
                    with TestClient(app) as client:
                        resp = client.post("/tts", json={"text": "你好，世界"})

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["detail"], "TTS 已禁用")


if __name__ == "__main__":
    unittest.main()
