import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartResponse } from '../types/chat'

const CHART_COLOURS = ['#3b82f6', '#f97316', '#22c55e', '#e879f9']

function buildChartData(response: ChartResponse) {
  return response.labels.map((label, index) => {
    const row: Record<string, string | number> = { label }

    response.datasets.forEach((dataset) => {
      const value = dataset.data[index]
      row[dataset.label] = Number.isFinite(value) ? value : 0
    })

    return row
  })
}

export default function ChartGraphic({ response }: { response: ChartResponse }) {
  const data = buildChartData(response)

  if (response.chart_type === 'radar') {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="label" />
          {response.datasets.map((dataset, index) => (
            <Radar
              dataKey={dataset.label}
              fill={CHART_COLOURS[index % CHART_COLOURS.length]}
              fillOpacity={0.25}
              key={dataset.label}
              stroke={CHART_COLOURS[index % CHART_COLOURS.length]}
            />
          ))}
          <Legend />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    )
  }

  if (response.chart_type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis />
          <Tooltip />
          <Legend />
          {response.datasets.map((dataset, index) => (
            <Line
              dataKey={dataset.label}
              key={dataset.label}
              stroke={CHART_COLOURS[index % CHART_COLOURS.length]}
              type="monotone"
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" />
        <YAxis />
        <Tooltip />
        <Legend />
        {response.datasets.map((dataset, index) => (
          <Bar dataKey={dataset.label} fill={CHART_COLOURS[index % CHART_COLOURS.length]} key={dataset.label} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
