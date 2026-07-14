import type { GARunDetail } from '@/lib/types'
import { Skeleton } from '@/components/ui/loading-skeleton'

interface RunInfoCardsProps {
  detail: GARunDetail | undefined
  loading: boolean
}

export function RunInfoCards({ detail, loading }: RunInfoCardsProps) {
  if (loading && !detail) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border bg-card p-3 space-y-1.5">
            <Skeleton className="h-2.5 w-12" />
            <Skeleton className="h-5 w-16" />
          </div>
        ))}
      </div>
    )
  }

  if (!detail) {
    return null
  }

  const infoItems = [
    { label: 'Seed', value: detail.seed },
    { label: 'Generations', value: detail.n_generations },
    { label: 'Islands', value: detail.n_islands },
    { label: 'Population', value: detail.pop_size },
    { label: 'Signal Type', value: detail.signal_type },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {infoItems.map((item) => (
        <div key={item.label} className="rounded-lg border border-border bg-card p-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{item.label}</div>
          <div className="text-sm font-mono font-medium text-foreground mt-0.5">
            {String(item.value)}
          </div>
        </div>
      ))}
    </div>
  )
}
