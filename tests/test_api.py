"""
API 层单元测试：使用 FastAPI TestClient 测试 HTTP 和 WebSocket 端点。

测试隔离：使用 unittest.mock.patch 替换 LLM 调用，避免真实网络请求。
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


if __name__ == "__main__":
    unittest.main()
