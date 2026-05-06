from dataclasses import dataclass


@dataclass
class ProactiveEvent:
    """感知层向人格层传递的主动介入事件。

    感知层只生成事件，不直接决定角色说什么。
    """

    tag: str
    """事件标签，如 "idle_too_long" / "late_night" / "long_work"。"""

    trigger_name: str
    """触发器类名，便于日志追踪。"""
