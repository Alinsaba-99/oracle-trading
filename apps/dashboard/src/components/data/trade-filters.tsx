import { useState } from 'react'
import type { TradeFilters as TF } from '@/hooks/use-trades'

interface TradeFiltersProps {
  filters: TF
  hasFilters: boolean
  onChange: (next: Partial<TF>) => void
  onClear: () => void
}

export function TradeFilters({ filters, hasFilters, onChange, onClear }: TradeFiltersProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-3 text-sm"
      >
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Filters
          {hasFilters && (
            <span className="w-2 h-2 rounded-full bg-accent" />
          )}
        </span>
        <svg className={`w-4 h-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">From</label>
            <input
              type="date"
              value={filters.from}
              onChange={(e) => onChange({ from: e.target.value })}
              className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">To</label>
            <input
              type="date"
              value={filters.to}
              onChange={(e) => onChange({ to: e.target.value })}
              className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Engine</label>
            <select
              value={filters.engine}
              onChange={(e) => onChange({ engine: e.target.value })}
              className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">All</option>
              <option value="walk_forward">Walk-Forward</option>
              <option value="vectorized">Vectorized</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Fold</label>
            <select
              value={filters.fold}
              onChange={(e) => onChange({ fold: e.target.value })}
              className="w-full px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
            <option value="">All</option>
              <option value="0">Fold 0</option>
              <option value="1">Fold 1</option>
              <option value="2">Fold 2</option>
              <option value="3">Fold 3</option>
              <option value="4">Fold 4</option>
              <option value="5">Fold 5</option>
              <option value="6">Fold 6</option>
              <option value="7">Fold 7</option>
              <option value="8">Fold 8</option>
              <option value="9">Fold 9</option>
            </select>
          </div>
          {hasFilters && (
            <div className="col-span-full flex justify-end">
              <button
                onClick={onClear}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
