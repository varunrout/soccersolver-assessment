export interface PlayerSummary {
  player_id: string
  name: string
  position: 'GK' | 'DEF' | 'MID' | 'FWD'
  club: string
  league: string
  market_value_eur: number
}

export interface PlayerDetail extends PlayerSummary {
  age: number
  goals: number
  assists: number
  minutes_played: number
  shots: number
  passes: number
  xg: number
  xa: number
}

export interface PlayerPercentiles {
  player_id: string
  /** Percentile rank 0–100 per per-90 metric within position+league peer group. null when peer group < 5. */
  metrics: Record<string, number | null>
}

export interface PlayerDetailWithPercentiles extends PlayerDetail {
  percentiles: PlayerPercentiles | null
}

export interface RankedPlayer {
  rank: number
  player_id: string
  name: string
  club: string
  league: string
  position: string
  metric_value: number
  metric_label: string
}

export interface MetricComparison {
  metric_name: string
  label: string
  value_a: number
  value_b: number
  winner: 'a' | 'b' | 'draw'
}

export interface MarketContext {
  value_a: number
  value_b: number
  league_avg_a: number | null
  league_avg_b: number | null
}

export interface ComparisonResult {
  player_a: PlayerDetail
  player_b: PlayerDetail
  metrics: MetricComparison[]
  market_context: MarketContext
}

