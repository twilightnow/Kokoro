from pathlib import Path
from typing import Union

import yaml

from .character import CharacterConfig, PersonalityConfig, ProactiveStyle


def load_character(yaml_path: Union[str, Path]) -> CharacterConfig:
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"角色配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    p = data.get("personality", {})
    personality = PersonalityConfig(
        core_fear=p.get("core_fear", ""),
        surface_trait=p.get("surface_trait", ""),
        hidden_trait=p.get("hidden_trait", ""),
    )

    ps = data.get("proactive_style", {})
    proactive_style = ProactiveStyle(
        idle_too_long=ps.get("idle_too_long", ""),
        user_working_late=ps.get("user_working_late", ""),
        user_gaming=ps.get("user_gaming", ""),
    )

    return CharacterConfig(
        name=data.get("name", ""),
        version=data.get("version", ""),
        personality=personality,
        behavior_rules=data.get("behavior_rules", []),
        proactive_style=proactive_style,
        forbidden_words=data.get("forbidden_words", []),
        verbal_habits=data.get("verbal_habits", []),
        mood_expressions=data.get("mood_expressions", {}),
        emotion_triggers=data.get("emotion_triggers", {}),
    )
