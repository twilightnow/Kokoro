from dataclasses import dataclass
from typing import Dict, List, Optional

_PERSIST_ROUNDS = 3


@dataclass
class EmotionState:
    mood: str = "normal"
    persist_count: int = 0

    def trigger(self, new_mood: str) -> None:
        self.mood = new_mood
        self.persist_count = _PERSIST_ROUNDS

    def decay(self) -> None:
        if self.mood != "normal":
            self.persist_count -= 1
            if self.persist_count <= 0:
                self.mood = "normal"
                self.persist_count = 0

    def update(self, event: Optional[str] = None) -> None:
        """接受已检测到的事件名，只负责状态跃迁和衰减。

        不直接接收用户输入文本，触发检测由独立的 detect_event() 负责。
        """
        if event:
            self.trigger(event)
        else:
            self.decay()


def detect_event(
    user_input: str, triggers: Dict[str, List[str]]
) -> Optional[str]:
    """检测用户输入中触发的情绪事件，返回情绪名称或 None。

    只做检测，不修改状态。多个情绪同时命中时，取第一个命中的情绪。
    """
    for mood_name, keywords in triggers.items():
        for kw in keywords:
            if kw in user_input:
                return mood_name
    return None
