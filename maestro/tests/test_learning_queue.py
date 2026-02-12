from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

from learning import queue


class LearningQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)

        self._orig_queue_dir = queue.LEARNING_QUEUE_DIR
        self._orig_pending = queue.PENDING_DIR
        self._orig_processing = queue.PROCESSING_DIR
        self._orig_done = queue.DONE_DIR
        self._orig_lock_path = queue.LOCK_PATH
        queue.release_worker_lock()

        queue.LEARNING_QUEUE_DIR = self._tmp_path / "learning_queue"
        queue.PENDING_DIR = queue.LEARNING_QUEUE_DIR / "pending"
        queue.PROCESSING_DIR = queue.LEARNING_QUEUE_DIR / "processing"
        queue.DONE_DIR = queue.LEARNING_QUEUE_DIR / "done"
        queue.LOCK_PATH = queue.LEARNING_QUEUE_DIR / "worker.lock"
        queue.ensure_learning_dirs()

    def tearDown(self) -> None:
        queue.release_worker_lock()
        queue.LEARNING_QUEUE_DIR = self._orig_queue_dir
        queue.PENDING_DIR = self._orig_pending
        queue.PROCESSING_DIR = self._orig_processing
        queue.DONE_DIR = self._orig_done
        queue.LOCK_PATH = self._orig_lock_path
        self._tmp.cleanup()

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_enqueue_claim_finalize_lifecycle(self) -> None:
        pending_path = queue.enqueue_workspace_entry(
            workspace_slug="walk_in_cooler_install",
            workspace_snapshot={"metadata": {"slug": "walk_in_cooler_install"}, "pages": [], "notes": []},
            user_message="build workspace",
            assistant_response="done",
            tool_calls=[{"name": "add_page"}],
            engine="opus",
        )
        self.assertTrue(pending_path.exists())
        self.assertEqual(pending_path.parent, queue.PENDING_DIR)

        claimed = queue.claim_next_job()
        self.assertIsNotNone(claimed)
        processing_path, payload = claimed  # type: ignore[misc]
        self.assertTrue(processing_path.exists())
        self.assertEqual(payload["status"], "processing")
        self.assertIn("processing_started_at", payload)

        done_path = queue.finalize_job(
            processing_path,
            payload,
            status="done",
            result={"claims": [], "missions": [], "scores": []},
            errors=[],
        )
        self.assertTrue(done_path.exists())
        final_payload = self._read_json(done_path)
        self.assertEqual(final_payload["status"], "done")
        self.assertIn("processing_finished_at", final_payload)
        self.assertEqual(final_payload["claims"], [])

    def test_recover_processing_to_pending(self) -> None:
        sample = {"id": "sample_job", "status": "processing"}
        processing_path = queue.PROCESSING_DIR / "sample_job.json"
        processing_path.write_text(json.dumps(sample), encoding="utf-8")

        recovered = queue.recover_processing_to_pending()
        self.assertEqual(recovered, 1)
        self.assertFalse(processing_path.exists())
        self.assertTrue((queue.PENDING_DIR / "sample_job.json").exists())

    def test_worker_lock_exclusive(self) -> None:
        first = queue.acquire_worker_lock()
        self.assertTrue(first)

        held_fd = queue._LOCK_FD
        queue._LOCK_FD = None
        second = queue.acquire_worker_lock()
        self.assertFalse(second)
        queue._LOCK_FD = held_fd

        queue.release_worker_lock()
        self.assertFalse(queue.LOCK_PATH.exists())
        third = queue.acquire_worker_lock()
        self.assertTrue(third)


if __name__ == "__main__":
    unittest.main()
