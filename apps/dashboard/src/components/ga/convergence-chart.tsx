import { useEffect, useRef } from 'react'
import Plotly, { type PlotlyData } from 'plotly.js-dist-min'
import type { ConvergencePoint } from '@/lib/types'
import { ChartSkeleton } from '@/components/ui/loading-skeleton'

interface ConvergenceChartProps {
  points: ConvergencePoint[] | undefined
  loading: boolean
}

export function ConvergenceChart({ points, loading }: ConvergenceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !points?.length) return

    const gens = points.map((p) => p.generation)
    const best = points.map((p) => p.best_sharpe)
    const avg = points.map((p) => p.avg_sharpe)

    const traces: PlotlyData[] = [
      {
        x: gens,
        y: best,
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Best Sharpe',
        line: { color: '#22c55e', width: 2 },
        marker: { color: '#22c55e', size: 6 },
      },
    ]

    // avg_sharpe — only if data is non-zero or non-identical to best
    if (avg.some((v) => v !== best[0])) {
      traces.push({
        x: gens,
        y: avg,
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        name: 'Avg Sharpe',
        line: { color: '#3b82f6', width: 2, dash: 'dot' },
        marker: { color: '#3b82f6', size: 4 },
      })
    }

    Plotly.newPlot(
      containerRef.current,
      traces,
      {
        height: 320,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#71717a', family: 'JetBrains Mono, monospace' },
        xaxis: {
          title: 'Generation',
          gridcolor: '#232326',
          zeroline: false,
        },
        yaxis: {
          title: 'Sharpe',
          gridcolor: '#232326',
          zeroline: false,
        },
        margin: { l: 50, r: 20, t: 10, b: 50 },
        hovermode: 'x unified',
        showlegend: true,
        legend: { x: 0, y: 1, font: { color: '#e4e4e7' }, orientation: 'h' },
      },
      { responsive: true, displayModeBar: false, displaylogo: false },
    )

    return () => {
      Plotly.purge(containerRef.current!)
    }
  }, [points])

  if (loading && !points) {
    return <ChartSkeleton height="h-[320px]" />
  }

  if (!points?.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 h-[320px] flex items-center justify-center text-muted-foreground text-sm">
        No convergence data available
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-xs text-muted-foreground mb-1">Convergence</div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}
