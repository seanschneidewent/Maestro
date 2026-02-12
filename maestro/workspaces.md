# Workspaces — Implementation Spec

## Vision

A workspace is a superintendent's curated lens on a scope concept. It's not a folder of plans. It's a living collection of page references, annotations, and notes — all focused on one specific thing the superintendent needs to build. Maestro and the superintendent iterate on the workspace together until it's a perfectly crisp and grounded spec space.

Workspaces like:
- "Walk-In Cooler Specs and Layouts"
- "RTU HVAC + Condensation Lines"
- "Structural Steel"
- "Refuse Enclosure Build"

Maestro uses its **existing knowledge tools** (list_pages, search_knowledge, get_sheet_index, get_region_detail) to reason through the knowledge store and decide what belongs. The workspace tools just manage the container. The intelligence is in Maestro, not in the workspace system.

---

## Data Model (On Disk)

### Folder Structure

```
Maestro/
  knowledge_store/                    # ingested plan data (existing, untouched)
    Chick-fil-A Love Field FSU.../
      pages/
        K_201_.../
        M103_.../
        ...

  workspaces/                         # NEW — all workspace data lives here
    workspaces.json                   # index of all workspaces
    walk_in_cooler_install/
      workspace.json                  # metadata
      pages.json                      # page references
      notes.json                      # observations and notes
      annotations/                    # vision highlights (future)
    rtu_hvac/
      workspace.json
      pages.json
      notes.json
      annotations/
    structural_steel/
      ...

  maestro python/
    tools/
      workspaces.py                   # workspace manager (NEW)
      tools_v13.py                    # existing tool registry
      vision.py                       # existing vision tools
```

### workspaces.json (Index)

Lives at `workspaces/workspaces.json`. Quick lookup of all workspaces without walking directories.

```json
{
  "workspaces": [
    {
      "slug": "walk_in_cooler_install",
      "title": "Walk-In Cooler Install",
      "page_count": 6,
      "created": "2026-02-11T21:30:00",
      "updated": "2026-02-11T21:45:00"
    },
    {
      "slug": "rtu_hvac",
      "title": "RTU HVAC + Condensation Lines",
      "page_count": 4,
      "created": "2026-02-12T09:00:00",
      "updated": "2026-02-12T09:15:00"
    }
  ]
}
```

### workspace.json (Metadata)

Lives at `workspaces/<slug>/workspace.json`. The identity of the workspace.

```json
{
  "title": "Walk-In Cooler Install",
  "slug": "walk_in_cooler_install",
  "description": "Equipment specs, rough-in dimensions, plumbing, mechanical, electrical requirements for walk-in cooler installation",
  "created": "2026-02-11T21:30:00",
  "updated": "2026-02-11T21:45:00",
  "status": "active"
}
```

Fields:
- **title**: Human-readable name, chosen by superintendent or Maestro
- **slug**: Folder name, derived from title (lowercase, underscores, no special chars)
- **description**: What this workspace covers — Maestro uses this to understand the scope
- **created/updated**: ISO timestamps
- **status**: "active" or "archived"

### pages.json (Page References)

Lives at `workspaces/<slug>/pages.json`. The curated lens — references to knowledge store pages, NOT copies of data.

```json
{
  "pages": [
    {
      "page_name": "K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001",
      "reason": "Shows cooler footprint and adjacent equipment layout",
      "added_by": "maestro",
      "added_at": "2026-02-11T21:30:00",
      "regions_of_interest": []
    },
    {
      "page_name": "K_211_ENLARGED_EQUIPMENT_FLOOR_PLAN_p001",
      "reason": "Enlarged plan with rough-in dimensions at cooler location",
      "added_by": "maestro",
      "added_at": "2026-02-11T21:30:00",
      "regions_of_interest": ["r_0.12_0.34_0.56_0.78"]
    },
    {
      "page_name": "A111_Floor_Finish_Plan_p001",
      "reason": "Slab depression and floor treatment at cooler location",
      "added_by": "superintendent",
      "added_at": "2026-02-11T21:35:00",
      "regions_of_interest": []
    }
  ]
}
```

Fields:
- **page_name**: Matches the folder name in knowledge_store/pages/. This is the link — no data duplication.
- **reason**: Why this page is in the workspace. Maestro writes this when it adds a page.
- **added_by**: "maestro" or "superintendent" — tracks who added it
- **added_at**: ISO timestamp
- **regions_of_interest**: Optional list of specific region IDs on this page that are relevant to the scope. Empty means the whole page is relevant.

### notes.json (Observations)

Lives at `workspaces/<slug>/notes.json`. Running log of observations from Maestro and the superintendent.

```json
{
  "notes": [
    {
      "text": "Cooler compressor is on a 30A/208V dedicated circuit out of Panel LP-1",
      "source": "maestro",
      "source_page": "E001_ELECTRICAL_SCHEDULES_DETAILS_p001",
      "added_at": "2026-02-11T21:32:00"
    },
    {
      "text": "Plumber is handling condensate, not HVAC — removed M103",
      "source": "superintendent",
      "source_page": null,
      "added_at": "2026-02-11T21:40:00"
    }
  ]
}
```

