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
class CharacterConfig:
    name: str
    version: str
    personality: PersonalityConfig
    behavior_rules: List[str] = field(default_factory=list)
    proactive_style: ProactiveStyle = field(default_factory=ProactiveStyle)
    forbidden_words: List[str] = field(default_factory=list)
    verbal_habits: List[str] = field(default_factory=list)
    mood_expressions: Dict[str, str] = field(default_factory=dict)
    emotion_triggers: Dict[str, List[str]] = field(default_factory=dict)
