"""
感知数据采集器：整合 InputTracker 和 WindowMonitor，生成 PerceptionContext。

职责边界：
  - 负责采集，不判断触发条件
  - 输出 PerceptionContext，人格层以此构建 prompt
"""
from datetime import datetime
from typing import Optional

from .context import PerceptionContext
from .input_tracker import InputTracker
from .window_monitor import WindowMonitor


class PerceptionCollector:
    """感知数据采集器，整合 InputTracker 和 WindowMonitor 生成 PerceptionContext。"""

    def __init__(
        self,
        input_tracker: InputTracker,
        window_monitor: WindowMonitor,
    ) -> None:
        self._input = input_tracker
        self._window = window_monitor
        self._last_ctx: Optional[PerceptionContext] = None

    def collect(self) -> PerceptionContext:
        """采集当前一次感知快照，返回 PerceptionContext。"""
        now = datetime.now()
        title = self._window.collect()
        idle_sec = self._input.idle_seconds()
        switches_pm = self._window.switches_per_minute()

        ctx = PerceptionContext(
            timestamp=now,
            active_window_title=title,
            is_user_active=idle_sec < 300,   # 5 分钟无操作视为不活跃
            hour=now.hour,
            idle_seconds=idle_sec,
            switches_per_minute=switches_pm,
            is_gaming=self._window.is_gaming(title),
        )
        self._last_ctx = ctx
        return ctx

    def last_perception(self) -> Optional[PerceptionContext]:
        """返回最近一次采集的 PerceptionContext，供 ProactiveEngine 调用。"""
        return self._last_ctx