Fields:
- **text**: The observation or note
- **source**: "maestro" or "superintendent"
- **source_page**: Which page this observation came from (if applicable)
- **added_at**: ISO timestamp

---

## Tools

Six workspace tools exposed to the chat engine. These are MANAGEMENT operations — Maestro uses its existing knowledge tools (list_pages, search_knowledge, get_sheet_index, get_region_detail) to reason about WHAT to add.

### create_workspace(title, description)

Creates a new workspace.

- Generates slug from title (lowercase, spaces → underscores, strip special chars)
- Creates folder at `workspaces/<slug>/`
- Writes `workspace.json`, empty `pages.json`, empty `notes.json`
- Creates empty `annotations/` directory
- Updates `workspaces.json` index
- Returns: workspace metadata (slug, title, description, created)

### list_workspaces()

Returns all workspaces with summary info.

- Reads `workspaces.json`
- Returns: list of {slug, title, description, page_count, status, updated}

### get_workspace(workspace_slug)

Returns full workspace state.

- Reads workspace.json + pages.json + notes.json
- Returns: metadata + all pages with reasons + all notes

### add_page(workspace_slug, page_name, reason)

Adds a knowledge store page reference to the workspace.

- Validates page_name exists in knowledge store
- Checks for duplicates (don't add same page twice)
- Appends to pages.json with reason, added_by="maestro", timestamp
- Updates page_count in workspaces.json
- Updates workspace.json updated timestamp
- Returns: confirmation with page_name and reason

### remove_page(workspace_slug, page_name)

Removes a page from the workspace.

- Removes from pages.json
- Updates page_count in workspaces.json
- Updates workspace.json updated timestamp
- Returns: confirmation

### add_note(workspace_slug, note_text, source_page)

Adds an observation or note to the workspace.

- Appends to notes.json with source="maestro", timestamp
- source_page is optional (null if it's a general observation)
- Returns: confirmation

---

## Engine Integration

### Tool Registration

`workspaces.py` exports a `get_workspace_tools()` function that returns tool definitions in the same format as `tools_v13.py`. The engine files import and merge them:

```python
from tools.tools_v13 import get_tools, process_tool_call
from tools.workspaces import get_workspace_tools, process_workspace_tool_call

all_tools = get_tools() + get_workspace_tools()
```

Tool call routing checks workspace tools first (by name prefix or a simple name lookup), falls through to existing tools.

### System Prompt Addition

Add workspace awareness to Maestro's system prompt (in experience or the engine's prompt builder):

```
You can create and manage WORKSPACES — curated collections of plan pages focused on a specific scope of work. Use your existing knowledge tools to research what belongs, then use workspace tools to build and organize the workspace. The superintendent may ask you to create workspaces, add or remove pages, or just answer questions while referencing a workspace.
```

### Knowledge Store Path

`workspaces.py` needs the knowledge store path to validate page names. Pass it at initialization, same pattern as `tools_v13.py`:

```python
# workspaces.py
WORKSPACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workspaces")
KNOWLEDGE_STORE_DIR = None  # set by init_workspaces(knowledge_store_path)
```

---

## Workflow Examples

### Example 1: Superintendent Requests a Workspace

**Super:** I need to get my head around the walk-in cooler install. Can you build me a workspace for that?

**Maestro:** On it. Let me pull together what we've got on the walk-in cooler.

*→ calls list_pages() — sees 197 pages across all disciplines*
*→ calls search_knowledge("walk-in cooler") — finds hits in kitchen and MEP sheets*
*→ calls get_sheet_index("K_201") — equipment layout with cooler footprint*
*→ calls get_sheet_index("K_211") — enlarged plan with rough-in dimensions*
*→ calls get_sheet_index("K_611") — plumbing rough-in elevations*
*→ calls get_sheet_index("M103") — HVAC floor plan, condensate routing*
*→ calls get_region_detail("K_801", "r_0.12_0.05...") — equipment schedule, Kolpak specs*

*→ calls create_workspace("Walk-In Cooler Install", "Equipment specs, rough-in dimensions, plumbing, mechanical, electrical requirements for walk-in cooler")*
*→ calls add_page("walk_in_cooler_install", "K_201_OVERALL_EQUIPMENT_FLOOR_PLAN_p001", "Shows cooler footprint and adjacent equipment layout")*
*→ calls add_page(...K_211..., "Enlarged plan with rough-in dimensions at cooler location")*
*→ calls add_page(...K_611..., "Plumbing rough-in elevations for cooler drain connections")*
*→ calls add_page(...K_801..., "Equipment schedule — Kolpak model, dimensions, electrical requirements")*
*→ calls add_page(...M103..., "Mechanical plan showing condensate drain routing from compressor")*

**Maestro:** Built your workspace — "Walk-In Cooler Install." I pulled 5 sheets:

- **K-201** — Overall equipment plan, shows the cooler footprint next to the prep area
- **K-211** — Enlarged plan with your rough-in dimensions
- **K-611** — Plumbing rough-in elevations for the drain connections
- **K-801** — Equipment schedule, it's a Kolpak unit, 8'x10' walk-in
- **M-103** — Mechanical plan showing the condensate drain routing from the compressor

Want me to check the electrical side too? I saw a reference to the panel schedule that might have the cooler circuit.

**Super:** Yeah grab the electrical. And add the floor finish plan — I need to know about the slab depression.

*→ calls search_knowledge("panel schedule cooler circuit")*
*→ calls get_sheet_index("E001") — panel board schedule with cooler circuit*
*→ calls get_sheet_index("A111") — floor finish plan, cooler area floor treatment*
*→ calls add_page(...E001..., "Panel board schedule — cooler compressor circuit breaker and wire size")*
*→ calls add_page(...A111..., "Floor finish plan — slab depression and floor treatment at cooler location")*

**Maestro:** Done. Added the panel board schedule — your cooler compressor is on a 30A/208V dedicated circuit out of Panel LP-1. And A-111 shows a 4" slab depression at the cooler location with sealed concrete finish.

Your workspace is 7 sheets now. Anything else, or is that a solid starting point?

**Super:** That's good. Drop the mechanical plan actually — the plumber is handling the condensate, not my HVAC guy on this one.

*→ calls remove_page("walk_in_cooler_install", "M103_FLOOR_PLAN_p001")*
*→ calls add_note("walk_in_cooler_install", "Plumber is handling condensate, not HVAC — removed M103 per superintendent", null)*

**Maestro:** Dropped M-103. Workspace is 6 sheets, focused on kitchen equipment, plumbing, electrical, and architectural. Clean scope.

---

### Example 2: Maestro Answers a Question, Super Pins It

**Super:** What's the structural connection detail for the canopy columns?

**Maestro:** *(uses existing knowledge tools to research and answer)*

Let me check... The canopy columns connect to the footings with a 3/4" anchor bolt pattern — 4 bolts at 8" on center. Base plate is 12"x12"x3/4" welded to HSS 6x6x1/4 columns. Detail is on S4.1.

**Super:** Add that to a structural steel workspace.

*→ calls create_workspace("Structural Steel", "Steel connections, framing details, column-to-footing details, canopy structure")*
*→ calls add_page("structural_steel", "S4_1_Framing_Details_p001", "Canopy column base plate and anchor bolt connection detail")*
*→ calls add_note("structural_steel", "Canopy columns: HSS 6x6x1/4, base plate 12x12x3/4, 4x 3/4\" anchor bolts at 8\" OC", "S4_1_Framing_Details_p001")*

**Maestro:** Created "Structural Steel" workspace and added S4.1 with the connection detail. Want me to pull in the rest of the structural package?

---

### Example 3: Reviewing an Existing Workspace

**Super:** What's in my cooler workspace?

*→ calls get_workspace("walk_in_cooler_install")*

**Maestro:** Your "Walk-In Cooler Install" workspace has 6 sheets:

1. **K-201** — Overall equipment plan (cooler footprint)
2. **K-211** — Enlarged plan (rough-in dimensions)
3. **K-611** — Plumbing rough-in elevations (drain connections)
4. **K-801** — Equipment schedule (Kolpak 8'x10', specs)
5. **E-001** — Panel board schedule (30A/208V dedicated circuit, Panel LP-1)
6. **A-111** — Floor finish plan (4" slab depression, sealed concrete)

Notes:
- Cooler compressor on 30A/208V dedicated circuit out of Panel LP-1
- Plumber handling condensate, not HVAC

Anything you want to add or change?

---

## What's NOT In Scope (V1)

- **Vision annotations** — spawning Gemini agentic vision with targeted missions to produce highlighted images. This is the next evolution but requires its own spec.
- **Async learning integration** — learning agent watching workspace interactions. Coming but separate from workspace foundation.
- **Multi-project workspaces** — workspaces currently reference one knowledge store. Multi-project support comes when we have multiple ingested plan sets.
- **Workspace sharing/export** — generating PDFs or shareable links from workspaces.
- **Workspace templates** — pre-built workspace structures for common scopes (cooler, HVAC, steel). Could emerge naturally from Maestro's experience over time.

---

## Implementation Order

1. **workspaces.py** — the manager file with all 6 tools + JSON read/write helpers
2. **Tool registration** — wire workspace tools into the engine files (Gemini, Opus, GPT)
3. **System prompt update** — add workspace awareness to Maestro's experience
4. **Test** — interactive chat.py session, create a workspace, add/remove pages, verify on-disk output
5. **Commit** — push to GitHub

---

*Spec created: 2026-02-11*
