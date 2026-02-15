import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

// Skip auth in dev mode — remove this for production
const DEV_BYPASS = import.meta.env.DEV

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (DEV_BYPASS) return children

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-maestro-50">
        <div className="text-maestro-500 text-lg">Loading...</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/auth" replace />
  }

  return children
}
