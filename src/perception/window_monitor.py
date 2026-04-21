"""
活动窗口标题监控。使用 pygetwindow 获取当前前台窗口标题。
"""
import time
from collections import deque
from typing import Deque, Optional, Tuple


class WindowMonitor:
    """监控活动窗口标题，统计切换频率。

    职责边界：
      - 只采集窗口标题和切换事件，不判断场景含义
      - 场景判断（游戏/代码/浏览器）由触发器负责
    """

    # 游戏窗口标题关键词（粗判，不依赖截图）
    GAME_KEYWORDS: tuple = (
        "Steam", "Origin", "Epic", "Battle.net",
        "League of Legends", "Genshin", "原神",
        "英雄联盟", "Minecraft", "Overwatch", "守望先锋",
    )

    def __init__(self, history_window_seconds: int = 60) -> None:
        self._history_window = history_window_seconds
        # (timestamp, window_title) 的时间窗口队列
        self._switch_history: Deque[Tuple[float, str]] = deque()
        self._last_title: str = ""

    def current_title(self) -> str:
        """获取当前活动窗口标题。失败时返回空字符串。"""
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else ""
        except Exception:
            return ""

    def record_switch(self, title: str) -> None:
        """记录一次窗口切换。"""
        self._switch_history.append((time.monotonic(), title))

    def switches_per_minute(self) -> float:
        """返回最近 history_window_seconds 内的窗口切换次数/分钟。"""
        now = time.monotonic()
        cutoff = now - self._history_window
        # 清理过期记录
        while self._switch_history and self._switch_history[0][0] < cutoff:
            self._switch_history.popleft()
        if not self._switch_history:
            return 0.0
        # 换算为每分钟切换次数
        count = len(self._switch_history)
        return count / (self._history_window / 60.0)

    def collect(self) -> str:
        """采集当前窗口标题，内部更新切换历史，返回标题字符串。"""
        title = self.current_title()
        if title and title != self._last_title:
            self.record_switch(title)
            self._last_title = title
        return title

    def is_gaming(self, title: str) -> bool:
        """粗判是否在玩游戏（基于窗口标题关键词）。"""
        return any(kw.lower() in title.lower() for kw in self.GAME_KEYWORDS)
