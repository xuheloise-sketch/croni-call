import unittest

from croni_remote.service import CallGateway, GatewayError, MAX_SPOKEN_CHARACTERS


class FakePolicy:
    def __init__(self):
        self.active = False
        self.allowed = True
        self.reason = ""
        self.expired = False
        self.attempts = 0
        self.ends = 0

    def status(self):
        return {"active": self.active, "calls_today": self.attempts, "daily_limit": 3, "quiet_hours": True}

    def check_start(self):
        return type("Decision", (), {"allowed": self.allowed, "reason": self.reason})()

    def record_attempt(self):
        self.attempts += 1
        self.active = True

    def record_end(self):
        self.ends += 1
        self.active = False

    def maximum_duration_reached(self):
        return self.expired


class FakeWorker:
    def __init__(self):
        self.calls = []
        self.result = 'User replied: "hello"'
        self.error = None

    async def call(self, method, *args):
        self.calls.append((method, args))
        if self.error:
            raise self.error
        return self.result


class CallGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.policy = FakePolicy()
        self.worker = FakeWorker()
        self.gateway = CallGateway(self.policy, self.worker)

    async def test_start_records_attempt_and_uses_fixed_public_shape(self):
        result = await self.gateway.call_start("你好")
        self.assertTrue(result["ok"])
        self.assertTrue(self.policy.active)
        self.assertEqual(self.worker.calls, [("call_start", ("你好",))])

    async def test_policy_block_never_reaches_phone(self):
        self.policy.allowed = False
        self.policy.reason = "quiet hours are active"
        result = await self.gateway.call_start("你好")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.worker.calls, [])

    async def test_no_answer_closes_policy_state(self):
        self.worker.result = "[NO ANSWER] — the user did not pick up"
        result = await self.gateway.call_start("你好")
        self.assertEqual(result["status"], "completed")
        self.assertFalse(self.policy.active)

    async def test_engine_failure_is_sanitized_and_closes_state(self):
        self.worker.error = RuntimeError("sip:secret-user@example.test")
        with self.assertRaisesRegex(GatewayError, "phone engine could not complete"):
            await self.gateway.call_start("你好")
        self.assertFalse(self.policy.active)

    async def test_maximum_duration_ends_before_another_turn(self):
        self.policy.active = True
        self.policy.expired = True
        self.worker.result = "call ended"
        result = await self.gateway.converse("还在吗")
        self.assertEqual(result["status"], "ended")
        self.assertEqual(self.worker.calls, [("call_end", ("",))])
        self.assertFalse(self.policy.active)

    async def test_oversized_line_is_rejected(self):
        with self.assertRaisesRegex(GatewayError, "at most"):
            await self.gateway.call_start("x" * (MAX_SPOKEN_CHARACTERS + 1))
        self.assertEqual(self.worker.calls, [])


if __name__ == "__main__":
    unittest.main()
