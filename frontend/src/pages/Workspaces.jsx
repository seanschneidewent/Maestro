import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { on } from '../lib/websocket'

export default function Workspaces() {
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    api.listWorkspaces()
      .then(data => setWorkspaces(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const unsub = on('workspace', load) // Refresh on workspace changes
    return unsub
  }, [])

  if (loading) return <div className="p-4 text-maestro-500">Loading workspaces...</div>

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold text-maestro-900 mb-4">Workspaces</h2>
      {workspaces.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm border border-maestro-100">
          <p className="text-maestro-500">No workspaces yet.</p>
          <p className="text-sm text-maestro-400 mt-1">Maestro creates workspaces as it reviews your plans.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workspaces.map(ws => (
            <Link
              key={ws.slug}
              to={`/app/workspaces/${ws.slug}`}
              className="block bg-white rounded-2xl p-5 shadow-sm border border-maestro-100 hover:border-accent/30 active:bg-maestro-50 transition-all"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-maestro-900">{ws.title}</h3>
                  {ws.description && (
                    <p className="text-sm text-maestro-500 mt-1 line-clamp-2">{ws.description}</p>
                  )}
                </div>
                <div className="ml-3 flex flex-col items-end gap-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    ws.status === 'active'
                      ? 'bg-success/10 text-success'
                      : 'bg-maestro-100 text-maestro-500'
                  }`}>
                    {ws.status}
                  </span>
                </div>
              </div>
              <div className="flex gap-4 mt-3 text-xs text-maestro-400">
                <span>{ws.page_count} pages</span>
                <span>Updated {new Date(ws.updated).toLocaleDateString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
