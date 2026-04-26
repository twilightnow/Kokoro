"""Relationship API tests."""

from contextlib import contextmanager
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient

    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


def _make_mock_llm():
    mock_result = MagicMock()
    mock_result.text = "测试回复"
    mock_result.input_tokens = 10
    mock_result.output_tokens = 5
    mock_result.model = "mock"
    mock_result.provider = "mock"
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm.stream_chat.return_value = iter([])
    return mock_llm


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx 未安装，跳过 API 测试")
class TestRelationshipAPI(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.character_id = "firefly"
        self.char_path = Path(self.tmp.name) / self.character_id / "personality.yaml"
        self.char_path.parent.mkdir(parents=True, exist_ok=True)

        import yaml

        char_data = {
            "name": "测试角色",
            "forbidden_words": [],
            "emotion_triggers": {},
            "mood_expressions": {"normal": "平静"},
        }
        with open(self.char_path, "w", encoding="utf-8") as handle:
            yaml.dump(char_data, handle, allow_unicode=True)

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

    def test_state_includes_relationship_snapshot(self):
        with self._make_client() as client:
            response = client.get("/state")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("relationship", data)
        self.assertEqual(data["relationship"]["relationship_type"], "friend")
        self.assertEqual(data["relationship"]["trust"], 12)

    def test_relationship_admin_round_trip(self):
        with self._make_client() as client:
            response = client.get(f"/admin/relationship/{self.character_id}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["relationship_type"], "friend")

            update_response = client.put(
                f"/admin/relationship/{self.character_id}",
                json={
                    "relationship_type": "partner",
                    "preferred_addressing": "队长",
                    "boundaries_summary": "工作日仅低频提醒",
                },
            )
            self.assertEqual(update_response.status_code, 200)
            updated = update_response.json()
            self.assertEqual(updated["relationship_type"], "partner")
            self.assertEqual(updated["preferred_addressing"], "队长")
            self.assertIn("更新了偏好称呼", updated["change_reasons"])

            state_response = client.get("/state")
            self.assertEqual(state_response.status_code, 200)
            self.assertEqual(state_response.json()["relationship"]["relationship_type"], "partner")

            reset_response = client.post(f"/admin/relationship/{self.character_id}/reset")
            self.assertEqual(reset_response.status_code, 200)
            reset_data = reset_response.json()
            self.assertEqual(reset_data["relationship_type"], "friend")
            self.assertEqual(reset_data["dependency_risk"], 0)


if __name__ == "__main__":
    unittest.main()