from collections import deque
from dataclasses import dataclass, field, replace
from math import ceil
from typing import Deque, Dict, List, Optional, Union

from .character import EmotionProfileConfig

_PERSIST_ROUNDS = 3
_DEFAULT_INTENSITY = 0.6
_DEFAULT_RECOVERY_RATE = 0.2
_MAX_RECENT_EVENTS = 5
_MAX_TIMELINE_SEGMENTS = 12
_TIMELINE_END_THRESHOLD = 0.05


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _estimate_remaining_turns(intensity: float, recovery_rate: float) -> int:
    if intensity <= 0 or recovery_rate <= 0:
        return 0
    return max(0, ceil((intensity - 1e-9) / recovery_rate))


def _normalized_profile(profile: Optional[EmotionProfileConfig] = None) -> EmotionProfileConfig:
    profile = profile or EmotionProfileConfig()
    return EmotionProfileConfig(
        base_intensity=max(0.0, profile.base_intensity),
        recovery_rate=max(0.01, profile.recovery_rate),
        min_duration_turns=max(0, profile.min_duration_turns),
        max_duration_turns=max(max(0, profile.min_duration_turns), profile.max_duration_turns),
        stacking=max(0.0, profile.stacking),
        tts=profile.tts,
    )


def _segment_remaining_turns(
    intensity: float,
    recovery_rate: float,
    elapsed_turns: int,
    minimum: int,
    maximum: int,
) -> int:
    estimated = _estimate_remaining_turns(intensity, recovery_rate)
    floor = max(0, minimum - elapsed_turns)
    ceiling = max(0, maximum - elapsed_turns)
    return min(ceiling, max(floor, estimated))


def _relationship_closeness(relationship_context: object) -> float:
    if relationship_context is None:
        return 0.0

    values: list[float] = []
    for key in ("trust", "intimacy", "familiarity"):
        value = None
        if isinstance(relationship_context, dict):
            value = relationship_context.get(key)
        else:
            value = getattr(relationship_context, key, None)
        if isinstance(value, (int, float)):
            values.append(_clamp(float(value) / 100.0, 0.0, 1.0))

    if not values:
        return 0.0
    return sum(values) / len(values)


@dataclass
class EmotionEvent:
    mood: str
    keyword: str = ""
    reason: str = ""
    source: str = "user_input"
    intensity: float = _DEFAULT_INTENSITY
    recovery_rate: float = _DEFAULT_RECOVERY_RATE
    profile: EmotionProfileConfig = field(default_factory=EmotionProfileConfig)


@dataclass
class EmotionEventRecord:
    mood: str
    keyword: str
    reason: str
    source: str
    intensity: float
    recovery_rate: float
    started_at_turn: int
    duration_turns: int


@dataclass
class EmotionSegment:
    mood: str
    keyword: str
    reason: str
    source: str
    intensity: float
    recovery_rate: float
    started_at_turn: int
    last_updated_turn: int
    elapsed_turns: int
    estimated_remaining_turns: int
    min_duration_turns: int
    max_duration_turns: int
    stacking: float
    tts_rate_delta: str = ""
    tts_volume_delta: str = ""
    ended_at_turn: Optional[int] = None
    end_reason: str = ""


@dataclass
class EmotionSummary:
    mood: str = "normal"
    keyword: str = ""
    reason: str = ""
    source: str = ""
    intensity: float = 0.0
    recovery_rate: float = _DEFAULT_RECOVERY_RATE
    started_at_turn: int = 0
    elapsed_turns: int = 0
    estimated_remaining_turns: int = 0
    phase: str = "idle"
    rate_delta: str = ""
    volume_delta: str = ""


