from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from croni_remote.config import RemoteConfig
from croni_remote.policy import CallPolicy


class MutableClock:
    def __init__(self, value: datetime):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def config(path: Path, **overrides) -> RemoteConfig:
    values = dict(
        resource_url="https://call.example.test/mcp",
        auth_issuer_url="https://call.example.test",
        bearer_token="x" * 48,
        sip_callee="sip:yolie@example.test",
        host="127.0.0.1",
        port=8765,
        timezone=ZoneInfo("Asia/Shanghai"),
        quiet_start=(23, 0),
        quiet_end=(8, 0),
        daily_call_limit=2,
        minimum_retry_seconds=300,
        maximum_call_seconds=900,
        state_file=path,
        allowed_hosts=("call.example.test",),
        allowed_origins=("https://call.example.test",),
    )
    values.update(overrides)
    return RemoteConfig(**values)


class CallPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "policy.json"
        self.clock = MutableClock(datetime(2026, 10, 28, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")))
        self.policy = CallPolicy(config(self.path), self.clock)

    def tearDown(self):
        self.temp.cleanup()

    def test_quiet_hours_span_midnight(self):
        self.clock.value = self.clock.value.replace(hour=23, minute=30)
        self.assertFalse(self.policy.check_start().allowed)
        self.clock.value = (self.clock.value + timedelta(days=1)).replace(hour=7, minute=59)
        self.assertFalse(self.policy.check_start().allowed)
        self.clock.value = self.clock.value.replace(hour=8, minute=0)
        self.assertTrue(self.policy.check_start().allowed)

    def test_retry_interval(self):
        self.policy.record_attempt()
        decision = self.policy.check_start()
        self.assertFalse(decision.allowed)
        self.assertIn("retry interval", decision.reason)
        self.clock.value += timedelta(seconds=300)
        self.assertTrue(self.policy.check_start().allowed)

    def test_daily_limit(self):
        self.policy.record_attempt()
        self.policy.record_end()
        self.clock.value += timedelta(seconds=300)
        self.policy.record_attempt()
        self.policy.record_end()
        self.clock.value += timedelta(seconds=300)
        self.assertFalse(self.policy.check_start().allowed)

    def test_maximum_duration(self):
        self.policy.record_attempt()
        self.clock.value += timedelta(seconds=899)
        self.assertFalse(self.policy.maximum_duration_reached())
        self.clock.value += timedelta(seconds=1)
        self.assertTrue(self.policy.maximum_duration_reached())

    def test_state_file_is_private(self):
        self.policy.record_attempt()
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
