"""
NotifyEvent — 统一外部事件入口。

所有触发主动动作的来源（reminder、perception、idle、time、外部插件）
都先转换成 NotifyEvent，再由 ProactiveScheduler 统一调度。

职责边界：
  - 定义 NotifyEvent 数据结构
  - 各来源到 NotifyEvent 的适配函数
  - NotifyEvent → ProactiveSignal 的转换
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

from .action import ProactiveScene, ProactiveSignal, UrgencyLevel

NotifySource = Literal["reminder", "perception", "external"]
PrivacyLevel = Literal["public", "private", "sensitive"]

_URGENCY_PRIORITY: dict[str, int] = {
    "critical": 99,
    "high": 90,
    "normal": 70,
    "low": 50,
}

_VALID_SCENES: frozenset[str] = frozenset(
    ["late_night", "long_work", "idle_return", "window_switch", "gaming", "reminder"]
)
_VALID_URGENCIES: frozenset[str] = frozenset(["low", "normal", "high", "critical"])
_VALID_PRIVACY_LEVELS: frozenset[str] = frozenset(["public", "private", "sensitive"])


def _new_notify_id() -> str:
    return f"ntf_{uuid4().hex[:12]}"


@dataclass
class NotifyEvent:
    """统一外部触发事件。

    Attributes:
        source:        事件来源，用于溯源。
        scene:         对应 ProactiveScene，决定调度策略。
        urgency:       紧急程度。critical 可跳过 DND 时间窗口限制。
        payload:       附加载荷，内容由来源决定（如 reminder_id、title）。
        privacy_level: 隐私级别，public 事件在隐私感知触发期也允许处理。
        id:            唯一事件 ID。
        created_at:    事件创建时间。
    """

    source: NotifySource
    scene: ProactiveScene
    urgency: UrgencyLevel = "normal"
    payload: dict[str, object] = field(default_factory=dict)
    privacy_level: PrivacyLevel = "public"
    id: str = field(default_factory=_new_notify_id)
    created_at: datetime = field(default_factory=datetime.now)

    def to_signal(self) -> ProactiveSignal:
        """将 NotifyEvent 转换为 ProactiveScheduler 使用的 ProactiveSignal。"""
        return ProactiveSignal(
            scene=self.scene,
            reason=f"{self.source}:{self.id}",
            trigger_name=f"NotifyEvent[{self.source}]",
            detected_at=self.created_at,
            priority=_URGENCY_PRIORITY.get(self.urgency, 70),
            urgency=self.urgency,
            notify_source=self.source,
            metadata=dict(self.payload),
        )


# ---------------------------------------------------------------------------
# 来源适配函数
# ---------------------------------------------------------------------------

def reminder_to_notify_event(
    reminder_id: str,
    title: str,
    *,
    urgency: UrgencyLevel = "high",
) -> NotifyEvent:
    """将到期提醒转换为 NotifyEvent。

    提醒默认 urgency=high，以便在 DND 期间仍可触发（critical 级别才完全绕过 DND）。
    """
    return NotifyEvent(
        source="reminder",
        scene="reminder",
        urgency=urgency,
        payload={"reminder_id": reminder_id, "title": title, "summary": title},
        privacy_level="public",
    )


def perception_signal_to_notify_event(signal: ProactiveSignal) -> NotifyEvent:
    """将感知检测器产生的 ProactiveSignal 包装为 NotifyEvent。

    保留原始 priority 语义：将 priority 映射回最接近的 urgency。
    """
    if signal.priority >= 95:
        urgency: UrgencyLevel = "critical"
    elif signal.priority >= 80:
        urgency = "high"
    elif signal.priority >= 60:
        urgency = "normal"
    else:
        urgency = "low"

    return NotifyEvent(
        source="perception",
        scene=signal.scene,
        urgency=urgency,
        payload=dict(signal.metadata),
        privacy_level="private",  # 感知事件默认隐私级别更高
    )


def validate_external_notify_params(scene: str, urgency: str, privacy_level: str) -> tuple[ProactiveScene, UrgencyLevel, PrivacyLevel]:
    """校验外部 API 传入的参数，返回类型安全的值。

    Raises:
        ValueError: 当任一参数非法时。
    """
    if scene not in _VALID_SCENES:
        raise ValueError(f"无效 scene: {scene!r}，合法值为 {sorted(_VALID_SCENES)}")
    if urgency not in _VALID_URGENCIES:
        raise ValueError(f"无效 urgency: {urgency!r}，合法值为 {sorted(_VALID_URGENCIES)}")
    if privacy_level not in _VALID_PRIVACY_LEVELS:
        raise ValueError(f"无效 privacy_level: {privacy_level!r}，合法值为 {sorted(_VALID_PRIVACY_LEVELS)}")
    return scene, urgency, privacy_level  # type: ignore[return-value]
