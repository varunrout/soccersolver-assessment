import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, comparePlayers, getPlayerProfile } from '../api/client'
import ComparisonChart from '../components/ComparisonChart'
import PlayerSelector from '../components/PlayerSelector'
import type { ComparisonResult, PlayerDetail, PlayerSummary } from '../types/player'
import { formatMarketValue } from '../utils/formatters'

type CompareStatus = 'idle' | 'loading' | 'success' | 'not-found' | 'error'

function toSummary(player: PlayerDetail): PlayerSummary {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    club: player.club,
    league: player.league,
    market_value_eur: player.market_value_eur,
  }
}

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

function MarketContext({ result }: { result: ComparisonResult }) {
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

export default function ComparePage() {
  const [searchParams] = useSearchParams()
  const [playerA, setPlayerA] = useState<PlayerSummary | null>(null)
  const [playerB, setPlayerB] = useState<PlayerSummary | null>(null)
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [status, setStatus] = useState<CompareStatus>('idle')
  const preselectAbortRef = useRef<AbortController | null>(null)
  const compareAbortRef = useRef<AbortController | null>(null)
  const compareRequestIdRef = useRef(0)

  const canCompare = playerA !== null && playerB !== null

  const clearComparison = useCallback(() => {
    compareAbortRef.current?.abort()
    compareRequestIdRef.current += 1
    setResult(null)
    setStatus('idle')
  }, [])

  const handleSelectA = (player: PlayerSummary | null) => {
    setPlayerA(player)
    clearComparison()
  }

  const handleSelectB = (player: PlayerSummary | null) => {
    setPlayerB(player)
    clearComparison()
  }

  const loadPreselectedPlayer = useCallback((playerId: string, slot: 'a' | 'b', signal: AbortSignal) => {
    const trimmedId = playerId.trim()

    if (!trimmedId) {
      return
    }

    getPlayerProfile(trimmedId, signal)
      .then((profile) => {
        if (signal.aborted) {
          return
        }

        if (slot === 'a') {
          setPlayerA(toSummary(profile))
        } else {
          setPlayerB(toSummary(profile))
        }
      })
      .catch(() => {
        // Invalid preselection should leave the normal selector usable.
      })
  }, [])

  useEffect(() => {
    preselectAbortRef.current?.abort()
    const controller = new AbortController()
    preselectAbortRef.current = controller

    const preselectedA = searchParams.get('playerA')
    const preselectedB = searchParams.get('playerB')

    if (preselectedA) {
      loadPreselectedPlayer(preselectedA, 'a', controller.signal)
    }

    if (preselectedB) {
      loadPreselectedPlayer(preselectedB, 'b', controller.signal)
    }

    return () => {
      controller.abort()
    }
  }, [loadPreselectedPlayer, searchParams])

  useEffect(() => {
    return () => {
      preselectAbortRef.current?.abort()
      compareAbortRef.current?.abort()
    }
  }, [])

  const runComparison = useCallback(() => {
    if (!playerA || !playerB) {
      return
    }

    compareAbortRef.current?.abort()
    const controller = new AbortController()
    const requestId = compareRequestIdRef.current + 1
    compareRequestIdRef.current = requestId
    compareAbortRef.current = controller

    setResult(null)
    setStatus('loading')

    comparePlayers(playerA.player_id, playerB.player_id, controller.signal)
      .then((comparison) => {
        if (compareRequestIdRef.current !== requestId) {
          return
        }

        setResult(comparison)
        setStatus('success')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }

        if (compareRequestIdRef.current !== requestId) {
          return
        }

        setResult(null)
        setStatus(error instanceof ApiError && error.status === 404 ? 'not-found' : 'error')
      })
  }, [playerA, playerB])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    runComparison()
  }

  return (
    <div className="page compare-page">
      <header className="compare-header">
        <h1 className="page-title">Compare Players</h1>
        <p>Select two players to compare their per-90 performance and market context.</p>
      </header>

      <form className="compare-builder" onSubmit={handleSubmit}>
        <div className="selector-grid">
          <PlayerSelector label="Player A" selectedPlayer={playerA} onSelect={handleSelectA} />
          <PlayerSelector label="Player B" selectedPlayer={playerB} onSelect={handleSelectB} />
        </div>

        <div className="compare-submit-row">
          <button className="btn btn-primary" type="submit" disabled={!canCompare || status === 'loading'}>
            Compare players
          </button>
          {!canCompare ? <p className="search-help">Select both players to enable comparison.</p> : null}
        </div>
      </form>

      <div className="comparison-live-region" aria-live="polite" aria-atomic="true">
        {status === 'loading' ? 'Comparing selected players' : ''}
      </div>

      {status === 'loading' ? (
        <div className="profile-skeleton" aria-label="Loading comparison">
          <span className="skeleton skeleton-title">Loading comparison</span>
          <span className="skeleton skeleton-line" />
          <span className="skeleton skeleton-line skeleton-line--short" />
        </div>
      ) : null}

      {status === 'not-found' ? (
        <section className="profile-message" role="alert">
          <h2 className="section-title">One or both selected players could not be found.</h2>
          <p>Change a selection and try again.</p>
        </section>
      ) : null}

      {status === 'error' ? (
        <section className="profile-message" role="alert">
          <h2 className="section-title">We couldn&apos;t compare these players right now. Please try again.</h2>
          <button className="btn btn-primary" type="button" onClick={runComparison}>Retry</button>
        </section>
      ) : null}

      {status === 'success' && result ? (
        <>
          <section className="comparison-header-grid" aria-label="Selected player comparison">
            <PlayerIdentity player={result.player_a} label="Player A" />
            <PlayerIdentity player={result.player_b} label="Player B" />
          </section>
          <ComparisonChart result={result} />
          <MarketContext result={result} />
        </>
      ) : null}
    </div>
  )
}
