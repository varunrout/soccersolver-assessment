import { useId } from 'react'
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
import type { ChartResponse, ResponseUnion, TableResponse } from '../types/chat'
import ComparisonResultView from './ComparisonResultView'

interface Props {
  response: ResponseUnion
}

const CHART_COLOURS = ['#3b82f6', '#f97316', '#22c55e', '#e879f9']

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '—'
  }

  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toLocaleString('en-GB', { maximumFractionDigits: 3 }) : '—'
  }

  if (typeof value === 'boolean') {
    return value ? 'True' : 'False'
  }

  try {
    const serialized = JSON.stringify(value)
    return serialized.length > 120 ? `${serialized.slice(0, 117)}...` : serialized
  } catch {
    return '—'
  }
}

function TableRenderer({ response }: { response: TableResponse }) {
  const generatedId = useId()
  const headingId = `table-${generatedId}`

  return (
    <section className="response-card" aria-labelledby={headingId}>
      <h2 className="section-title" id={headingId}>{response.title}</h2>
      {response.rows.length === 0 ? (
        <p className="placeholder-text">No results to display.</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                {response.columns.map((column) => (
                  <th key={column} scope="col">{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {response.rows.map((row, index) => (
                <tr key={`row-${index}`}>
                  {response.columns.map((column) => (
                    <td key={column}>{formatCellValue(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

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

function ChartGraphic({ response }: { response: ChartResponse }) {
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

function ChartRenderer({ response }: { response: ChartResponse }) {
  const generatedId = useId()
  const headingId = `chart-${generatedId}`

  return (
    <section className="response-card" aria-labelledby={headingId}>
      <h2 className="section-title" id={headingId}>{response.title}</h2>
      <div className="chart-canvas" role="img" aria-label={`${response.title} ${response.chart_type} chart`}>
        <ChartGraphic response={response} />
      </div>
      <div className="chart-values" aria-label={`${response.title} chart values`}>
        <table className="data-table" aria-label={`${response.title} chart values`}>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {response.datasets.map((dataset) => (
                <th key={dataset.label} scope="col">{dataset.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {response.labels.map((label, index) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                {response.datasets.map((dataset) => (
                  <td key={dataset.label}>{formatCellValue(dataset.data[index])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function ResponseRenderer({ response }: Props) {
  switch (response.type) {
    case 'text':
      return (
        <div className={response.is_error ? 'response-box response-box--error' : 'response-box'} role={response.is_error ? 'alert' : undefined}>
          {response.is_error ? <strong>Unable to complete request</strong> : null}
          <p>{response.message}</p>
        </div>
      )

    case 'table':
      return <TableRenderer response={response} />

    case 'chart':
      return <ChartRenderer response={response} />

    case 'comparison':
      return <ComparisonResultView result={response.result} />

    default:
      return <p className="placeholder-text">This response could not be displayed.</p>
  }
}
