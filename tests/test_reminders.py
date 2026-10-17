import tempfile
import unittest
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# Keep source-checkout discovery independent of an editable install or test order.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from renyyt.errors import ConfigError
from renyyt.reminders import ReminderError, ReminderStore, next_scheduler_run, parse_run_times


class ReminderStoreTestCase(unittest.TestCase):
    def subscription(self, endpoint="https://push.example/sub/1"):
        return {"endpoint": endpoint, "keys": {"p256dh": "p256-key", "auth": "auth-key"}}

    def test_sync_due_mark_sent_and_unsubscribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReminderStore(Path(tmp) / "reminders.sqlite3")
            trigger = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
            collection = trigger + timedelta(days=1)
            reminder = {"collectionDate": collection.date().isoformat(), "label": "Sekajäte", "triggerAt": trigger.isoformat()}
            sid, count = store.sync(self.subscription(), [reminder], locale="fi")
            self.assertEqual(count, 1)
            self.assertEqual(store.stats(), {"subscriptions": 1, "pending": 1})
            due = store.due(now=(trigger + timedelta(hours=1)).timestamp())
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0]["label"], "Sekajäte")
            store.mark_sent(due[0]["reminder_id"], sent_at=(trigger + timedelta(hours=1, minutes=1)).timestamp())
            self.assertEqual(store.stats()["pending"], 0)
            store.unsubscribe(self.subscription())
            self.assertEqual(store.stats(), {"subscriptions": 0, "pending": 0})
            self.assertTrue(sid)

    def test_resync_does_not_recreate_already_sent_identical_reminder(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReminderStore(Path(tmp) / "reminders.sqlite3")
            trigger = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)
            collection = trigger + timedelta(days=1)
            reminder = {"collectionDate": collection.date().isoformat(), "label": "Sekajäte", "triggerAt": trigger.isoformat()}
            store.sync(self.subscription(), [reminder])
            due = store.due(now=(trigger + timedelta(hours=1)).timestamp())
            store.mark_sent(due[0]["reminder_id"])
            _, count = store.sync(self.subscription(), [reminder])
            self.assertEqual(count, 0)
            self.assertEqual(store.stats()["pending"], 0)

    def test_subscription_and_reminder_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ReminderStore(Path(tmp) / "r.sqlite3")
            with self.assertRaises(ReminderError):
                store.sync({"endpoint": "http://push.example/x", "keys": {"p256dh": "x", "auth": "y"}}, [])
            with self.assertRaises(ReminderError):
                store.sync(self.subscription(), [{"collectionDate": "2026-10-12", "label": "X", "triggerAt": "not-a-date"}])

    def test_parse_run_times_and_next_run(self):
        times = parse_run_times("07:00,18:00,07:00")
        self.assertEqual(times, [(7, 0), (18, 0)])
        now = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(next_scheduler_run(times, timezone.utc, now=now), datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc))
        with self.assertRaises(ConfigError):
            parse_run_times("25:00")


if __name__ == "__main__":
    unittest.main()

