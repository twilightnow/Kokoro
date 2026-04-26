import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reminder.repository import ReminderRepository
from src.reminder.service import RoutineReminderService


class TestRoutineReminderService(unittest.TestCase):

    def test_create_and_reload_persists_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RoutineReminderService(ReminderRepository(Path(tmp)))
            created = service.create(
                "firefly",
                "喝水",
                datetime(2026, 4, 26, 9, 0, 0),
                note="记得起身",
                repeat_rule="once",
            )

            reloaded_service = RoutineReminderService(ReminderRepository(Path(tmp)))
            items = reloaded_service.list("firefly")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, created.id)
        self.assertEqual(items[0].title, "喝水")
        self.assertEqual(items[0].note, "记得起身")
        self.assertEqual(items[0].status, "scheduled")

    def test_due_once_reminder_is_marked_pending_ack_and_not_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RoutineReminderService(ReminderRepository(Path(tmp)))
            created = service.create(
                "firefly",
                "午饭",
                datetime(2026, 4, 26, 12, 0, 0),
            )

            first_due = service.due("firefly", datetime(2026, 4, 26, 12, 30, 0))
            second_due = service.due("firefly", datetime(2026, 4, 26, 12, 31, 0))
            stored = service.get("firefly", created.id)

        self.assertEqual(len(first_due), 1)
        self.assertEqual(first_due[0].id, created.id)
        self.assertEqual(first_due[0].status, "scheduled")
        self.assertEqual(second_due, [])
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "pending_ack")
        self.assertIsNotNone(stored.last_triggered_at)

    def test_daily_reminder_advances_due_at_after_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RoutineReminderService(ReminderRepository(Path(tmp)))
            created = service.create(
                "firefly",
                "拉伸",
                datetime(2026, 4, 26, 18, 0, 0),
                repeat_rule="daily",
            )

            due_items = service.due("firefly", datetime(2026, 4, 26, 18, 5, 0))
            stored = service.get("firefly", created.id)

        self.assertEqual(len(due_items), 1)
        self.assertEqual(due_items[0].repeat_rule, "daily")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.status, "scheduled")
        self.assertEqual(stored.due_at, datetime(2026, 4, 27, 18, 0, 0).isoformat())

    def test_complete_and_snooze_update_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RoutineReminderService(ReminderRepository(Path(tmp)))
            created = service.create(
                "firefly",
                "散步",
                datetime(2026, 4, 26, 20, 0, 0),
            )

            service.due("firefly", datetime(2026, 4, 26, 20, 1, 0))
            snoozed = service.snooze(
                "firefly",
                created.id,
                datetime(2026, 4, 26, 20, 30, 0),
            )
            completed = service.complete("firefly", created.id, datetime(2026, 4, 26, 20, 35, 0))

        self.assertEqual(snoozed.status, "scheduled")
        self.assertEqual(snoozed.due_at, datetime(2026, 4, 26, 20, 30, 0).isoformat())
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.completed_at, datetime(2026, 4, 26, 20, 35, 0).isoformat())

    def test_delete_removes_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RoutineReminderService(ReminderRepository(Path(tmp)))
            created = service.create(
                "firefly",
                "读书",
                datetime.now() + timedelta(hours=2),
            )

            deleted = service.delete("firefly", created.id)
            items = service.list("firefly")

        self.assertTrue(deleted)
        self.assertEqual(items, [])