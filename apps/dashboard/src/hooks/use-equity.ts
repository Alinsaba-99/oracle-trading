import { useQuery } from '@tanstack/react-query'
import { request } from '@/lib/api'
import { POLLING_INTERVALS } from '@/lib/constants'
import type { EquityCurve } from '@/lib/types'

export function useEquity() {
  return useQuery<EquityCurve>({
    queryKey: ['performance-equity'],
    queryFn: () => request<EquityCurve>('/performance/equity'),
    refetchInterval: POLLING_INTERVALS.EQUITY,
  })
}
