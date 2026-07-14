import { useQuery } from '@tanstack/react-query'
import { request } from '@/lib/api'
import { POLLING_INTERVALS } from '@/lib/constants'
import type { PerformanceSummary } from '@/lib/types'

export function useSummary() {
  return useQuery<PerformanceSummary>({
    queryKey: ['performance-summary'],
    queryFn: () => request<PerformanceSummary>('/performance/summary'),
    refetchInterval: POLLING_INTERVALS.SUMMARY,
  })
}
