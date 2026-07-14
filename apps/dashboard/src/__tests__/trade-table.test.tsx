import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TradeTable } from '@/components/data/trade-table'
import type { TradeList } from '@/lib/types'

const mockData: TradeList = {
  items: [
    { time: '2026-07-12T12:34:56', experiment_id: 'abc12345', fold: '0', engine: 'walk_forward', total_return: 0.123, sharpe_ratio: 1.24 },
    { time: '2026-07-11T10:00:00', experiment_id: 'def67890', fold: '1', engine: 'vectorized', total_return: -0.042, sharpe_ratio: 0.89 },
  ],
  total: 100,
  limit: 20,
  offset: 0,
}

describe('TradeTable', () => {
  const onPageChange = vi.fn()
  const onSelectTrade = vi.fn()

  it('shows table skeleton when loading without data', () => {
    const { container } = render(
      <TradeTable
        data={undefined}
        loading={true}
        error={null}
        currentPage={1}
        totalPages={5}
        onPageChange={onPageChange}
        onSelectTrade={onSelectTrade}
      />,
    )
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThanOrEqual(5)
  })

  it('shows empty state when no items', () => {
    render(
      <TradeTable
        data={{ items: [], total: 0, limit: 20, offset: 0 }}
        loading={false}
        error={null}
        currentPage={1}
        totalPages={1}
        onPageChange={onPageChange}
        onSelectTrade={onSelectTrade}
      />,
    )
    expect(screen.getByText(/no trades found/i)).toBeInTheDocument()
  })

  it('renders trade rows and pagination', () => {
    render(
      <TradeTable
        data={mockData}
        loading={false}
        error={null}
        currentPage={1}
        totalPages={5}
        onPageChange={onPageChange}
        onSelectTrade={onSelectTrade}
      />,
    )
    expect(screen.getByText('abc12345')).toBeInTheDocument()
    expect(screen.getByText('def67890')).toBeInTheDocument()
    expect(screen.getByText('100 total')).toBeInTheDocument()
  })

  it('shows error state', () => {
    render(
      <TradeTable
        data={undefined}
        loading={false}
        error={new Error('Failed to fetch')}
        currentPage={1}
        totalPages={1}
        onPageChange={onPageChange}
        onSelectTrade={onSelectTrade}
      />,
    )
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument()
  })

  it('calls onSelectTrade when clicking a row', async () => {
    const user = userEvent.setup()
    render(
      <TradeTable
        data={mockData}
        loading={false}
        error={null}
        currentPage={1}
        totalPages={5}
        onPageChange={onPageChange}
        onSelectTrade={onSelectTrade}
      />,
    )
    await user.click(screen.getByText('abc12345'))
    expect(onSelectTrade).toHaveBeenCalledWith(mockData.items[0])
  })
})
