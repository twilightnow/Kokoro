"""
键鼠活跃状态追踪。使用 pynput 监听事件，记录最后活跃时间。
监听器在后台线程运行，但只更新时间戳，不做任何业务判断。
"""
import threading
import time
from typing import Optional


class InputTracker:
    """追踪用户最后一次键鼠操作的时间戳。

    职责边界：
      - 只记录时间，不判断"是否空闲"（空闲判断由触发器负责）
      - 不 import 任何业务层模块
    """

    def __init__(self) -> None:
        self._last_activity: float = time.monotonic()
        self._lock = threading.Lock()
        self._listeners: list = []

    def start(self) -> None:
        """启动 pynput 后台监听。导入失败时静默降级。"""
        try:
            from pynput import keyboard, mouse

            def _on_event(*args, **kwargs):
                self.mark_active()

            kb_listener = keyboard.Listener(
                on_press=_on_event,
                daemon=True,
            )
            mouse_listener = mouse.Listener(
                on_move=_on_event,
                on_click=_on_event,
                on_scroll=_on_event,
                daemon=True,
            )
            kb_listener.start()
            mouse_listener.start()
            self._listeners = [kb_listener, mouse_listener]
        except ImportError:
            pass  # pynput 不可用，降级处理
        except Exception:
            pass

    def stop(self) -> None:
        """停止监听器。"""
        for listener in self._listeners:
            try:
                listener.stop()
            except Exception:
                pass
        self._listeners = []

    def idle_seconds(self) -> float:
        """返回距离最后一次活动的秒数。"""
        with self._lock:
            return time.monotonic() - self._last_activity

    def mark_active(self) -> None:
        """手动标记活跃（用于测试或无 pynput 时的降级）。"""
        with self._lock:
            self._last_activity = time.monotonic()
