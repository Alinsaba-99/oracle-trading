export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Panoramica delle performance del sistema
        </p>
      </div>

      {/* Metrics Grid — 4 skeleton cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {['Sharpe', 'Sortino', 'Profit Factor', 'Max Drawdown'].map((label) => (
          <div key={label} className="rounded-lg border border-border bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">{label}</div>
            <div className="h-8 w-20 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>

      {/* Charts placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 h-80 flex items-center justify-center text-muted-foreground text-sm">
          Equity Curve (TradingView)
        </div>
        <div className="rounded-lg border border-border bg-card p-4 h-80 flex items-center justify-center text-muted-foreground text-sm">
          Drawdown (Area Chart)
        </div>
      </div>
    </div>
  )
}
