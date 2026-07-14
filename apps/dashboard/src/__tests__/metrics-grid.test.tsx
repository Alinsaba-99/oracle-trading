import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricsGrid } from '@/components/data/metrics-grid'

const mockData = {
  sharpe: 1.24,
  sortino: 0.89,
  profit_factor: 1.67,
  max_drawdown: 0.123,
  calmar: 0.0,
  cagr: 0.0,
  total_return: 0.0,
}

describe('MetricsGrid', () => {
  it('shows 4 skeleton cards when loading', () => {
    const { container } = render(<MetricsGrid data={undefined} loading={true} />)
    const skeletons = container.querySelectorAll('.animate-pulse')
    // 4 MetricCardSkeleton components, each with 2 animated elements (label + value)
    expect(skeletons.length).toBe(8)
  })

  it('shows 4 placeholder dashes when no data', () => {
    render(<MetricsGrid data={null} loading={false} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBe(4)
  })

  it('renders metric values when data provided', () => {
    render(<MetricsGrid data={mockData} loading={false} />)
    expect(screen.getByText('1.24')).toBeInTheDocument()
    expect(screen.getByText('0.89')).toBeInTheDocument()
    expect(screen.getByText('1.67')).toBeInTheDocument()
    // max_drawdown is formatted as percentage
    expect(screen.getByText('+12.3%')).toBeInTheDocument()
  })
})
