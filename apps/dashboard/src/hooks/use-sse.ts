import { useCallback, useEffect, useRef, useState } from 'react'

interface SSEState {
  connected: boolean
  lastEvent: string | null
}

const MAX_RETRY_MS = 30_000
const INITIAL_RETRY_MS = 1_000

export function useSSE(
  url: string,
  onEvent?: (event: MessageEvent) => void,
): SSEState {
  const [connected, setConnected] = useState(false)
  const lastEventRef = useRef<string | null>(null)
  const retryMsRef = useRef(INITIAL_RETRY_MS)
  const onEventRef = useRef(onEvent)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  onEventRef.current = onEvent

  const connect = useCallback(() => {
    const es = new EventSource(url)

    es.onopen = () => {
      if (!mountedRef.current) {
        es.close()
        return
      }
      setConnected(true)
      retryMsRef.current = INITIAL_RETRY_MS
    }

    es.onerror = () => {
      setConnected(false)
      es.close()

      if (!mountedRef.current) return

      const delay = retryMsRef.current + Math.random() * 500
      retryMsRef.current = Math.min(retryMsRef.current * 2, MAX_RETRY_MS)
      timerRef.current = setTimeout(connect, delay)
    }

    es.onmessage = (e) => {
      lastEventRef.current = e.data
      onEventRef.current?.(e)
    }

    return es
  }, [url])

  useEffect(() => {
    mountedRef.current = true
    const es = connect()
    return () => {
      mountedRef.current = false
      es.close()
      setConnected(false)
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [connect])

  return { connected, lastEvent: lastEventRef.current }
}
