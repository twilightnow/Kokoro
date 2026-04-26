from datetime import datetime
from typing import Optional

from ..personality.character import CharacterConfig
from .action import ProactiveAction, ProactiveSignal, new_proactive_event_id
from .policy import ProactivePolicy
from .profile import ProactiveSettings
from .templates import expression_for_scene, quick_actions_for_scene, short_template_for_scene


def _reminder_template_from_metadata(metadata: dict[str, object]) -> str:
    title = str(metadata.get("title") or "").strip()
    if not title:
        return short_template_for_scene("reminder")
    return f"到约好的时间了，我来提醒你：{title}"


class ProactiveScheduler:
    def __init__(self, policy: ProactivePolicy | None = None) -> None:
        self._policy = policy or ProactivePolicy()

    def plan(
        self,
        signals: list[ProactiveSignal],
        settings: ProactiveSettings,
        character: CharacterConfig,
        character_id: str,
        recent_entries: list[dict[str, object]],
        now: datetime | None = None,
        emotion_summary: Optional[dict[str, object]] = None,
        privacy_dnd_reason: str = "",
    ) -> ProactiveAction | None:
        if not signals:
            return None

        current_time = now or datetime.now()
        signal = sorted(signals, key=lambda item: item.priority, reverse=True)[0]
        decision = self._policy.evaluate(
            signal.scene,
            settings,
            recent_entries,
            character_id,
            current_time,
            privacy_dnd_reason=privacy_dnd_reason,
        )
        level = decision.level if decision.allowed else "silent"
        content = ""
        generated_by = "silent"
        actions: list[str] = []
        expression = expression_for_scene(signal.scene)
        intensity = float(emotion_summary.get("intensity", 0.0)) if emotion_summary else 0.0
        emotion_mood = str(emotion_summary.get("mood", "normal")) if emotion_summary else "normal"
        if emotion_mood and emotion_mood != "normal" and intensity >= 0.35:
            expression = emotion_mood if intensity >= 0.75 or expression == "normal" else expression

        if decision.allowed:
            actions = quick_actions_for_scene(signal.scene)
            if intensity >= 0.75 and signal.scene != "reminder":
                if level == "full":
                    level = "short"
                elif level == "short":
                    level = "expression"
            if level in {"short", "full"}:
                if signal.scene == "reminder":
                    content = _reminder_template_from_metadata(signal.metadata)
                else:
                    content = short_template_for_scene(signal.scene)
                generated_by = "template"
            elif level == "expression":
                generated_by = "expression"

        return ProactiveAction(
            id=new_proactive_event_id(),
            timestamp=current_time.isoformat(),
            character_id=character_id,
            scene=signal.scene,
            level=level,
            decision="sent" if decision.allowed else "suppressed",
            reason=signal.reason,
            content=content,
            expression=expression,
            actions=actions,
            suppressed_by=decision.suppressed_by,
            settings_mode=settings.mode,
            daily_count_before=decision.daily_count_before,
            generated_by=generated_by,
            metadata={
                **dict(signal.metadata),
                "emotion": dict(emotion_summary or {}),
                "privacy_dnd_reason": privacy_dnd_reason,
            },
        )
