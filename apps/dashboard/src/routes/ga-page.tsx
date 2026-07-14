import { lazy, Suspense, useState } from 'react'
import { useGARuns, useGARunDetail } from '@/hooks/use-ga-runs'
import { PageShell } from '@/components/ui/page-shell'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { ErrorBanner } from '@/components/ui/error-banner'
import { EmptyState } from '@/components/ui/empty-state'
import { ChartSkeleton } from '@/components/ui/loading-skeleton'
import { RunSelector } from '@/components/ga/run-selector'
import { RunInfoCards } from '@/components/ga/run-info-cards'
import { BestParams } from '@/components/ga/best-params'

// Lazy-loaded Plotly components (~5MB)
const ParetoScatter = lazy(() =>
  import('@/components/ga/pareto-scatter').then((m) => ({ default: m.ParetoScatter })),
)
const ConvergenceChart = lazy(() =>
  import('@/components/ga/convergence-chart').then((m) => ({ default: m.ConvergenceChart })),
)

export default function GaPage() {
  const {
    data: runsData,
    isLoading: runsLoading,
    error: runsError,
    refetch: refetchRuns,
  } = useGARuns()
  const runs = runsData?.runs

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useGARunDetail(selectedRunId)

  // Auto-select first run when list loads
  const [hasAutoSelected, setHasAutoSelected] = useState(false)
  if (runs && runs.length > 0 && !selectedRunId && !hasAutoSelected) {
    setSelectedRunId(runs[0].run_id)
    setHasAutoSelected(true)
  }

  const chartLoading = detailLoading && !detail

  // Surface error: prefer detail error, fall back to runs error
  const errorMessage = runsError
    ? `Failed to load GA runs: ${runsError.message}`
    : detailError
      ? `Failed to load run detail: ${detailError.message}`
      : null

  const handleRetry = () => {
    refetchRuns()
    if (selectedRunId) refetchDetail()
  }

  return (
    <PageShell
      title="Genetic Algorithm"
      description="Risultati delle run di evoluzione genetica"
    >
      <ErrorBoundary>
        <ErrorBanner message={errorMessage} onRetry={handleRetry} />

        {/* Top bar: selector + info */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <RunSelector
            runs={runs}
            selectedId={selectedRunId}
            loading={runsLoading}
            onChange={setSelectedRunId}
          />
        </div>

        {!runs || runs.length === 0 ? (
          <EmptyState
            title="No GA runs found"
            description="Launch a GA run from CLI to see results here."
          />
        ) : (
          <>
            <RunInfoCards detail={detail} loading={detailLoading} />

            {/* Charts — lazy loaded */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Suspense fallback={<ChartSkeleton height="h-[400px]" />}>
                <ParetoScatter
                  individuals={detail?.pareto_front}
                  loading={chartLoading}
                />
              </Suspense>
              <Suspense fallback={<ChartSkeleton height="h-[320px]" />}>
                <ConvergenceChart
                  points={detail?.convergence}
                  loading={chartLoading}
                />
              </Suspense>
            </div>

            {/* Best params */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <BestParams
                best={detail?.pareto_front?.[0]}
                loading={detailLoading}
              />
            </div>
          </>
        )}
      </ErrorBoundary>
    </PageShell>
  )
}
