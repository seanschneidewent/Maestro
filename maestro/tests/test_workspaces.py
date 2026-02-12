from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

from tools import workspaces


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)

        self._orig_workspaces_dir = workspaces.WORKSPACES_DIR
        self._orig_index_path = workspaces.WORKSPACES_INDEX_PATH
        self._orig_project = getattr(workspaces, "_project")

        workspaces.WORKSPACES_DIR = self._tmp_path / "workspaces"
        workspaces.WORKSPACES_INDEX_PATH = workspaces.WORKSPACES_DIR / "workspaces.json"

        workspaces.init_workspaces(
            {
                "pages": {
                    "K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001": {},
                    "K_201A_DETAIL_p001": {},
                    "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001": {},
                    "M103_FLOOR_PLAN_p001": {},
                    "A111_Floor_Finish_Plan_p001": {},
                }
            }
        )

    def tearDown(self) -> None:
        workspaces.WORKSPACES_DIR = self._orig_workspaces_dir
        workspaces.WORKSPACES_INDEX_PATH = self._orig_index_path
        workspaces.init_workspaces(self._orig_project)
        self._tmp.cleanup()

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_create_workspace_initializes_files_and_index(self) -> None:
        result = workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["slug"], "walk_in_cooler_install")

        workspace_dir = workspaces.WORKSPACES_DIR / "walk_in_cooler_install"
        self.assertTrue((workspace_dir / "workspace.json").exists())
        self.assertTrue((workspace_dir / "pages.json").exists())
        self.assertTrue((workspace_dir / "notes.json").exists())
        self.assertTrue((workspace_dir / "annotations").is_dir())

        index = self._read_json(workspaces.WORKSPACES_INDEX_PATH)
        self.assertEqual(len(index["workspaces"]), 1)
        self.assertEqual(index["workspaces"][0]["slug"], "walk_in_cooler_install")
        self.assertEqual(index["workspaces"][0]["page_count"], 0)

    def test_create_workspace_idempotent_by_slug(self) -> None:
        first = workspaces.create_workspace("Walk-In Cooler Install", "Initial description")
        second = workspaces.create_workspace("Walk In Cooler Install", "New description")

        self.assertIsInstance(first, dict)
        self.assertIsInstance(second, dict)
        self.assertEqual(first["slug"], second["slug"])
        self.assertEqual(second["description"], "Initial description")

        index = self._read_json(workspaces.WORKSPACES_INDEX_PATH)
        self.assertEqual(len(index["workspaces"]), 1)

    def test_list_workspaces_returns_summary_fields(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "Rough-in dimensions",
        )

        rows = workspaces.list_workspaces()
        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertEqual(row["slug"], "walk_in_cooler_install")
        self.assertEqual(row["description"], "Equipment scope")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["page_count"], 1)
        self.assertTrue(row["updated"])

    def test_get_workspace_returns_metadata_pages_and_notes(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "Rough-in dimensions",
        )
        workspaces.add_note("walk_in_cooler_install", "Check slab depression", "A111")

        payload = workspaces.get_workspace("walk_in_cooler_install")
        self.assertIsInstance(payload, dict)
        self.assertIn("metadata", payload)
        self.assertIn("pages", payload)
        self.assertIn("notes", payload)
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(len(payload["notes"]), 1)

    def test_add_page_exact_match_updates_index_count(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "Rough-in dimensions",
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["page_name"], "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001")

        index = self._read_json(workspaces.WORKSPACES_INDEX_PATH)
        self.assertEqual(index["workspaces"][0]["page_count"], 1)

    def test_add_page_fuzzy_unique_match(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "K_211", "Rough-in dimensions")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["page_name"], "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001")

    def test_add_page_rejects_ambiguous_match(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "K_201", "Scope page")

        self.assertIsInstance(result, str)
        self.assertIn("ambiguous", result.lower())
        self.assertIn("K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001", result)
        self.assertIn("K_201A_DETAIL_p001", result)

    def test_add_page_rejects_unknown_page(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "ZZ999", "Scope page")

        self.assertIsInstance(result, str)
        self.assertIn("not found", result.lower())

    def test_add_page_rejects_duplicate_page(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211", "Initial add")
        result = workspaces.add_page("walk_in_cooler_install", "K_211", "Duplicate add")

        self.assertIsInstance(result, str)
        self.assertIn("already in workspace", result.lower())

    def test_remove_page_updates_count_and_missing_page_errors(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "M103_FLOOR_PLAN_p001", "Mechanical context")

        removed = workspaces.remove_page("walk_in_cooler_install", "M103")
        self.assertIsInstance(removed, dict)
        self.assertTrue(removed["removed"])
        self.assertEqual(removed["page_count"], 0)

        missing = workspaces.remove_page("walk_in_cooler_install", "M103")
        self.assertIsInstance(missing, str)
        self.assertIn("not in workspace", missing.lower())

    def test_add_note_with_and_without_source_page(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        first = workspaces.add_note("walk_in_cooler_install", "General observation")
        second = workspaces.add_note("walk_in_cooler_install", "Floor finish note", "A111")

        self.assertIsInstance(first, dict)
        self.assertIsInstance(second, dict)

        payload = workspaces.get_workspace("walk_in_cooler_install")
        self.assertEqual(len(payload["notes"]), 2)
        self.assertIsNone(payload["notes"][0]["source_page"])
        self.assertEqual(payload["notes"][1]["source_page"], "A111_Floor_Finish_Plan_p001")

    def test_add_page_requires_loaded_project(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.init_workspaces(None)

        result = workspaces.add_page("walk_in_cooler_install", "K_211", "Rough-in dimensions")
        self.assertIsInstance(result, str)
        self.assertIn("no project loaded", result.lower())

    def test_corrupt_and_missing_workspace_json_are_healed_on_write(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        paths = workspaces._workspace_paths("walk_in_cooler_install")

        paths["pages"].write_text("{broken json", encoding="utf-8")
        if paths["notes"].exists():
            paths["notes"].unlink()

        page_result = workspaces.add_page("walk_in_cooler_install", "K_211", "Rough-in dimensions")
        note_result = workspaces.add_note("walk_in_cooler_install", "Recovered note")

        self.assertIsInstance(page_result, dict)
        self.assertIsInstance(note_result, dict)

        healed_pages = self._read_json(paths["pages"])
        healed_notes = self._read_json(paths["notes"])
        self.assertEqual(len(healed_pages["pages"]), 1)
        self.assertEqual(len(healed_notes["notes"]), 1)


if __name__ == "__main__":
    unittest.main()
