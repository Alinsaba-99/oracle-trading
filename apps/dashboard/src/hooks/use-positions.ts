import { useEffect } from 'react'
import { create } from 'zustand'
import { request } from '@/lib/api'
import type { PositionModel } from '@/lib/types'

interface PositionsStore {
  positions: PositionModel[]
  loading: boolean
  error: string | null
  fetch: () => Promise<void>
}

export const usePositionsStore = create<PositionsStore>((set) => ({
  positions: [],
  loading: false,
  error: null,
  fetch: async () => {
    set({ loading: true, error: null })
    try {
      const positions = await request<PositionModel[]>('/trades/positions')
      set({ positions, loading: false })
    } catch (e) {
      set({ error: (e as Error).message, loading: false })
    }
  },
}))

/** Poll positions every 30s and sync on SSE events. */
export function usePositions() {
  const store = usePositionsStore()

  useEffect(() => {
    store.fetch()
    const interval = setInterval(store.fetch, 30_000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return store
}
