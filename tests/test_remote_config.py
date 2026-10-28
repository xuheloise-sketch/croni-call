from pathlib import Path
import unittest

from croni_remote.config import ConfigError, RemoteConfig


def valid_env() -> dict[str, str]:
    return {
        "CRONI_MCP_RESOURCE_URL": "https://call.example.test/mcp",
        "CRONI_MCP_BEARER_TOKEN": "x" * 48,
        "VOICE_SIP_CALLEE": "sip:yolie@example.test",
        "CRONI_POLICY_STATE_FILE": "/tmp/croni-policy-test.json",
    }


class RemoteConfigTests(unittest.TestCase):
    def test_valid_minimum_config(self):
        config = RemoteConfig.from_env(valid_env())
        self.assertEqual(config.sip_callee, "sip:yolie@example.test")
        self.assertEqual(config.port, 8765)
        self.assertEqual(config.state_file, Path("/tmp/croni-policy-test.json"))

    def test_plain_http_is_rejected(self):
        env = valid_env()
        env["CRONI_MCP_RESOURCE_URL"] = "http://call.example.test/mcp"
        with self.assertRaises(ConfigError):
            RemoteConfig.from_env(env)

    def test_short_token_is_rejected(self):
        env = valid_env()
        env["CRONI_MCP_BEARER_TOKEN"] = "short"
        with self.assertRaises(ConfigError):
            RemoteConfig.from_env(env)

    def test_arbitrary_non_sip_callee_is_rejected(self):
        env = valid_env()
        env["VOICE_SIP_CALLEE"] = "https://example.test/phone"
        with self.assertRaises(ConfigError):
            RemoteConfig.from_env(env)

    def test_partial_quiet_hours_are_rejected(self):
        env = valid_env()
        env["CRONI_QUIET_START"] = "22:00"
        env["CRONI_QUIET_END"] = ""
        with self.assertRaises(ConfigError):
            RemoteConfig.from_env(env)


if __name__ == "__main__":
    unittest.main()
