from .character import CharacterConfig
from .emotion import EmotionState


def build_system_prompt(config: CharacterConfig, state: EmotionState) -> str:
    """人格层统一组装 system prompt，其他层不直接拼接角色输出。"""
    mood_expr = config.mood_expressions.get(state.mood, state.mood)

    rules_text = "\n".join(f"- {rule}" for rule in config.behavior_rules)
    habits_text = "、".join(config.verbal_habits)
    forbidden_text = "、".join(config.forbidden_words)

    return (
        f"你是{config.name}。\n"
        f"核心性格：{config.personality.core_fear}\n"
        f"外在表现：{config.personality.surface_trait}\n"
        f"内在真实：{config.personality.hidden_trait}\n\n"
        f"行为规则：\n{rules_text}\n\n"
        f"口癖：{habits_text}\n\n"
        f"禁用词（绝对不能出现在回复中）：{forbidden_text}\n\n"
        f"当前情绪：{mood_expr}\n\n"
        f"回复要求：\n"
        f"- 用中文回复，严格保持角色一致性\n"
        f"- 每次回复不超过3句话，保持简洁\n"
        f"- 不要跳出角色，不要提及自己是AI或语言模型"
    )
