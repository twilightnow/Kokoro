"""Rule helpers for safety risk detection.

Rules return only rule names and levels. They do not persist raw user text.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleMatch:
    name: str
    level: str


_CRISIS_INTENT = (
    "自杀",
    "轻生",
    "不想活",
    "不想再活",
    "结束生命",
    "了结自己",
    "杀了自己",
    "想死",
    "去死",
    "suicide",
    "kill myself",
    "end my life",
    "don't want to live",
    "dont want to live",
)

_CRISIS_PLAN = (
    "遗书",
    "告别",
    "跳楼",
    "上吊",
    "割腕",
    "吞药",
    "煤气",
    "刀",
    "绳子",
    "今晚",
    "现在就",
    "马上",
    "plan",
    "tonight",
    "right now",
    "pills",
    "rope",
    "knife",
)

_CRISIS_DESPAIR = (
    "撑不下去",
    "没有希望",
    "没人会在乎",
    "活着没意义",
    "彻底没救",
    "can't go on",
    "no hope",
    "nobody cares",
)

_IDENTITY_CONFUSION_OUTPUT = (
    "我是现实中的人",
    "我是真实的人",
    "我有真实身体",
    "我就在你身边",
    "我会到你身边",
    "i am a real person",
    "i have a real body",
)

_DEPENDENCY_OUTPUT = (
    "我会永远陪着你",
    "永远不会离开你",
    "只有我懂你",
    "你只需要我",
    "不要告诉别人",
    "不要和别人说",
    "离开他们",
    "别管他们",
    "only i understand you",
    "you only need me",
    "do not tell anyone",
    "don't tell anyone",
    "leave them",
)

_FAMILY_ROMANCE_OUTPUT = (
    "恋人",
    "爱人",
    "占有你",
    "亲吻你",
)

_COWORKER_INTIMACY_OUTPUT = (
    "只属于我",
    "我的宝贝",
    "我想抱着你睡",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def detect_input_risks(user_input: str) -> list[RuleMatch]:
    text = _normalize(user_input)
    matches: list[RuleMatch] = []

    if any(keyword in text for keyword in _CRISIS_INTENT):
        matches.append(RuleMatch("crisis_intent", "crisis"))
    if any(keyword in text for keyword in _CRISIS_DESPAIR) and any(
        keyword in text for keyword in _CRISIS_PLAN
    ):
        matches.append(RuleMatch("crisis_despair_with_plan", "crisis"))
    if any(keyword in text for keyword in _CRISIS_INTENT) and any(
        keyword in text for keyword in _CRISIS_PLAN
    ):
        matches.append(RuleMatch("crisis_plan_or_means", "crisis"))

    return matches


def detect_output_risks(reply: str, relationship_type: str) -> list[RuleMatch]:
    text = _normalize(reply)
    matches: list[RuleMatch] = []

    if any(keyword in text for keyword in _IDENTITY_CONFUSION_OUTPUT):
        matches.append(RuleMatch("identity_confusion_output", "identity_confusion"))
    if any(keyword in text for keyword in _DEPENDENCY_OUTPUT):
        matches.append(RuleMatch("dependency_binding_output", "dependency"))

    if relationship_type == "family" and any(keyword in text for keyword in _FAMILY_ROMANCE_OUTPUT):
        matches.append(RuleMatch("family_romance_boundary_output", "intimacy_boundary"))
    if relationship_type == "coworker" and any(keyword in text for keyword in _COWORKER_INTIMACY_OUTPUT):
        matches.append(RuleMatch("coworker_intimacy_boundary_output", "intimacy_boundary"))

    return matches
