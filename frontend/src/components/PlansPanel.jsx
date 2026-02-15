import { useState } from 'react'
import { ChevronRight, FileText, FolderOpen, PanelLeftClose } from 'lucide-react'
import { api } from '../lib/api'

function DisciplineNode({ disc, expanded, pages, onToggle, onPageClick, indent = 0 }) {
  const isOpen = expanded[disc.name]
  const hasChildren = disc.children && disc.children.length > 0

  return (
    <div>
      <button
        onClick={() => onToggle(disc.name, hasChildren)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-50 text-left"
        style={{ paddingLeft: `${12 + indent * 16}px` }}
      >
        <ChevronRight
          size={14}
          className={`shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
        />
        <FolderOpen size={14} className="shrink-0 text-cyan-600" />
        <span className="truncate font-medium">{disc.name}</span>
        <span className="ml-auto text-xs text-slate-400">{disc.page_count}</span>
      </button>
      {isOpen && hasChildren && disc.children.map(child => (
        <DisciplineNode
          key={child.name}
          disc={child}
          expanded={expanded}
          pages={pages}
          onToggle={onToggle}
          onPageClick={onPageClick}
          indent={indent + 1}
        />
      ))}
      {isOpen && !hasChildren && pages[disc.name] && (
        <div style={{ paddingLeft: `${20 + indent * 16}px` }}>
          {pages[disc.name].map(p => (
            <button
              key={p.page_name}
              onClick={() => onPageClick(p.page_name)}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-cyan-50 text-left rounded-r"
            >
              <FileText size={12} className="shrink-0 text-slate-400" />
              <span className="truncate">{p.page_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function PlansPanel({ disciplines, onPageClick, onCollapse }) {
  const [expanded, setExpanded] = useState({})
  const [pages, setPages] = useState({})

  const toggle = async (discName, hasChildren) => {
    const isOpen = expanded[discName]
    setExpanded(prev => ({ ...prev, [discName]: !isOpen }))
    if (!isOpen && !hasChildren && !pages[discName]) {
      try {
        const res = await api.listPages(discName)
        setPages(prev => ({ ...prev, [discName]: res.pages || [] }))
      } catch (e) {
        console.error(e)
      }
    }
  }

  return (
    <>
      <div className="px-4 py-3 border-b border-slate-200 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-bold">
            Maestro<span className="text-cyan-600">Super</span>
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">Plans</p>
        </div>
        {onCollapse && (
          <button onClick={onCollapse} className="p-1 hover:bg-slate-100 rounded mt-0.5" title="Collapse panel">
            <PanelLeftClose size={14} className="text-slate-400" />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        {disciplines.map(d => (
          <DisciplineNode
            key={d.name}
            disc={d}
            expanded={expanded}
            pages={pages}
            onToggle={toggle}
            onPageClick={onPageClick}
          />
        ))}
        {disciplines.length === 0 && (
          <p className="px-4 py-8 text-sm text-slate-400 text-center">No plans loaded</p>
        )}
      </div>
    </>
  )
}
