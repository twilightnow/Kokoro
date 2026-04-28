from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MemoryRecordMeta:
    """记忆条目的附加元数据，用于 prompt 注入提示。"""

    source: str = "user"
    """来源：``"user"`` 表示用户明确说出，``"llm_extract"`` 表示 LLM 推断提取。"""
    confidence: Optional[float] = None
    """置信度 0.0–1.0。None 表示未评估。"""
    importance: float = 0.5
    """主观重要性 0.0–1.0，由用户或系统设置。"""


@dataclass
class MemoryContext:
    """跨层数据契约：记忆层向人格层提供的结构化记忆上下文。

    Phase 0：空占位。Phase 2：填充实际内容。接口从 Phase 0 起固定，不允许跨层直接传 dict。
    """

    summary_items: list[str] = field(default_factory=list)
    """最近 N 条摘要，每条 ≤100 字，由摘要记忆层填充。"""

    long_term_items: dict[str, str] = field(default_factory=dict)
    """key→value 已确认事实，如 {"user_name": "小明"}。注入时总长度不超过 budget。"""

    preference_items: dict[str, str] = field(default_factory=dict)
    """用户偏好记忆，如称呼、回复风格、提醒频率和兴趣偏好。"""

    boundary_items: dict[str, str] = field(default_factory=dict)
    """用户明确要求避免、不要记录或不要再提及的边界信息。"""

    event_items: dict[str, str] = field(default_factory=dict)
    """近期重要事件、压力源、目标等结构化事件记忆。"""

    record_meta: dict[str, MemoryRecordMeta] = field(default_factory=dict)
    """按 key 存储各记忆条目的元数据（来源、置信度、重要性），供 prompt builder 使用。
    key 与上面各分类 dict 的 key 对应。key 在跨分类唯一即可（同 key 不应出现在多个分类中）。"""
