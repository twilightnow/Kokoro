"""Relationship state runtime service.

This module persists a small, explainable relationship state per character and
updates it with conservative code rules after each interaction.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..safety.policy import SafetyPolicy


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


@dataclass
class RelationshipState:
    """Persisted relationship state for a single character."""

    intimacy: int = 8
    trust: int = 12
    familiarity: int = 10
    interaction_quality_recent: int = 50
    preferred_addressing: str = ""
    relationship_type: str = "friend"
    boundaries_summary: str = ""
    dependency_risk: int = 0
    updated_at: str = field(default_factory=_utc_now)
    change_reasons: list[str] = field(default_factory=list)


class RelationshipService:
    """Loads, persists, summarizes, and slowly updates relationship state.

    The state is intentionally small and conservative so it can be inspected and
    reset from the admin UI without depending on LLM output.
    """

    _MAX_CHANGE_REASONS = 8
    _PROMPT_SUMMARY_MAX_CHARS = 360
    _ALLOWED_RELATIONSHIP_TYPES = {"friend", "partner", "family", "mentor", "coworker"}

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = Path(data_dir or os.environ.get("KOKORO_DATA_DIR", "./data"))

    def _state_path(self, character_id: str) -> Path:
        return self._data_dir / "runtime" / character_id / "relationship.json"

    def get_state(self, character_id: str) -> RelationshipState:
        path = self._state_path(character_id)
        if not path.exists():
            state = RelationshipState()
            self._save_state(character_id, state)
            return state

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = RelationshipState()
            self._save_state(character_id, state)
            return state

        return self._state_from_dict(raw)

    def update_profile(
        self,
        character_id: str,
        *,
        relationship_type: str | None = None,
        preferred_addressing: str | None = None,
        boundaries_summary: str | None = None,
    ) -> RelationshipState:
        state = self.get_state(character_id)
        reasons: list[str] = []

        if relationship_type is not None:
            requested_type = relationship_type.strip().lower()
            normalized_type = requested_type or "friend"
            if normalized_type not in self._ALLOWED_RELATIONSHIP_TYPES:
                normalized_type = "friend"
                reasons.append("不支持的关系类型已回退为 friend")
            if normalized_type != state.relationship_type:
                state.relationship_type = normalized_type
                reasons.append(f"关系类型更新为 {normalized_type}")

        if preferred_addressing is not None:
            normalized_addressing = preferred_addressing.strip()
            if normalized_addressing != state.preferred_addressing:
                state.preferred_addressing = normalized_addressing
                reasons.append("更新了偏好称呼")

        if boundaries_summary is not None:
            normalized_boundaries = boundaries_summary.strip()
            if normalized_boundaries != state.boundaries_summary:
                state.boundaries_summary = normalized_boundaries
                reasons.append("更新了关系边界摘要")

        self._append_reasons(state, reasons)
        self._save_state(character_id, state)
        return state

    def reset_state(self, character_id: str) -> RelationshipState:
        state = RelationshipState(change_reasons=["关系状态已重置为默认值"])
        self._save_state(character_id, state)
        return state

    def record_interaction(
        self,
        character_id: str,
        *,
        user_input: str,
        reply: str,
        flagged: bool,
        turn: int,
    ) -> RelationshipState:
        state = self.get_state(character_id)
        del reply  # Reserved for later scoring refinements.

        quality_signal = self._interaction_quality_signal(user_input, flagged)
        previous_quality = state.interaction_quality_recent
        smoothed_quality = int(round(previous_quality * 0.72 + quality_signal * 0.28))
        state.interaction_quality_recent = _clamp(smoothed_quality)

        reasons = [f"第 {turn} 轮互动已记录"]

        familiarity_delta = 1
        if len(user_input.strip()) >= 18:
            familiarity_delta += 1
            reasons.append("用户提供了更完整的近况")

        state.familiarity = _clamp(state.familiarity + familiarity_delta)

        if quality_signal >= 58 and turn % 2 == 0:
            state.trust = _clamp(state.trust + 1)
            reasons.append("近期互动质量稳定，信任度小幅上升")
        elif quality_signal <= 40:
            state.trust = _clamp(state.trust - 1)
            reasons.append("近期互动紧张，信任度小幅回落")

        if quality_signal >= 65 and turn % 3 == 0:
            state.intimacy = _clamp(state.intimacy + 1)
            reasons.append("多轮积极互动后，亲密度缓慢上升")
        elif flagged:
            state.intimacy = _clamp(state.intimacy - 1)
            reasons.append("本轮触发禁用词检查，亲密度未继续上升")

        dependency_delta = self._dependency_risk_delta(user_input)
        if dependency_delta:
            state.dependency_risk = _clamp(state.dependency_risk + dependency_delta)
            reasons.append("检测到依赖性表达，依赖风险小幅上升")
        elif state.dependency_risk > 0 and turn % 4 == 0:
            state.dependency_risk = _clamp(state.dependency_risk - 1)
            reasons.append("近期未见依赖性表达，依赖风险缓慢回落")

        self._append_reasons(state, reasons)
        self._save_state(character_id, state)
        return state

    def summary_for_prompt(self, character_id: str) -> str:
        state = self.get_state(character_id)
        parts = [
            f"关系类型: {state.relationship_type}",
            f"亲密度 {state.intimacy}/100",
            f"信任度 {state.trust}/100",
            f"熟悉度 {state.familiarity}/100",
            f"近期互动质量 {state.interaction_quality_recent}/100",
            f"依赖风险 {state.dependency_risk}/100",
        ]
        if state.preferred_addressing:
            parts.append(f"偏好称呼: {self._truncate_text(state.preferred_addressing, 40)}")
        if state.boundaries_summary:
            parts.append(f"边界摘要: {self._truncate_text(state.boundaries_summary, 120)}")
        if state.change_reasons:
            parts.append(f"最近变化: {self._truncate_text(state.change_reasons[-1], 80)}")
        return self._truncate_text("；".join(parts), self._PROMPT_SUMMARY_MAX_CHARS)

    def boundary_summary(self, relationship_type: str) -> str:
        """Return executable expression boundary text for a relationship type."""
        return SafetyPolicy().boundary_summary(relationship_type)

    def _truncate_text(self, value: str, max_chars: int) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 1].rstrip() + "…"

    def _append_reasons(self, state: RelationshipState, reasons: list[str]) -> None:
        filtered = [reason.strip() for reason in reasons if reason.strip()]
        if not filtered:
            return

        state.change_reasons = (state.change_reasons + filtered)[-self._MAX_CHANGE_REASONS:]

    def _save_state(self, character_id: str, state: RelationshipState) -> None:
        state.updated_at = _utc_now()
        path = self._state_path(character_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _state_from_dict(self, raw: dict[str, Any]) -> RelationshipState:
        return RelationshipState(
            intimacy=_clamp(int(raw.get("intimacy", 8))),
            trust=_clamp(int(raw.get("trust", 12))),
            familiarity=_clamp(int(raw.get("familiarity", 10))),
            interaction_quality_recent=_clamp(int(raw.get("interaction_quality_recent", 50))),
            preferred_addressing=str(raw.get("preferred_addressing", "")),
            relationship_type=self._normalize_relationship_type(raw.get("relationship_type")),
            boundaries_summary=str(raw.get("boundaries_summary", "")),
            dependency_risk=_clamp(int(raw.get("dependency_risk", 0))),
            updated_at=str(raw.get("updated_at", _utc_now())),
            change_reasons=[str(item) for item in raw.get("change_reasons", []) if str(item).strip()],
        )

    def _normalize_relationship_type(self, value: Any) -> str:
        normalized = str(value or "friend").strip().lower() or "friend"
        if normalized not in self._ALLOWED_RELATIONSHIP_TYPES:
            return "friend"
        return normalized

    def _interaction_quality_signal(self, user_input: str, flagged: bool) -> int:
        if flagged:
            return 35

        normalized = user_input.lower()
        positive_keywords = (
            "谢谢",
            "晚安",
            "早安",
            "开心",
            "喜欢",
            "想你",
            "辛苦",
            "抱抱",
        )
        negative_keywords = (
            "烦",
            "滚",
            "闭嘴",
            "讨厌",
            "生气",
            "算了",
            "别说了",
        )

        quality = 55
        if any(keyword in normalized for keyword in positive_keywords):
            quality += 12
        if any(keyword in normalized for keyword in negative_keywords):
            quality -= 18
        if len(user_input.strip()) >= 24:
            quality += 4
        return _clamp(quality)

    def _dependency_risk_delta(self, user_input: str) -> int:
        normalized = user_input.lower()
        risky_patterns = (
            "只有你",
            "只剩你",
            "别离开我",
            "不要别人",
            "别管他们",
            "只和你",
            "只能和你",
        )
        return 2 if any(pattern in normalized for pattern in risky_patterns) else 0
