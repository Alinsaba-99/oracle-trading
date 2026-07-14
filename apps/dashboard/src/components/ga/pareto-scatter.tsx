import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import type { ParetoIndividual } from '@/lib/types'
import { ChartSkeleton } from '@/components/ui/loading-skeleton'

interface ParetoScatterProps {
  individuals: ParetoIndividual[] | undefined
  loading: boolean
}

export function ParetoScatter({ individuals, loading }: ParetoScatterProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || !individuals?.length) return

    const sharpe = individuals.map((p) => p.sharpe)
    const sortino = individuals.map((p) => p.sortino)
    const calmar = individuals.map((p) => p.calmar)
    const maxdd = individuals.map((p) => p.max_drawdown)

    Plotly.newPlot(
      containerRef.current,
      [
        {
          x: sharpe,
          y: sortino,
          z: calmar,
          type: 'scatter3d',
          mode: 'markers',
          marker: {
            size: 12,
            color: maxdd,
            colorscale: 'Viridis',
            showscale: true,
            colorbar: { title: 'Max DD' },
            symbol: 'circle',
            line: { color: '#e4e4e7', width: 1 },
          },
          text: individuals.map(
            (p, i) =>
              `Individual ${i + 1}<br>` +
              `Sharpe: ${p.sharpe.toFixed(4)}<br>` +
              `Sortino: ${p.sortino.toFixed(4)}<br>` +
              `Calmar: ${p.calmar.toFixed(4)}<br>` +
              `MaxDD: ${(p.max_drawdown * 100).toFixed(2)}%`,
          ),
          hovertemplate: '%{text}<extra></extra>',
        },
      ],
      {
        height: 400,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#71717a', family: 'JetBrains Mono, monospace' },
        scene: {
          bgcolor: 'rgba(0,0,0,0)',
          xaxis: { title: 'Sharpe', gridcolor: '#232326' },
          yaxis: { title: 'Sortino', gridcolor: '#232326' },
          zaxis: { title: 'Calmar', gridcolor: '#232326' },
        },
        margin: { l: 10, r: 10, t: 10, b: 10 },
        hovermode: 'closest',
        dragmode: 'turntable',
      },
      { responsive: true, displayModeBar: false, displaylogo: false },
    )

    return () => {
      Plotly.purge(containerRef.current!)
    }
  }, [individuals])

  if (loading && !individuals) {
    return <ChartSkeleton height="h-[400px]" />
  }

  if (!individuals?.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 h-[400px] flex items-center justify-center text-muted-foreground text-sm">
        No Pareto individuals available
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-xs text-muted-foreground mb-1">Pareto Front (4D: Sharpe · Sortino · Calmar · MaxDD)</div>
      <div ref={containerRef} className="w-full" />
    </div>
  )
}
