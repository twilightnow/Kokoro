from pathlib import Path
from typing import Union

import yaml

from .character import (
    BehaviorConfig,
    CharacterConfig,
    DialogueConfig,
    EmotionProfileConfig,
    EmotionTtsConfig,
    IdentityConfig,
    LLMModuleConfig,
    DisplayModuleConfig,
    MemoryConfig,
    ModulesConfig,
    PersonalityConfig,
    ProactiveConfig,
    ProactiveStyle,
    TTSModuleConfig,
)

_REQUIRED_TOP_FIELDS = ("name", "emotion_triggers")


def _require_field(condition: bool, field_name: str, source: Union[str, Path]) -> None:
    if not condition:
        raise ValueError(
            f"角色配置缺少必填字段 '{field_name}'（文件: {source}）\n"
            "请确认 YAML 中包含此字段。"
        )


def _ensure_mapping(value: object, field_name: str, source: Union[str, Path]) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} 必须为对象（文件: {source}）")
    return value


def _parse_string_list(value: object, field_name: str, source: Union[str, Path]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} 必须为列表（文件: {source}）")

    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] 必须为字符串（文件: {source}）")
        items.append(item)
    return items


def _parse_identity(raw_identity: object, source: Union[str, Path]) -> IdentityConfig:
    identity = _ensure_mapping(raw_identity, "identity", source)
    return IdentityConfig(
        description=str(identity.get("description", "") or ""),
        scenario=str(identity.get("scenario", "") or ""),
    )


def _parse_behavior(data: dict, source: Union[str, Path]) -> BehaviorConfig:
    behavior = _ensure_mapping(data.get("behavior"), "behavior", source)
    return BehaviorConfig(
        rules=_parse_string_list(behavior.get("rules", data.get("behavior_rules", [])), "behavior.rules", source),
        verbal_habits=_parse_string_list(
            behavior.get("verbal_habits", data.get("verbal_habits", [])),
            "behavior.verbal_habits",
            source,
        ),
        forbidden_words=_parse_string_list(
            behavior.get("forbidden_words", data.get("forbidden_words", [])),
            "behavior.forbidden_words",
            source,
        ),
    )


def _parse_dialogue(raw_dialogue: object, source: Union[str, Path]) -> DialogueConfig:
    dialogue = _ensure_mapping(raw_dialogue, "dialogue", source)
    return DialogueConfig(
        first_message=str(dialogue.get("first_message", "") or ""),
        examples=_parse_string_list(dialogue.get("examples", []), "dialogue.examples", source),
        post_history_instructions=str(dialogue.get("post_history_instructions", "") or ""),
    )


def _parse_modules(raw_modules: object, source: Union[str, Path]) -> ModulesConfig:
    modules = _ensure_mapping(raw_modules, "modules", source)
    llm = _ensure_mapping(modules.get("llm"), "modules.llm", source)
    tts = _ensure_mapping(modules.get("tts"), "modules.tts", source)
    display = _ensure_mapping(modules.get("display"), "modules.display", source)

    return ModulesConfig(
        llm=LLMModuleConfig(
            provider=str(llm.get("provider", "") or ""),
            model=str(llm.get("model", "") or ""),
        ),
        tts=TTSModuleConfig(
            provider=str(tts.get("provider", "") or ""),
            voice=str(tts.get("voice", "") or ""),
        ),
        display=DisplayModuleConfig(
            mode=str(display.get("mode", "") or ""),
        ),
    )


def _parse_memory(raw_memory: object, source: Union[str, Path]) -> MemoryConfig:
    memory = _ensure_mapping(raw_memory, "memory", source)
    return MemoryConfig(
        extraction_policy=str(memory.get("extraction_policy", "") or ""),
        recall_style=str(memory.get("recall_style", "") or ""),
    )


def _parse_proactive(data: dict, source: Union[str, Path]) -> ProactiveConfig:
    proactive = _ensure_mapping(data.get("proactive"), "proactive", source)
    style_source = proactive.get("style", data.get("proactive_style", {}))
    style = _ensure_mapping(style_source, "proactive.style", source)
    return ProactiveConfig(
        style=ProactiveStyle(
            idle_too_long=str(style.get("idle_too_long", "") or ""),
            user_working_late=str(style.get("user_working_late", "") or ""),
            user_gaming=str(style.get("user_gaming", "") or ""),
        )
    )


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
        _require_field(field in data, field, source)

    raw_behavior = data.get("behavior")
    has_forbidden_words = "forbidden_words" in data
    if isinstance(raw_behavior, dict):
        has_forbidden_words = has_forbidden_words or ("forbidden_words" in raw_behavior)
    _require_field(has_forbidden_words, "forbidden_words", source)

    p = _ensure_mapping(data.get("personality"), "personality", source)
    personality = PersonalityConfig(
        core_fear=str(p.get("core_fear", "") or ""),
        surface_trait=str(p.get("surface_trait", "") or ""),
        hidden_trait=str(p.get("hidden_trait", "") or ""),
    )

    identity = _parse_identity(data.get("identity"), source)
    behavior = _parse_behavior(data, source)
    dialogue = _parse_dialogue(data.get("dialogue"), source)
    modules = _parse_modules(data.get("modules"), source)
    memory = _parse_memory(data.get("memory"), source)
    proactive = _parse_proactive(data, source)

    config = CharacterConfig(
        name=data["name"],
        version=data.get("version", ""),
        schema_version=str(data.get("schema_version", "1")),
        identity=identity,
        personality=personality,
        behavior=behavior,
        dialogue=dialogue,
        modules=modules,
        memory=memory,
        proactive=proactive,
        behavior_rules=list(behavior.rules),
        proactive_style=ProactiveStyle(
            idle_too_long=proactive.style.idle_too_long,
            user_working_late=proactive.style.user_working_late,
            user_gaming=proactive.style.user_gaming,
        ),
        forbidden_words=list(behavior.forbidden_words),
        verbal_habits=list(behavior.verbal_habits),
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
    if not config.effective_behavior_rules():
        warnings.append("behavior_rules 为空，角色行为约束将不生效")
    if not config.effective_verbal_habits():
        warnings.append("verbal_habits 为空，角色将没有口头禅")
    p = config.personality
    if not any([p.core_fear, p.surface_trait, p.hidden_trait]):
        warnings.append("personality 三项（core_fear / surface_trait / hidden_trait）均为空，人格深度将严重不足")
    if config.schema_version >= "2":
        if not config.identity.description:
            warnings.append("identity.description 为空，角色身份描述较弱")
        if not config.dialogue.first_message:
            warnings.append("dialogue.first_message 为空，首次开场风格未显式定义")

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
