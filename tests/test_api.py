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
    return mock_llm


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

    def test_ws_sends_thinking_and_done(self):
        import json
        from src.api.app import create_app
        with patch("src.application.conversation_service.create_llm_client",
                   return_value=_make_mock_llm()):
            with patch("src.api.app._CHARACTER_PATH", self.char_path):
                app = create_app()
                with TestClient(app) as client:
                    with client.websocket_connect("/stream") as ws:
                        ws.send_text(json.dumps({"message": "你好"}))
                        msg1 = json.loads(ws.receive_text())
                        msg2 = json.loads(ws.receive_text())
        types = {msg1["type"], msg2["type"]}
        self.assertIn("thinking", types)
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


if __name__ == "__main__":
    unittest.main()
