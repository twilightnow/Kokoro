"""
主动介入触发器。

设计原则：
  - BaseTrigger 是纯函数式的检查器，不持有状态
  - 状态（上次触发时间）由 CooldownManager 管理
  - 触发条件只看 PerceptionContext，不依赖历史序列
"""
from abc import ABC, abstractmethod
from typing import Optional

from .context import PerceptionContext


class BaseTrigger(ABC):
    """触发器基类。子类只需实现 check()，返回触发原因字符串或 None。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """触发器唯一标识（用于冷却 key）。"""

    @abstractmethod
    def check(self, ctx: PerceptionContext) -> Optional[str]:
        """检查是否触发。返回触发原因（角色说话的场景描述），或 None。"""


class IdleTrigger(BaseTrigger):
    """用户空闲超过阈值触发。"""

    name = "idle"

    def __init__(self, threshold_sec: int = 7200) -> None:  # 默认 2 小时
        self._threshold = threshold_sec

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.idle_seconds >= self._threshold:
            return "用户已长时间没有操作电脑"
        return None


class LateNightTrigger(BaseTrigger):
    """深夜仍在活跃时触发。"""

    name = "late_night"

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.is_late_night and ctx.is_user_active:
            return "深夜用户仍在使用电脑"
        return None


class LongWorkTrigger(BaseTrigger):
    """持续工作超过阈值触发（由 ProactiveEngine 内联处理）。"""

    name = "long_work"

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        # 此触发器由 ProactiveEngine 内联处理（需要 elapsed 计时），此处始终返回 None
        return None


class WindowSwitchTrigger(BaseTrigger):
    """频繁切换窗口触发（可能处于纠结/分心状态）。"""

    name = "window_switch"

    def __init__(self, freq_threshold: float = 10.0) -> None:  # 10 次/分钟
        self._threshold = freq_threshold

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.switches_per_minute >= self._threshold:
            return "用户频繁切换窗口，可能处于纠结状态"
        return None


class GamingTrigger(BaseTrigger):
    """检测到用户在游戏时触发。"""

    name = "gaming"

    def check(self, ctx: PerceptionContext) -> Optional[str]:
        if ctx.is_gaming:
            return "用户正在打游戏"
        return None
