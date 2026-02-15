# Frontend Build — Alignment Document

## Intent
Build a clean, white-themed three-panel layout for Maestro's frontend. This is a **workspace viewer + plan browser**, NOT a chat app. The conversation with Maestro happens over iMessage. This frontend is the super's window into Maestro's brain.

## What To Build

### Layout: Three Panels
```
┌──────────────┬─────────────────────────────────┬──────────────────┐
│  Left Panel  │        Center Stage             │  Right Panel     │
│  (240px)     │        (flex-1)                 │  (320px)         │
│              │                                 │                  │
│  Plan Tree   │    Active Workspace View        │  Workspace       │
│  by disc.    │    - Page thumbnails w/ notes   │  Switcher        │
│              │    - Workspace notes             │                  │
│  Click page  │    - Click card → full PNG      │  List of all     │
│  → view PNG  │                                 │  workspaces      │
│              │                                 │  + create new    │
└──────────────┴─────────────────────────────────┴──────────────────┘
```

### Three Interactions:
1. **Left Panel — Plan File Tree**: Browse all pages grouped by discipline. Click a page → opens full PNG viewer overlay/modal.
2. **Center — Workspace View**: Shows the active workspace's pages as cards (with page PNG thumbnail, page name, notes, reason for inclusion). Also shows workspace-level notes from Maestro.
3. **Right Panel — Workspace Switcher**: List all workspaces, switch between them, create new ones.

### NO Chat. NO Conversation UI. NO Brain Toggle.

## Tech Stack (already scaffolded)
- React 19 + Vite 7 + Tailwind v4 (CSS-first, no tailwind.config.js)
- react-router-dom v7
- JSX (not TypeScript)
- Already has: `lib/api.js`, `lib/websocket.js`

## Backend API (already working on port 8000)

### REST Endpoints to use:
- `GET /api/knowledge/disciplines` → `{ disciplines: [{ name, page_count }] }`
- `GET /api/knowledge/pages?discipline=X` → `{ pages: [{ page_name, discipline, sheet_reflection, pointer_count, cross_references }] }`
- `GET /api/knowledge/pages/:page_name` → Full page detail with pointers
- `GET /api/workspaces` → `[{ slug, title, description, page_count, status, created, updated }]`
- `GET /api/workspaces/:slug` → `{ metadata: {...}, pages: [{ page_name, reason, added_by, added_at, regions_of_interest }], notes: [{ text, source, source_page, added_at }] }`
- `GET /api/project` → Project metadata

### WebSocket (ws://localhost:8000/ws):
Events to listen for:
- `workspace` — `{ action: "page_added"|"note_added"|"created", workspace_slug, detail }`
- `message` — new conversation message
- `finding` — Maestro found something

### Page Images:
Plan PNGs live at: `knowledge_store/<project_name>/pages/<page_dir>/page.png`

**IMPORTANT**: The backend does NOT currently serve static files for these. You MUST add a static file mount in `server.py`:
```python
from fastapi.staticfiles import StaticFiles
# After app is created, mount the knowledge store:
app.mount("/static/pages", StaticFiles(directory="knowledge_store"), name="pages")
```

Then images can be loaded at: `/static/pages/<project_name>/pages/<page_dir>/page.png`

BUT — we also need an API endpoint that maps page_name → image URL. Add this to routes.py:
```python
@api_router.get("/knowledge/pages/{page_name:path}/image")
async def get_page_image(page_name: str):
    """Return the image path for a knowledge store page."""
    if not _project:
        raise HTTPException(status_code=503, detail="No project loaded")
    page = _project.get("pages", {}).get(page_name)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{page_name}' not found")
    # page_name maps to a directory in knowledge_store/pages/
    # The image is at pages/<dir_name>/page.png
    # We need to find the directory name from the index
    return {"image_url": f"/static/pages/{page_name}/page.png"}
```

