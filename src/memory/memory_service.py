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

from .context import MemoryContext, MemoryRecordMeta
from .memory_ops_log import MemoryOpsLog
from .long_term_memory import LongTermMemory, normalize_fact_category
from .record import MemoryRecord
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
    "例如名字、职业、爱好、习惯、偏好、边界、近期事件。只提取用户主动说出的内容，不要推断。\n\n"
    "优先输出如下 JSON 结构："
    "{\"items\": [{\"type\": \"fact|preference|boundary|event\", \"key\": \"...\", \"value\": \"...\", \"confidence\": 0.0, \"evidence\": \"用户原句\"}]}。"
    "如果无法提供 items 结构，也可以退化为扁平 JSON 对象。"
    "如果没有可提取的信息，输出 {\"items\": []}。只输出 JSON，不要其他内容。"
)
_SUMMARY_MAX_ITEMS = 3
_FACT_CATEGORY_PRIORITY = {
    "boundary": 0,
    "preference": 1,
    "fact": 2,
    "event": 3,
}
_FACT_TRIGGER_MARKERS = (
    "我叫",
    "叫我",
    "我是",
    "我在",
    "我住",
    "我来自",
    "我喜欢",
    "我不喜欢",
    "我希望",
    "我想",
    "我最近",
    "今天",
    "这周",
    "计划",
    "目标",
    "不要",
    "别再",
    "别提",
    "隐私",
    "工作",
    "学校",
    "家人",
    "生日",
    "prefer",
    "favorite",
    "boundary",
    "privacy",
)


_EXTRACTION_POLICY_AGGRESSIVE = "aggressive"
_RECALL_STYLE_NARRATIVE = "narrative"
_RECALL_STYLE_MINIMAL = "minimal"


