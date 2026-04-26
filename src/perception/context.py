from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PerceptionContext:
    """
    Level 0 感知上下文 — 本地零成本，无需外部 API。
    感知层只向人格层输出结构化上下文描述，不直接决定回复。
    """

    timestamp: datetime = field(default_factory=datetime.now)
    active_window_title: str = ""
    active_app_name: str = ""
    is_user_active: bool = True
    hour: int = 0
    idle_seconds: float = 0.0
    """距最后键鼠操作的秒数。"""
    switches_per_minute: float = 0.0
    """最近1分钟窗口切换频率。"""
    is_gaming: bool = False
    """是否在游戏（基于窗口标题粗判）。"""
    is_fullscreen: bool = False
    """是否处于全屏窗口。当前采集器无法判断时保持 False。"""
    blocked_reason: str = ""
    """隐私黑名单命中原因。非空时标题已被清空。"""
    dnd_reason: str = ""
    """隐私勿扰命中原因。用于主动策略静默。"""
    redactions: list[str] = field(default_factory=list)
    """隐私过滤命中的脱敏规则名称。"""

    @classmethod
    def capture(cls) -> "PerceptionContext":
        now = datetime.now()
        return cls(
            timestamp=now,
            hour=now.hour,
        )

    @property
    def is_late_night(self) -> bool:
        return self.hour >= 23 or self.hour < 4

    @property
    def time_of_day(self) -> str:
        if self.hour < 6:
            return "深夜"
        elif self.hour < 12:
            return "上午"
        elif self.hour < 18:
            return "下午"
        elif self.hour < 23:
            return "晚上"
        else:
            return "深夜"

