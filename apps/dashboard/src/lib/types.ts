/** API response types matching Pydantic models. */

export interface PerformanceSummary {
  sharpe: number
  sortino: number
  calmar: number
  max_drawdown: number
  profit_factor: number
  cagr: number
  total_return: number
  run_id?: string
  run_seed?: number
  run_generations?: number
}

export interface EquityPoint {
  date: string
  equity: number
  drawdown: number
}

export interface EquityCurve {
  points: EquityPoint[]
}

export interface TradeModel {
  time: string
  experiment_id?: string
  fold?: string
  engine?: string
  total_return: number
  sharpe_ratio: number
}

export interface TradeList {
  items: TradeModel[]
  total: number
  limit: number
  offset: number
}

export interface PositionModel {
  asset: string
  side: string
  qty: number
  entry_price: number
  current_price: number
  pnl: number
  pnl_pct: number
}

export interface GARunSummary {
  run_id: string
  seed: number
  n_generations: number
  n_islands: number
  pop_size: number
  signal_type: string
  timing_s: number
}

export interface ParetoIndividual {
  sharpe: number
  sortino: number
  calmar: number
  max_drawdown: number
  params: Record<string, number>
}

export interface ConvergencePoint {
  generation: number
  best_sharpe: number
  avg_sharpe: number
  best_sortino: number
  avg_sortino: number
  best_calmar: number
  avg_calmar: number
}

export interface GARunDetail {
  run_id: string
  seed: number
  n_generations: number
  n_islands: number
  pop_size: number
  signal_type: string
  status: string
  pareto_front: ParetoIndividual[]
  convergence: ConvergencePoint[]
}

export interface TodaySummary {
  trades: number
  wins: number
  losses: number
  profit_factor: number
  pnl: number
}
