import { useSummary } from '@/hooks/use-summary'
import { useEquity } from '@/hooks/use-equity'
import { useSSE } from '@/hooks/use-sse'
import { usePositionsStore } from '@/hooks/use-positions'
import { PageShell } from '@/components/ui/page-shell'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ErrorBanner } from '@/components/ui/error-banner'
import { MetricsGrid } from '@/components/data/metrics-grid'
import { EquityChart } from '@/components/charts/equity-chart'
import { DrawdownChart } from '@/components/charts/drawdown-chart'

export default function DashboardPage() {
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useSummary()
  const {
    data: equity,
    isLoading: equityLoading,
    error: equityError,
    refetch: refetchEquity,
  } = useEquity()

  // SSE for position updates — refetch positions on any event
  const refetchPositions = usePositionsStore((s) => s.fetch)
  useSSE('/api/v1/stream/positions', () => { refetchPositions() })

  // Surface the first meaningful error
  const errorMessage = summaryError
    ? `Failed to load performance data: ${summaryError.message}`
    : equityError
      ? `Failed to load equity data: ${equityError.message}`
      : null

  const showRetry = !!(summaryError || equityError)

  return (
    <PageShell
      title="Dashboard"
      description="Panoramica delle performance del sistema"
    >
      <ErrorBanner
        message={errorMessage}
        onRetry={showRetry ? () => { refetchSummary(); refetchEquity() } : undefined}
      />

      <ErrorBoundary>
        <MetricsGrid data={summary} loading={summaryLoading} />
      </ErrorBoundary>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ErrorBoundary>
          <EquityChart data={equity} loading={equityLoading} />
        </ErrorBoundary>
        <ErrorBoundary>
          <DrawdownChart data={equity} loading={equityLoading} />
        </ErrorBoundary>
      </div>
    </PageShell>
  )
}
