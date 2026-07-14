import type { TradeModel, TradeList } from '@/lib/types'
import { formatTime, formatDate, formatPct, formatRatio } from '@/lib/formats'
import { TableSkeleton } from '@/components/ui/loading-skeleton'
import { EmptyState } from '@/components/ui/empty-state'

interface TradeTableProps {
  data: TradeList | undefined
  loading: boolean
  error: Error | null
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onSelectTrade: (trade: TradeModel) => void
}

export function TradeTable({
  data,
  loading,
  error,
  currentPage,
  totalPages,
  onPageChange,
  onSelectTrade,
}: TradeTableProps) {
  if (loading && !data) {
    return <TableSkeleton rows={8} />
  }

  if (error) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 flex flex-col items-center justify-center text-center">
        <span className="text-2xl mb-2 text-destructive">⚠</span>
        <p className="text-sm text-muted-foreground">{error.message}</p>
      </div>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        title="No trades found"
        description="Run a backtest or connect a broker to see trades here."
      />
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <Th>Time</Th>
              <Th>Experiment</Th>
              <Th>Fold</Th>
              <Th>Engine</Th>
              <Th className="text-right">Total Return</Th>
              <Th className="text-right">Sharpe</Th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((trade, i) => (
              <tr
                key={`${trade.time}-${i}`}
                onClick={() => onSelectTrade(trade)}
                className="border-b border-border last:border-0 hover:bg-accent/30 cursor-pointer transition-colors"
              >
                <Td>{formatShortDateTime(trade.time)}</Td>
                <Td className="font-mono text-xs">{trade.experiment_id || '—'}</Td>
                <Td><span className="font-mono text-xs">{trade.fold}</span></Td>
                <Td>{trade.engine}</Td>
                <Td className={`text-right font-mono ${trade.total_return >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {formatPct(trade.total_return)}
                </Td>
                <Td className="text-right font-mono">{formatRatio(trade.sharpe_ratio)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-border">
        <span className="text-xs text-muted-foreground">
          {data.total} total
        </span>
        <div className="flex items-center gap-1">
          <PageButton
            disabled={currentPage <= 1}
            onClick={() => onPageChange(currentPage - 1)}
          >
            ← Prev
          </PageButton>
          {renderPageNumbers(currentPage, totalPages, onPageChange)}
          <PageButton
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange(currentPage + 1)}
          >
            Next →
          </PageButton>
        </div>
      </div>
    </div>
  )
}

// ── Helpers ──

function Th({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={`px-4 py-2.5 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider ${className}`}>
      {children}
    </th>
  )
}

function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-2.5 text-sm text-foreground ${className}`}>{children}</td>
}

function PageButton({ disabled, onClick, children }: { disabled: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="px-2.5 py-1 text-xs rounded-md bg-accent text-accent-foreground hover:bg-accent/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  )
}

function renderPageNumbers(current: number, total: number, onChange: (p: number) => void) {
  const pages: (number | '...')[] = []
  const delta = 1

  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    if (current - delta > 2) pages.push('...')
    for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) {
      pages.push(i)
    }
    if (current + delta < total - 1) pages.push('...')
    pages.push(total)
  }

  return pages.map((p, i) =>
    p === '...' ? (
      <span key={`e-${i}`} className="px-1 text-xs text-muted-foreground">…</span>
    ) : (
      <button
        key={p}
        onClick={() => onChange(p)}
        className={`px-2 py-1 text-xs rounded-md transition-colors ${
          p === current
            ? 'bg-accent text-accent-foreground font-medium'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        {p}
      </button>
    ),
  )
}

function formatShortDateTime(iso: string): string {
  return `${formatDate(iso)} ${formatTime(iso)}`
}
