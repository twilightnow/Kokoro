from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal
from uuid import uuid4

InterventionLevel = Literal["silent", "expression", "short", "full"]
ProactiveScene = Literal[
    "late_night",
    "long_work",
    "idle_return",
    "window_switch",
    "gaming",
    "reminder",
]


def new_proactive_event_id() -> str:
    return f"evt_{uuid4().hex[:12]}"


@dataclass
class ProactiveSignal:
    scene: ProactiveScene
    reason: str
    trigger_name: str
    detected_at: datetime = field(default_factory=datetime.now)
    priority: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ProactiveAction:
    id: str
    timestamp: str
    character_id: str
    scene: ProactiveScene
    level: InterventionLevel
    decision: str
    reason: str
    content: str = ""
    expression: str = ""
    actions: list[str] = field(default_factory=list)
    suppressed_by: str | None = None
    settings_mode: str = "normal"
    daily_count_before: int = 0
    user_responded: bool = False
    feedback: str | None = None
    generated_by: str = "template"
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)