"""
截断日志：记录因 token budget 超限被丢弃的记忆条目，用于后期分析和优化。
"""
import json
from datetime import datetime
from pathlib import Path


class TruncationLog:
    """记录因 token budget 超限被丢弃的记忆条目，用于后期分析和优化裁剪策略。"""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _log_path(self, character_id: str) -> Path:
        path = self._data_dir / "memories" / character_id / "truncation.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def record(
        self,
        character_id: str,
        kind: str,
        dropped_keys: list,
        budget: int,
        used: int,
    ) -> None:
        """追加一条截断记录到 memories/<character_id>/truncation.log（纯文本，按行）。

        Args:
            character_id: 角色 ID。
            kind: "fact" | "summary"。
            dropped_keys: 被丢弃的 key 或摘要前几字的列表。
            budget: 本次 token 预算。
            used: 实际使用的 token 数。
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        dropped_json = json.dumps(dropped_keys, ensure_ascii=False)
        line = (
            f"{timestamp} | kind={kind} | budget={budget} | used={used} | dropped={dropped_json}"
        )
        try:
            path = self._log_path(character_id)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
