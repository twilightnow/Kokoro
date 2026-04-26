import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _default_log_dir() -> Path:
    """KOKORO_DATA_DIR 環境変数をもとにログディレクトリを解決する。"""
    data_dir = Path(os.environ.get("KOKORO_DATA_DIR", "./data"))
    return data_dir / "logs"


class SessionLogger:
    """
    以 JSONL 格式记录会话日志，便于后续回放和排查角色偏移。
    """

    def __init__(self, log_dir: Optional[str] = None) -> None:
        if log_dir is not None:
            self._log_dir = Path(log_dir)
        else:
            self._log_dir = _default_log_dir()
        self._log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = self._log_dir / f"session_{ts}.jsonl"
        self._records: list = []

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def records(self) -> list[Dict[str, Any]]:
        """返回当前会话已写入内存的日志记录副本。"""
        return list(self._records)

    def log(
        self,
        turn: int,
        user_input: str,
        mood_before: str,
        mood_after: str,
        persist_count: int,
        reply: str,
        flagged: bool,
        usage: Optional[Dict] = None,
        safety: Optional[Dict] = None,
    ) -> None:
        record: Dict = {
            "turn": turn,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "mood_before": mood_before,
            "mood_after": mood_after,
            "persist_count": persist_count,
            "reply": reply,
            "flagged": flagged,
        }
        if usage:
            record["usage"] = usage
        if safety:
            record["safety"] = safety
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

        for record in self._records:
            mood_counts[record["mood_after"]] += 1
            if record["flagged"]:
                flagged_count += 1
            if record["mood_after"] == last_mood:
                current_streak += 1
            else:
                max_streak = max(max_streak, current_streak)
                current_streak = 1
                last_mood = record["mood_after"]
            max_streak = max(max_streak, current_streak)

        print("\n========== 会话摘要 ==========")
        print(f"总轮次: {total}")
        print(f"情绪分布: {dict(mood_counts)}")
        print(f"禁用词触发次数: {flagged_count}")
        print(f"最长连续同一情绪轮次: {max_streak}")
        print(f"日志路径: {self._log_path}")
        print("==============================\n")
