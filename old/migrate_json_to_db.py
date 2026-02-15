# migrate_json_to_db.py — One-time migration of JSON data to SQLite
#
# Reads workspaces/, schedule.json, conversation.json and inserts into maestro.db
#
# Run: python scripts/migrate_json_to_db.py

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "maestro"))

from maestro.db.session import init_db
from maestro.db import repository as repo

WORKSPACES_DIR = ROOT / "workspaces"

def main():
    print("Initializing database...")
    init_db()

    # Create project
    project_name = "Chick-fil-A Love Field FSU"
    p = repo.get_or_create_project(project_name, str(ROOT / "knowledge_store"))
    pid = p["id"]
    print(f"Project: {project_name} (id: {pid})")

    # --- Migrate workspaces ---
    index_path = WORKSPACES_DIR / "workspaces.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        workspaces = index.get("workspaces", [])
        print(f"\nMigrating {len(workspaces)} workspaces...")

        for ws_entry in workspaces:
            slug = ws_entry["slug"]
            title = ws_entry["title"]
            ws_dir = WORKSPACES_DIR / slug

            # Read workspace metadata
            meta_path = ws_dir / "workspace.json"
            description = ""
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                description = meta.get("description", "")

            # Create workspace
            repo.create_workspace(pid, title, description, slug)
            print(f"  [{slug}] created")

            # Migrate pages
            pages_path = ws_dir / "pages.json"
            if pages_path.exists():
                pages_data = json.loads(pages_path.read_text(encoding="utf-8"))
                pages = pages_data.get("pages", [])
                for page in pages:
                    page_name = page.get("page_name", "")
                    reason = page.get("reason", "")
                    if page_name:
                        result = repo.add_page(pid, slug, page_name, reason or "Migrated from JSON")
                        if isinstance(result, dict):
                            pass  # success
                        # skip duplicates silently
                print(f"    {len(pages)} pages")

            # Migrate notes
            notes_path = ws_dir / "notes.json"
            if notes_path.exists():
                notes_data = json.loads(notes_path.read_text(encoding="utf-8"))
                notes = notes_data.get("notes", [])
                for note in notes:
                    text = note.get("text", "")
                    source_page = note.get("source_page")
                    if text:
                        repo.add_note(pid, slug, text, source_page=source_page)
                print(f"    {len(notes)} notes")

    # --- Migrate schedule ---
    schedule_path = WORKSPACES_DIR / "schedule.json"
    if schedule_path.exists():
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
        events = schedule.get("events", [])
        print(f"\nMigrating {len(events)} schedule events...")
        for evt in events:
            repo.add_event(
                pid,
                title=evt.get("title", ""),
                start=evt.get("start", ""),
                end=evt.get("end"),
                event_type=evt.get("type", "phase"),
                notes=evt.get("notes", ""),
            )
        print(f"  Done")
    else:
        print("\nNo schedule.json found")

    # --- Migrate conversation ---
    conv_path = WORKSPACES_DIR / "conversation.json"
    if conv_path.exists():
        conv = json.loads(conv_path.read_text(encoding="utf-8"))
        messages = conv.get("messages", [])
        summary = conv.get("summary", "")
        total_exchanges = conv.get("total_exchanges", 0)
        compactions = conv.get("compactions", 0)

        print(f"\nMigrating conversation ({len(messages)} messages)...")

        repo.get_or_create_conversation(pid)

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                repo.add_message(pid, role, content)
            elif isinstance(content, list):
                # Extract text from content blocks
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                if texts:
                    repo.add_message(pid, role, "\n".join(texts))

        if summary:
            repo.update_conversation_state(pid, summary=summary)

        # Set exchange count
        for _ in range(total_exchanges):
            repo.update_conversation_state(pid, increment_exchanges=True)
        for _ in range(compactions):
            repo.update_conversation_state(pid, increment_compactions=True)

        print(f"  Done")
    else:
        print("\nNo conversation.json found")

    # --- Summary ---
    print(f"\n{'='*50}")
    workspaces = repo.list_workspaces(pid)
    events = repo.list_events(pid)
    msg_count = repo.count_messages(pid)
    conv = repo.get_or_create_conversation(pid)
    print(f"  Project: {project_name}")
    print(f"  Workspaces: {len(workspaces)}")
    total_pages = sum(w.get('page_count', 0) for w in workspaces)
    print(f"  Total pages across workspaces: {total_pages}")
    print(f"  Schedule events: {len(events)}")
    print(f"  Messages: {msg_count}")
    print(f"  Exchanges: {conv['total_exchanges']}")
    print(f"{'='*50}")
    print(f"  Migration complete! DB at: {ROOT / 'maestro.db'}")


if __name__ == "__main__":
    main()
