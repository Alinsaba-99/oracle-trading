import { useEffect, useRef } from 'react'
import { createChart, type IChartApi, type ISeriesApi, type LineData, type UTCTimestamp } from 'lightweight-charts'
import type { EquityCurve } from '@/lib/types'
import { ChartSkeleton } from '@/components/ui/loading-skeleton'

interface EquityChartProps {
  data: EquityCurve | null | undefined
  loading: boolean
}

export function EquityChart({ data, loading }: EquityChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#71717a',
      },
      grid: {
        vertLines: { color: '#232326' },
        horzLines: { color: '#232326' },
      },
      width: containerRef.current.clientWidth,
      height: 320,
      crosshair: {
        vertLine: { color: '#3b82f6', width: 1, style: 2 },
        horzLine: { color: '#3b82f6', width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: '#232326',
      },
      timeScale: {
        borderColor: '#232326',
        timeVisible: true,
      },
      handleScroll: false,
      handleScale: false,
    })

    const series = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })

    chartRef.current = chart
    seriesRef.current = series

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !data?.points?.length) return
    const lineData: LineData[] = data.points.map((p) => ({
      time: (new Date(p.date).getTime() / 1000) as UTCTimestamp,
      value: p.equity,
    }))
    seriesRef.current.setData(lineData)
    chartRef.current?.timeScale().fitContent()
  }, [data])

  if (loading) return <ChartSkeleton />

  if (!data?.points?.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 h-80 flex items-center justify-center text-muted-foreground text-sm">
        No equity data yet
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-xs text-muted-foreground mb-2">Equity Curve</div>
      <div ref={containerRef} />
    </div>
  )
}
