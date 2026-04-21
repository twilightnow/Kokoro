from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .character import CharacterConfig
from .emotion import EmotionState
from ..memory.context import MemoryContext
from ..perception.context import PerceptionContext

# 触发告警的 token 估算阈值
_PROMPT_TOKEN_WARN = 600
_PROMPT_TOKEN_HARD = 1200


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。
    中文约 1.5 字/token，英文约 4 字/token，此处用字符数 / 1.5 作为混合文本的保守估算。
    """
    return max(1, int(len(text) / 1.5))


@dataclass
class PromptContext:
    """人格层 prompt 组装的统一输入数据契约。

    各层通过此结构向人格层传递信息，人格层统一编排输出。
    """

    character: CharacterConfig
    emotion: EmotionState
    memory: Optional[MemoryContext] = field(default=None)
    perception: Optional[PerceptionContext] = field(default=None)


def build_system_prompt(ctx: PromptContext) -> str:
    """人格层统一组装 system prompt，其他层不直接拼接角色输出。"""
    config = ctx.character
    state = ctx.emotion

    mood_expr = config.mood_expressions.get(state.mood, state.mood)
    rules_text = "\n".join(f"- {rule}" for rule in config.behavior_rules)
    habits_text = "、".join(config.verbal_habits)
    forbidden_text = "、".join(config.forbidden_words)

    parts = [
        f"你是{config.name}。",
        f"核心性格：{config.personality.core_fear}",
        f"外在表现：{config.personality.surface_trait}",
        f"内在真实：{config.personality.hidden_trait}",
        "",
        f"行为规则：\n{rules_text}",
        "",
        f"口癖：{habits_text}",
        "",
        f"禁用词（绝对不能出现在回复中）：{forbidden_text}",
        "",
        f"当前情绪：{mood_expr}",
    ]

    # 注入记忆上下文（Phase 2 及以后填充）
    mem = ctx.memory
    if mem and (mem.summary_items or mem.long_term_items):
        parts.append("")
        parts.append("【背景记忆】")
        if mem.long_term_items:
            for k, v in mem.long_term_items.items():
                parts.append(f"- {k}: {v}")
        if mem.summary_items:
            parts.append("近期对话摘要：")
            for s in mem.summary_items:
                parts.append(f"- {s}")

    # 注入感知上下文（Phase 3 及以后填充）
    if ctx.perception:
        parts.append("")
        parts.append("【当前场景】")
        p = ctx.perception
        parts.append(f"时间段：{p.time_of_day}")
        if p.is_late_night:
            parts.append("（深夜）")
        if p.active_window_title:
            parts.append(f"当前窗口：{p.active_window_title[:40]}")
        if p.is_gaming:
            parts.append("（用户正在游戏）")
        if not p.is_user_active:
            parts.append("（用户当前不活跃）")

    parts.extend(
        [
            "",
            "回复要求：",
            "- 用中文回复，严格保持角色一致性",
            "- 每次回复不超过3句话，保持简洁",
            "- 不要跳出角色，不要提及自己是AI或语言模型",
        ]
    )

    return "\n".join(parts)