class MemoryService:
    """记忆服务门面：对应用层暴露统一接口，屏蔽内部三级存储细节。"""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is None:
            data_dir = Path(os.environ.get("KOKORO_DATA_DIR", "./data"))
        self._data_dir = data_dir
        self._working_memory = WorkingMemory(max_rounds=10)
        self._summary_memory = SummaryMemory(data_dir)
        self._long_term_memory = LongTermMemory(data_dir)
        self._ops_log = MemoryOpsLog(data_dir)
        self._truncation_log = TruncationLog(data_dir)
        self._extraction_policy: str = ""
        self._recall_style: str = ""

    def configure_memory(self, extraction_policy: str = "", recall_style: str = "") -> None:
        """从角色卡配置中应用记忆策略。

        extraction_policy:
            ``"aggressive"`` — 每次会话结束都提取事实，不依赖触发词。
            其他/空值   — 保守提取（默认），只有检测到触发词才调用 LLM 提取。

        recall_style:
            ``"minimal"``    — 只注入边界和偏好，跳过事实和摘要。
            ``"narrative"``  — 将各类记忆合并为一段自然语言描述注入 prompt。
            其他/空值   — 结构化注入（默认），按类别分别列出 key: value。
        """
        self._extraction_policy = (extraction_policy or "").strip().lower()
        self._recall_style = (recall_style or "").strip().lower()

    @property
    def working_memory(self) -> WorkingMemory:
        """暴露工作记忆，供应用层追加消息和截断。"""
        return self._working_memory

    def get_context(
        self,
        character_id: str,
        token_budget: int = 500,
        query_text: str = "",
    ) -> MemoryContext:
        """生成当前轮次的记忆上下文，由人格层注入 system prompt。"""
        if token_budget <= 0:
            return MemoryContext()

        records = self.retrieve(
            query_text=query_text,
            character_id=character_id,
            filters={"status": "confirmed"},
        )
        return self.build_context(character_id, records, token_budget)

    def retrieve(
        self,
        query_text: str,
        character_id: str,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[MemoryRecord]:
        """Retrieve structured memory records from the current repository backend."""
        filters = filters or {}
        expected_status = filters.get("status")
        expected_type = filters.get("type")
        query = query_text.strip().lower()
        query_terms = [term for term in query.split() if term]

        records = [
            record
            for record in self._long_term_memory.read_records(character_id).values()
            if record.status not in {"archived", "rejected"}
        ]
        blocked_keys = {
            record.key
            for record in records
            if record.status == "candidate" and record.memory_type != "event"
        }
        if expected_status:
            records = [record for record in records if record.status == expected_status]
        if expected_type:
            records = [record for record in records if record.memory_type == normalize_fact_category(expected_type)]
        records = [
            record
            for record in records
            if not (
                record.status == "confirmed"
                and record.key in blocked_keys
                and record.memory_type != "event"
            )
        ]

        def score(record: MemoryRecord) -> tuple[int, float, int, str, str]:
            text = " ".join(
                part for part in [record.key, record.value, record.evidence or ""] if part
            ).lower()
            match_score = 0
            if not query_terms:
                match_score = 1
            else:
                for term in query_terms:
                    if term in record.key.lower():
                        match_score += 5
                    elif term in text:
                        match_score += 3
            return (
                match_score,
                record.importance,
                -_FACT_CATEGORY_PRIORITY.get(normalize_fact_category(record.memory_type), 99),
                record.updated_at,
                record.record_id,
            )

        ranked = sorted(records, key=score, reverse=True)
        if query_terms:
            matched = [record for record in ranked if score(record)[0] > 0]
        else:
            matched = ranked

        self._ops_log.record(
            character_id,
            "retrieve_completed",
            query=query_text,
            returned=len(matched),
            filters=filters,
        )
        return matched

    def build_context(
        self,
        character_id: str,
        records: List[MemoryRecord],
        token_budget: int,
    ) -> MemoryContext:
        """Build prompt-facing memory context from retrieved records."""

        fact_budget = min(token_budget // 2, 200)
        confirmed = [
            record
            for record in records
            if record.status == "confirmed"
        ]
        confirmed.sort(
            key=lambda record: (
                _FACT_CATEGORY_PRIORITY.get(normalize_fact_category(record.memory_type), 99),
                -record.importance,
                record.updated_at,
                record.record_id,
            )
        )

        selected_facts: Dict[str, str] = {}
        selected_preferences: Dict[str, str] = {}
        selected_boundaries: Dict[str, str] = {}
        selected_events: Dict[str, str] = {}
        record_meta: Dict[str, MemoryRecordMeta] = {}
        selected_record_ids: List[str] = []
        used_fact_tokens = 0
        dropped_fact_ids: List[str] = []
        for record in confirmed:
            text = f"{record.key}: {record.value}"
            tokens = _estimate_tokens(text)
            if used_fact_tokens + tokens <= fact_budget:
                category = normalize_fact_category(record.memory_type)
                meta_key = record.key
                if category == "preference":
                    selected_preferences[record.key] = record.value
                elif category == "boundary":
                    selected_boundaries[record.key] = record.value
                elif category == "event":
                    meta_key = record.key
                    if record.key in selected_events:
                        meta_key = f"{record.key}:{record.record_id[:8]}"
                    selected_events[meta_key] = record.value
                else:
                    selected_facts[record.key] = record.value
                record_meta[meta_key] = MemoryRecordMeta(
                    source=record.source,
                    confidence=record.confidence,
                    importance=record.importance,
                )
                selected_record_ids.append(record.record_id)
                used_fact_tokens += tokens
            else:
                dropped_fact_ids.append(record.record_id)

        if dropped_fact_ids:
            self._truncation_log.record(
                character_id=character_id,
                kind="fact",
                dropped_keys=dropped_fact_ids,
                budget=fact_budget,
                used=used_fact_tokens,
            )

        summary_budget = token_budget - used_fact_tokens
        all_summaries = self._summary_memory.load_recent_summaries(
            character_id, n=5
        )
        selected_summaries: List[str] = []
        used_summary_tokens = 0
        dropped_summaries: List[str] = []
        for summary in reversed(all_summaries):
            tokens = _estimate_tokens(summary)
            if used_summary_tokens + tokens <= summary_budget:
                selected_summaries.insert(0, summary)
                used_summary_tokens += tokens
            else:
                dropped_summaries.append(summary[:20])

        if dropped_summaries:
            self._truncation_log.record(
                character_id=character_id,
                kind="summary",
                dropped_keys=dropped_summaries,
                budget=summary_budget,
                used=used_summary_tokens,
            )

        if selected_record_ids:
            self._long_term_memory.touch_records(character_id, selected_record_ids)

        return self._apply_recall_style(
            MemoryContext(
                summary_items=selected_summaries,
                long_term_items=selected_facts,
                preference_items=selected_preferences,
                boundary_items=selected_boundaries,
                event_items=selected_events,
                record_meta=record_meta,
            )
        )

    def _apply_recall_style(self, ctx: MemoryContext) -> MemoryContext:
        """按 recall_style 对记忆上下文进行后处理。"""
        if self._recall_style == _RECALL_STYLE_MINIMAL:
            # minimal：只保留边界和偏好，丢弃事实、事件、摘要
            kept_keys = set(ctx.preference_items) | set(ctx.boundary_items)
            return MemoryContext(
                summary_items=[],
                long_term_items={},
                preference_items=ctx.preference_items,
                boundary_items=ctx.boundary_items,
                event_items={},
                record_meta={k: v for k, v in ctx.record_meta.items() if k in kept_keys},
            )
        if self._recall_style == _RECALL_STYLE_NARRATIVE:
            # narrative：将所有记忆合并为一段自然语言摘要，放入 summary_items
            # record_meta 不再适用（内容已合并为自然语言）
            fragments: List[str] = []
            if ctx.boundary_items:
                parts = "; ".join(f"{k}: {v}" for k, v in ctx.boundary_items.items())
                fragments.append(f"用户边界：{parts}")
            if ctx.preference_items:
                parts = "; ".join(f"{k}: {v}" for k, v in ctx.preference_items.items())
                fragments.append(f"用户偏好：{parts}")
            if ctx.long_term_items:
                parts = "; ".join(f"{k}: {v}" for k, v in ctx.long_term_items.items())
                fragments.append(f"已知事实：{parts}")
            if ctx.event_items:
                parts = "; ".join(f"{k}: {v}" for k, v in ctx.event_items.items())
                fragments.append(f"近期事件：{parts}")
            narrative_summaries = [". ".join(fragments)] if fragments else []
            narrative_summaries.extend(ctx.summary_items)
            return MemoryContext(
                summary_items=narrative_summaries,
                long_term_items={},
                preference_items={},
                boundary_items={},
                event_items={},
            )
        # structured（默认）：保持原样
        return ctx

    def _categorize_fact(self, key: str, value: str) -> str:
        normalized_key = key.strip().lower()
        normalized_value = value.strip().lower()

        preference_markers = (
            "pref",
            "prefer",
            "favorite",
            "like",
            "dislike",
            "habit",
            "hobby",
            "style",
            "voice",
            "tone",
            "address",
        )
        boundary_markers = (
            "boundary",
            "limit",
            "avoid",
            "privacy",
            "sensitive",
            "forbid",
            "forbidden",
            "do_not",
            "dont",
        )
        event_markers = (
            "event",
            "recent",
            "goal",
            "stress",
            "pressure",
            "project",
            "todo",
            "deadline",
            "plan",
        )

        if any(marker in normalized_key for marker in boundary_markers):
            return "boundary"
        if any(marker in normalized_key for marker in preference_markers):
            return "preference"
        if any(marker in normalized_key for marker in event_markers):
            return "event"
        if any(marker in normalized_value for marker in ("不要", "别再", "不想", "别提", "隐私")):
            return "boundary"
        if any(marker in normalized_value for marker in ("喜欢", "偏好", "希望", "叫我", "称呼", "语气")):
            return "preference"
        if any(marker in normalized_value for marker in ("最近", "这周", "今天", "目标", "压力", "截止")):
            return "event"
        return "fact"

    def _extract_facts(
        self,
        character_id: str,
        history: List[Dict[str, str]],
        llm_chat_fn: Callable,
    ) -> None:
        """调用 LLM 从对话历史提取用户显式陈述的事实，写入 LongTermMemory。

        失败时不抛出异常，不影响主链路，但会写入 memory_ops 日志。
        """
        self._ops_log.record(character_id, "extract_started", message_count=len(history))
        try:
            result = llm_chat_fn(_FACT_EXTRACT_PROMPT, history)
            raw_text: str = result.text if hasattr(result, "text") else str(result)
            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            payload: Dict[str, Any] = json.loads(raw_text)
            items = self._normalize_extracted_items(payload)
            if not items:
                self._ops_log.record(character_id, "extract_empty")
                return
            for item in items:
                mutation = self._long_term_memory.write_record(
                    character_id,
                    item["key"],
                    item["value"],
                    source="llm_extract",
                    memory_type=item["memory_type"],
                    status="candidate",
                    evidence=item.get("evidence"),
                    confidence=item.get("confidence"),
                    metadata={"extracted": True},
                )
                self._ops_log.record(
                    character_id,
                    mutation.action,
                    record_id=mutation.record.record_id,
                    key=mutation.record.key,
                    memory_type=mutation.record.memory_type,
                    related_record_id=mutation.related_record_id,
                )
        except json.JSONDecodeError as error:
            self._ops_log.record(character_id, "parse_failed", error=str(error))
        except Exception as error:
            self._ops_log.record(character_id, "persist_failed", error=str(error))

    def _normalize_extracted_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        raw_items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                key = str(raw.get("key") or "").strip()
                value = str(raw.get("value") or "").strip()
                if not key or not value:
                    continue
                items.append({
                    "key": key,
                    "value": value,
                    "memory_type": normalize_fact_category(raw.get("type")),
                    "confidence": (
                        float(raw["confidence"])
                        if isinstance(raw.get("confidence"), (int, float))
                        else None
                    ),
                    "evidence": str(raw.get("evidence") or "").strip() or None,
                })
            return items

        if not isinstance(payload, dict):
            return items

        for key, value in payload.items():
            if key == "items":
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            items.append({
                "key": key,
                "value": value.strip(),
                "memory_type": self._categorize_fact(key, value),
                "confidence": None,
                "evidence": None,
            })
        return items

    def _should_extract_facts(self, history: List[Dict[str, str]]) -> bool:
        user_messages = [
            str(item.get("content", "")).strip().lower()
            for item in history
            if item.get("role") == "user"
        ]
        if not user_messages:
            return False

        combined = "\n".join(message for message in user_messages if message)
        if not combined:
            return False

        return any(marker in combined for marker in _FACT_TRIGGER_MARKERS)

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
                self._ops_log.record(character_id, "summary_created", length=len(summary.strip()))
            else:
                self._ops_log.record(character_id, "summary_empty")
        except Exception as error:
            self._ops_log.record(character_id, "summary_failed", error=str(error))

        # 步骤 2：提取长期事实（轮数 ≥ 2 才值得提取）
        # aggressive 策略：无论是否包含触发词都提取；conservative（默认）：需要触发词
        if len(history) >= 2:
            should_extract = (
                self._extraction_policy == _EXTRACTION_POLICY_AGGRESSIVE
                or self._should_extract_facts(history)
            )
            if should_extract:
                self._extract_facts(character_id, history, llm_chat_fn)
            else:
                self._ops_log.record(character_id, "extract_skipped")
