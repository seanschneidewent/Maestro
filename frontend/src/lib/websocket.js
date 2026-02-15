// websocket.js — WebSocket client for real-time events
//
// Connects to Maestro's WebSocket and dispatches typed events.
// Auto-reconnects on disconnect.

const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws`

let socket = null
let reconnectTimer = null
const listeners = new Map() // type → Set<callback>

export function connect() {
  if (socket?.readyState === WebSocket.OPEN) return

  socket = new WebSocket(WS_URL)

  socket.onopen = () => {
    console.log('[WS] Connected')
    clearTimeout(reconnectTimer)
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const type = data.type
      // Dispatch to type-specific listeners
      const typeListeners = listeners.get(type)
      if (typeListeners) {
        typeListeners.forEach((cb) => cb(data))
      }
      // Dispatch to wildcard listeners
      const allListeners = listeners.get('*')
      if (allListeners) {
        allListeners.forEach((cb) => cb(data))
      }
    } catch (err) {
      console.warn('[WS] Parse error:', err)
    }
  }

  socket.onclose = () => {
    console.log('[WS] Disconnected, reconnecting in 3s...')
    reconnectTimer = setTimeout(connect, 3000)
  }

  socket.onerror = () => {
    socket?.close()
  }
}

export function disconnect() {
  clearTimeout(reconnectTimer)
  socket?.close()
  socket = null
}

export function on(type, callback) {
  if (!listeners.has(type)) listeners.set(type, new Set())
  listeners.get(type).add(callback)
  return () => listeners.get(type)?.delete(callback) // unsubscribe
}

export function onAny(callback) {
  return on('*', callback)
}
