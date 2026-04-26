"""
记忆层单元测试：MemoryService token budget 裁剪、事实提取、截断日志。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.memory._token import _estimate_tokens
from src.memory.memory_service import MemoryService
from src.memory.truncation_log import TruncationLog


# ── _estimate_tokens ─────────────────────────────────────────────────────────

class TestTokenEstimate(unittest.TestCase):

    def test_basic_chinese(self):
        # 15 个字 → int(15 / 1.5) = 10
        self.assertEqual(_estimate_tokens("这是一段十五字的中文文本好吧！"), 10)

    def test_empty_string_returns_one(self):
        self.assertEqual(_estimate_tokens(""), 1)

    def test_single_char(self):
        self.assertEqual(_estimate_tokens("A"), 1)

    def test_longer_text(self):
        text = "A" * 300
        self.assertEqual(_estimate_tokens(text), 200)


# ── get_context() with token budget ──────────────────────────────────────────

class TestGetContextWithBudget(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.ms = MemoryService(self.data_dir)
        self.char_id = "test_char"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_facts(self, facts: dict):
        for key, value in facts.items():
            self.ms._long_term_memory.write_fact(self.char_id, key, value)

    def _write_summaries(self, summaries: list):
        for s in summaries:
            self.ms._summary_memory.save_summary(self.char_id, s)

    def test_empty_data_returns_empty_context(self):
        ctx = self.ms.get_context(self.char_id, token_budget=500)
        self.assertEqual(ctx.summary_items, [])
        self.assertEqual(ctx.long_term_items, {})

    def test_budget_sufficient_returns_all(self):
        self._write_facts({"user_name": "小明", "user_job": "程序员"})
        self._write_summaries(["第一次对话摘要", "第二次对话摘要"])
        ctx = self.ms.get_context(self.char_id, token_budget=500)
        self.assertIn("user_name", ctx.long_term_items)
        self.assertIn("user_job", ctx.long_term_items)
        self.assertEqual(len(ctx.summary_items), 2)

    def test_budget_zero_returns_empty_context(self):
        self._write_facts({"user_name": "小明"})
        self._write_summaries(["摘要"])
        ctx = self.ms.get_context(self.char_id, token_budget=0)
        self.assertEqual(ctx.summary_items, [])
        self.assertEqual(ctx.long_term_items, {})

    def test_tight_budget_truncates_facts(self):
        # 写入超出预算的大量事实
        for i in range(20):
            self.ms._long_term_memory.write_fact(
                self.char_id, f"key_{i}", "值" * 20
            )
        # 小 budget，不可能装下全部
        ctx = self.ms.get_context(self.char_id, token_budget=50)
        total_tokens = sum(
            _estimate_tokens(f"{k}: {v}")
            for k, v in ctx.long_term_items.items()
        )
        self.assertLessEqual(total_tokens, 25)  # fact_budget = min(25, 200)

    def test_pending_facts_excluded(self):
        # 写入冲突的事实 → pending_confirm=True
        self.ms._long_term_memory.write_fact(self.char_id, "user_name", "Alice")
        self.ms._long_term_memory.write_fact(self.char_id, "user_name", "Bob")  # conflict
        ctx = self.ms.get_context(self.char_id, token_budget=500)
        self.assertNotIn("user_name", ctx.long_term_items)

    def test_summary_budget_limited(self):
        # 写入 5 条摘要，给非常紧的 budget
        for i in range(5):
            self.ms._summary_memory.save_summary(self.char_id, "短摘要" * 3)
        ctx = self.ms.get_context(self.char_id, token_budget=10)
        # budget 极小，摘要可能被裁剪
        total_tokens = sum(_estimate_tokens(s) for s in ctx.summary_items)
        self.assertLessEqual(total_tokens, 10)

    def test_context_splits_memory_categories(self):
        self.ms._long_term_memory.write_fact(self.char_id, "user_name", "小明", category="fact")
        self.ms._long_term_memory.write_fact(self.char_id, "reply_style", "简短", category="preference")
        self.ms._long_term_memory.write_fact(self.char_id, "privacy", "不要记录公司名", category="boundary")
        self.ms._long_term_memory.write_fact(self.char_id, "recent_goal", "本周完成论文", category="event")

        ctx = self.ms.get_context(self.char_id, token_budget=500)

        self.assertEqual(ctx.long_term_items["user_name"], "小明")
        self.assertEqual(ctx.preference_items["reply_style"], "简短")
        self.assertEqual(ctx.boundary_items["privacy"], "不要记录公司名")
        self.assertEqual(ctx.event_items["recent_goal"], "本周完成论文")


# ── _extract_facts() 事实提取 ─────────────────────────────────────────────────

class TestFactExtraction(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.ms = MemoryService(self.data_dir)
        self.char_id = "test_char"

    def tearDown(self):
        self.tmp.cleanup()

    def _make_llm_fn(self, return_text: str):
        mock_result = MagicMock()
        mock_result.text = return_text
        fn = MagicMock(return_value=mock_result)
        return fn

    def _make_history(self, n=3):
        return [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "我叫小明"},
        ][:n]

    def test_valid_json_writes_facts(self):
        llm_fn = self._make_llm_fn('{"user_name": "小明", "user_job": "程序员"}')
        history = self._make_history()
        self.ms._extract_facts(self.char_id, history, llm_fn)
        records = self.ms._long_term_memory.read_records(self.char_id)
        candidates = {
            record.key: record
            for record in records.values()
            if record.status == "candidate"
        }
        self.assertEqual(candidates["user_name"].value, "小明")
        self.assertEqual(candidates["user_job"].value, "程序员")
        self.assertEqual(self.ms._long_term_memory.get_confirmed_facts(self.char_id), {})

    def test_empty_json_no_change(self):
        llm_fn = self._make_llm_fn('{}')
        self.ms._extract_facts(self.char_id, self._make_history(), llm_fn)
        facts = self.ms._long_term_memory.get_confirmed_facts(self.char_id)
        self.assertEqual(facts, {})

    def test_invalid_json_silent_failure(self):
        llm_fn = self._make_llm_fn('不是JSON格式的文本')
        # 不抛异常
        self.ms._extract_facts(self.char_id, self._make_history(), llm_fn)
        facts = self.ms._long_term_memory.get_confirmed_facts(self.char_id)
        self.assertEqual(facts, {})

    def test_llm_raises_exception_silent(self):
        llm_fn = MagicMock(side_effect=RuntimeError("LLM 挂了"))
        # 不抛异常
        self.ms._extract_facts(self.char_id, self._make_history(), llm_fn)

    def test_non_string_values_filtered(self):
        llm_fn = self._make_llm_fn('{"age": 25, "user_name": "小明"}')
        self.ms._extract_facts(self.char_id, self._make_history(), llm_fn)
        records = self.ms._long_term_memory.read_records(self.char_id)
        keys = {record.key for record in records.values()}
        self.assertNotIn("age", keys)
        self.assertIn("user_name", keys)

    def test_on_session_end_skips_extract_for_short_history(self):
        llm_fn = self._make_llm_fn('{"user_name": "小明"}')
        # 只有 1 条消息，历史轮数 < 2 时不提取事实
        self.ms.on_session_end(
            self.char_id,
            [{"role": "user", "content": "你好"}],
            llm_fn,
        )
        # LLM 被调用了一次（摘要），事实提取未调用（因为历史 < 2）
        self.assertEqual(llm_fn.call_count, 1)

    def test_on_session_end_skips_fact_extract_for_small_talk(self):
        llm_fn = self._make_llm_fn('{}')

        self.ms.on_session_end(
            self.char_id,
            [
                {"role": "user", "content": "哈哈"},
                {"role": "assistant", "content": "嗯嗯"},
                {"role": "user", "content": "继续聊"},
                {"role": "assistant", "content": "好呀"},
            ],
            llm_fn,
        )

        self.assertEqual(llm_fn.call_count, 1)

    def test_on_session_end_extracts_facts_for_preference_like_content(self):
        llm_fn = self._make_llm_fn('{"drink_preference": "手冲咖啡"}')

        self.ms.on_session_end(
            self.char_id,
            [
                {"role": "user", "content": "我最近很喜欢手冲咖啡。"},
                {"role": "assistant", "content": "听起来不错。"},
            ],
            llm_fn,
        )

        self.assertEqual(llm_fn.call_count, 2)
        facts = self.ms._long_term_memory.read_facts(self.char_id)
        self.assertEqual(facts["drink_preference"].value, "手冲咖啡")

    def test_extract_facts_categorizes_boundaries_and_preferences(self):
        llm_fn = self._make_llm_fn('{"reply_style": "简短一点", "privacy_boundary": "不要记住住址"}')
        self.ms._extract_facts(self.char_id, self._make_history(), llm_fn)

        facts = self.ms._long_term_memory.read_facts(self.char_id)

        self.assertEqual(facts["reply_style"].category, "preference")
        self.assertEqual(facts["privacy_boundary"].category, "boundary")


# ── TruncationLog ─────────────────────────────────────────────────────────────

class TestTruncationLog(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.log = TruncationLog(self.data_dir)
        self.char_id = "test_char"

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_creates_file(self):
        self.log.record(self.char_id, "fact", ["key1"], budget=200, used=210)
        log_path = self.data_dir / "memories" / self.char_id / "truncation.log"
        self.assertTrue(log_path.exists())

    def test_record_format(self):
        self.log.record(self.char_id, "fact", ["user_age"], budget=200, used=210)
        log_path = self.data_dir / "memories" / self.char_id / "truncation.log"
        content = log_path.read_text(encoding="utf-8")
        self.assertIn("kind=fact", content)
        self.assertIn("budget=200", content)
        self.assertIn("used=210", content)
        self.assertIn("user_age", content)

    def test_multiple_records_appended(self):
        self.log.record(self.char_id, "fact", ["k1"], budget=100, used=110)
        self.log.record(self.char_id, "summary", ["s1"], budget=50, used=60)
        log_path = self.data_dir / "memories" / self.char_id / "truncation.log"
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn("kind=fact", lines[0])
        self.assertIn("kind=summary", lines[1])


if __name__ == "__main__":
    unittest.main()

