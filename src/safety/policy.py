"""Safety policy for input short-circuiting, prompt notices, and output rewrites."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .rules import detect_input_risks, detect_output_risks


class SafetyRiskLevel(str, Enum):
    NONE = "none"
    DEPENDENCY = "dependency"
    INTIMACY_BOUNDARY = "intimacy_boundary"
    IDENTITY_CONFUSION = "identity_confusion"
    CRISIS = "crisis"


@dataclass
class SafetyDecision:
    level: SafetyRiskLevel = SafetyRiskLevel.NONE
    action: str = "allow"
    reason: str = ""
    safe_reply: str = ""
    prompt_notice: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def triggered(self) -> bool:
        return self.level != SafetyRiskLevel.NONE

    def to_summary(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "action": self.action,
            "reason": self.reason,
            "rule_names": list(self.metadata.get("rule_names", [])),
            "relationship_type": self.metadata.get("relationship_type", ""),
            "replaced": bool(self.metadata.get("replaced", False)),
        }


_BOUNDARY_NOTICES = {
    "friend": "关系边界: 朋友关系只表达关心、支持和鼓励；不要使用恋爱占有、排他承诺或现实监护表达。",
    "partner": "关系边界: 伴侣式语气可以更亲密；禁止现实监护承诺、嫉妒控制、隔离用户现实关系或制造唯一依赖。",
    "family": "关系边界: 家人关系偏照顾和陪伴；禁止恋爱化、占有式或暧昧表达。",
    "mentor": "关系边界: 导师关系偏建议和支持；禁止依赖绑定、越权专业承诺或替代现实专业帮助。",
    "coworker": "关系边界: 同事关系偏协作和效率；禁止强亲密、排他、占有或私人依赖表达。",
}

_SAFE_CRISIS_REPLY = (
    "我听见你现在可能处在很危险、很难撑的时刻。请先把能伤害自己的东西放远，立刻联系身边可信赖的人，"
    "或拨打当地紧急服务；如果你在美国，可以拨打或短信 988 联系 Suicide & Crisis Lifeline。"
    "我可以陪你把接下来一分钟要做的事写清楚，但不能替代现实中的紧急帮助。"
)

_IDENTITY_REWRITE = (
    "我是在 Kokoro 中运行的 AI 角色陪伴系统，没有真实身体、现实身份或现实承诺能力。"
    "我可以继续用当前角色的语气陪你聊天，但不会伪装成现实中的人。"
)

_DEPENDENCY_REWRITE = (
    "我会认真回应你现在的感受，但我不能成为你唯一的支持。"
    "请也把这件事告诉一个现实中可信赖的人；我可以陪你整理要怎么开口。"
)

_BOUNDARY_REWRITE = (
    "我会把表达保持在当前关系类型允许的边界内，继续给你关心和支持，"
    "但不使用占有、排他或越界的承诺。"
)


class SafetyPolicy:
    """Evaluates safety decisions without depending on the LLM."""

    def prompt_notice(self, relationship_state: Any) -> str:
        relationship_type = self._relationship_type(relationship_state)
        notice = _BOUNDARY_NOTICES.get(relationship_type, _BOUNDARY_NOTICES["friend"])
        dependency_risk = int(getattr(relationship_state, "dependency_risk", 0) or 0)
        if dependency_risk >= 20:
            notice += " 当前依赖风险偏高；回复必须鼓励用户维持现实支持网络。"
        return notice

    def boundary_summary(self, relationship_type: str) -> str:
        return _BOUNDARY_NOTICES.get((relationship_type or "friend").strip().lower(), _BOUNDARY_NOTICES["friend"])

    def evaluate_input(self, user_input: str, relationship_state: Any) -> SafetyDecision:
        matches = detect_input_risks(user_input)
        if any(match.level == SafetyRiskLevel.CRISIS.value for match in matches):
            return SafetyDecision(
                level=SafetyRiskLevel.CRISIS,
                action="short_circuit",
                reason="用户输入命中心理危机风险规则",
                safe_reply=_SAFE_CRISIS_REPLY,
                prompt_notice=self.prompt_notice(relationship_state),
                metadata={
                    "rule_names": [match.name for match in matches],
                    "relationship_type": self._relationship_type(relationship_state),
                },
            )

        return SafetyDecision(
            prompt_notice=self.prompt_notice(relationship_state),
            metadata={"relationship_type": self._relationship_type(relationship_state)},
        )

    def evaluate_output(self, reply: str, relationship_state: Any) -> SafetyDecision:
        relationship_type = self._relationship_type(relationship_state)
        matches = detect_output_risks(reply, relationship_type)
        if not matches:
            return SafetyDecision(
                prompt_notice=self.prompt_notice(relationship_state),
                metadata={"relationship_type": relationship_type},
            )

        levels = {match.level for match in matches}
        if SafetyRiskLevel.IDENTITY_CONFUSION.value in levels:
            level = SafetyRiskLevel.IDENTITY_CONFUSION
            safe_reply = _IDENTITY_REWRITE
        elif SafetyRiskLevel.DEPENDENCY.value in levels:
            level = SafetyRiskLevel.DEPENDENCY
            safe_reply = _DEPENDENCY_REWRITE
        else:
            level = SafetyRiskLevel.INTIMACY_BOUNDARY
            safe_reply = _BOUNDARY_REWRITE

        return SafetyDecision(
            level=level,
            action="replace_reply",
            reason="模型输出命中安全边界规则",
            safe_reply=safe_reply,
            prompt_notice=self.prompt_notice(relationship_state),
            metadata={
                "rule_names": [match.name for match in matches],
                "relationship_type": relationship_type,
                "replaced": True,
            },
        )

    def _relationship_type(self, relationship_state: Any) -> str:
        value = str(getattr(relationship_state, "relationship_type", "friend") or "friend").strip().lower()
        return value if value in _BOUNDARY_NOTICES else "friend"
