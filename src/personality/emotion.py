from dataclasses import dataclass
from typing import Dict, List

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

    def update(self, user_input: str, triggers: Dict[str, List[str]]) -> None:
        """
        触发优先级：用户本轮输入命中触发词 → 更新情绪；否则执行衰减。
        多个情绪同时命中时，取第一个命中的情绪。
        """
        for mood_name, keywords in triggers.items():
            for kw in keywords:
                if kw in user_input:
                    self.trigger(mood_name)
                    return
        self.decay()
