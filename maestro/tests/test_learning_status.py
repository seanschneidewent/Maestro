from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

from learning import status


class LearningStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self._orig_status_path = status.STATUS_PATH
        status.STATUS_PATH = self._tmp_path / "learning_status.json"

    def tearDown(self) -> None:
        status.STATUS_PATH = self._orig_status_path
        self._tmp.cleanup()

    def test_write_read_and_clear_status(self) -> None:
        written = status.write_status(True, "testing status line", {"stage": "claims"})
        self.assertTrue(status.STATUS_PATH.exists())
        self.assertTrue(written["active"])
        self.assertEqual(written["message"], "testing status line")

        payload = status.read_status()
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["details"]["stage"], "claims")

        status.clear_status()
        self.assertFalse(status.STATUS_PATH.exists())
        self.assertIsNone(status.read_status())

    def test_atomic_write_overwrites_previous_payload(self) -> None:
        status.write_status(True, "first")
        first_text = status.STATUS_PATH.read_text(encoding="utf-8")
        self.assertIn("first", first_text)

        status.write_status(False, "second")
        second_text = status.STATUS_PATH.read_text(encoding="utf-8")
        self.assertIn("second", second_text)
        self.assertNotIn("first", second_text)


if __name__ == "__main__":
    unittest.main()
