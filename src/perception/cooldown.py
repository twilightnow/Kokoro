"""
冷却管理器：防止触发器频繁打扰用户。

全局冷却：任意触发器触发后，所有触发器进入冷却期。
独立冷却：每类触发器有独立冷却，同类不重复触发。
"""
import time
from typing import Dict


class CooldownManager:
    """双层冷却：全局 + 每类触发器独立。

    职责边界：只管理时间，不做任何感知或触发判断。
    """

    GLOBAL_COOLDOWN_SEC: int = 1800      # 30 分钟全局冷却
    PER_TRIGGER_COOLDOWN_SEC: int = 3600  # 同类触发器 1 小时独立冷却

    def __init__(self) -> None:
        self._global_last: float = 0.0
        self._trigger_last: Dict[str, float] = {}

    def can_trigger(self, trigger_name: str) -> bool:
        """检查指定触发器是否已过冷却期。"""
        now = time.monotonic()
        if now - self._global_last < self.GLOBAL_COOLDOWN_SEC:
            return False
        last = self._trigger_last.get(trigger_name, 0.0)
        return now - last >= self.PER_TRIGGER_COOLDOWN_SEC

    def mark_triggered(self, trigger_name: str) -> None:
        """记录触发时间（同时刷新全局冷却和独立冷却）。"""
        now = time.monotonic()
        self._global_last = now
        self._trigger_last[trigger_name] = now

    def reset(self) -> None:
        """清空所有冷却（测试用）。"""
        self._global_last = 0.0
        self._trigger_last.clear()
