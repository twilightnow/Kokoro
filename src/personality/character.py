from dataclasses import dataclass, field
from typing import Dict, List


def _clone_list(items: List[str]) -> List[str]:
    return list(items) if items else []


@dataclass
class PersonalityConfig:
    core_fear: str = ""
    surface_trait: str = ""
    hidden_trait: str = ""


@dataclass
class IdentityConfig:
    description: str = ""
    scenario: str = ""


@dataclass
class BehaviorConfig:
    rules: List[str] = field(default_factory=list)
    verbal_habits: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)


@dataclass
class ProactiveStyle:
    idle_too_long: str = ""
    user_working_late: str = ""
    user_gaming: str = ""


def _style_has_content(style: "ProactiveStyle") -> bool:
    return any([
        style.idle_too_long,
        style.user_working_late,
        style.user_gaming,
    ])


def _clone_proactive_style(style: "ProactiveStyle") -> "ProactiveStyle":
    return ProactiveStyle(
        idle_too_long=style.idle_too_long,
        user_working_late=style.user_working_late,
        user_gaming=style.user_gaming,
    )


@dataclass
class DialogueConfig:
    first_message: str = ""
    examples: List[str] = field(default_factory=list)
    post_history_instructions: str = ""


@dataclass
class LLMModuleConfig:
    provider: str = ""
    model: str = ""


@dataclass
class TTSModuleConfig:
    provider: str = ""
    voice: str = ""


@dataclass
class DisplayModuleConfig:
    mode: str = ""


@dataclass
class ModulesConfig:
    llm: LLMModuleConfig = field(default_factory=LLMModuleConfig)
    tts: TTSModuleConfig = field(default_factory=TTSModuleConfig)
    display: DisplayModuleConfig = field(default_factory=DisplayModuleConfig)


@dataclass
class MemoryConfig:
    extraction_policy: str = ""
    recall_style: str = ""


@dataclass
class ProactiveConfig:
    style: ProactiveStyle = field(default_factory=ProactiveStyle)


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
    identity: IdentityConfig = field(default_factory=IdentityConfig)
    personality: PersonalityConfig = field(default_factory=PersonalityConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    dialogue: DialogueConfig = field(default_factory=DialogueConfig)
    modules: ModulesConfig = field(default_factory=ModulesConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
    behavior_rules: List[str] = field(default_factory=list)
    proactive_style: ProactiveStyle = field(default_factory=ProactiveStyle)
    forbidden_words: List[str] = field(default_factory=list)
    verbal_habits: List[str] = field(default_factory=list)
    mood_expressions: Dict[str, str] = field(default_factory=dict)
    emotion_triggers: Dict[str, List[str]] = field(default_factory=dict)
    emotion_profiles: Dict[str, EmotionProfileConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.behavior.rules and not self.behavior_rules:
            self.behavior_rules = _clone_list(self.behavior.rules)
        elif self.behavior_rules and not self.behavior.rules:
            self.behavior.rules = _clone_list(self.behavior_rules)

        if self.behavior.verbal_habits and not self.verbal_habits:
            self.verbal_habits = _clone_list(self.behavior.verbal_habits)
        elif self.verbal_habits and not self.behavior.verbal_habits:
            self.behavior.verbal_habits = _clone_list(self.verbal_habits)

        if self.behavior.forbidden_words and not self.forbidden_words:
            self.forbidden_words = _clone_list(self.behavior.forbidden_words)
        elif self.forbidden_words and not self.behavior.forbidden_words:
            self.behavior.forbidden_words = _clone_list(self.forbidden_words)

        proactive_style = self.proactive.style
        if _style_has_content(proactive_style) and not _style_has_content(self.proactive_style):
            self.proactive_style = _clone_proactive_style(proactive_style)
        elif _style_has_content(self.proactive_style) and not _style_has_content(proactive_style):
            self.proactive.style = _clone_proactive_style(self.proactive_style)

    def effective_behavior_rules(self) -> List[str]:
        return self.behavior.rules or self.behavior_rules

    def effective_verbal_habits(self) -> List[str]:
        return self.behavior.verbal_habits or self.verbal_habits

    def effective_forbidden_words(self) -> List[str]:
        return self.behavior.forbidden_words or self.forbidden_words

    def to_role_card_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "identity": {
                "description": self.identity.description,
                "scenario": self.identity.scenario,
            },
            "personality": {
                "core_fear": self.personality.core_fear,
                "surface_trait": self.personality.surface_trait,
                "hidden_trait": self.personality.hidden_trait,
            },
            "behavior": {
                "rules": self.effective_behavior_rules(),
                "verbal_habits": self.effective_verbal_habits(),
                "forbidden_words": self.effective_forbidden_words(),
            },
            "dialogue": {
                "first_message": self.dialogue.first_message,
                "examples": list(self.dialogue.examples),
                "post_history_instructions": self.dialogue.post_history_instructions,
            },
            "modules": {
                "llm": {
                    "provider": self.modules.llm.provider,
                    "model": self.modules.llm.model,
                },
                "tts": {
                    "provider": self.modules.tts.provider,
                    "voice": self.modules.tts.voice,
                },
                "display": {
                    "mode": self.modules.display.mode,
                },
            },
            "memory": {
                "extraction_policy": self.memory.extraction_policy,
                "recall_style": self.memory.recall_style,
            },
            "proactive": {
                "style": {
                    "idle_too_long": self.proactive.style.idle_too_long,
                    "user_working_late": self.proactive.style.user_working_late,
                    "user_gaming": self.proactive.style.user_gaming,
                },
            },
        }
