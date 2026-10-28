from pathlib import Path
import os
import tempfile
import unittest

from tools.test_phone import _load_env


class TestPhoneConfigTests(unittest.TestCase):
    def test_loads_plain_values_without_executing_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            config = Path(directory) / "voice.env"
            config.write_text(
                "VOICE_SIP_USER=croni\n"
                f"VOICE_SIP_PASS=$(touch {marker})\n"
                "export VOICE_DISPLAY_NAME='Croni'\n",
                encoding="utf-8",
            )
            old = {key: os.environ.get(key) for key in (
                "VOICE_SIP_USER", "VOICE_SIP_PASS", "VOICE_DISPLAY_NAME"
            )}
            for key in old:
                os.environ.pop(key, None)
            try:
                _load_env(config)
                self.assertEqual(os.environ["VOICE_SIP_USER"], "croni")
                self.assertEqual(os.environ["VOICE_SIP_PASS"], f"$(touch {marker})")
                self.assertEqual(os.environ["VOICE_DISPLAY_NAME"], "Croni")
                self.assertFalse(marker.exists())
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
