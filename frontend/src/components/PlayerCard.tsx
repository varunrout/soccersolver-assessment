import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import type { PlayerSummary } from '../types/player'
import { formatMarketValue } from '../utils/formatters'
import PlayerAvatar from './ui/PlayerAvatar'

interface Props {
  player: PlayerSummary
}

export default function PlayerCard({ player }: Props) {
  return (
    <Link className="player-card" to={`/player/${player.player_id}`} aria-label={`View ${player.name} profile`}>
      <div className="player-card__visual">
        <PlayerAvatar name={player.name} playerId={player.player_id} position={player.position} size="large" />
        <span className="player-card__open" aria-hidden="true"><ArrowUpRight size={18} /></span>
      </div>
      <div className="player-card__body">
        <div className="player-card__name">{player.name}</div>
        <div className="player-card__meta">
          <span>{player.club}</span>
          <span>{player.league}</span>
        </div>
      </div>
      <div className="player-card__stats">
        <span>Estimated market value</span>
        <strong>{formatMarketValue(player.market_value_eur)}</strong>
      </div>
    </Link>
  )
}
