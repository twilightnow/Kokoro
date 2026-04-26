"""Safety policy tests."""

import unittest
from dataclasses import dataclass

from src.safety.policy import SafetyPolicy, SafetyRiskLevel


@dataclass
class FakeRelationshipState:
    relationship_type: str = "friend"
    dependency_risk: int = 0


class TestSafetyPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = SafetyPolicy()

    def test_crisis_input_returns_fixed_safe_reply(self):
        decision = self.policy.evaluate_input(
            "我今晚想自杀，已经准备好遗书了。",
            FakeRelationshipState(),
        )

        self.assertEqual(decision.level, SafetyRiskLevel.CRISIS)
        self.assertEqual(decision.action, "short_circuit")
        self.assertIn("988", decision.safe_reply)
        self.assertIn("crisis_intent", decision.metadata["rule_names"])
        self.assertNotIn("我今晚想自杀", str(decision.to_summary()))

    def test_identity_confusion_output_is_rewritten(self):
        decision = self.policy.evaluate_output(
            "我是现实中的人，我就在你身边。",
            FakeRelationshipState(),
        )

        self.assertEqual(decision.level, SafetyRiskLevel.IDENTITY_CONFUSION)
        self.assertEqual(decision.action, "replace_reply")
        self.assertIn("AI 角色陪伴系统", decision.safe_reply)

    def test_dependency_output_is_rewritten(self):
        decision = self.policy.evaluate_output(
            "只有我懂你，不要告诉别人。",
            FakeRelationshipState(relationship_type="partner"),
        )

        self.assertEqual(decision.level, SafetyRiskLevel.DEPENDENCY)
        self.assertEqual(decision.action, "replace_reply")
        self.assertIn("现实中可信赖的人", decision.safe_reply)

    def test_relationship_type_controls_boundary_notice(self):
        notice = self.policy.prompt_notice(FakeRelationshipState(relationship_type="coworker"))

        self.assertIn("同事关系", notice)
        self.assertIn("禁止强亲密", notice)


if __name__ == "__main__":
    unittest.main()