@dataclass
class EmotionTimeline:
    character_id: str = ""
    turn: int = 0
    max_segments: int = _MAX_TIMELINE_SEGMENTS
    current_segment: Optional[EmotionSegment] = None
    segments: Deque[EmotionSegment] = field(
        default_factory=lambda: deque(maxlen=_MAX_TIMELINE_SEGMENTS)
    )

    def _build_segment(self, event: EmotionEvent, turn: int) -> EmotionSegment:
        profile = _normalized_profile(event.profile)
        intensity = max(0.0, event.intensity)
        recovery_rate = max(0.01, event.recovery_rate)
        remaining = _segment_remaining_turns(
            intensity,
            recovery_rate,
            0,
            profile.min_duration_turns,
            profile.max_duration_turns,
        )
        return EmotionSegment(
            mood=event.mood,
            keyword=event.keyword,
            reason=event.reason or (f"用户提到“{event.keyword}”" if event.keyword else ""),
            source=event.source,
            intensity=intensity,
            recovery_rate=recovery_rate,
            started_at_turn=max(0, turn),
            last_updated_turn=max(0, turn),
            elapsed_turns=0,
            estimated_remaining_turns=remaining,
            min_duration_turns=profile.min_duration_turns,
            max_duration_turns=profile.max_duration_turns,
            stacking=profile.stacking,
            tts_rate_delta=profile.tts.rate_delta,
            tts_volume_delta=profile.tts.volume_delta,
        )

    def _sync_segment(self, segment: EmotionSegment, turn: int) -> EmotionSegment:
        elapsed_turns = max(0, turn - segment.started_at_turn)
        remaining = _segment_remaining_turns(
            segment.intensity,
            segment.recovery_rate,
            elapsed_turns,
            segment.min_duration_turns,
            segment.max_duration_turns,
        )
        return replace(
            segment,
            last_updated_turn=max(segment.last_updated_turn, turn),
            elapsed_turns=elapsed_turns,
            estimated_remaining_turns=remaining,
        )

    def _archive_current(self, turn: int, reason: str) -> None:
        if self.current_segment is None:
            return
        archived = self._sync_segment(self.current_segment, turn)
        archived = replace(
            archived,
            ended_at_turn=max(archived.last_updated_turn, turn),
            end_reason=reason,
            estimated_remaining_turns=0,
        )
        self.segments.append(archived)
        self.current_segment = None

    def _apply_decay(self, turn: int) -> Optional[EmotionSegment]:
        if self.current_segment is None:
            self.turn = max(self.turn, turn)
            return None

        next_turn = max(turn, self.current_segment.last_updated_turn + 1)
        elapsed_updates = max(1, next_turn - self.current_segment.last_updated_turn)
        decayed_intensity = max(
            0.0,
            self.current_segment.intensity - self.current_segment.recovery_rate * elapsed_updates,
        )
        floor_intensity = _TIMELINE_END_THRESHOLD if next_turn - self.current_segment.started_at_turn < self.current_segment.min_duration_turns else 0.0
        self.current_segment = replace(
            self.current_segment,
            intensity=max(decayed_intensity, floor_intensity),
        )
        self.current_segment = self._sync_segment(self.current_segment, next_turn)
        self.turn = next_turn

        if (
            self.current_segment.intensity <= _TIMELINE_END_THRESHOLD
            and self.current_segment.elapsed_turns >= self.current_segment.min_duration_turns
        ):
            self._archive_current(next_turn, "recovered")
            return None
        return self.current_segment

    def update(self, event: Optional[EmotionEvent] = None, turn: int = 0) -> Optional[EmotionSegment]:
        next_turn = max(self.turn, turn)
        if event is None:
            return self._apply_decay(next_turn)

        self.turn = next_turn
        if event.mood == "normal" or event.intensity <= 0:
            self._archive_current(next_turn, "manual_reset")
            return None

        if self.current_segment is None:
            self.current_segment = self._build_segment(event, next_turn)
            return self.current_segment

        current = self.current_segment
        if current.mood == event.mood:
            stacked_intensity = current.intensity + max(0.0, event.intensity) * max(0.0, current.stacking)
            self.current_segment = replace(
                current,
                keyword=event.keyword or current.keyword,
                reason=event.reason or current.reason,
                source=event.source or current.source,
                intensity=stacked_intensity,
                recovery_rate=max(current.recovery_rate, event.recovery_rate),
                tts_rate_delta=event.profile.tts.rate_delta or current.tts_rate_delta,
                tts_volume_delta=event.profile.tts.volume_delta or current.tts_volume_delta,
            )
            self.current_segment = self._sync_segment(self.current_segment, next_turn)
            return self.current_segment

        takeover_threshold = max(current.intensity * 0.85, 0.35)
        if event.intensity >= takeover_threshold:
            self._archive_current(next_turn, f"overridden_by:{event.mood}")
            self.current_segment = self._build_segment(event, next_turn)
            return self.current_segment

        weakened_intensity = max(0.0, current.intensity - max(0.0, event.intensity) * 0.5)
        self.current_segment = replace(current, intensity=weakened_intensity)
        self.current_segment = self._sync_segment(self.current_segment, next_turn)
        if (
            self.current_segment.intensity <= _TIMELINE_END_THRESHOLD
            and self.current_segment.elapsed_turns >= self.current_segment.min_duration_turns
        ):
            self._archive_current(next_turn, f"weakened_by:{event.mood}")
            self.current_segment = self._build_segment(event, next_turn)
        return self.current_segment


