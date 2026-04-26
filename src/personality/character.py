from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PersonalityConfig:
    core_fear: str = ""
    surface_trait: str = ""
    hidden_trait: str = ""


@dataclass
class ProactiveStyle:
    idle_too_long: str = ""
    user_working_late: str = ""
    user_gaming: str = ""


@dataclass
class EmotionTtsConfig:
    rate_delta: str = ""
    volume_delta: str = ""


@dataclass
class EmotionProfileConfig:
    base_intensity: float = 0.6
    recovery_rate: float = 0.2
    min_duration_turns: int = 1
    max_duration_turns: int = 8
    stacking: float = 0.35
    tts: EmotionTtsConfig = field(default_factory=EmotionTtsConfig)


@dataclass
class CharacterConfig:
    name: str
    version: str = ""
    schema_version: str = "1"
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    behavior_rules: List[str] = field(default_factory=list)
    proactive_style: ProactiveStyle = field(default_factory=ProactiveStyle)
    forbidden_words: List[str] = field(default_factory=list)
    verbal_habits: List[str] = field(default_factory=list)
    mood_expressions: Dict[str, str] = field(default_factory=dict)
    emotion_triggers: Dict[str, List[str]] = field(default_factory=dict)
    emotion_profiles: Dict[str, EmotionProfileConfig] = field(default_factory=dict)
