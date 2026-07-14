import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RunSelector } from '@/components/ga/run-selector'
import { BestParams } from '@/components/ga/best-params'
import type { GARunSummary } from '@/lib/types'

const mockRuns: GARunSummary[] = [
  { run_id: 'pb_seed42', seed: 42, n_generations: 20, n_islands: 1, pop_size: 12, signal_type: 'knn', timing_s: 120 },
  { run_id: 'legacy', seed: 123, n_generations: 60, n_islands: 2, pop_size: 30, signal_type: 'hybrid', timing_s: 0 },
]

describe('RunSelector', () => {
  const onChange = vi.fn()

  it('shows skeleton while loading without runs', () => {
    const { container } = render(
      <RunSelector runs={undefined} selectedId={null} loading={true} onChange={onChange} />,
    )
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows placeholder when no runs available', () => {
    render(
      <RunSelector runs={[]} selectedId={null} loading={false} onChange={onChange} />,
    )
    expect(screen.getByText(/no ga runs found/i)).toBeInTheDocument()
  })

  it('renders run options', () => {
    render(
      <RunSelector runs={mockRuns} selectedId="pb_seed42" loading={false} onChange={onChange} />,
    )
    expect(screen.getByText(/pb_seed42/)).toBeInTheDocument()
    expect(screen.getByText(/legacy/)).toBeInTheDocument()
  })

  it('calls onChange when selection changes', async () => {
    const user = userEvent.setup()
    render(
      <RunSelector runs={mockRuns} selectedId="pb_seed42" loading={false} onChange={onChange} />,
    )
    await user.selectOptions(screen.getByRole('combobox'), 'legacy')
    expect(onChange).toHaveBeenCalledWith('legacy')
  })
})

describe('BestParams', () => {
  const mockBest = {
    sharpe: 1.24,
    sortino: 0.89,
    calmar: 0.5,
    max_drawdown: 0.123,
    params: { knn_k: 8, threshold: 0.5 },
  }

  it('shows skeleton while loading', () => {
    const { container } = render(<BestParams best={undefined} loading={true} />)
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(<BestParams best={undefined} loading={false} />)
    expect(screen.getByText(/no best individual/i)).toBeInTheDocument()
  })

  it('renders metrics and param table', () => {
    render(<BestParams best={mockBest} loading={false} />)
    expect(screen.getByText('1.2400')).toBeInTheDocument()
    expect(screen.getByText('0.8900')).toBeInTheDocument()
    expect(screen.getByText('knn_k')).toBeInTheDocument()
    expect(screen.getByText('8.0000')).toBeInTheDocument()
    expect(screen.getByText('threshold')).toBeInTheDocument()
  })
})