@dataclass
class EmotionState:
    mood: str = "normal"
    persist_count: int = 0
    keyword: str = ""
    reason: str = ""
    source: str = ""
    intensity: float = 0.0
    started_at_turn: int = 0
    duration_turns: int = 0
    elapsed_turns: int = 0
    recovery_rate: float = _DEFAULT_RECOVERY_RATE
    recent_events: Deque[EmotionEventRecord] = field(
        default_factory=lambda: deque(maxlen=_MAX_RECENT_EVENTS)
    )
    timeline: EmotionTimeline = field(default_factory=EmotionTimeline)

    @property
    def estimated_remaining_turns(self) -> int:
        return _estimate_remaining_turns(self.intensity, self.recovery_rate)

    def _reset_current(self) -> None:
        self.mood = "normal"
        self.persist_count = 0
        self.keyword = ""
        self.reason = ""
        self.source = ""
        self.intensity = 0.0
        self.started_at_turn = 0
        self.duration_turns = 0
        self.elapsed_turns = 0
        self.recovery_rate = _DEFAULT_RECOVERY_RATE

    def _sync_from_timeline(self) -> None:
        segment = self.timeline.current_segment
        if segment is None:
            self._reset_current()
            return

        self.mood = segment.mood
        self.keyword = segment.keyword
        self.reason = segment.reason
        self.source = segment.source
        self.intensity = segment.intensity
        self.started_at_turn = segment.started_at_turn
        self.duration_turns = segment.estimated_remaining_turns
        self.elapsed_turns = segment.elapsed_turns
        self.recovery_rate = segment.recovery_rate
        self.persist_count = segment.estimated_remaining_turns

    def _apply_event(self, event: EmotionEvent, turn: int = 0) -> None:
        normalized_profile = _normalized_profile(event.profile)
        normalized_event = EmotionEvent(
            mood=event.mood,
            keyword=event.keyword,
            reason=event.reason,
            source=event.source,
            intensity=max(0.0, event.intensity),
            recovery_rate=max(0.01, event.recovery_rate),
            profile=normalized_profile,
        )

        segment = self.timeline.update(normalized_event, turn=turn)
        if segment is not None:
            self.recent_events.append(
                EmotionEventRecord(
                    mood=segment.mood,
                    keyword=segment.keyword,
                    reason=segment.reason,
                    source=segment.source,
                    intensity=segment.intensity,
                    recovery_rate=segment.recovery_rate,
                    started_at_turn=segment.started_at_turn,
                    duration_turns=segment.estimated_remaining_turns,
                )
            )
        self._sync_from_timeline()

    @property
    def current_segment(self) -> Optional[EmotionSegment]:
        return self.timeline.current_segment

    @property
    def timeline_segments(self) -> List[EmotionSegment]:
        return list(self.timeline.segments)

    @property
    def emotion_summary(self) -> EmotionSummary:
        segment = self.timeline.current_segment
        if segment is None:
            return EmotionSummary()

        if segment.elapsed_turns == 0:
            phase = "triggered"
        elif segment.estimated_remaining_turns <= 1:
            phase = "recovering"
        else:
            phase = "steady"

        return EmotionSummary(
            mood=segment.mood,
            keyword=segment.keyword,
            reason=segment.reason,
            source=segment.source,
            intensity=segment.intensity,
            recovery_rate=segment.recovery_rate,
            started_at_turn=segment.started_at_turn,
            elapsed_turns=segment.elapsed_turns,
            estimated_remaining_turns=segment.estimated_remaining_turns,
            phase=phase,
            rate_delta=segment.tts_rate_delta,
            volume_delta=segment.tts_volume_delta,
        )

    def trigger(self, new_mood: Union[str, EmotionEvent], turn: int = 0) -> None:
        if isinstance(new_mood, EmotionEvent):
            event = new_mood
        else:
            event = EmotionEvent(mood=new_mood, source="manual")
        self._apply_event(event, turn=turn)

    def set_manual_state(
        self,
        mood: str,
        persist_count: int = 0,
        *,
        intensity: Optional[float] = None,
        reason: str = "",
        source: str = "debug_inject",
        keyword: str = "",
        recovery_rate: Optional[float] = None,
        turn: int = 0,
    ) -> None:
        normalized_recovery = max(0.01, recovery_rate or _DEFAULT_RECOVERY_RATE)
        normalized_persist = max(0, persist_count)
        if intensity is None:
            inferred_intensity = normalized_persist * normalized_recovery
        else:
            inferred_intensity = intensity
        self._apply_event(
            EmotionEvent(
                mood=mood,
                keyword=keyword,
                reason=reason,
                source=source,
                intensity=inferred_intensity,
                recovery_rate=normalized_recovery,
                profile=EmotionProfileConfig(
                    base_intensity=max(0.0, inferred_intensity),
                    recovery_rate=normalized_recovery,
                    min_duration_turns=0,
                    max_duration_turns=max(normalized_persist, _PERSIST_ROUNDS),
                    stacking=0.35,
                ),
            ),
            turn=turn,
        )

    def decay(self) -> None:
        if self.mood == "normal":
            return

        next_turn = self.timeline.turn + 1 if self.timeline.turn > 0 else max(1, self.started_at_turn + 1)
        self.timeline.update(None, turn=next_turn)
        self._sync_from_timeline()

    def update(self, event: Optional[Union[str, EmotionEvent]] = None, turn: int = 0) -> None:
        """接受已检测到的事件名，只负责状态跃迁和衰减。

        不直接接收用户输入文本，触发检测由独立的 detect_event() 负责。
        """
        if event:
            self.trigger(event, turn=turn)
        else:
            self.decay()


