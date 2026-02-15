import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function Knowledge() {
  const [disciplines, setDisciplines] = useState([])
  const [pages, setPages] = useState([])
  const [selectedDisc, setSelectedDisc] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.listDisciplines().catch(() => ({ disciplines: [] })),
      api.listPages().catch(() => ({ pages: [] })),
    ]).then(([disc, pg]) => {
      setDisciplines(disc?.disciplines || [])
      setPages(pg?.pages || [])
      setLoading(false)
    })
  }, [])

  const filterByDiscipline = (disc) => {
    setSelectedDisc(disc)
    setSearchResults(null)
    if (disc) {
      api.listPages(disc).then(data => setPages(data?.pages || []))
    } else {
      api.listPages().then(data => setPages(data?.pages || []))
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    api.search(searchQuery).then(setSearchResults)
  }

  if (loading) return <div className="p-4 text-maestro-500">Loading plans...</div>

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold text-maestro-900 mb-4">Plans</h2>

      {/* Search */}
      <form onSubmit={handleSearch} className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search plans..."
            className="flex-1 bg-white border border-maestro-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-accent"
          />
          <button
            type="submit"
            className="bg-accent text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-accent-dark transition-colors"
          >
            Search
          </button>
        </div>
      </form>

      {/* Search results */}
      {searchResults && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-maestro-700">
              {searchResults.count} results for "{searchResults.query}"
            </h3>
            <button onClick={() => setSearchResults(null)} className="text-xs text-accent-dark">Clear</button>
          </div>
          <div className="space-y-2">
            {searchResults.results.map((r, i) => (
              <div key={i} className="bg-white rounded-xl p-3 shadow-sm border border-maestro-100">
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-maestro-100 text-maestro-600 px-2 py-0.5 rounded">{r.type}</span>
                  <span className="text-sm font-medium text-maestro-900">{r.page_name}</span>
                  {r.region_id && <span className="text-xs text-maestro-400">→ {r.label || r.region_id}</span>}
                </div>
                <p className="text-xs text-maestro-500 mt-1 line-clamp-2">{r.match_context}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Discipline filter */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 -mx-4 px-4">
        <button
          onClick={() => filterByDiscipline(null)}
          className={`whitespace-nowrap text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
            !selectedDisc ? 'bg-maestro-900 text-white' : 'bg-maestro-100 text-maestro-600'
          }`}
        >
          All ({disciplines.reduce((sum, d) => sum + d.page_count, 0)})
        </button>
        {disciplines.map(d => (
          <button
            key={d.name}
            onClick={() => filterByDiscipline(d.name)}
            className={`whitespace-nowrap text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
              selectedDisc === d.name ? 'bg-maestro-900 text-white' : 'bg-maestro-100 text-maestro-600'
            }`}
          >
            {d.name} ({d.page_count})
          </button>
        ))}
      </div>

      {/* Pages list */}
      <div className="space-y-2">
        {pages.map(page => (
          <div key={page.page_name} className="bg-white rounded-xl p-4 shadow-sm border border-maestro-100">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-maestro-900 text-sm">{page.page_name}</h4>
                <p className="text-xs text-maestro-500 mt-1 line-clamp-2">{page.sheet_reflection}</p>
              </div>
              <span className="ml-2 text-xs text-maestro-400">{page.pointer_count} details</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
