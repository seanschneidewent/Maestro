import { useState, useEffect, useCallback } from 'react'
import { Layers, Plus, Loader2, CheckCircle2, PanelRightClose } from 'lucide-react'
import { api } from '../lib/api'
import { useWebSocket } from '../hooks/useWebSocket'

export default function WorkspaceSwitcher({ activeSlug, onSelect, onCollapse }) {
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const data = await api.listWorkspaces()
      setWorkspaces(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('Failed to load workspaces', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  // Refresh on workspace events
  useWebSocket('workspace', useCallback((data) => {
    if (data.action === 'created') load()
  }, [load]))

  return (
    <div className="w-80 border-l border-slate-200 bg-white flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {onCollapse && (
            <button onClick={onCollapse} className="p-1 hover:bg-slate-100 rounded" title="Collapse panel">
              <PanelRightClose size={14} className="text-slate-400" />
            </button>
          )}
          <Layers size={16} className="text-cyan-600" />
          <h2 className="text-sm font-semibold text-slate-800">Workspaces</h2>
        </div>
        <span className="text-xs text-slate-400">{workspaces.length}</span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={18} className="animate-spin text-slate-400" />
          </div>
        ) : workspaces.length === 0 ? (
          <div className="px-4 py-8 text-center text-slate-400">
            <Layers size={32} className="mx-auto mb-2 opacity-40" />
            <p className="text-xs">No workspaces yet</p>
            <p className="text-xs mt-1">Maestro creates these as it works</p>
          </div>
        ) : (
          workspaces.map(ws => {
            const isActive = ws.slug === activeSlug
            return (
              <button
                key={ws.slug}
                onClick={() => onSelect(ws.slug)}
                className={`w-full text-left px-4 py-3 transition-colors border-l-2 ${
                  isActive
                    ? 'bg-cyan-50 border-cyan-500'
                    : 'border-transparent hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium truncate ${isActive ? 'text-cyan-700' : 'text-slate-700'}`}>
                      {ws.title || ws.slug}
                    </p>
                    {ws.description && (
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{ws.description}</p>
                    )}
                    <div className="flex gap-3 mt-1 text-xs text-slate-400">
                      <span>{ws.page_count || 0} pages</span>
                      {ws.status && <span>{ws.status}</span>}
                    </div>
                  </div>
                  {isActive && <CheckCircle2 size={16} className="text-cyan-500 ml-2 mt-0.5 flex-shrink-0" />}
                </div>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
