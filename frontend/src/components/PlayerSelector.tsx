import { useCallback, useEffect, useRef, useState } from 'react'
import { searchPlayers } from '../api/client'
import type { PlayerSummary } from '../types/player'
import { formatMarketValue } from '../utils/formatters'

interface Props {
  label: string
  selectedPlayer: PlayerSummary | null
  onSelect: (player: PlayerSummary | null) => void
}

type SelectorStatus = 'idle' | 'loading' | 'success' | 'error'

const MIN_QUERY_LENGTH = 2
const DEBOUNCE_MS = 300

export default function PlayerSelector({ label, selectedPlayer, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlayerSummary[]>([])
  const [status, setStatus] = useState<SelectorStatus>('idle')
  const [searchedQuery, setSearchedQuery] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)
  const debounceRef = useRef<number | null>(null)

  const inputId = `${label.toLowerCase().replace(/\s+/g, '-')}-search`
  const trimmedQuery = query.trim()

  const clearDebounce = useCallback(() => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
  }, [])

  const clearSearch = useCallback(() => {
    abortRef.current?.abort()
    requestIdRef.current += 1
    setResults([])
    setStatus('idle')
    setSearchedQuery('')
  }, [])

  const runSearch = useCallback((nextQuery: string) => {
    const trimmed = nextQuery.trim()

    clearDebounce()

    if (trimmed.length < MIN_QUERY_LENGTH) {
      clearSearch()
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    abortRef.current = controller

    setSearchedQuery(trimmed)
    setStatus('loading')

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
  }, [clearDebounce, clearSearch])

  useEffect(() => {
    if (selectedPlayer) {
      clearDebounce()
      clearSearch()
      setQuery('')
      return
    }

    if (trimmedQuery.length < MIN_QUERY_LENGTH) {
      clearDebounce()
      clearSearch()
      return
    }

    clearDebounce()
    debounceRef.current = window.setTimeout(() => {
      runSearch(trimmedQuery)
    }, DEBOUNCE_MS)

    return clearDebounce
  }, [clearDebounce, clearSearch, runSearch, selectedPlayer, trimmedQuery])

  useEffect(() => {
    return () => {
      clearDebounce()
      abortRef.current?.abort()
    }
  }, [clearDebounce])

  const handleSelect = (player: PlayerSummary) => {
    onSelect(player)
  }

  const handleClear = () => {
    onSelect(null)
    setQuery('')
    clearSearch()
  }

  return (
    <section className="player-selector" aria-labelledby={`${inputId}-label`}>
      <div className="player-selector__header">
        <label className="search-label" id={`${inputId}-label`} htmlFor={inputId}>{label}</label>
        {selectedPlayer ? (
          <button className="text-button" type="button" onClick={handleClear}>Clear</button>
        ) : null}
      </div>

      {selectedPlayer ? (
        <div className="selected-player">
          <strong>{selectedPlayer.name}</strong>
          <span>{selectedPlayer.position} · {selectedPlayer.club} · {selectedPlayer.league}</span>
          <span>Estimated market value {formatMarketValue(selectedPlayer.market_value_eur)}</span>
        </div>
      ) : (
        <>
          <input
            className="search-input"
            id={inputId}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by player name"
            aria-describedby={`${inputId}-help`}
          />
          <p className="search-help" id={`${inputId}-help`}>Enter at least 2 characters, then choose a player.</p>
        </>
      )}

      <div className="selector-live-region" aria-live="polite" aria-atomic="true">
        {status === 'loading' ? `Searching ${label}` : ''}
      </div>

      {!selectedPlayer && status === 'loading' ? <p className="placeholder-text">Searching players...</p> : null}
      {!selectedPlayer && status === 'error' ? (
        <p className="selector-error" role="alert">We couldn't search for players right now.</p>
      ) : null}
      {!selectedPlayer && status === 'success' && results.length === 0 ? (
        <p className="placeholder-text">No players found for "{searchedQuery}".</p>
      ) : null}
      {!selectedPlayer && results.length > 0 ? (
        <ul className="selector-results" aria-label={`${label} search results`}>
          {results.map((player) => (
            <li key={player.player_id}>
              <button type="button" onClick={() => handleSelect(player)}>
                <strong>{player.name}</strong>
                <span>{player.position} · {player.club} · {player.league}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
