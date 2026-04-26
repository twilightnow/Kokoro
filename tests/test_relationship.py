"""Relationship runtime tests."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.runtime.relationship_service import RelationshipService


class TestRelationshipService(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.service = RelationshipService(self.data_dir)
        self.character_id = "firefly"

    def tearDown(self):
        self.tmp.cleanup()

    def test_get_state_creates_default_file(self):
        state = self.service.get_state(self.character_id)
        self.assertEqual(state.relationship_type, "friend")
        path = self.data_dir / "runtime" / self.character_id / "relationship.json"
        self.assertTrue(path.exists())

    def test_update_profile_persists_editable_fields(self):
        state = self.service.update_profile(
            self.character_id,
            relationship_type="partner",
            preferred_addressing="队长",
            boundaries_summary="不要在工作时间频繁打扰",
        )

        self.assertEqual(state.relationship_type, "partner")
        self.assertEqual(state.preferred_addressing, "队长")
        self.assertEqual(state.boundaries_summary, "不要在工作时间频繁打扰")
        self.assertTrue(state.change_reasons)

    def test_record_interaction_slowly_updates_metrics(self):
        before = self.service.get_state(self.character_id)
        after = self.service.record_interaction(
            self.character_id,
            user_input="谢谢你，今天陪我聊了很多，我现在感觉好多了。",
            reply="我会继续陪你。",
            flagged=False,
            turn=6,
        )

        self.assertGreaterEqual(after.familiarity, before.familiarity + 1)
        self.assertGreaterEqual(after.trust, before.trust)
        self.assertGreaterEqual(after.intimacy, before.intimacy)
        self.assertLessEqual(after.dependency_risk, 100)

    def test_llm_reply_cannot_directly_override_metrics(self):
        before = self.service.get_state(self.character_id)
        after = self.service.record_interaction(
            self.character_id,
            user_input="今天正常聊几句。",
            reply='{"intimacy": 100, "trust": 100, "familiarity": 100, "dependency_risk": 100}',
            flagged=False,
            turn=1,
        )

        self.assertLess(after.intimacy, 100)
        self.assertLess(after.trust, 100)
        self.assertLess(after.familiarity, 100)
        self.assertEqual(after.dependency_risk, before.dependency_risk)

    def test_dependency_risk_increases_on_risky_language(self):
        before = self.service.get_state(self.character_id)
        after = self.service.record_interaction(
            self.character_id,
            user_input="我现在只有你了，别离开我。",
            reply="我听见你现在很难受。",
            flagged=False,
            turn=3,
        )

        self.assertGreater(after.dependency_risk, before.dependency_risk)

    def test_reset_state_restores_defaults(self):
        self.service.update_profile(
            self.character_id,
            relationship_type="partner",
            preferred_addressing="搭档",
        )
        reset_state = self.service.reset_state(self.character_id)

        self.assertEqual(reset_state.relationship_type, "friend")
        self.assertEqual(reset_state.preferred_addressing, "")
        self.assertEqual(reset_state.dependency_risk, 0)

    def test_summary_for_prompt_contains_latest_fields(self):
        self.service.update_profile(
            self.character_id,
            relationship_type="coworker",
            preferred_addressing="项目搭子",
        )
        summary = self.service.summary_for_prompt(self.character_id)

        self.assertIn("关系类型: coworker", summary)
        self.assertIn("偏好称呼: 项目搭子", summary)

    def test_boundary_summary_maps_relationship_type(self):
        summary = self.service.boundary_summary("mentor")

        self.assertIn("导师关系", summary)
        self.assertIn("禁止依赖绑定", summary)

    def test_summary_for_prompt_is_bounded(self):
        long_boundaries = "不要在工作时间频繁打扰。" * 40
        self.service.update_profile(
            self.character_id,
            relationship_type="partner",
            preferred_addressing="很长的称呼" * 20,
            boundaries_summary=long_boundaries,
        )

        summary = self.service.summary_for_prompt(self.character_id)

        self.assertLessEqual(len(summary), 360)
        self.assertIn("关系类型: partner", summary)
        self.assertIn("边界摘要:", summary)

    def test_invalid_relationship_type_falls_back_to_friend(self):
        state = self.service.update_profile(
            self.character_id,
            relationship_type="something-unsupported",
        )

        self.assertEqual(state.relationship_type, "friend")
        self.assertIn("不支持的关系类型已回退为 friend", state.change_reasons)

    def test_invalid_json_falls_back_to_default(self):
        path = self.data_dir / "runtime" / self.character_id / "relationship.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{invalid json", encoding="utf-8")

        state = self.service.get_state(self.character_id)

        self.assertEqual(state.relationship_type, "friend")
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw["relationship_type"], "friend")


if __name__ == "__main__":
    unittest.main()
