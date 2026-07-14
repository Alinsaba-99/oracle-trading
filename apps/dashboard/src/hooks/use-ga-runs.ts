import { useQuery } from '@tanstack/react-query'
import { request } from '@/lib/api'
import { POLLING_INTERVALS } from '@/lib/constants'
import type { GARunDetail, GARunSummary } from '@/lib/types'

interface GARunsResponse {
  runs: GARunSummary[]
}

export function useGARuns() {
  return useQuery<GARunsResponse>({
    queryKey: ['ga-runs'],
    queryFn: () => request<GARunsResponse>('/ga/runs'),
    refetchInterval: POLLING_INTERVALS.GA_RUNS,
    select: (data) => ({
      // Deduplicate runs by run_id — the checkpoint scanner returns
      // duplicates when multiple dirs have the same run_id
      runs: data.runs.filter(
        (r, i, arr) => arr.findIndex((x) => x.run_id === r.run_id) === i,
      ),
    }),
  })
}

export function useGARunDetail(runId: string | null) {
  return useQuery<GARunDetail>({
    queryKey: ['ga-run-detail', runId],
    queryFn: () => request<GARunDetail>(`/ga/runs/${runId}`),
    enabled: !!runId,
  })
}
