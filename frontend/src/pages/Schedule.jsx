import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const TYPE_COLORS = {
  milestone: 'bg-accent/10 text-accent-dark',
  phase: 'bg-blue-50 text-blue-700',
  inspection: 'bg-purple-50 text-purple-700',
  delivery: 'bg-green-50 text-green-700',
  meeting: 'bg-maestro-100 text-maestro-600',
}

export default function Schedule() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listEvents()
      .then(data => setEvents(data?.events || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-4 text-maestro-500">Loading schedule...</div>

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold text-maestro-900 mb-4">Schedule</h2>
      {events.length === 0 ? (
        <div className="bg-white rounded-2xl p-8 text-center shadow-sm border border-maestro-100">
          <p className="text-maestro-500">No events on the schedule.</p>
          <p className="text-sm text-maestro-400 mt-1">Maestro will add events as it learns about your project timeline.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {events.map(evt => (
            <div key={evt.id} className="bg-white rounded-xl p-4 shadow-sm border border-maestro-100">
              <div className="flex items-start justify-between">
                <h3 className="font-medium text-maestro-900">{evt.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${TYPE_COLORS[evt.type] || TYPE_COLORS.meeting}`}>
                  {evt.type}
                </span>
              </div>
              <p className="text-sm text-maestro-600 mt-1">
                {evt.start}{evt.end !== evt.start ? ` → ${evt.end}` : ''}
              </p>
              {evt.notes && <p className="text-sm text-maestro-500 mt-2">{evt.notes}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
