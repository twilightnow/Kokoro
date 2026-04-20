from typing import Dict, List


class WorkingMemory:
    """
    最近 N 轮对话的工作记忆。
    截断在每轮发送前执行（调用 truncate()），截断后再追加当前输入。
    """

    def __init__(self, max_rounds: int = 10) -> None:
        self._max_messages = max_rounds * 2
        self._history: List[Dict[str, str]] = []

    def add(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def truncate(self) -> None:
        # `truncate()` is called before appending the current user input.
        # Keep one full turn worth of space so the outgoing request stays
        # within the configured round limit after the new user message is added.
        if len(self._history) >= self._max_messages:
            self._history = self._history[-(self._max_messages - 2) :]

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()

    def __len__(self) -> int:
        return len(self._history)
