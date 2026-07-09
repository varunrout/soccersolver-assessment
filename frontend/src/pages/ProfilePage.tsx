import { useParams } from 'react-router-dom'
import MetricsChart from '../components/MetricsChart'

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>()

  // TODO (Issue #8): fetch GET /players/:id
  const player = null

  return (
    <div className="page">
      <h1 className="page-title">Player Profile</h1>

      {player ? (
        <MetricsChart labels={[]} values={[]} title="Stats" />
      ) : (
        <div className="placeholder-card">
          <p className="placeholder-text">
            Player profile for <code>{id}</code> will appear here once the API is connected (Issue #8).
          </p>
        </div>
      )}
    </div>
  )
}
