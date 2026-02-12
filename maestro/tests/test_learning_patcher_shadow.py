from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

from learning import patcher


class LearningPatcherShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self._orig_repo_root = patcher.REPO_ROOT
        patcher.REPO_ROOT = self._tmp_path

        self.target_file = self._tmp_path / "maestro/identity/experience/patterns.json"
        self.target_file.parent.mkdir(parents=True, exist_ok=True)
        self.target_file.write_text(
            json.dumps({"cross_discipline": []}, indent=2),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        patcher.REPO_ROOT = self._orig_repo_root
        self._tmp.cleanup()

    def test_shadow_mode_records_old_value_without_writing(self) -> None:
        fake_patches = [
            {
                "patch_id": "p_001",
                "type": "experience",
                "target": "maestro/identity/experience/patterns.json",
                "operation": "append_unique",
                "path": "cross_discipline",
                "value": "detail sheets outrank schedules",
                "reason": "conflict resolution",
                "claim_id": "c_001",
            }
        ]

        with patch.object(patcher, "generate_patch_candidates", return_value=(fake_patches, [])):
            result = patcher.generate_and_apply_patches(
                job={"id": "job_001"},
                claims=[],
                verifications=[],
                scores=[],
                mode="shadow",
            )

        self.assertEqual(result["mode"], "shadow")
        self.assertEqual(len(result["proposed"]), 1)
        self.assertEqual(result["applied"], [])
        self.assertEqual(result["proposed"][0]["old_value"], [])

        payload = json.loads(self.target_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["cross_discipline"], [])


if __name__ == "__main__":
    unittest.main()
