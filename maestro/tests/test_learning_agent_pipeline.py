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

from learning import agent, queue


class LearningAgentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)

        self._orig_queue_dir = queue.LEARNING_QUEUE_DIR
        self._orig_pending = queue.PENDING_DIR
        self._orig_processing = queue.PROCESSING_DIR
        self._orig_done = queue.DONE_DIR
        self._orig_lock_path = queue.LOCK_PATH
        self._orig_log_path = agent.LEARNING_LOG_PATH

        queue.release_worker_lock()
        queue.LEARNING_QUEUE_DIR = self._tmp_path / "learning_queue"
        queue.PENDING_DIR = queue.LEARNING_QUEUE_DIR / "pending"
        queue.PROCESSING_DIR = queue.LEARNING_QUEUE_DIR / "processing"
        queue.DONE_DIR = queue.LEARNING_QUEUE_DIR / "done"
        queue.LOCK_PATH = queue.LEARNING_QUEUE_DIR / "worker.lock"
        queue.ensure_learning_dirs()

        agent.LEARNING_LOG_PATH = self._tmp_path / "learning_log.json"

    def tearDown(self) -> None:
        queue.release_worker_lock()
        queue.LEARNING_QUEUE_DIR = self._orig_queue_dir
        queue.PENDING_DIR = self._orig_pending
        queue.PROCESSING_DIR = self._orig_processing
        queue.DONE_DIR = self._orig_done
        queue.LOCK_PATH = self._orig_lock_path
        agent.LEARNING_LOG_PATH = self._orig_log_path
        self._tmp.cleanup()

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_pipeline_writes_done_payload_with_stage_outputs(self) -> None:
        pending_path = queue.enqueue_workspace_entry(
            workspace_slug="walk_in_cooler_install",
            workspace_snapshot={"metadata": {"slug": "walk_in_cooler_install"}, "pages": [], "notes": []},
            user_message="build workspace",
            assistant_response="workspace built",
            tool_calls=[],
            engine="opus",
        )
        self.assertTrue(pending_path.exists())
        claimed = queue.claim_next_job()
        self.assertIsNotNone(claimed)
        processing_path, payload = claimed  # type: ignore[misc]

        fake_claims = [
            {
                "claim_id": "c_001",
                "text": "Hood at 64 AFF",
                "source_page": "M904",
                "claim_type": "dimensional",
                "verification_priority": "high",
                "source_anchor": "note 1",
            }
        ]
        fake_missions = [
            {
                "mission_id": "m_001",
                "claim_ids": ["c_001"],
                "target_page": "M904",
                "instruction": "verify hood height",
                "expected_values": {"c_001": "64 AFF"},
            }
        ]
        fake_verification = {
            "mission_id": "m_001",
            "claim_ids": ["c_001"],
            "target_page": "M904",
            "verification_status": "ok",
            "findings": "64 AFF confirmed",
            "trace_path": str(self._tmp_path / "trace.json"),
        }
        fake_scores = [
            {
                "claim_id": "c_001",
                "score": "verified",
                "vision_found": "64 AFF confirmed",
                "confidence": "high",
                "rationale": "matched exactly",
                "action_taken": None,
            }
        ]
        fake_patch_result = {
            "mode": "shadow",
            "proposed": [{"patch_id": "p_001"}],
            "applied": [],
            "errors": [],
        }

        with (
            patch.object(agent.claims, "extract_claims", return_value=(fake_claims, [])),
            patch.object(agent.missions, "build_missions", return_value=(fake_missions, [])),
            patch.object(agent.missions, "verify_mission", return_value=fake_verification),
            patch.object(agent.scorer, "score_claims", return_value=(fake_scores, [])),
            patch.object(agent.patcher, "generate_and_apply_patches", return_value=fake_patch_result),
            patch.object(agent, "load_project", return_value={"pages": {}}),
        ):
            agent._process_claimed_job(processing_path, payload)

        done_files = list(queue.DONE_DIR.glob("*.json"))
        self.assertEqual(len(done_files), 1)
        done_payload = self._read_json(done_files[0])

        self.assertEqual(done_payload["status"], "done")
        self.assertIn("processing_started_at", done_payload)
        self.assertIn("processing_finished_at", done_payload)
        self.assertEqual(done_payload["claims"], fake_claims)
        self.assertEqual(done_payload["mission_plan"], fake_missions)
        self.assertEqual(done_payload["missions"], [fake_verification])
        self.assertEqual(done_payload["scores"], fake_scores)
        self.assertEqual(done_payload["patches_proposed"], [{"patch_id": "p_001"}])
        self.assertEqual(done_payload["patches_applied"], [])
        self.assertEqual(done_payload["errors"], [])

        log = self._read_json(agent.LEARNING_LOG_PATH)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["job_id"], done_payload["id"])


if __name__ == "__main__":
    unittest.main()
