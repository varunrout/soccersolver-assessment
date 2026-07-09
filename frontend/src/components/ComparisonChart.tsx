import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { ComparisonResult } from '../types/player'

interface Props {
  result: ComparisonResult
}

export default function ComparisonChart({ result }: Props) {
  const data = result.metrics.map((m) => ({
    metric: m.metric,
    [result.player_a.name]: m.player_a,
    [result.player_b.name]: m.player_b,
  }))

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">
        {result.player_a.name} vs {result.player_b.name}
      </h3>
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="metric" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey={result.player_a.name} fill="#3b82f6" />
          <Bar dataKey={result.player_b.name} fill="#f97316" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
