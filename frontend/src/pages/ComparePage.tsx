import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ApiError, comparePlayers, getPlayerProfile } from '../api/client'
import ComparisonResultView from '../components/ComparisonResultView'
import PlayerSelector from '../components/PlayerSelector'
import type { ComparisonResult, PlayerDetail, PlayerSummary } from '../types/player'

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
        <ComparisonResultView result={result} />
      ) : null}
    </div>
  )
}
