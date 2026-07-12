import { Link } from 'react-router-dom'
import type { ComparisonResult, PlayerDetail } from '../types/player'
import { formatMarketValue } from '../utils/formatters'
import ComparisonChart from './ComparisonChart'

function PlayerIdentity({ player, label }: { player: PlayerDetail, label: string }) {
  return (
    <article className="comparison-player-card">
      <span className="profile-badge">{label}</span>
      <h2><Link to={`/player/${player.player_id}`}>{player.name}</Link></h2>
      <p>{player.position} · {player.club} · {player.league}</p>
      <dl>
        <div>
          <dt>Age</dt>
          <dd>{player.age}</dd>
        </div>
        <div>
          <dt>Estimated market value</dt>
          <dd>{formatMarketValue(player.market_value_eur)}</dd>
        </div>
      </dl>
    </article>
  )
}

export function MarketContext({ result }: { result: ComparisonResult }) {
  const marketRows = [
    {
      side: 'a',
      label: result.player_a.name,
      value: result.market_context.value_a,
      average: result.market_context.league_avg_a,
    },
    {
      side: 'b',
      label: result.player_b.name,
      value: result.market_context.value_b,
      average: result.market_context.league_avg_b,
    },
  ]

  return (
    <section className="comparison-panel" aria-labelledby="market-context-heading">
      <h2 className="section-title" id="market-context-heading">Market Context</h2>
      <p className="section-note">
        Peer-group averages use players in the same position and league who meet the backend minutes threshold.
      </p>
      <div className="market-grid">
        {marketRows.map((row) => (
          <article className="market-card" key={row.side}>
            <h3>{row.label}</h3>
            <dl>
              <div>
                <dt>Estimated market value</dt>
                <dd>{formatMarketValue(row.value)}</dd>
              </div>
              <div>
                <dt>Peer-group average</dt>
                <dd>{row.average === null ? 'Not available' : formatMarketValue(row.average)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  )
}

export default function ComparisonResultView({ result }: { result: ComparisonResult }) {
  return (
    <>
      <section className="comparison-header-grid" aria-label="Selected player comparison">
        <PlayerIdentity player={result.player_a} label="Player A" />
        <PlayerIdentity player={result.player_b} label="Player B" />
      </section>
      <ComparisonChart result={result} />
      <MarketContext result={result} />
    </>
  )
}
