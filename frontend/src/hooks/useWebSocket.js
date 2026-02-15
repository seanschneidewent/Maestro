import { useEffect, useRef } from 'react'

export function useWebSocket({ onWorkspace, onMessage, onFinding } = {}) {
  const wsRef = useRef(null)
  const handlersRef = useRef({ onWorkspace, onMessage, onFinding })
  handlersRef.current = { onWorkspace, onMessage, onFinding }

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws`
    let ws
    let retryTimeout

    function connect() {
      ws = new WebSocket(url)
      wsRef.current = ws

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data)
          const h = handlersRef.current
          if (data.type === 'workspace' && h.onWorkspace) h.onWorkspace(data)
          if (data.type === 'message' && h.onMessage) h.onMessage(data)
          if (data.type === 'finding' && h.onFinding) h.onFinding(data)
        } catch {}
      }

      ws.onclose = () => {
        retryTimeout = setTimeout(connect, 3000)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      clearTimeout(retryTimeout)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  return wsRef
}
