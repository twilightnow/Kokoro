"""
记忆服务：协调工作记忆、摘要记忆、长期记忆，对外输出 MemoryContext。

职责：
  - 编排三级记忆的读写
  - 会话结束时调用 LLM 生成摘要并提取长期事实
  - 对外只暴露 MemoryService 和 MemoryContext，不让上层直接碰文件结构
"""
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .context import MemoryContext
from .long_term_memory import LongTermMemory
from .summary_memory import SummaryMemory
from .truncation_log import TruncationLog
from .working_memory import WorkingMemory
from ._token import _estimate_tokens

_SUMMARY_SYSTEM_PROMPT = (
    "你是对话摘要助手。请将以下对话历史压缩为一段不超过100字的摘要，"
    "重点保留用户说出的关键信息和重要事件。只输出摘要文字，不要解释。"
)
_FACT_EXTRACT_PROMPT = (
    "你是信息提取助手。从以下对话中提取用户（User）明确陈述的个人信息，"
    "例如名字、职业、爱好、习惯等。只提取用户主动说出的内容，不要推断。\n\n"
    "输出格式为 JSON 对象，key 为信息类别（英文小写下划线），value 为用户原话中的值。"
    "例如：{\"user_name\": \"小明\", \"user_job\": \"程序员\"}\n\n"
    "如果没有可提取的信息，输出空对象 {}。只输出 JSON，不要其他内容。"
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
        self._truncation_log = TruncationLog(data_dir)

    @property
    def working_memory(self) -> WorkingMemory:
        """暴露工作记忆，供应用层追加消息和截断。"""
        return self._working_memory

    def get_context(
        self,
        character_id: str,
        token_budget: int = 500,
    ) -> MemoryContext:
        """生成当前轮次的记忆上下文，由人格层注入 system prompt。

        token 分配策略：
          长期事实预算 = min(token_budget // 2, 200)  — 最多占一半，上限 200
          摘要预算     = token_budget - 实际使用的长期事实 token 数
        """
        if token_budget <= 0:
            return MemoryContext()

        # ── 长期事实裁剪 ────────────────────────────────────────────────────────
        fact_budget = min(token_budget // 2, 200)
        all_facts = self._long_term_memory.read_facts(character_id)
        # 只取已确认事实，按 updated_at 降序（最新优先）
        confirmed = [
            (k, v)
            for k, v in all_facts.items()
            if not v.pending_confirm
        ]
        confirmed.sort(key=lambda kv: kv[1].updated_at, reverse=True)

        selected_facts: Dict[str, str] = {}
        used_fact_tokens = 0
        dropped_fact_keys: List[str] = []
        for key, record in confirmed:
            text = f"{key}: {record.value}"
            tokens = _estimate_tokens(text)
            if used_fact_tokens + tokens <= fact_budget:
                selected_facts[key] = record.value
                used_fact_tokens += tokens
            else:
                dropped_fact_keys.append(key)

        if dropped_fact_keys:
            self._truncation_log.record(
                character_id=character_id,
                kind="fact",
                dropped_keys=dropped_fact_keys,
                budget=fact_budget,
                used=used_fact_tokens,
            )

        # ── 摘要裁剪 ────────────────────────────────────────────────────────────
        summary_budget = token_budget - used_fact_tokens
        all_summaries = self._summary_memory.load_recent_summaries(
            character_id, n=5
        )
        # load_recent_summaries 返回旧→新顺序，反转后从最新开始尝试填充
        selected_summaries: List[str] = []
        used_summary_tokens = 0
        dropped_summaries: List[str] = []
        for summary in reversed(all_summaries):
            tokens = _estimate_tokens(summary)
            if used_summary_tokens + tokens <= summary_budget:
                selected_summaries.insert(0, summary)  # 保持旧→新顺序
                used_summary_tokens += tokens
            else:
                dropped_summaries.append(summary[:20])  # 只记录前 20 字便于追溯

        if dropped_summaries:
            self._truncation_log.record(
                character_id=character_id,
                kind="summary",
                dropped_keys=dropped_summaries,
                budget=summary_budget,
                used=used_summary_tokens,
            )

        return MemoryContext(
            summary_items=selected_summaries,
            long_term_items=selected_facts,
        )

    def _extract_facts(
        self,
        character_id: str,
        history: List[Dict[str, str]],
        llm_chat_fn: Callable,
    ) -> None:
        """调用 LLM 从对话历史提取用户显式陈述的事实，写入 LongTermMemory。

        失败时静默，不抛出异常，不影响主链路。
        """
        try:
            result = llm_chat_fn(_FACT_EXTRACT_PROMPT, history)
            raw_text: str = result.text if hasattr(result, "text") else str(result)
            raw_text = raw_text.strip()
            # 尝试从 markdown 代码块中提取 JSON
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                # 去掉首尾 ``` 行
                raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            facts: Dict[str, Any] = json.loads(raw_text)
            if not isinstance(facts, dict):
                return
            for key, value in facts.items():
                if isinstance(value, str) and value.strip():
                    self._long_term_memory.write_fact(
                        character_id, key, value.strip(), source="llm_extract"
                    )
        except (json.JSONDecodeError, Exception):
            pass

    def on_session_end(
        self,
        character_id: str,
        history: List[Dict[str, str]],
        llm_chat_fn: Any,
    ) -> None:
        """会话结束钩子：调用 LLM 生成摘要并提取长期事实。

        Args:
            character_id: 角色 ID（用于隔离存储路径）。
            history: 本次会话的消息列表。
            llm_chat_fn: callable (system_prompt, messages) -> LLMResult（或带 .text 的对象）。
        """
        if not history:
            return

        # 步骤 1：生成摘要（独立 try/except）
        try:
            result = llm_chat_fn(_SUMMARY_SYSTEM_PROMPT, history)
            summary: str = result.text if hasattr(result, "text") else str(result)
            if summary.strip():
                self._summary_memory.save_summary(character_id, summary.strip())
        except Exception:
            pass

        # 步骤 2：提取长期事实（轮数 ≥ 2 才值得提取）
        if len(history) >= 2:
            self._extract_facts(character_id, history, llm_chat_fn)
