from pathlib import Path
from typing import Union

import yaml

from .character import (
    CharacterConfig,
    EmotionProfileConfig,
    EmotionTtsConfig,
    PersonalityConfig,
    ProactiveStyle,
)

_REQUIRED_TOP_FIELDS = ("name", "emotion_triggers", "forbidden_words")


def _parse_emotion_profiles(raw_profiles: object, source: Union[str, Path]) -> dict[str, EmotionProfileConfig]:
    if raw_profiles is None:
        return {}
    if not isinstance(raw_profiles, dict):
        raise ValueError(f"emotion_profiles 必须为对象（文件: {source}）")

    profiles: dict[str, EmotionProfileConfig] = {}
    for mood, raw_profile in raw_profiles.items():
        if not isinstance(mood, str) or not mood:
            raise ValueError(f"emotion_profiles 的键必须为非空字符串（文件: {source}）")
        if raw_profile is None:
            raw_profile = {}
        if not isinstance(raw_profile, dict):
            raise ValueError(f"emotion_profiles.{mood} 必须为对象（文件: {source}）")

        raw_tts = raw_profile.get("tts", {})
        if raw_tts is None:
            raw_tts = {}
        if not isinstance(raw_tts, dict):
            raise ValueError(f"emotion_profiles.{mood}.tts 必须为对象（文件: {source}）")

        profiles[mood] = EmotionProfileConfig(
            base_intensity=float(raw_profile.get("base_intensity", 0.6)),
            recovery_rate=float(raw_profile.get("recovery_rate", 0.2)),
            min_duration_turns=int(raw_profile.get("min_duration_turns", 1)),
            max_duration_turns=int(raw_profile.get("max_duration_turns", 8)),
            stacking=float(raw_profile.get("stacking", 0.35)),
            tts=EmotionTtsConfig(
                rate_delta=str(raw_tts.get("rate_delta", "")),
                volume_delta=str(raw_tts.get("volume_delta", "")),
            ),
        )
    return profiles


def parse_character_data(data: dict, source: Union[str, Path] = "<memory>") -> CharacterConfig:
    """从已解析的 YAML 数据构建并校验角色配置。"""
    if not isinstance(data, dict):
        raise ValueError(f"角色配置必须是对象（文件: {source}）")

    for field in _REQUIRED_TOP_FIELDS:
        if field not in data:
            raise ValueError(
                f"角色配置缺少必填字段 '{field}'（文件: {source}）\n"
                f"请确认 YAML 中包含此字段。"
            )

    p = data.get("personality", {})
    if p is None:
        p = {}
    if not isinstance(p, dict):
        raise ValueError(f"personality 必须为对象（文件: {source}）")
    personality = PersonalityConfig(
        core_fear=p.get("core_fear", ""),
        surface_trait=p.get("surface_trait", ""),
        hidden_trait=p.get("hidden_trait", ""),
    )

    ps = data.get("proactive_style", {})
    if ps is None:
        ps = {}
    if not isinstance(ps, dict):
        raise ValueError(f"proactive_style 必须为对象（文件: {source}）")
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
        emotion_profiles=_parse_emotion_profiles(data.get("emotion_profiles"), source),
    )
    validate_character(config)
    return config


def validate_character(config: CharacterConfig) -> None:
    """角色配置完整性校验。字段缺失或类型错误时抛出 ValueError，可选字段为空时打印警告。"""
    errors = []
    warnings = []

    # 必填项
    if not config.name:
        errors.append("name: 必填项不能为空")
    if not isinstance(config.emotion_triggers, dict):
        errors.append("emotion_triggers: 必须为字典类型，格式: {情绪名: [触发词, ...]}")
    elif not config.emotion_triggers:
        warnings.append("emotion_triggers 为空，情绪状态机将不会被触发")
    if not isinstance(config.forbidden_words, list):
        errors.append("forbidden_words: 必须为列表类型")
    if not isinstance(config.mood_expressions, dict):
        errors.append("mood_expressions: 必须为字典类型，格式: {情绪名: 描述}")
    if not isinstance(config.emotion_profiles, dict):
        errors.append("emotion_profiles: 必须为字典类型，格式: {情绪名: {base_intensity, recovery_rate, ...}}")
    else:
        for mood_name, profile in config.emotion_profiles.items():
            if not isinstance(profile, EmotionProfileConfig):
                errors.append(f"emotion_profiles.{mood_name}: 必须为 EmotionProfileConfig")
                continue
            if profile.recovery_rate <= 0:
                errors.append(f"emotion_profiles.{mood_name}.recovery_rate: 必须大于 0")
            if profile.min_duration_turns < 0:
                errors.append(f"emotion_profiles.{mood_name}.min_duration_turns: 不能小于 0")
            if profile.max_duration_turns < profile.min_duration_turns:
                errors.append(f"emotion_profiles.{mood_name}.max_duration_turns: 不能小于 min_duration_turns")
            if profile.stacking < 0:
                errors.append(f"emotion_profiles.{mood_name}.stacking: 不能小于 0")

    # 可选但建议填写的字段
    if not config.behavior_rules:
        warnings.append("behavior_rules 为空，角色行为约束将不生效")
    if not config.verbal_habits:
        warnings.append("verbal_habits 为空，角色将没有口头禅")
    p = config.personality
    if not any([p.core_fear, p.surface_trait, p.hidden_trait]):
        warnings.append("personality 三项（core_fear / surface_trait / hidden_trait）均为空，人格深度将严重不足")

    # emotion_triggers 中的情绪名建议与 mood_expressions 对齐
    if isinstance(config.emotion_triggers, dict) and isinstance(config.mood_expressions, dict):
        unknown = set(config.emotion_triggers) - set(config.mood_expressions)
        if unknown:
            warnings.append(
                f"emotion_triggers 中的情绪 {sorted(unknown)} 在 mood_expressions 中没有对应描述"
            )

    if errors:
        raise ValueError("角色配置校验失败:\n" + "\n".join(f"  - {e}" for e in errors))

    for w in warnings:
        print(f"[警告] 角色配置: {w}")


def load_character(yaml_path: Union[str, Path]) -> CharacterConfig:
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"角色配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return parse_character_data(data, path)
