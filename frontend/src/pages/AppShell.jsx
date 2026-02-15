import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useEffect } from 'react'
import { connect, disconnect } from '../lib/websocket'

const navItems = [
  { to: '/app', label: 'Home', icon: '⚡' },
  { to: '/app/workspaces', label: 'Workspaces', icon: '📋' },
  { to: '/app/schedule', label: 'Schedule', icon: '📅' },
  { to: '/app/knowledge', label: 'Plans', icon: '📐' },
]

export default function AppShell() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  // Connect WebSocket on mount
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [])

  const handleSignOut = async () => {
    await signOut()
    navigate('/auth')
  }

  return (
    <div className="min-h-screen bg-maestro-50 flex flex-col">
      {/* Top bar */}
      <header className="bg-white border-b border-maestro-200 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold text-maestro-900">Maestro</span>
          <span className="text-xs bg-accent/10 text-accent-dark px-2 py-0.5 rounded-full font-medium">LIVE</span>
        </div>
        <button
          onClick={handleSignOut}
          className="text-sm text-maestro-500 hover:text-maestro-700"
        >
          Sign out
        </button>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>

      {/* Bottom nav (mobile) */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-maestro-200 flex justify-around py-2 px-4 safe-bottom">
        {navItems.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/app'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                isActive
                  ? 'text-accent-dark bg-accent/10'
                  : 'text-maestro-500 hover:text-maestro-700'
              }`
            }
          >
            <span className="text-lg">{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
