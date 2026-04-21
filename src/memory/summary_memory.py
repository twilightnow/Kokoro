"""
会话摘要记忆：会话结束后生成摘要，下次会话时作为上下文背景注入。

存储格式：memories/<character_id>/summaries.jsonl
每条记录：{"summary": "...", "created_at": "ISO 8601"}
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List


class SummaryMemory:
    """会话摘要记忆：存储和读取历史会话摘要。

    职责：存储和检索摘要，不负责生成（生成由应用层通过 LLM 完成）。
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _summaries_path(self, character_id: str) -> Path:
        path = self._data_dir / "memories" / character_id / "summaries.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_summary(self, character_id: str, summary: str) -> None:
        """保存一条会话摘要。空摘要不写入。"""
        summary = summary.strip()
        if not summary:
            return
        # 超过 100 字则截断（路线图约束）
        if len(summary) > 100:
            summary = summary[:100]
        record = {
            "summary": summary,
            "created_at": datetime.now().isoformat(),
        }
        path = self._summaries_path(character_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_recent_summaries(self, character_id: str, n: int = 3) -> List[str]:
        """读取最近 n 条摘要（按时间顺序，最旧在前）。"""
        path = self._summaries_path(character_id)
        if not path.exists():
            return []

        lines = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)

        recent = lines[-n:] if len(lines) > n else lines
        result = []
        for line in recent:
            try:
                record = json.loads(line)
                result.append(record["summary"])
            except (json.JSONDecodeError, KeyError):
                continue
        return result
