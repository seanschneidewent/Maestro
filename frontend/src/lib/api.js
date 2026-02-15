// api.js — Maestro API client
//
// Wraps fetch with auth headers and base URL handling.
// In dev: Vite proxy sends /api to localhost:8000
// In prod: same origin or configured API_URL

const API_BASE = import.meta.env.VITE_API_URL || ''

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API error: ${res.status}`)
  }
  return res.json()
}

export const api = {
  // Project
  getProject: () => request('/api/project'),

  // Workspaces
  listWorkspaces: () => request('/api/workspaces'),
  getWorkspace: (slug) => request(`/api/workspaces/${slug}`),

  // Schedule
  listEvents: (params) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/schedule${qs ? '?' + qs : ''}`)
  },
  getUpcoming: (days = 7) => request(`/api/schedule/upcoming?days=${days}`),
  getEvent: (id) => request(`/api/schedule/${id}`),

  // Conversation
  getConversation: () => request('/api/conversation'),
  getMessages: (limit = 50, before) => {
    const params = new URLSearchParams({ limit })
    if (before) params.set('before', before)
    return request(`/api/conversation/messages?${params}`)
  },

  // Knowledge
  listDisciplines: () => request('/api/knowledge/disciplines'),
  listPages: (discipline) => {
    const qs = discipline ? `?discipline=${encodeURIComponent(discipline)}` : ''
    return request(`/api/knowledge/pages${qs}`)
  },
  getPage: (name) => request(`/api/knowledge/pages/${encodeURIComponent(name)}`),
  getPageImage: (name) => request(`/api/knowledge/page-image/${encodeURIComponent(name)}`),
  getPageThumbUrl: (name, w = 800) => `/api/knowledge/page-thumb/${encodeURIComponent(name)}?w=${w}`,
  search: (q) => request(`/api/knowledge/search?q=${encodeURIComponent(q)}`),

  // Health
  health: () => request('/api/health'),
}
