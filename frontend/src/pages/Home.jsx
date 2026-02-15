import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { on } from '../lib/websocket'

export default function Home() {
  const [project, setProject] = useState(null)
  const [workspaces, setWorkspaces] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const [recentEvents, setRecentEvents] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.getProject().catch(() => null),
      api.listWorkspaces().catch(() => []),
      api.getUpcoming(7).catch(() => ({ events: [] })),
    ]).then(([proj, ws, up]) => {
      setProject(proj)
      setWorkspaces(Array.isArray(ws) ? ws : [])
      setUpcoming(up?.events || [])
    }).catch(err => setError(err.message))

    // Live updates
    const unsub = on('*', (event) => {
      setRecentEvents(prev => [event, ...prev].slice(0, 20))
    })
    return unsub
  }, [])

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-danger/10 text-danger rounded-xl p-4 text-sm">
          <p className="font-medium">Can't connect to Maestro</p>
          <p className="mt-1 text-danger/70">Make sure the server is running on localhost:8000</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-6">
      {/* Project header */}
      {project && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-maestro-100">
          <h2 className="text-lg font-semibold text-maestro-900">{project.name}</h2>
          <div className="flex gap-4 mt-2 text-sm text-maestro-500">
            <span>{project.page_count} pages</span>
            <span>{project.pointer_count} details</span>
            <span>{project.discipline_count} disciplines</span>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="w-2 h-2 bg-success rounded-full animate-pulse"></span>
            <span className="text-sm text-maestro-600">Engine: {project.engine}</span>
          </div>
        </div>
      )}

      {/* Active workspaces */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-maestro-700 uppercase tracking-wide">Active Workspaces</h3>
          <Link to="/app/workspaces" className="text-sm text-accent-dark font-medium">See all →</Link>
        </div>
        {workspaces.length === 0 ? (
          <p className="text-sm text-maestro-400">No workspaces yet. Maestro will create them as it reviews your plans.</p>
        ) : (
          <div className="space-y-2">
            {workspaces.slice(0, 5).map(ws => (
              <Link
                key={ws.slug}
                to={`/app/workspaces/${ws.slug}`}
                className="block bg-white rounded-xl p-4 shadow-sm border border-maestro-100 hover:border-accent/30 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-maestro-900">{ws.title}</h4>
                  <span className="text-xs text-maestro-400">{ws.page_count} pages</span>
                </div>
                {ws.description && (
                  <p className="text-sm text-maestro-500 mt-1 line-clamp-1">{ws.description}</p>
                )}
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Upcoming schedule */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-maestro-700 uppercase tracking-wide">Coming Up</h3>
          <Link to="/app/schedule" className="text-sm text-accent-dark font-medium">Full schedule →</Link>
        </div>
        {upcoming.length === 0 ? (
          <p className="text-sm text-maestro-400">Nothing on the schedule this week.</p>
        ) : (
          <div className="space-y-2">
            {upcoming.map(evt => (
              <div key={evt.id} className="bg-white rounded-xl p-4 shadow-sm border border-maestro-100">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-maestro-900">{evt.title}</h4>
                  <span className="text-xs bg-maestro-100 text-maestro-600 px-2 py-0.5 rounded-full">{evt.type}</span>
                </div>
                <p className="text-sm text-maestro-500 mt-1">{evt.start}{evt.end !== evt.start ? ` → ${evt.end}` : ''}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Live feed */}
      {recentEvents.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-maestro-700 uppercase tracking-wide mb-3">Live Activity</h3>
          <div className="space-y-1">
            {recentEvents.slice(0, 10).map((evt, i) => (
              <div key={i} className="text-sm text-maestro-600 bg-white rounded-lg px-3 py-2 border border-maestro-100">
                <span className="font-medium text-maestro-800">{evt.type}</span>
                {evt.content && <span className="ml-2 text-maestro-500">{evt.content.slice(0, 80)}</span>}
                {evt.reason && <span className="ml-2 text-maestro-500">{evt.reason.slice(0, 80)}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
