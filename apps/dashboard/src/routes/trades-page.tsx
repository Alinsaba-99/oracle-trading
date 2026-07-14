import { useState } from 'react'
import { useTrades } from '@/hooks/use-trades'
import { PageShell } from '@/components/ui/page-shell'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { TradeFilters } from '@/components/data/trade-filters'
import { TradeTable } from '@/components/data/trade-table'
import { TradeDetailPanel } from '@/components/data/trade-detail-panel'
import { ExportCsvButton } from '@/components/data/export-csv-button'
import type { TradeModel } from '@/lib/types'

export default function TradesPage() {
  const {
    data,
    isLoading,
    error,
    currentPage,
    totalPages,
    filters,
    hasFilters,
    goToPage,
    updateFilters,
    clearFilters,
  } = useTrades(20)

  const [selectedTrade, setSelectedTrade] = useState<TradeModel | null>(null)

  return (
    <PageShell
      title="Trade Log"
      description="Cronologia completa degli ordini eseguiti"
    >
      <ErrorBoundary>
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <TradeFilters
              filters={filters}
              hasFilters={hasFilters}
              onChange={updateFilters}
              onClear={clearFilters}
            />
          </div>
          <ExportCsvButton />
        </div>
      </ErrorBoundary>

      <ErrorBoundary>
        <TradeTable
          data={data}
          loading={isLoading}
          error={error}
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={goToPage}
          onSelectTrade={setSelectedTrade}
        />
      </ErrorBoundary>

      <TradeDetailPanel
        trade={selectedTrade}
        onClose={() => setSelectedTrade(null)}
      />
    </PageShell>
  )
}
