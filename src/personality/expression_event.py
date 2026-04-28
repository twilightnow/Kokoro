"""
表现层事件协议：统一情绪状态 → 表情动作 → TTS 参数。

ExpressionEvent 是一次角色回复的"表演指令"，包含：
- emotion  : 当前情绪名称与强度
- motion   : 推荐给展示层的动作名称及优先级
- speech   : TTS 调整参数（语速偏移、停顿）
- playback : 执行意图（queue / immediate）

frontend 消费方可以：
  1. 将 emotion.name 映射到 Live2D / model3d 表情参数
  2. 将 motion.name 映射到对应动画动作
  3. 将 speech.rate_delta / volume_delta 传递给 TTS 引擎
  4. 根据 playback.intent 决定是否打断当前动画
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpressionEmotion:
    """情绪描述。"""

    name: str = "normal"
    """当前情绪名称，与 emotion_triggers 键对应，如 happy / sad / angry / normal。"""

    intensity: float = 0.0
    """情绪强度 [0, 1]。"""

    keyword: str = ""
    """触发该情绪的关键词，调试用。"""

    reason: str = ""
    """情绪原因描述，调试用。"""


@dataclass
class ExpressionMotion:
    """展示层动作描述。"""

    name: str = ""
    """动作名称，来自角色卡 mood_expressions 映射；空字符串表示无推荐动作。"""

    priority: int = 50
    """动作优先级 [0, 100]，值越高越优先；高强度情绪触发更高优先级。"""


@dataclass
class ExpressionSpeech:
    """TTS 语音调整参数，来自 EmotionProfileConfig.tts。"""

    rate_delta: str = ""
    """语速偏移，如 '+8%' / '-5%'，符合 EdgeTTS SSML 格式。"""

    volume_delta: str = ""
    """音量偏移，如 '+10%' / '-10%'。"""

    pause_ms: int = 0
    """回复前建议静音时长（毫秒），高强度情绪触发更长停顿，营造自然感。"""


@dataclass
class ExpressionPlayback:
    """播放控制意图。"""

    intent: str = "queue"
    """
    queue     — 将动作加入队列，当前动画结束后播放（默认）
    immediate — 立即打断当前动画并播放（高强度情绪）
    """


@dataclass
class ExpressionEvent:
    """表现层统一事件：frontend 根据此对象驱动动画和 TTS。"""

    emotion: ExpressionEmotion = field(default_factory=ExpressionEmotion)
    motion: ExpressionMotion = field(default_factory=ExpressionMotion)
    speech: ExpressionSpeech = field(default_factory=ExpressionSpeech)
    playback: ExpressionPlayback = field(default_factory=ExpressionPlayback)

    def to_dict(self) -> dict:
        return {
            "emotion": {
                "name": self.emotion.name,
                "intensity": self.emotion.intensity,
                "keyword": self.emotion.keyword,
                "reason": self.emotion.reason,
            },
            "motion": {
                "name": self.motion.name,
                "priority": self.motion.priority,
            },
            "speech": {
                "rate_delta": self.speech.rate_delta,
                "volume_delta": self.speech.volume_delta,
                "pause_ms": self.speech.pause_ms,
            },
            "playback": {
                "intent": self.playback.intent,
            },
        }


_HIGH_INTENSITY_THRESHOLD = 0.7
_HIGH_PRIORITY = 80
_DEFAULT_PRIORITY = 50
_HIGH_PAUSE_MS = 200
_DEFAULT_PAUSE_MS = 80


def build_expression_event(
    mood: str,
    intensity: float,
    keyword: str,
    reason: str,
    rate_delta: str,
    volume_delta: str,
    mood_expressions: Optional[dict[str, str]] = None,
) -> ExpressionEvent:
    """从情绪状态和角色卡配置构造 ExpressionEvent。

    Args:
        mood:             当前情绪名称
        intensity:        情绪强度 [0, 1]
        keyword:          触发词
        reason:           情绪原因
        rate_delta:       来自 EmotionProfileConfig.tts.rate_delta
        volume_delta:     来自 EmotionProfileConfig.tts.volume_delta
        mood_expressions: 角色卡 mood_expressions 字典，映射 mood → 动作名称
    """
    is_high = intensity >= _HIGH_INTENSITY_THRESHOLD
    motion_name = (mood_expressions or {}).get(mood, "") if mood != "normal" else ""
    motion_priority = _HIGH_PRIORITY if is_high else _DEFAULT_PRIORITY
    pause_ms = _HIGH_PAUSE_MS if is_high else (_DEFAULT_PAUSE_MS if mood != "normal" else 0)
    playback_intent = "immediate" if is_high and motion_name else "queue"

    return ExpressionEvent(
        emotion=ExpressionEmotion(
            name=mood,
            intensity=intensity,
            keyword=keyword,
            reason=reason,
        ),
        motion=ExpressionMotion(
            name=motion_name,
            priority=motion_priority,
        ),
        speech=ExpressionSpeech(
            rate_delta=rate_delta,
            volume_delta=volume_delta,
            pause_ms=pause_ms,
        ),
        playback=ExpressionPlayback(
            intent=playback_intent,
        ),
    )
