import { FileText, StickyNote, Clock, MessageSquare } from 'lucide-react'
import { api } from '../lib/api'
import { useState } from 'react'

function PageCard({ page, onPageClick }) {
  const thumbUrl = api.getPageThumbUrl(page.page_name, 800)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  return (
    <div
      onClick={() => onPageClick(page.page_name)}
      className="bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer overflow-hidden"
    >
      <div className="h-52 bg-slate-100 flex items-center justify-center overflow-hidden relative">
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
      <div className="p-4">
        <h3 className="text-sm font-semibold">{page.page_name}</h3>
        {page.reason && (
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{page.reason}</p>
        )}
        <div className="flex items-center gap-2 mt-2.5 text-xs text-slate-400">
          <span>{page.added_by || 'maestro'}</span>
          {page.added_at && (
            <>
              <span>·</span>
              <Clock size={10} />
              <span>{new Date(page.added_at).toLocaleDateString()}</span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function NoteCard({ note }) {
  return (
    <div className="border-l-3 border-cyan-400 bg-cyan-50/50 rounded-r-lg px-4 py-3">
      <div className="flex items-start gap-2">
        <MessageSquare size={13} className="text-cyan-500 mt-0.5 shrink-0" />
        <div>
          <p className="text-sm text-slate-700 leading-relaxed">{note.text}</p>
          <p className="text-xs text-slate-400 mt-1.5">
            {note.source || 'maestro'}{note.source_page ? ` · ${note.source_page}` : ''}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function WorkspaceView({ workspace, onPageClick }) {
  if (!workspace) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
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

  // Build interleaved narrative: notes grouped by source_page
  const notesByPage = {}
  const generalNotes = []
  for (const n of notes) {
    if (n.source_page) {
      if (!notesByPage[n.source_page]) notesByPage[n.source_page] = []
      notesByPage[n.source_page].push(n)
    } else {
      generalNotes.push(n)
    }
  }

  return (
    <>
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200">
        <h2 className="text-xl font-bold">{meta.title || meta.slug}</h2>
        {meta.description && (
          <p className="text-sm text-slate-500 mt-1">{meta.description}</p>
        )}
        <div className="flex gap-4 mt-2 text-xs text-slate-400">
          <span>{pages.length} pages</span>
          <span>{notes.length} notes</span>
        </div>
      </div>

      {/* Storytelling content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-[640px] mx-auto space-y-4">
          {/* General notes at the top */}
          {generalNotes.map((n, i) => (
            <NoteCard key={`general-${i}`} note={n} />
          ))}

          {/* Interleaved pages + their notes */}
          {pages.map(p => (
            <div key={p.page_name} className="space-y-3">
              <PageCard page={p} onPageClick={onPageClick} />
              {notesByPage[p.page_name] && notesByPage[p.page_name].map((n, i) => (
                <NoteCard key={`${p.page_name}-note-${i}`} note={n} />
              ))}
            </div>
          ))}

          {pages.length === 0 && notes.length === 0 && (
            <div className="text-center text-slate-400 py-12">
              <p>This workspace is empty</p>
              <p className="text-xs mt-1">Maestro will add pages and notes as it reviews plans</p>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
