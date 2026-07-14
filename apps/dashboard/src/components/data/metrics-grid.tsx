import type { PerformanceSummary } from '@/lib/types'
import { formatPct, formatRatio } from '@/lib/formats'
import { MetricCardSkeleton } from '@/components/ui/loading-skeleton'

interface MetricsGridProps {
  data: PerformanceSummary | null | undefined
  loading: boolean
}

const metrics = [
  { key: 'sharpe', label: 'Sharpe', color: 'text-green-500' },
  { key: 'sortino', label: 'Sortino', color: 'text-green-500' },
  { key: 'profit_factor', label: 'Profit Factor', color: 'text-blue-500' },
  { key: 'max_drawdown', label: 'Max Drawdown', color: 'text-red-500' },
] as const

export function MetricsGrid({ data, loading }: MetricsGridProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m) => (
          <div key={m.key} className="rounded-lg border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">{m.label}</div>
            <div className="text-lg text-muted-foreground">—</div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m) => {
        const raw = data[m.key as keyof PerformanceSummary] as number
        const formatted = m.key === 'max_drawdown' ? formatPct(raw) : formatRatio(raw)
        return (
          <div key={m.key} className="rounded-lg border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">{m.label}</div>
            <div className={`text-lg font-mono font-semibold ${m.color}`}>
              {formatted}
            </div>
          </div>
        )
      })}
      {data.run_id && (
        <div className="col-span-full text-xs text-muted-foreground pt-1 border-t border-border">
          Run: {data.run_id}
          {data.run_seed !== undefined && ` · Seed: ${data.run_seed}`}
          {data.run_generations !== undefined && ` · Gen: ${data.run_generations}`}
        </div>
      )}
    </div>
  )
}
