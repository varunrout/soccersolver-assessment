export interface PlayerSummary {
  player_id: string
  name: string
  position: string
  club: string
  league: string
  age: number
  market_value_eur: number
}

export interface PlayerPercentiles {
  goals: number
  assists: number
  minutes_played: number
  shots: number
  passes: number
  xg: number
  xa: number
}

export interface PlayerDetail extends PlayerSummary {
  goals: number
  assists: number
  minutes_played: number
  shots: number
  passes: number
  xg: number
  xa: number
}

export interface PlayerDetailWithPercentiles {
  player: PlayerDetail
  percentiles: PlayerPercentiles
  league_rank: number | null
  similar_players: PlayerSummary[]
}

export interface MetricComparison {
  metric: string
  player_a: number
  player_b: number
  percentile_a: number
  percentile_b: number
  winner: 'a' | 'b' | 'draw'
}

export interface MarketContext {
  player_a_value: number
  player_b_value: number
  value_ratio: number
  better_value: 'a' | 'b' | 'equal'
}

export interface ComparisonResult {
  player_a: PlayerDetail
  player_b: PlayerDetail
  metrics: MetricComparison[]
  overall_winner: 'a' | 'b' | 'draw'
  market_context: MarketContext
}