Actually — look at how the knowledge store is structured:
- `knowledge_store/<project>/pages/<page_dir>/page.png`
- The `page_dir` names are like `03904_RW_Project_Schedule_REV_8_13_25_p001`
- The `page_name` in the API is the display name like "A000 Egress Plan"

We need to map display names to directory names. The index.json has this mapping. Add an endpoint that returns the image URL given a page name.

## Files to Modify/Create

### Modify:
- `server.py` — Add StaticFiles mount for knowledge_store
- `maestro/api/routes.py` — Add page image endpoint
- `frontend/src/App.jsx` — Replace routing with single-page three-panel layout
- `frontend/src/lib/api.js` — Add knowledge/workspace endpoints

### Create (in `frontend/src/`):
- `components/PlansPanel.jsx` — Left panel: discipline tree with page list
- `components/WorkspaceView.jsx` — Center: active workspace content
- `components/WorkspacePageCard.jsx` — Individual page card in workspace
- `components/WorkspaceSwitcher.jsx` — Right panel: workspace list + create
- `components/PlanViewerModal.jsx` — Full-screen PNG viewer overlay
- `components/Layout.jsx` — Three-panel shell
- `hooks/useWebSocket.js` — Hook wrapping the websocket client

### Delete/Ignore:
- `pages/Auth.jsx`, `pages/Home.jsx`, `pages/Knowledge.jsx`, `pages/Schedule.jsx` — not needed
- `contexts/AuthContext.jsx`, `components/ProtectedRoute.jsx` — no auth for now

## Design

### Theme: White/Light
- Background: `bg-white` or `bg-slate-50`
- Borders: `border-slate-200`
- Text: `text-slate-800` primary, `text-slate-500` secondary
- Accent: cyan (`text-cyan-600`, `bg-cyan-50`, `border-cyan-500`)
- Cards: `bg-white border border-slate-200 rounded-xl shadow-sm`
- Hover: `hover:bg-slate-50`
- Selected states: `bg-cyan-50 border-l-2 border-cyan-500`

### Left Panel (PlansPanel)
- Header: "MaestroSuper" logo text (cyan accent on "Super" — like the old UI, but keeping simple for now, just "Plans")
- Collapsible discipline folders (ChevronRight rotates on expand)
- Page items with FileText icon
- Selected page gets cyan highlight
- Scrollable

### Center (WorkspaceView)
- Top bar: workspace title + description
- Grid of WorkspacePageCards (2 columns on desktop)
- Below cards: workspace notes list
- Empty state when no workspace selected

### Right Panel (WorkspaceSwitcher)  
- Header: "Workspaces"
- Create new workspace input + button
- List of workspace items (click to switch)
- Active workspace gets cyan highlight
- Bottom: current workspace stats

### PlanViewerModal
- Full screen overlay with dark backdrop
- PNG image with zoom/pan (can use CSS transform for MVP, no library needed)
- Close button (X) top right
- Page name header

## Constraints
- Do NOT touch `knowledge/ingest.py`
- Do NOT touch `identity/soul.json` or `identity/tone.json`
- Do NOT touch `knowledge/gemini_service.py`
- Keep it simple — this is an MVP viewer, not a full app
- Use lucide-react for icons (already in old codebase, need to add to package.json)
- No TypeScript — plain JSX
- Vite proxy config: add proxy for `/api` and `/ws` and `/static` to `localhost:8000`

## Vite Config
Update `vite.config.js` to proxy API calls:
```js
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/static': 'http://localhost:8000',
    }
  }
})
```

## Install
```bash
cd frontend
npm install lucide-react
```

## Success Criteria
1. Load the page → see three panels
2. Left panel loads disciplines + pages from `/api/knowledge/disciplines` and `/api/knowledge/pages`
3. Click a page → PNG viewer modal opens showing the plan image
4. Right panel loads workspaces from `/api/workspaces`
5. Click a workspace → center shows that workspace's pages and notes
6. WebSocket updates workspace view in real-time when Maestro adds a note/page
