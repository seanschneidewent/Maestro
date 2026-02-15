import { useState, useEffect, useCallback } from 'react'
import { FolderOpen, Layers } from 'lucide-react'
import { api } from './lib/api'
import { useWebSocket } from './hooks/useWebSocket'
import PlansPanel from './components/PlansPanel'
import WorkspaceView from './components/WorkspaceView'
import WorkspaceSwitcher from './components/WorkspaceSwitcher'
import PlanViewerModal from './components/PlanViewerModal'

export default function App() {
  const [disciplines, setDisciplines] = useState([])
  const [workspaces, setWorkspaces] = useState([])
  const [activeWorkspace, setActiveWorkspace] = useState(null)
  const [workspaceDetail, setWorkspaceDetail] = useState(null)
  const [viewingAsset, setViewingAsset] = useState(null)
  const [highlightInProgress, setHighlightInProgress] = useState({})
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)

  // Load disciplines
  useEffect(() => {
    api.listDisciplines().then(d => setDisciplines(d.disciplines || [])).catch(console.error)
  }, [])

  // Load workspaces
  const loadWorkspaces = useCallback(() => {
    api.listWorkspaces().then(ws => {
      setWorkspaces(ws)
      setActiveWorkspace(current => current ?? (ws[0]?.slug ?? null))
      if (ws.length === 0) {
        setWorkspaceDetail(null)
      }
    }).catch(console.error)
  }, [])

  useEffect(() => { loadWorkspaces() }, [loadWorkspaces])

  // Load workspace detail when active changes
  useEffect(() => {
    if (!activeWorkspace) return
    api.getWorkspace(activeWorkspace).then(setWorkspaceDetail).catch(console.error)
  }, [activeWorkspace])

  // WebSocket for live updates
  useWebSocket({
    onWorkspace: (data) => {
      loadWorkspaces()

      const eventKey = `${data.workspace_slug}:${data.page_name || ''}`
      const hid = Number.isInteger(data.highlight_id) ? data.highlight_id : null
      if (data.action === 'page_highlight_started' && data.page_name) {
        setHighlightInProgress(prev => {
          const existing = Array.isArray(prev[eventKey]) ? prev[eventKey] : []
          const nextIds = hid == null || existing.includes(hid) ? existing : [...existing, hid]
          return { ...prev, [eventKey]: nextIds.length ? nextIds : existing }
        })
      }
      if ((data.action === 'page_highlight_complete' || data.action === 'page_highlight_failed' || data.action === 'highlight_removed') && data.page_name) {
        setHighlightInProgress(prev => {
          const existing = Array.isArray(prev[eventKey]) ? prev[eventKey] : []
          const next = { ...prev }
          if (hid == null) {
            delete next[eventKey]
            return next
          }
          const filtered = existing.filter(id => id !== hid)
          if (filtered.length === 0) {
            delete next[eventKey]
          } else {
            next[eventKey] = filtered
          }
          return next
        })
      }

      if (data.workspace_slug === activeWorkspace && activeWorkspace) {
        api.getWorkspace(activeWorkspace).then(setWorkspaceDetail).catch(console.error)
      }
    },
  })

  // Open page viewer
  const openPage = useCallback(async (pageName) => {
    try {
      const { image_url } = await api.getPageImage(pageName)
      setViewingAsset({ title: pageName, image_url })
    } catch (e) {
      console.error('Failed to load page image:', e)
    }
  }, [])

  return (
    <div className="h-screen flex bg-white text-slate-800 overflow-hidden">
      {/* Left panel */}
      <div
        className={`shrink-0 border-r border-slate-200 flex flex-col overflow-hidden transition-all duration-200 ${
          leftCollapsed ? 'w-12' : 'w-60'
        }`}
      >
        {leftCollapsed ? (
          <button
            onClick={() => setLeftCollapsed(false)}
            className="flex items-center justify-center py-4 hover:bg-slate-50"
            title="Expand plans"
          >
            <FolderOpen size={18} className="text-cyan-600" />
          </button>
        ) : (
          <PlansPanel
            disciplines={disciplines}
            onPageClick={openPage}
            onCollapse={() => setLeftCollapsed(true)}
          />
        )}
      </div>

      <div className="flex-1 overflow-hidden flex flex-col">
        <WorkspaceView
          workspace={activeWorkspace ? workspaceDetail : null}
          onPageClick={openPage}
          highlightInProgress={highlightInProgress}
        />
      </div>

      {/* Right panel */}
      <div
        className={`shrink-0 border-l border-slate-200 flex flex-col overflow-hidden transition-all duration-200 ${
          rightCollapsed ? 'w-12' : 'w-80'
        }`}
      >
        {rightCollapsed ? (
          <button
            onClick={() => setRightCollapsed(false)}
            className="flex items-center justify-center py-4 hover:bg-slate-50"
            title="Expand workspaces"
          >
            <Layers size={18} className="text-cyan-600" />
          </button>
        ) : (
          <WorkspaceSwitcher
            workspaces={workspaces}
            activeSlug={activeWorkspace}
            onSelect={setActiveWorkspace}
            onCreated={loadWorkspaces}
            onCollapse={() => setRightCollapsed(true)}
          />
        )}
      </div>

      {viewingAsset && (
        <PlanViewerModal
          title={viewingAsset.title}
          imageUrl={viewingAsset.image_url}
          onClose={() => setViewingAsset(null)}
        />
      )}
    </div>
  )
}
