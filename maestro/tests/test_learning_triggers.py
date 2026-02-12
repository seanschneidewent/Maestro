from __future__ import annotations

import sys
import unittest
from pathlib import Path

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

from learning import agent


class LearningTriggerTests(unittest.TestCase):
    def test_explicit_correction_detection_high_precision(self) -> None:
        self.assertTrue(agent.is_explicit_correction("that's wrong, use M904"))
        self.assertTrue(agent.is_explicit_correction("Correction: hood is at 66 AFF"))
        self.assertTrue(agent.is_explicit_correction("That is not correct."))

        self.assertFalse(agent.is_explicit_correction("can you double check this"))
        self.assertFalse(agent.is_explicit_correction("I think this might need more detail"))
        self.assertFalse(agent.is_explicit_correction("actually, continue with the same answer"))

    def test_mutating_workspace_slug_extraction(self) -> None:
        slug = agent.mutated_workspace_slug_from_tool_call(
            "add_page",
            {"workspace_slug": "walk_in_cooler_install"},
            {"workspace_slug": "walk_in_cooler_install", "page_name": "K_211"},
        )
        self.assertEqual(slug, "walk_in_cooler_install")

        slug_from_create = agent.mutated_workspace_slug_from_tool_call(
            "create_workspace",
            {"title": "Walk In Cooler Install"},
            {"slug": "walk_in_cooler_install"},
        )
        self.assertEqual(slug_from_create, "walk_in_cooler_install")

        no_slug = agent.mutated_workspace_slug_from_tool_call(
            "list_workspaces",
            {},
            [{"slug": "walk_in_cooler_install"}],
        )
        self.assertIsNone(no_slug)

    def test_extract_relevant_pages_from_tool_calls(self) -> None:
        tool_calls = [
            {"name": "get_region_detail", "args": {"page_name": "M904", "region_id": "r_001"}, "result": {"ok": True}},
            {"name": "add_note", "args": {"source_page": "A111"}, "result": {"workspace_slug": "walk_in"}},
            {"name": "add_page", "args": {"page_name": "K_211"}, "result": {"page_name": "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001"}},
        ]
        pages = agent.extract_relevant_pages(tool_calls)
        self.assertEqual(
            pages,
            ["A111", "K_211", "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001", "M904"],
        )


if __name__ == "__main__":
    unittest.main()