def detect_event(
    user_input: str,
    triggers: Dict[str, List[str]],
    emotion_profiles: Optional[Dict[str, EmotionProfileConfig]] = None,
    *,
    relationship_context: object = None,
    previous_state: Optional[EmotionState] = None,
) -> Optional[EmotionEvent]:
    """检测用户输入中触发的情绪事件，返回情绪名称或 None。

    只做检测，不修改状态。多个情绪同时命中时，取第一个命中的情绪。
    """
    for mood_name, keywords in triggers.items():
        for kw in keywords:
            if kw and kw in user_input:
                profile = _normalized_profile((emotion_profiles or {}).get(mood_name))
                intensity = profile.base_intensity
                if previous_state is not None and previous_state.mood == mood_name:
                    intensity += previous_state.intensity * profile.stacking

                closeness = _relationship_closeness(relationship_context)
                if closeness >= 0.5:
                    if mood_name in {"happy", "shy"}:
                        intensity += 0.1 * closeness
                    elif mood_name in {"angry", "cold"}:
                        intensity = max(0.1, intensity - 0.08 * closeness)

                return EmotionEvent(
                    mood=mood_name,
                    keyword=kw,
                    reason=f"用户提到“{kw}”",
                    source="user_input",
                    intensity=intensity,
                    recovery_rate=profile.recovery_rate,
                    profile=profile,
                )
    return None
