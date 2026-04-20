import json
import tempfile
import unittest
from pathlib import Path

from src.logger.session_log import SessionLogger


class SessionLoggerTests(unittest.TestCase):
    def test_log_writes_jsonl_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=tmp_dir)
            logger.log(
                turn=1,
                user_input="hello",
                mood_before="normal",
                mood_after="happy",
                persist_count=0,
                reply="hi",
                flagged=False,
            )

            log_path = Path(logger.log_path)
            self.assertTrue(log_path.exists())

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

            record = json.loads(lines[0])
            self.assertEqual(record["turn"], 1)
            self.assertEqual(record["user_input"], "hello")
            self.assertEqual(record["reply"], "hi")
            self.assertFalse(record["flagged"])


if __name__ == "__main__":
    unittest.main()
