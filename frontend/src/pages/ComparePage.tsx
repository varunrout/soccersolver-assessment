import { useState } from 'react'
import ComparisonChart from '../components/ComparisonChart'
import type { ComparisonResult } from '../types/player'

export default function ComparePage() {
  const [playerA, setPlayerA] = useState('')
  const [playerB, setPlayerB] = useState('')
  const [result, _setResult] = useState<ComparisonResult | null>(null)

  // TODO (Issue #8): fetch GET /players/compare?a=:playerA&b=:playerB
  const handleCompare = (e: React.FormEvent) => {
    e.preventDefault()
    console.log('compare not yet implemented', playerA, playerB)
  }

  return (
    <div className="page">
      <h1 className="page-title">Compare Players</h1>

      <form className="compare-form" onSubmit={handleCompare}>
        <input
          className="search-input"
          type="text"
          placeholder="Player A — name or ID"
          value={playerA}
          onChange={(e) => setPlayerA(e.target.value)}
        />
        <span className="vs-label">vs</span>
        <input
          className="search-input"
          type="text"
          placeholder="Player B — name or ID"
          value={playerB}
          onChange={(e) => setPlayerB(e.target.value)}
        />
        <button className="btn btn-primary" type="submit">Compare</button>
      </form>

      {result ? (
        <ComparisonChart result={result} />
      ) : (
        <p className="placeholder-text">
          Enter two player names or IDs and click Compare. (API integration coming in Issue #8.)
        </p>
      )}
    </div>
  )
}
