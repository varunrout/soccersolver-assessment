import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PlayerCard from '../components/PlayerCard'
import type { PlayerSummary } from '../types/player'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, _setResults] = useState<PlayerSummary[]>([])
  const navigate = useNavigate()

  // TODO (Issue #8): wire up GET /players/search?q=
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    console.log('search not yet implemented', query)
  }

  return (
    <div className="page">
      <h1 className="page-title">Player Search</h1>
      <form className="search-form" onSubmit={handleSearch}>
        <input
          className="search-input"
          type="text"
          placeholder="Search by name, club or league…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-primary" type="submit">Search</button>
      </form>

      {results.length > 0 ? (
        <div className="card-grid">
          {results.map((p) => (
            <PlayerCard
              key={p.player_id}
              player={p}
              onClick={() => navigate(`/player/${p.player_id}`)}
            />
          ))}
        </div>
      ) : (
        <p className="placeholder-text">
          Search for a player to see results. (API integration coming in Issue #8.)
        </p>
      )}
    </div>
  )
}
