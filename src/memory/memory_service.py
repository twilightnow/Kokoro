"""
记忆服务：协调工作记忆、摘要记忆、长期记忆，对外输出 MemoryContext。

职责：
  - 编排三级记忆的读写
  - 会话结束时调用 LLM 生成摘要并保存
  - 对外只暴露 MemoryService 和 MemoryContext，不让上层直接碰文件结构
"""
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .context import MemoryContext
from .long_term_memory import LongTermMemory
from .summary_memory import SummaryMemory
from .working_memory import WorkingMemory

_SUMMARY_SYSTEM_PROMPT = (
    "你是对话摘要助手。请将以下对话历史压缩为一段不超过100字的摘要，"
    "重点保留用户说出的关键信息和重要事件。只输出摘要文字，不要解释。"
)
_SUMMARY_MAX_ITEMS = 3


class MemoryService:
    """记忆服务门面：对应用层暴露统一接口，屏蔽内部三级存储细节。"""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is None:
            data_dir = Path(os.environ.get("KOKORO_DATA_DIR", "./data"))
        self._data_dir = data_dir
        self._working_memory = WorkingMemory(max_rounds=10)
        self._summary_memory = SummaryMemory(data_dir)
        self._long_term_memory = LongTermMemory(data_dir)

    @property
    def working_memory(self) -> WorkingMemory:
        """暴露工作记忆，供应用层追加消息和截断。"""
        return self._working_memory

    def get_context(self, character_id: str) -> MemoryContext:
        """生成当前轮次的记忆上下文，由人格层注入 system prompt。"""
        summaries = self._summary_memory.load_recent_summaries(
            character_id, n=_SUMMARY_MAX_ITEMS
        )
        facts = self._long_term_memory.get_confirmed_facts(character_id)
        return MemoryContext(
            summary_items=summaries,
            long_term_items=facts,
        )

    def on_session_end(
        self,
        character_id: str,
        history: List[Dict[str, str]],
        llm_chat_fn: Any,
    ) -> None:
        """会话结束钩子：调用 LLM 生成摘要并持久化。

        Args:
            character_id: 角色 ID（用于隔离存储路径）。
            history: 本次会话的消息列表。
            llm_chat_fn: callable (system_prompt, messages) -> LLMResult（或带 .text 的对象）。
        """
        if not history:
            return
        try:
            result = llm_chat_fn(_SUMMARY_SYSTEM_PROMPT, history)
            summary: str = result.text if hasattr(result, "text") else str(result)
            if summary.strip():
                self._summary_memory.save_summary(character_id, summary.strip())
        except Exception:
            # 摘要生成失败不阻断主对话链路
            pass
