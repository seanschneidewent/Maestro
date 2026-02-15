from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

MAESTRO_DIR = Path(__file__).resolve().parents[1]
if str(MAESTRO_DIR) not in sys.path:
    sys.path.insert(0, str(MAESTRO_DIR))

os.environ["DATABASE_URL"] = "sqlite://"

from maestro.db import session as db_session
from maestro.db import repository as repo
from maestro.db.models import Base
from maestro.db.session import engine
from maestro.tools import workspaces

# Shared in-memory SQLite across all sessions in this process
# (matches other test modules in this repo).
db_session.configure("sqlite:///file::memory:?cache=shared&uri=true")
db_session.init_db()


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        p = repo.get_or_create_project(f"CFA Love Field {uuid.uuid4().hex[:8]}", "/data/cfa")
        self.pid = p["id"]

        self.mock_project = {
            "pages": {
                "K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001": {},
                "K_201A_DETAIL_p001": {},
                "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001": {},
                "M103_FLOOR_PLAN_p001": {},
                "A111_Floor_Finish_Plan_p001": {},
            }
        }
        workspaces.init_workspaces(self.mock_project, self.pid)

    def tearDown(self) -> None:
        workspaces.init_workspaces(None, None)

    def test_create_workspace_idempotent_by_slug(self) -> None:
        first = workspaces.create_workspace("Walk-In Cooler Install", "Initial description")
        second = workspaces.create_workspace("Walk In Cooler Install", "New description")

        self.assertIsInstance(first, dict)
        self.assertIsInstance(second, dict)
        self.assertEqual(first["slug"], second["slug"])
        self.assertEqual(second["description"], "Initial description")

    def test_list_workspaces_returns_summary_fields(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001")

        payload = workspaces.list_workspaces()
        self.assertIsInstance(payload, dict)

        rows = payload["workspaces"]
        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertEqual(row["slug"], "walk_in_cooler_install")
        self.assertEqual(row["description"], "Equipment scope")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["page_count"], 1)
        self.assertTrue(row["updated"])

    def test_get_workspace_returns_metadata_pages_and_notes(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001")
        workspaces.add_note("walk_in_cooler_install", "Check slab depression", "A111")

        payload = workspaces.get_workspace("walk_in_cooler_install")
        self.assertIsInstance(payload, dict)
        self.assertIn("metadata", payload)
        self.assertIn("pages", payload)
        self.assertIn("notes", payload)
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(len(payload["notes"]), 1)

    def test_add_page_fuzzy_unique_match(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "K_211")

        self.assertIsInstance(result, dict)
        self.assertEqual(result["page_name"], "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001")

    def test_add_page_rejects_ambiguous_match(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "K_201")

        self.assertIsInstance(result, str)
        self.assertIn("ambiguous", result.lower())
        self.assertIn("K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001", result)
        self.assertIn("K_201A_DETAIL_p001", result)

    def test_add_page_rejects_unknown_page(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        result = workspaces.add_page("walk_in_cooler_install", "ZZ999")

        self.assertIsInstance(result, str)
        self.assertIn("not found", result.lower())

    def test_add_page_rejects_duplicate_page(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211")
        result = workspaces.add_page("walk_in_cooler_install", "K_211")

        self.assertIsInstance(result, str)
        self.assertIn("already in workspace", result.lower())

    def test_add_description_set_and_clear(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211")

        set_result = workspaces.add_description(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "Rough-in dimensions",
        )
        clear_result = workspaces.add_description(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "",
        )

        self.assertIsInstance(set_result, dict)
        self.assertEqual(set_result["description"], "Rough-in dimensions")
        self.assertIsInstance(clear_result, dict)
        self.assertEqual(clear_result["description"], "")

    def test_remove_page_updates_count_and_missing_page_errors(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "M103_FLOOR_PLAN_p001")

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

    def test_remove_highlight(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.add_page("walk_in_cooler_install", "K_211")

        added = repo.add_highlight(
            self.pid,
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            "Find rough-in",
        )
        self.assertIsInstance(added, dict)

        hid = added["highlight"]["id"]
        removed = workspaces.remove_highlight(
            "walk_in_cooler_install",
            "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
            hid,
        )
        self.assertIsInstance(removed, dict)
        self.assertTrue(removed["removed"])

    def test_add_page_requires_loaded_project(self) -> None:
        workspaces.create_workspace("Walk-In Cooler Install", "Equipment scope")
        workspaces.init_workspaces(None, self.pid)

        result = workspaces.add_page("walk_in_cooler_install", "K_211")
        self.assertIsInstance(result, str)
        self.assertIn("no project loaded", result.lower())


if __name__ == "__main__":
    unittest.main()
