import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { searchPlayers } from '../api/client'
import PlayerCard from '../components/PlayerCard'
import type { PlayerSummary } from '../types/player'

type SearchStatus = 'idle' | 'loading' | 'success' | 'error'

const MIN_QUERY_LENGTH = 2
const DEBOUNCE_MS = 300
const EXAMPLE_SEARCHES = ['Mohamed Salah', 'Harry Kane', 'Kylian Mbappe']

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [results, setResults] = useState<PlayerSummary[]>([])
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [hasSearched, setHasSearched] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)
  const debounceRef = useRef<number | null>(null)

  const trimmedQuery = query.trim()
  const canSearch = trimmedQuery.length >= MIN_QUERY_LENGTH

  const clearDebounce = useCallback(() => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
  }, [])

  const clearSearchState = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    requestIdRef.current += 1
    setSubmittedQuery('')
    setResults([])
    setStatus('idle')
    setHasSearched(false)
  }, [])

  const runSearch = useCallback((nextQuery: string) => {
    const trimmed = nextQuery.trim()

    clearDebounce()

    if (trimmed.length < MIN_QUERY_LENGTH) {
      if (trimmed.length === 0) {
        clearSearchState()
      }
      return
    }

    abortRef.current?.abort()

    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    abortRef.current = controller

    setSubmittedQuery(trimmed)
    setStatus('loading')
    setHasSearched(true)

    searchPlayers(trimmed, controller.signal)
      .then((players) => {
        if (requestIdRef.current !== requestId) {
          return
        }

        setResults(players)
        setStatus('success')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }

        if (requestIdRef.current !== requestId) {
          return
        }

        setResults([])
        setStatus('error')
      })
  }, [clearDebounce, clearSearchState])

  useEffect(() => {
    const trimmed = query.trim()

    if (trimmed.length === 0) {
      clearDebounce()
      clearSearchState()
      return
    }

    if (trimmed.length < MIN_QUERY_LENGTH) {
      clearDebounce()
      abortRef.current?.abort()
      setStatus('idle')
      setResults([])
      setSubmittedQuery('')
      setHasSearched(false)
      return
    }

    clearDebounce()
    debounceRef.current = window.setTimeout(() => {
      runSearch(trimmed)
    }, DEBOUNCE_MS)

    return clearDebounce
  }, [clearDebounce, clearSearchState, query, runSearch])

  useEffect(() => {
    return () => {
      clearDebounce()
      abortRef.current?.abort()
    }
  }, [clearDebounce])

  const resultSummary = useMemo(() => {
    const noun = results.length === 1 ? 'player' : 'players'

    return `${results.length} ${noun} found for "${submittedQuery}"`
  }, [results.length, submittedQuery])

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault()
    runSearch(query)
  }

  const handleRetry = () => {
    runSearch(submittedQuery || query)
  }

  const showInitialState = status === 'idle' && !hasSearched && results.length === 0
  const showEmptyState = status === 'success' && results.length === 0
  const showResults = status === 'success' && results.length > 0

  return (
    <div className="page search-page">
      <div className="search-header">
        <h1 className="page-title">Player Search</h1>
        <p className="search-intro">Search more than 2,400 players across Europe's Big Five leagues.</p>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <label className="search-label" htmlFor="player-search">Search players</label>
        <div className="search-controls">
          <input
            id="player-search"
            className="search-input"
            type="search"
            placeholder="Search by player name"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-describedby="player-search-help"
          />
          <button className="btn btn-primary" type="submit" disabled={!canSearch || status === 'loading'}>
            Search
          </button>
        </div>
        <p className="search-help" id="player-search-help">Enter at least 2 characters.</p>
      </form>

      <div className="search-live-region" aria-live="polite" aria-atomic="true">
        {status === 'loading' ? `Searching for ${submittedQuery}` : ''}
        {status === 'success' ? resultSummary : ''}
      </div>

      {showInitialState ? (
        <section className="search-empty-panel" aria-label="Search suggestions">
          <p>Try a player name to start exploring the dataset.</p>
          <div className="example-searches" aria-label="Example searches">
            {EXAMPLE_SEARCHES.map((example) => (
              <span key={example}>{example}</span>
            ))}
          </div>
        </section>
      ) : null}

      {status === 'loading' ? (
        <div className="card-grid" aria-label="Loading player results">
          {[0, 1, 2].map((item) => (
            <div className="player-card player-card--loading" key={item}>
              <span className="skeleton skeleton-title">Loading player result</span>
              <span className="skeleton skeleton-line" />
              <span className="skeleton skeleton-line skeleton-line--short" />
            </div>
          ))}
        </div>
      ) : null}

      {showResults ? (
        <>
          <p className="result-summary">{resultSummary}</p>
          <div className="card-grid">
            {results.map((player) => (
              <PlayerCard key={player.player_id} player={player} />
            ))}
          </div>
        </>
      ) : null}

      {showEmptyState ? (
        <section className="search-empty-panel" aria-live="polite">
          <p>No players found for "{submittedQuery}".</p>
          <p>Try checking the spelling or using the player's full name.</p>
        </section>
      ) : null}

      {status === 'error' ? (
        <section className="search-error" role="alert">
          <p>We couldn't search for players right now. Please try again.</p>
          <button className="btn btn-primary" type="button" onClick={handleRetry}>
            Retry
          </button>
        </section>
      ) : null}
    </div>
  )
}
