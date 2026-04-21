from pathlib import Path
from typing import Union

import yaml

from .character import CharacterConfig, PersonalityConfig, ProactiveStyle

_REQUIRED_TOP_FIELDS = ("name", "emotion_triggers", "forbidden_words")


def validate_character(config: CharacterConfig) -> None:
    """角色設定完整性検証。必須フィールド欠如時に ValueError を発生。"""
    errors = []
    if not config.name:
        errors.append("name: 必須项不能为空")
    if not isinstance(config.emotion_triggers, dict):
        errors.append("emotion_triggers: 必須为字典类型")
    if not isinstance(config.forbidden_words, list):
        errors.append("forbidden_words: 必須为列表类型")
    if errors:
        raise ValueError("角色配置校验失败:\n" + "\n".join(f"  - {e}" for e in errors))


def load_character(yaml_path: Union[str, Path]) -> CharacterConfig:
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"角色配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # 必需项目を事前チェック
    for field in _REQUIRED_TOP_FIELDS:
        if field not in data:
            raise ValueError(
                f"角色配置缺少必填字段 '{field}'（文件: {path}\n"
                f"请确认 YAML 中包含此字段。"
            )

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

    config = CharacterConfig(
        name=data["name"],
        version=data.get("version", ""),
        schema_version=str(data.get("schema_version", "1")),
        personality=personality,
        behavior_rules=data.get("behavior_rules", []),
        proactive_style=proactive_style,
        forbidden_words=data.get("forbidden_words", []),
        verbal_habits=data.get("verbal_habits", []),
        mood_expressions=data.get("mood_expressions", {}),
        emotion_triggers=data.get("emotion_triggers", {}),
    )
    validate_character(config)
    return config
