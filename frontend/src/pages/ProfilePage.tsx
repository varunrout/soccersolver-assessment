import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getPlayerProfile } from '../api/client'
import MetricsChart from '../components/MetricsChart'
import type { PlayerDetailWithPercentiles } from '../types/player'
import { formatDecimal, formatInteger, formatMarketValue } from '../utils/formatters'

type ProfileStatus = 'loading' | 'success' | 'not-found' | 'error' | 'invalid'

type StatItem = {
  label: string
  value: string
}

function getCoreStats(player: PlayerDetailWithPercentiles): StatItem[] {
  return [
    { label: 'Goals', value: formatInteger(player.goals) },
    { label: 'Assists', value: formatInteger(player.assists) },
    { label: 'Minutes played', value: formatInteger(player.minutes_played) },
    { label: 'Shots', value: formatInteger(player.shots) },
    { label: 'Passes', value: formatInteger(player.passes) },
    { label: 'xG', value: formatDecimal(player.xg) },
    { label: 'xA', value: formatDecimal(player.xa) },
  ]
}

function ProfileSkeleton() {
  return (
    <div className="profile-skeleton" aria-label="Loading player profile">
      <h1 className="page-title">Player Profile</h1>
      <span className="skeleton skeleton-title">Loading player profile</span>
      <span className="skeleton skeleton-line" />
      <span className="skeleton skeleton-line skeleton-line--short" />
    </div>
  )
}

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>()
  const [player, setPlayer] = useState<PlayerDetailWithPercentiles | null>(null)
  const [status, setStatus] = useState<ProfileStatus>('loading')
  const abortRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)

  const routePlayerId = id?.trim() ?? ''

  const loadProfile = useCallback((playerId: string) => {
    const trimmedId = playerId.trim()

    if (!trimmedId) {
      abortRef.current?.abort()
      requestIdRef.current += 1
      setPlayer(null)
      setStatus('invalid')
      return
    }

    abortRef.current?.abort()

    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    abortRef.current = controller

    setPlayer(null)
    setStatus('loading')

    getPlayerProfile(trimmedId, controller.signal)
      .then((profile) => {
        if (requestIdRef.current !== requestId) {
          return
        }

        setPlayer(profile)
        setStatus('success')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }

        if (requestIdRef.current !== requestId) {
          return
        }

        setPlayer(null)
        setStatus(error instanceof ApiError && error.status === 404 ? 'not-found' : 'error')
      })
  }, [])

  useEffect(() => {
    loadProfile(routePlayerId)

    return () => {
      abortRef.current?.abort()
    }
  }, [loadProfile, routePlayerId])

  const handleRetry = () => {
    loadProfile(routePlayerId)
  }

  return (
    <div className="page profile-page">
      <nav className="profile-actions" aria-label="Profile navigation">
        <Link to="/">Back to Player Search</Link>
        {routePlayerId ? <Link to={`/compare?playerA=${encodeURIComponent(routePlayerId)}`}>Compare this player</Link> : null}
      </nav>

      <div className="profile-live-region" aria-live="polite" aria-atomic="true">
        {status === 'loading' ? 'Loading player profile' : ''}
      </div>

      {status === 'loading' ? <ProfileSkeleton /> : null}

      {status === 'success' && player ? (
        <>
          <header className="profile-header">
            <div className="profile-header__identity">
              <span className="profile-badge">{player.position}</span>
              <h1 className="page-title">{player.name}</h1>
              <p>
                {player.club} {'\u00b7'} {player.league}
              </p>
            </div>
            <dl className="profile-facts">
              <div>
                <dt>Age</dt>
                <dd>{player.age}</dd>
              </div>
              <div>
                <dt>Estimated market value</dt>
                <dd>{formatMarketValue(player.market_value_eur)}</dd>
              </div>
            </dl>
          </header>

          <section className="profile-section" aria-labelledby="season-stats-heading">
            <h2 className="section-title" id="season-stats-heading">Season Statistics</h2>
            <div className="stats-grid">
              {getCoreStats(player).map((stat) => (
                <div className="stat-card" key={stat.label}>
                  <span>{stat.label}</span>
                  <strong>{stat.value}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="profile-section" aria-labelledby="percentiles-heading">
            <h2 className="visually-hidden" id="percentiles-heading">Contextual percentile metrics</h2>
            <MetricsChart percentiles={player.percentiles} />
          </section>
        </>
      ) : null}

      {status === 'not-found' || status === 'invalid' ? (
        <section className="profile-message" role="alert">
          <h1 className="page-title">Player not found.</h1>
          <p>Return to player search and try another player.</p>
          <Link className="btn btn-primary btn-link" to="/">Player Search</Link>
        </section>
      ) : null}

      {status === 'error' ? (
        <section className="profile-message" role="alert">
          <h1 className="page-title">We couldn&apos;t load this player right now.</h1>
          <div className="profile-message__actions">
            <button className="btn btn-primary" type="button" onClick={handleRetry}>Retry</button>
            <Link to="/">Back to Player Search</Link>
          </div>
        </section>
      ) : null}
    </div>
  )
}
