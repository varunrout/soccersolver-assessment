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

const CHART_COLOURS = ['#22d3a6', '#55a7ff', '#f6c453', '#f26d85']
const GRID_COLOUR = '#263b4c'
const AXIS_COLOUR = '#94a9b8'

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
          <PolarGrid stroke={GRID_COLOUR} />
          <PolarAngleAxis dataKey="label" tick={{ fill: AXIS_COLOUR }} />
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
          <CartesianGrid stroke={GRID_COLOUR} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: AXIS_COLOUR }} />
          <YAxis tick={{ fill: AXIS_COLOUR }} />
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
        <CartesianGrid stroke={GRID_COLOUR} strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fill: AXIS_COLOUR }} />
        <YAxis tick={{ fill: AXIS_COLOUR }} />
        <Tooltip />
        <Legend />
        {response.datasets.map((dataset, index) => (
          <Bar dataKey={dataset.label} fill={CHART_COLOURS[index % CHART_COLOURS.length]} key={dataset.label} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
