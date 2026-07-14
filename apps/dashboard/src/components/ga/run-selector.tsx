import type { GARunSummary } from '@/lib/types'

interface RunSelectorProps {
  runs: GARunSummary[] | undefined
  selectedId: string | null
  loading: boolean
  onChange: (runId: string) => void
}

export function RunSelector({ runs, selectedId, loading, onChange }: RunSelectorProps) {
  if (loading && !runs) {
    return (
      <div className="h-9 w-64 animate-pulse rounded-md bg-muted" />
    )
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="h-9 w-64 rounded-md bg-card border border-border flex items-center px-3">
        <span className="text-sm text-muted-foreground">No GA runs found</span>
      </div>
    )
  }

  return (
    <select
      value={selectedId || ''}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border border-border bg-card px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
    >
      <option value="" disabled>
        Select a GA run…
      </option>
      {runs.map((r) => (
        <option key={r.run_id} value={r.run_id}>
          {r.run_id} · seed {r.seed} · {r.n_generations} gen · {r.signal_type} · pop {r.pop_size}
        </option>
      ))}
    </select>
  )
}
