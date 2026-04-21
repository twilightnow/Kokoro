"""記憶層の動作確認スクリプト（セルフレビュー用）"""
import sys
import tempfile
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.memory.summary_memory import SummaryMemory
from src.memory.long_term_memory import LongTermMemory
from src.memory.memory_service import MemoryService


def test_summary():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        sm = SummaryMemory(d)
        for i in range(4):
            sm.save_summary("char", f"Summary {i}")
        s = sm.load_recent_summaries("char", n=3)
        assert len(s) == 3, f"Expected 3, got {len(s)}"
        print(f"SummaryMemory OK: {s}")


def test_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        ltm = LongTermMemory(d)
        ltm.write_fact("char", "name", "Alice")
        ltm.write_fact("char", "name", "Bob")  # conflict
        facts = ltm.read_facts("char")
        assert facts["name"].pending_confirm, "Conflict should be flagged"
        confirmed = ltm.get_confirmed_facts("char")
        assert "name" not in confirmed, "Conflicted key should not appear in confirmed"
        print("LongTermMemory conflict OK")


def test_memory_service():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        ms = MemoryService(d)
        ctx = ms.get_context("empty_char")
        assert ctx.summary_items == []
        assert ctx.long_term_items == {}
        print(f"MemoryService empty context OK: {ctx}")


if __name__ == "__main__":
    test_summary()
    test_conflict()
    test_memory_service()
    print("All memory layer tests passed!")
