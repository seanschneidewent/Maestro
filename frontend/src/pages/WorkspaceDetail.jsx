import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { on } from '../lib/websocket'

export default function WorkspaceDetail() {
  const { slug } = useParams()
  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('notes')

  const load = () => {
    api.getWorkspace(slug)
      .then(setWorkspace)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const unsub = on('workspace', (evt) => {
      if (evt.workspace_slug === slug) load()
    })
    return unsub
  }, [slug])

  if (loading) return <div className="p-4 text-maestro-500">Loading...</div>
  if (error) return <div className="p-4 text-danger">{error}</div>
  if (!workspace) return <div className="p-4 text-maestro-500">Workspace not found.</div>

  const { metadata, pages, notes } = workspace
  const tabs = [
    { id: 'notes', label: 'Findings', count: notes.length },
    { id: 'pages', label: 'Pages', count: pages.length },
  ]

  return (
    <div className="p-4">
      {/* Back */}
      <Link to="/app/workspaces" className="text-sm text-accent-dark font-medium">← All Workspaces</Link>

      {/* Header */}
      <div className="mt-3 mb-5">
        <h2 className="text-xl font-bold text-maestro-900">{metadata.title}</h2>
        <p className="text-sm text-maestro-500 mt-1">{metadata.description}</p>
        <div className="flex gap-3 mt-2 text-xs text-maestro-400">
          <span>{pages.length} pages</span>
          <span>{notes.length} findings</span>
          <span className={`px-2 py-0.5 rounded-full ${
            metadata.status === 'active' ? 'bg-success/10 text-success' : 'bg-maestro-100 text-maestro-500'
          }`}>{metadata.status}</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-maestro-100 rounded-xl p-1 mb-4">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === tab.id
                ? 'bg-white text-maestro-900 shadow-sm'
                : 'text-maestro-500 hover:text-maestro-700'
            }`}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'notes' && (
        <div className="space-y-3">
          {notes.length === 0 ? (
            <p className="text-sm text-maestro-400 text-center py-8">No findings yet. Maestro is still reviewing.</p>
          ) : (
            notes.map((note, i) => (
              <div key={i} className="bg-white rounded-xl p-4 shadow-sm border border-maestro-100">
                <p className="text-sm text-maestro-800 leading-relaxed">{note.text}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-maestro-400">
                  {note.source_page && (
                    <span className="bg-maestro-100 px-2 py-0.5 rounded">📄 {note.source_page}</span>
                  )}
                  <span>{new Date(note.added_at).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'pages' && (
        <div className="space-y-2">
          {pages.length === 0 ? (
            <p className="text-sm text-maestro-400 text-center py-8">No pages added yet.</p>
          ) : (
            pages.map((page, i) => (
              <div key={i} className="bg-white rounded-xl p-4 shadow-sm border border-maestro-100">
                <h4 className="font-medium text-maestro-900 text-sm">{page.page_name}</h4>
                <p className="text-xs text-maestro-500 mt-1">{page.reason}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-maestro-400">
                  <span>Added by {page.added_by}</span>
                  <span>{new Date(page.added_at).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
