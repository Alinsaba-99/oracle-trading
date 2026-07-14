import type { TradeModel } from '@/lib/types'
import { formatTime, formatDate, formatPct, formatRatio } from '@/lib/formats'

interface TradeDetailPanelProps {
  trade: TradeModel | null
  onClose: () => void
}

export function TradeDetailPanel({ trade, onClose }: TradeDetailPanelProps) {
  if (!trade) return null

  const rows: [string, string][] = [
    ['Time', `${formatDate(trade.time)} ${formatTime(trade.time)}`],
    ['Experiment ID', trade.experiment_id || '—'],
    ['Fold', trade.fold || '—'],
    ['Engine', trade.engine || '—'],
    ['Total Return', trade.total_return !== undefined ? formatPct(trade.total_return) : '—'],
    ['Sharpe Ratio', trade.sharpe_ratio !== undefined ? formatRatio(trade.sharpe_ratio) : '—'],
  ]

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Sheet */}
      <div className="fixed inset-y-0 right-0 w-full max-w-sm z-50 bg-card border-l border-border shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 h-14 border-b border-border">
          <h2 className="text-sm font-semibold">Trade Detail</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close trade detail"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-5 space-y-4">
          {rows.map(([label, value]) => (
            <div key={label}>
              <div className="text-xs text-muted-foreground mb-0.5">{label}</div>
              <div className="text-sm font-mono text-foreground">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
