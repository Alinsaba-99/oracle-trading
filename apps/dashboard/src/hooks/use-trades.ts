import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { request } from '@/lib/api'
import { POLLING_INTERVALS } from '@/lib/constants'
import type { TradeList } from '@/lib/types'

export interface TradeFilters {
  from: string
  to: string
  engine: string
  fold: string
}

const EMPTY_FILTERS: TradeFilters = { from: '', to: '', engine: '', fold: '' }

export function useTrades(pageSize = 20) {
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<TradeFilters>(EMPTY_FILTERS)

  const query = useQuery<TradeList>({
    queryKey: ['trades', offset, pageSize, filters],
    queryFn: () => {
      const params = new URLSearchParams()
      params.set('limit', String(pageSize))
      params.set('offset', String(offset))
      if (filters.from) params.set('from', filters.from)
      if (filters.to) params.set('to', filters.to)
      if (filters.engine) params.set('engine', filters.engine)
      if (filters.fold) params.set('fold', filters.fold)
      const qs = params.toString()
      return request<TradeList>(`/trades${qs ? `?${qs}` : ''}`)
    },
    refetchInterval: POLLING_INTERVALS.TRADES,
    placeholderData: (prev) => prev,
  })

  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / pageSize))
  const currentPage = Math.floor(offset / pageSize) + 1

  const goToPage = (page: number) => {
    setOffset(Math.max(0, (page - 1) * pageSize))
  }

  const resetPagination = () => setOffset(0)

  const updateFilters = (next: Partial<TradeFilters>) => {
    setFilters((prev) => ({ ...prev, ...next }))
    setOffset(0)
  }

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS)
    setOffset(0)
  }

  return {
    ...query,
    offset,
    pageSize,
    currentPage,
    totalPages,
    filters,
    hasFilters: filters.from !== '' || filters.to !== '' || filters.engine !== '' || filters.fold !== '',
    goToPage,
    resetPagination,
    updateFilters,
    clearFilters,
  }
}
