# Frontend Polish — Alignment Doc

## Intent
Three improvements to the Maestro workspace frontend: discipline tree cleanup, workspace storytelling layout, and panel collapse buttons.

## Architecture Discovery

### Current State
- **Frontend:** Vite 7 + React 19 + Tailwind v4, three-panel layout in `App.jsx`
- **Left panel (w-60):** `PlansPanel.jsx` — fetches disciplines from `/api/knowledge/disciplines`, lazy-loads pages per discipline
- **Center:** `WorkspaceView.jsx` — 2-column grid of `PageCard` components, notes section below
- **Right panel (w-80):** `WorkspaceSwitcher.jsx` — workspace list/create/switch
- **API:** `maestro/api/routes.py` — `/api/knowledge/disciplines` returns raw discipline names from `project.json` index
- **Icons:** lucide-react already installed

### Discipline Problem
Gemini ingest assigned 37 disciplines with inconsistent casing and granularity:
- `Architectural` AND `architectural` (separate entries)
- `Structural` AND `structural`
- `Civil` AND `civil`
- `Traffic / Civil`, `Traffic / Electrical`, `Traffic Control`, `Traffic Signal` (should all be under Traffic/Civil)
- `Plumbing (MEP)`, `Plumbing` AND `plumbing`
- `Electrical`, `electrical`, `Electrical/Lighting`
- `Structural/Electrical`, `structural/architectural`
- `Canopy`, `Signage & Canopy`, `Specialties (Canopy)`
- `Foodservice Equipment`, `foodservice`
- `Kitchen`, `kitchen`
- etc.

Should collapse to ~10-12 clean groups.

### Old Maestro-Super Approach
`disciplineClassifier.ts` used file prefix patterns (A=Architectural, S=Structural, M/E/P=MEP, C=Civil, K=Kitchen, G=General, VC=Vapor Mitigation) and folder name regex. This worked well.

## Requirements

### R1: Server-Side Discipline Normalization
Add a normalization function in `routes.py` (or a small utility) that maps raw discipline strings to canonical groups.

**Canonical disciplines (display order):**
1. General
2. Architectural
3. Structural
4. Civil (includes Traffic Signal, Traffic Control, Traffic/Civil, Surveying)
5. MEP (header only — contains sub-disciplines)
   - Mechanical
   - Electrical (includes Electrical/Lighting)
   - Plumbing (includes Plumbing (MEP))
6. Kitchen (includes Foodservice, Foodservice Equipment, foodservice)
7. Landscape (includes Irrigation)
8. Vapor Mitigation (includes Environmental, Demolition when VC-prefixed)
9. Canopy (includes Signage & Canopy, Specialties (Canopy))

**Rules:**
- Case-insensitive matching
- Compound disciplines like `Structural/Electrical` → put in first named discipline
- `structural/architectural` → Structural
- Unknown → General

**Apply to both endpoints:**
- `/api/knowledge/disciplines` — return normalized groups with counts
- `/api/knowledge/pages?discipline=X` — filter by normalized discipline

### R2: Workspace Storytelling Layout
Convert the center panel from 2-column grid to single-column stacked cards, interleaving notes with pages.

**Layout changes:**
- Remove `grid grid-cols-2` — use single column, max-width ~640px, centered
- Each page card: full-width thumbnail (taller, ~200px), page name below, reason text
- Notes rendered INLINE between page cards based on their `source_page` field
  - Note about page X appears right after page X's card
  - Notes without a source_page go at the top as "general notes"
- Notes styled as subtle callout blocks (left cyan border, light bg)
- Overall feel: scrollable narrative, like reading a document/story

**Mobile-friendly:** Single column naturally works on mobile.

### R3: Panel Collapse Buttons
Add collapse/expand toggle to both side panels.

**Left panel:**
- Small button at top-right of panel header (or on the border)
- Collapsed: panel shrinks to ~48px showing just a folder icon
- Click to expand back to full w-60

**Right panel:**
- Same pattern, collapses to ~48px with a list icon
- Click to expand back to w-80

**Implementation:** State in App.jsx (`leftCollapsed`, `rightCollapsed`), conditional width classes, transition animation.

## Constraints
- Do NOT modify `knowledge/ingest.py`, `identity/soul.json`, `identity/tone.json`, or `knowledge/gemini_service.py`
- Only modify: `maestro/api/routes.py`, and files under `frontend/src/`
- Keep all existing API endpoints backward-compatible
- Use Tailwind v4 classes (already configured)
- Use lucide-react for icons (already installed)

## Implementation Order
1. **R1** — Discipline normalization in routes.py (backend change, makes the tree usable)
2. **R3** — Panel collapse (small, self-contained UI change)
3. **R2** — Workspace storytelling layout (biggest visual change, benefits from collapsed panels for testing)

## Environment
- Working dir: `C:\Users\Sean Schneidewent\Maestro`
- Frontend: `frontend/` (Vite, run with `npm run dev` on port 5173)
- Backend: `maestro/api/routes.py`
- Server entry: `server.py` (loads knowledge store into `_project` dict, passes to `init_api`)
- Knowledge store data: `knowledge_store/Chick-fil-A Love Field FSU 03904 -CPS/index.json` has the page→discipline mapping
- The `_project` dict in routes.py has `pages` where each page has a `discipline` string field

## File Paths
- `maestro/api/routes.py` — discipline normalization + endpoint changes
- `frontend/src/App.jsx` — panel collapse state, layout changes
- `frontend/src/components/PlansPanel.jsx` — may need UI tweaks for collapsed state
- `frontend/src/components/WorkspaceView.jsx` — storytelling layout rewrite
- `frontend/src/components/WorkspaceSwitcher.jsx` — may need collapsed state UI