class ReminderEdgeCaseTestCase(unittest.TestCase):
    def subscription(self):
        return {"endpoint": "https://push.example/sub/x", "keys": {"p256dh": "p", "auth": "a"}}

    def test_validation_edge_cases_and_expiry(self):
        from renyyt.reminders import ReminderStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ReminderStore(Path(tmp) / "r.sqlite3")
            for bad in (None, "x"):
                with self.assertRaises(ReminderError):
                    store.validate_subscription(bad)
            with self.assertRaises(ReminderError):
                store.validate_subscription({"endpoint":"https://push.example/x", "keys": {}})
            with self.assertRaises(ReminderError):
                store.validate_reminders("x")
            with self.assertRaises(ReminderError):
                store.validate_reminders([{}] * 129)
            with self.assertRaises(ReminderError):
                store.validate_reminders(["x"])
            with self.assertRaises(ReminderError):
                store.validate_reminders([{"collectionDate":"", "label":"x", "triggerAt":"2026-10-10T00:00:00Z"}])
            with self.assertRaises(ReminderError):
                store.validate_reminders([{"collectionDate":"2026-10-10", "label":"x", "triggerAt":"2026-10-10T00:00:00"}])
            with mock.patch("renyyt.reminders.time.time", return_value=10000):
                self.assertEqual(store.validate_reminders([{"collectionDate":"1970-01-01", "label":"x", "triggerAt":"1970-01-01T00:00:00Z"}]), [])
                with self.assertRaises(ReminderError):
                    store.validate_reminders([{"collectionDate":"2099-01-01", "label":"x", "triggerAt":"2099-01-01T00:00:00Z"}])
            sid, _ = store.sync(self.subscription(), [])
            store.delete_subscription_id(sid)
            self.assertEqual(store.stats()["subscriptions"], 0)

    def test_notification_text_and_timezones(self):
        from renyyt.reminders import notification_text, scheduler_timezone
        self.assertIn("collection", notification_text("en-US", "Mixed", "2026-10-12")[1])
        self.assertIn("tyhjennys", notification_text("xx", "Sekajäte", "2026-10-12")[1])
        self.assertEqual(scheduler_timezone("UTC"), timezone.utc)
        self.assertIsNotNone(scheduler_timezone("local"))
        with self.assertRaises(ConfigError):
            scheduler_timezone("Definitely/Not_A_Zone")
        for value in ("7", "xx:00", "", "07:99"):
            with self.assertRaises(ConfigError):
                parse_run_times(value)

    def test_send_web_push_success_gone_and_failure(self):
        import sys, types
        from renyyt import reminders as mod
        calls = []
        class FakeResponse:
            def __init__(self, status): self.status_code = status
        class FakeWebPushException(Exception):
            def __init__(self, status=None):
                super().__init__("push failed")
                self.response = FakeResponse(status) if status else None
        fake = types.ModuleType("pywebpush")
        fake.WebPushException = FakeWebPushException
        row = {"reminder_id":1,"locale":"fi","label":"Sekajäte","collection_date":"2026-10-12","endpoint":"https://push.example/x","p256dh":"p","auth":"a"}
        config = {"vapid_subject":"mailto:a@example.com","vapid_private_key":"private","push_ttl":123}
        def success(**kwargs): calls.append(kwargs)
        fake.webpush = success
        with mock.patch.dict(sys.modules, {"pywebpush": fake}):
            self.assertEqual(mod.send_web_push(config, row), ("sent", None))
        self.assertEqual(calls[0]["ttl"], 123)
        def gone(**kwargs): raise FakeWebPushException(410)
        fake.webpush = gone
        with mock.patch.dict(sys.modules, {"pywebpush": fake}):
            self.assertEqual(mod.send_web_push(config, row), ("gone", 410))
        def fail(**kwargs): raise FakeWebPushException(500)
        fake.webpush = fail
        with mock.patch.dict(sys.modules, {"pywebpush": fake}):
            with self.assertRaises(ReminderError): mod.send_web_push(config, row)

    def test_run_due_all_result_paths(self):
        from renyyt import reminders as mod
        rows = [
            {"reminder_id":1,"subscription_id":"a"*64},
            {"reminder_id":2,"subscription_id":"b"*64},
            {"reminder_id":3,"subscription_id":"c"*64},
        ]
        class Store:
            def __init__(self): self.sent=[]; self.deleted=[]
            def due(self, now=None, limit=100): return rows
            def mark_sent(self, rid, sent_at=None): self.sent.append((rid,sent_at))
            def delete_subscription_id(self, sid): self.deleted.append(sid)
        store=Store(); logs=[]
        with mock.patch.object(mod, "send_web_push", side_effect=[("sent",None),("gone",410),ReminderError("x")]):
            stats=mod.run_due({"base_path":""}, store, logger=lambda level,event,**fields: logs.append((level,event,fields)), now=123)
        self.assertEqual(stats, {"due":3,"sent":1,"gone":1,"failed":1})
        self.assertEqual(store.sent, [(1,123)])
        self.assertEqual(store.deleted, ["b"*64])
        self.assertEqual({x[1] for x in logs}, {"reminder_sent","reminder_subscription_gone","reminder_send_failed"})

    def test_internal_scheduler_lifecycle_and_loop(self):
        from renyyt import reminders as mod
        config={"reminders_run_times":"07:00,18:00","reminders_timezone":"UTC"}
        scheduler=mod.InternalReminderScheduler(config, object(), logger=lambda *a,**k: None)
        fake_thread=mock.Mock(); fake_thread.is_alive.return_value=False
        with mock.patch("renyyt.reminders.threading.Thread", return_value=fake_thread):
            scheduler.start(); fake_thread.start.assert_called_once()
            scheduler.start()
        scheduler._thread = mock.Mock()
        scheduler.stop(); scheduler._thread.join.assert_called_once()
        class StopNow:
            def is_set(self): return False
            def wait(self, delay): return True
        scheduler._stop=StopNow()
        with mock.patch.object(mod, "next_scheduler_run", return_value=datetime.now(timezone.utc)):
            scheduler._loop()
