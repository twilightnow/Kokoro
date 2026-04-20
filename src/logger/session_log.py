import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class SessionLogger:
    """
    以 JSONL 格式记录会话日志。
    日志是复盘（"哪一轮开始不像她"）的核心工具，不是可选项。
    """

    def __init__(self, log_dir: str = "logs") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = self._log_dir / f"session_{ts}.jsonl"
        self._records: list = []

    @property
    def log_path(self) -> Path:
        return self._log_path

    def log(
        self,
        turn: int,
        user_input: str,
        mood_before: str,
        mood_after: str,
        persist_count: int,
        reply: str,
        flagged: bool,
    ) -> None:
        record = {
            "turn": turn,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "mood_before": mood_before,
            "mood_after": mood_after,
            "persist_count": persist_count,
            "reply": reply,
            "flagged": flagged,
        }
        self._records.append(record)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def print_summary(self) -> None:
        if not self._records:
            return

        total = len(self._records)
        mood_counts: defaultdict = defaultdict(int)
        flagged_count = 0
        max_streak = 0
        current_streak = 1
        last_mood = None

        for r in self._records:
            mood_counts[r["mood_after"]] += 1
            if r["flagged"]:
                flagged_count += 1
            if r["mood_after"] == last_mood:
                current_streak += 1
            else:
                max_streak = max(max_streak, current_streak)
                current_streak = 1
                last_mood = r["mood_after"]
            max_streak = max(max_streak, current_streak)

        print("\n========== 会话摘要 ==========")
        print(f"总轮次: {total}")
        print(f"情绪分布: {dict(mood_counts)}")
        print(f"禁用词触发次数: {flagged_count}")
        print(f"最长连续同一情绪轮次: {max_streak}")
        print(f"日志路径: {self._log_path}")
        print("==============================\n")
