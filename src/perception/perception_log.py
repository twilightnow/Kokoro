"""
感知事件日志：记录每次主动介入触发，供事后分析频率和效果。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class PerceptionLog:
    """记录感知触发事件到 JSONL 文件。"""

    def __init__(self, log_dir: Path) -> None:
        log_dir.mkdir(parents=True, exist_ok=True)
        self._path = log_dir / "perception_events.jsonl"

    def record(
        self,
        trigger_name: str,
        reason: str,
        character_id: str,
        proactive_reply: Optional[str] = None,
    ) -> None:
        """追加一条触发事件记录。失败时静默。"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger_name,
            "reason": reason,
            "character_id": character_id,
            "reply": proactive_reply,
        }
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
