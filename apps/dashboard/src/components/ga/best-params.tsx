import type { ParetoIndividual } from '@/lib/types'

interface BestParamsProps {
  best: ParetoIndividual | undefined
  loading: boolean
}

export function BestParams({ best, loading }: BestParamsProps) {
  if (loading && !best) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 space-y-2">
        <div className="h-3 w-24 animate-pulse rounded bg-muted" />
        <div className="h-4 w-full animate-pulse rounded bg-muted" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
      </div>
    )
  }

  if (!best) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 flex items-center justify-center text-muted-foreground text-sm">
        No best individual available
      </div>
    )
  }

  const paramEntries = Object.entries(best.params || {})

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground mb-3">Best Individual — Parameters</div>

      {/* Mini metrics row */}
      <div className="grid grid-cols-4 gap-3 mb-4 pb-3 border-b border-border">
        <MiniMetric label="Sharpe" value={best.sharpe.toFixed(4)} />
        <MiniMetric label="Sortino" value={best.sortino.toFixed(4)} />
        <MiniMetric label="Calmar" value={best.calmar.toFixed(4)} />
        <MiniMetric label="Max DD" value={`${(best.max_drawdown * 100).toFixed(2)}%`} />
      </div>

      {/* Params table */}
      <div className="max-h-60 overflow-y-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-xs text-muted-foreground font-medium uppercase tracking-wider pb-1.5">Parameter</th>
              <th className="text-right text-xs text-muted-foreground font-medium uppercase tracking-wider pb-1.5">Value</th>
            </tr>
          </thead>
          <tbody>
            {paramEntries.map(([key, value]) => (
              <tr key={key} className="border-b border-border last:border-0">
                <td className="py-1 pr-4 font-mono text-xs text-foreground">{key}</td>
                <td className="py-1 text-right font-mono text-xs text-foreground">{value.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  const color =
    label === 'Max DD'
      ? parseFloat(value) < 0
        ? 'text-red-500'
        : 'text-green-500'
      : parseFloat(value) > 0
        ? 'text-green-500'
        : 'text-red-500'

  return (
    <div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={`text-sm font-mono font-semibold ${color}`}>{value}</div>
    </div>
  )
}
