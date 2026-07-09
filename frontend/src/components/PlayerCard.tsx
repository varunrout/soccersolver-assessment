import type { PlayerSummary } from '../types/player'

interface Props {
  player: PlayerSummary
  onClick?: () => void
}

const FMT = new Intl.NumberFormat('en-GB', { notation: 'compact', maximumFractionDigits: 1 })

export default function PlayerCard({ player, onClick }: Props) {
  return (
    <div className="player-card" onClick={onClick} role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined}>
      <div className="player-card__name">{player.name}</div>
      <div className="player-card__meta">
        <span>{player.position}</span>
        <span>·</span>
        <span>{player.club}</span>
        <span>·</span>
        <span>{player.league}</span>
      </div>
      <div className="player-card__stats">
        <span>Age {player.age}</span>
        <span>€{FMT.format(player.market_value_eur)}</span>
      </div>
    </div>
  )
}
