import { useMemo, useState } from 'react'
import { FileText, Clock, MessageSquare, Sparkles, LoaderCircle, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'

const OVERLAY_COLORS = [
  'rgba(14, 165, 233, 0.25)',
  'rgba(34, 197, 94, 0.24)',
  'rgba(245, 158, 11, 0.24)',
  'rgba(239, 68, 68, 0.22)',
  'rgba(168, 85, 247, 0.22)',
  'rgba(20, 184, 166, 0.24)',
]

const OVERLAY_BORDERS = [
  'rgba(2, 132, 199, 0.95)',
  'rgba(21, 128, 61, 0.95)',
  'rgba(180, 83, 9, 0.95)',
  'rgba(185, 28, 28, 0.9)',
  'rgba(126, 34, 206, 0.9)',
  'rgba(15, 118, 110, 0.95)',
]

function PageCard({ page, onPageClick, pendingOverlayCount = 0 }) {
  const thumbUrl = api.getPageThumbUrl(page.page_name, 1000)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const [activeBoxKey, setActiveBoxKey] = useState(null)

  const highlights = useMemo(
    () => (Array.isArray(page.highlights) ? page.highlights : []),
    [page.highlights],
  )
  const pendingFromPayload = highlights.filter(h => (h.status || 'pending') === 'pending').length
  const failedCount = highlights.filter(h => h.status === 'failed').length
  const hasPending = pendingFromPayload > 0 || pendingOverlayCount > 0

  const overlayBoxes = useMemo(() => {
    const complete = highlights
      .filter(h => h.status === 'complete' && Array.isArray(h.bboxes) && h.bboxes.length > 0)
      .sort((a, b) => Number(a.id) - Number(b.id))

    return complete.flatMap((highlight, hIndex) => {
      const fill = OVERLAY_COLORS[hIndex % OVERLAY_COLORS.length]
      const border = OVERLAY_BORDERS[hIndex % OVERLAY_BORDERS.length]
      return highlight.bboxes
        .map((bbox, bIndex) => {
          const x = Number(bbox?.x)
          const y = Number(bbox?.y)
          const width = Number(bbox?.width)
          const height = Number(bbox?.height)
          if (![x, y, width, height].every(Number.isFinite)) return null
          if (width <= 0 || height <= 0) return null
          return {
            key: `${highlight.id}-${bIndex}`,
            mission: highlight.mission || `Highlight ${highlight.id}`,
            style: {
              left: `${Math.max(0, Math.min(1, x)) * 100}%`,
              top: `${Math.max(0, Math.min(1, y)) * 100}%`,
              width: `${Math.max(0, Math.min(1, width)) * 100}%`,
              height: `${Math.max(0, Math.min(1, height)) * 100}%`,
              backgroundColor: fill,
              borderColor: border,
            },
          }
        })
        .filter(Boolean)
    })
  }, [highlights])

  const activeMission = overlayBoxes.find(box => box.key === activeBoxKey)?.mission || null

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
      <div
        onClick={() => onPageClick(page.page_name)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onPageClick(page.page_name)
          }
        }}
        role="button"
        tabIndex={0}
        className="w-full text-left cursor-pointer"
      >
        <div className="relative bg-slate-100">
          {!error ? (
            <>
              {!loaded && (
                <div className="w-full min-h-44 flex items-center justify-center">
                  <FileText size={32} className="text-slate-300" />
                </div>
              )}
              <img
                src={thumbUrl}
                alt={page.page_name}
                className={`w-full h-auto block ${loaded ? '' : 'opacity-0'}`}
                onLoad={() => setLoaded(true)}
                onError={() => setError(true)}
                loading="lazy"
              />

              {loaded && overlayBoxes.length > 0 && (
                <div className="absolute inset-0 pointer-events-none">
                  {overlayBoxes.map((box) => (
                    <div
                      key={box.key}
                      className="absolute border-2 rounded-sm pointer-events-auto"
                      style={box.style}
                      onClick={(e) => {
                        e.stopPropagation()
                        setActiveBoxKey(prev => (prev === box.key ? null : box.key))
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          e.stopPropagation()
                          setActiveBoxKey(prev => (prev === box.key ? null : box.key))
                        }
                      }}
                      role="button"
                      tabIndex={0}
                      title={box.mission}
                    />
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="w-full min-h-44 flex items-center justify-center">
              <FileText size={32} className="text-slate-300" />
            </div>
          )}
        </div>
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-800">{page.page_name}</h3>
          <div className="inline-flex items-center gap-1 text-[11px] text-slate-500">
            <Clock size={10} />
            {page.added_at ? new Date(page.added_at).toLocaleDateString() : ''}
          </div>
        </div>

        {page.description ? (
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">{page.description}</p>
        ) : (
          <p className="text-xs text-slate-400 mt-2">No description yet.</p>
        )}

        <div className="mt-3 pt-3 border-t border-slate-200 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Highlights</p>
            <span className="text-[11px] text-slate-500">{highlights.length}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {overlayBoxes.length > 0 && (
              <span className="text-[11px] px-2 py-1 rounded-full bg-cyan-50 text-cyan-700 border border-cyan-200">
                {overlayBoxes.length} overlay box{overlayBoxes.length === 1 ? '' : 'es'}
              </span>
            )}

            {hasPending && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full border border-dashed border-amber-300 bg-amber-50 text-amber-700">
                <LoaderCircle size={12} className="animate-spin" />
                In progress
              </span>
            )}

            {failedCount > 0 && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full border border-rose-200 bg-rose-50 text-rose-700">
                <AlertCircle size={12} />
                {failedCount} failed
              </span>
            )}

            {highlights.length === 0 && !hasPending && (
              <span className="text-xs text-slate-400">No highlights yet</span>
            )}
          </div>

          {activeMission && (
            <div className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
              {activeMission}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function NoteCard({ note }) {
  return (
    <div className="border border-amber-200 bg-amber-50/60 rounded-xl px-4 py-3">
      <div className="flex items-start gap-2">
        <MessageSquare size={13} className="text-amber-600 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm text-slate-700 leading-relaxed">{note.text}</p>
          <p className="text-xs text-slate-500 mt-1.5">
            {note.source || 'maestro'}{note.source_page ? ` · ${note.source_page}` : ''}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function WorkspaceView({ workspace, onPageClick, highlightInProgress = {} }) {
  if (!workspace) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400 bg-gradient-to-br from-white to-slate-50">
        <div className="text-center">
          <FileText size={48} className="mx-auto mb-3 text-slate-300" />
          <p>Select a workspace to view</p>
        </div>
      </div>
    )
  }

  const meta = workspace.metadata || workspace
  const pages = workspace.pages || []
  const notes = workspace.notes || []

  return (
    <>
      <div className="px-6 py-4 border-b border-slate-200 bg-white/95 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">{meta.title || meta.slug}</h2>
            {meta.description && (
              <p className="text-sm text-slate-600 mt-1">{meta.description}</p>
            )}
          </div>
          <div className="text-right text-xs text-slate-500">
            <div>{pages.length} pages</div>
            <div>{notes.length} notes</div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-b from-slate-50 to-white">
        <div className="max-w-5xl mx-auto grid grid-cols-1 xl:grid-cols-[2fr_1fr] gap-6 items-start">
          <section className="space-y-4">
            {pages.map((p) => {
              const progress = highlightInProgress[`${meta.slug}:${p.page_name}`]
              const pendingOverlayCount = Array.isArray(progress) ? progress.length : 0
              return (
                <PageCard
                  key={p.page_name}
                  page={p}
                  onPageClick={onPageClick}
                  pendingOverlayCount={pendingOverlayCount}
                />
              )
            })}

            {pages.length === 0 && (
              <div className="text-center text-slate-400 py-12 bg-white rounded-xl border border-slate-200">
                <p>This workspace has no pages yet</p>
              </div>
            )}
          </section>

          <aside className="space-y-3 sticky top-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-amber-600" />
                <h3 className="text-sm font-semibold text-slate-800">Notes</h3>
              </div>
              {notes.length === 0 ? (
                <p className="text-xs text-slate-400">No notes yet.</p>
              ) : (
                <div className="space-y-2">
                  {notes.map((n, i) => (
                    <NoteCard key={`note-${i}`} note={n} />
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </>
  )
}
