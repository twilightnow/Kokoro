"""
主动介入引擎：整合感知采集、触发检查、冷却管理。

在 CLI 模式下，由 ConversationService 在每轮对话开始前调用 check()。
不引入后台线程（线程模式留给 P3A sidecar）。

职责边界：
  - 输出结构化事件（触发原因字符串），不输出台词
  - 不修改情绪状态，不构建 prompt
  - 台词由人格层根据 proactive_style 字段生成
"""
import time
from typing import List, Optional

from .collector import PerceptionCollector
from .cooldown import CooldownManager
from .event import ProactiveEvent
from .triggers import (
    BaseTrigger,
    GamingTrigger,
    IdleTrigger,
    LateNightTrigger,
    WindowSwitchTrigger,
)


class ProactiveEngine:
    """主动介入引擎，在对话轮间检查是否有触发条件满足。"""

    _LONG_WORK_THRESHOLD_SEC = 3600  # 持续活跃 1 小时

    def __init__(
        self,
        collector: PerceptionCollector,
        cooldown: Optional[CooldownManager] = None,
    ) -> None:
        self._collector = collector
        self._cooldown = cooldown or CooldownManager()
        self._triggers: List[BaseTrigger] = [
            IdleTrigger(threshold_sec=7200),
            LateNightTrigger(),
            WindowSwitchTrigger(freq_threshold=10.0),
            GamingTrigger(),
        ]
        self._session_active_since: float = time.monotonic()
        self._last_was_active: bool = True

    def check(self) -> Optional[ProactiveEvent]:
        """采集感知快照，检查所有触发器，返回第一个满足条件且未在冷却期的事件。

        返回 None 表示无主动介入。
        """
        ctx = self._collector.collect()

        # 维护持续活跃计时
        if ctx.is_user_active:
            if not self._last_was_active:
                self._session_active_since = time.monotonic()
            self._last_was_active = True
        else:
            self._last_was_active = False

        # 检查 LongWork（内联，避免 check() 接口不统一）
        elapsed = time.monotonic() - self._session_active_since
        if elapsed >= self._LONG_WORK_THRESHOLD_SEC:
            if self._cooldown.can_trigger("long_work"):
                self._cooldown.mark_triggered("long_work")
                return ProactiveEvent(tag="long_work", trigger_name="LongWorkTrigger")

        # 检查其余触发器
        for trigger in self._triggers:
            reason = trigger.check(ctx)
            if reason and self._cooldown.can_trigger(trigger.name):
                self._cooldown.mark_triggered(trigger.name)
                return ProactiveEvent(tag=trigger.name, trigger_name=type(trigger).__name__)

        return None

    def last_perception(self) -> Optional[object]:
        """返回最近一次采集的 PerceptionContext。"""
        return self._collector.last_perception()
