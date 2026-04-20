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
    is_user_active: bool = True
    hour: int = 0

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
