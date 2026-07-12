import { Link } from 'react-router-dom'
import type { PlayerSummary } from '../types/player'

interface Props {
  player: PlayerSummary
}

function formatCompact(value: number, divisor: number, suffix: string) {
  const amount = value / divisor
  const formatted = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1)

  return `€${formatted}${suffix}`
}

export function formatMarketValue(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return 'N/A'
  }

  if (value >= 1_000_000) {
    return formatCompact(value, 1_000_000, 'm')
  }

  if (value >= 1_000) {
    return formatCompact(value, 1_000, 'k')
  }

  return 'N/A'
}

export default function PlayerCard({ player }: Props) {
  return (
    <Link className="player-card" to={`/player/${player.player_id}`} aria-label={`View ${player.name} profile`}>
      <div className="player-card__name">{player.name}</div>
      <div className="player-card__meta">
        <span className="player-card__position">{player.position}</span>
        <span>{player.club}</span>
        <span>{player.league}</span>
      </div>
      <div className="player-card__stats">
        <span>Estimated market value</span>
        <strong>{formatMarketValue(player.market_value_eur)}</strong>
      </div>
    </Link>
  )
}
