import { FileText, Clock, MessageSquare, Sparkles, ImageOff, LoaderCircle } from 'lucide-react'
import { api } from '../lib/api'
import { useState } from 'react'

function HighlightThumb({ workspaceSlug, pageName, highlight, onOpen }) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  const imageUrl = api.getWorkspaceHighlightUrl(workspaceSlug, highlight.id)

  return (
    <button
      onClick={(e) => {
        e.stopPropagation()
        onOpen({
          title: `${pageName} · Highlight ${highlight.id}`,
          imageUrl,
        })
      }}
      className="group shrink-0 w-28 h-20 rounded-lg overflow-hidden border border-slate-300 bg-slate-100 relative"
      title={highlight.mission || `Highlight ${highlight.id}`}
    >
      {!error ? (
        <>
          {!loaded && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
              <LoaderCircle size={16} className="animate-spin" />
            </div>
          )}
          <img
            src={imageUrl}
            alt={highlight.mission || `Highlight ${highlight.id}`}
            className={`w-full h-full object-cover transition ${loaded ? 'opacity-100 group-hover:scale-105' : 'opacity-0'}`}
            onLoad={() => setLoaded(true)}
            onError={() => setError(true)}
            loading="lazy"
          />
        </>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-slate-400">
          <ImageOff size={14} />
        </div>
      )}
    </button>
  )
}

function PageCard({ workspaceSlug, page, onPageClick, onHighlightClick, isHighlighting }) {
  const thumbUrl = api.getPageThumbUrl(page.page_name, 800)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  const highlights = Array.isArray(page.highlights) ? page.highlights : []

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
      <button
        onClick={() => onPageClick(page.page_name)}
        className="w-full text-left"
      >
        <div className="h-56 bg-slate-100 flex items-center justify-center overflow-hidden relative">
          {!error ? (
            <>
              {!loaded && <FileText size={32} className="text-slate-300 absolute" />}
              <img
                src={thumbUrl}
                alt={page.page_name}
                className={`w-full h-full object-cover ${loaded ? '' : 'opacity-0'}`}
                onLoad={() => setLoaded(true)}
                onError={() => setError(true)}
                loading="lazy"
              />
            </>
          ) : (
            <FileText size={32} className="text-slate-300" />
          )}
        </div>
      </button>

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

        <div className="mt-3 pt-3 border-t border-slate-200">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Highlights</p>
            <span className="text-[11px] text-slate-500">{highlights.length}</span>
          </div>

          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {highlights.map((highlight) => (
              <HighlightThumb
                key={highlight.id}
                workspaceSlug={workspaceSlug}
                pageName={page.page_name}
                highlight={highlight}
                onOpen={onHighlightClick}
              />
            ))}

            {isHighlighting && (
              <div className="shrink-0 w-28 h-20 rounded-lg border border-dashed border-amber-300 bg-amber-50 flex flex-col items-center justify-center text-amber-700">
                <LoaderCircle size={14} className="animate-spin" />
                <span className="text-[10px] mt-1">In progress</span>
              </div>
            )}

            {highlights.length === 0 && !isHighlighting && (
              <div className="text-xs text-slate-400 py-5">No highlights yet</div>
            )}
          </div>
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

export default function WorkspaceView({ workspace, onPageClick, onHighlightClick, highlightInProgress = {} }) {
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
              return (
                <PageCard
                  key={p.page_name}
                  workspaceSlug={meta.slug}
                  page={p}
                  onPageClick={onPageClick}
                  onHighlightClick={onHighlightClick}
                  isHighlighting={Boolean(progress)}
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
