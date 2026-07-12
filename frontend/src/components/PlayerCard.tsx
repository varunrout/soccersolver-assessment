import { Link } from 'react-router-dom'
import type { PlayerSummary } from '../types/player'
import { formatMarketValue } from '../utils/formatters'

interface Props {
  player: PlayerSummary
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
