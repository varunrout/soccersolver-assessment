import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

interface Props {
  labels: string[]
  values: number[]   // percentile 0-100
  title: string
}

export default function MetricsChart({ labels, values, title }: Props) {
  const data = labels.map((label, i) => ({ label, value: values[i] ?? 0 }))

  if (data.length === 0) {
    return <div className="placeholder-card"><p className="placeholder-text">No metrics to display.</p></div>
  }

  return (
    <div className="chart-wrapper">
      <h3 className="chart-title">{title}</h3>
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="label" />
          <Radar dataKey="value" fill="#3b82f6" fillOpacity={0.5} stroke="#3b82f6" />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
