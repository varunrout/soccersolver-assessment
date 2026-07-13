import type { PlayerPercentiles } from '../types/player'

const METRIC_LABELS: Record<string, string> = {
  goals_p90: 'Goals per 90',
  assists_p90: 'Assists per 90',
  shots_p90: 'Shots per 90',
  passes_p90: 'Passes per 90',
  xg_p90: 'xG per 90',
  xa_p90: 'xA per 90',
}

type PercentileMetric = {
  key: string
  label: string
  value: number
}

function getPercentileBand(value: number) {
  if (value >= 90) return 'Elite'
  if (value >= 75) return 'Above average'
  if (value >= 40) return 'Average'
  return 'Below average'
}

interface Props {
  percentiles: PlayerPercentiles | null
}

function getOrdinalSuffix(value: number) {
  const mod100 = value % 100

  if (mod100 >= 11 && mod100 <= 13) {
    return 'th'
  }

  switch (value % 10) {
    case 1:
      return 'st'
    case 2:
      return 'nd'
    case 3:
      return 'rd'
    default:
      return 'th'
  }
}

export function formatPercentile(value: number) {
  const rounded = Math.round(value)

  return `${rounded}${getOrdinalSuffix(rounded)} percentile`
}

function getMetricLabel(key: string) {
  return METRIC_LABELS[key] ?? key.replace(/_/g, ' ')
}

function getDisplayMetrics(percentiles: PlayerPercentiles | null): PercentileMetric[] {
  if (!percentiles?.metrics) {
    return []
  }

  return Object.entries(percentiles.metrics)
    .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
    .map(([key, value]) => ({
      key,
      label: getMetricLabel(key),
      value: Math.min(100, Math.max(0, value as number)),
    }))
}

export default function MetricsChart({ percentiles }: Props) {
  const metrics = getDisplayMetrics(percentiles)

  if (metrics.length === 0) {
    return (
      <div className="placeholder-card">
        <p className="placeholder-text">Contextual percentile data is not available for this player.</p>
      </div>
    )
  }

  return (
    <div className="chart-wrapper percentile-chart">
      <h2 className="section-title">Contextual Percentiles</h2>
      <p className="section-note">
        Percentiles compare this player with players in the same position and league who meet the minimum-minutes
        threshold.
      </p>
      <div className="percentile-list">
        {metrics.map((metric) => (
          <div className="percentile-row" key={metric.key}>
            <div className="percentile-row__header">
              <div><span>{metric.label}</span><small>{getPercentileBand(metric.value)}</small></div>
              <strong>{Math.round(metric.value)}<span>/100</span></strong>
            </div>
            <div
              className="percentile-bar"
              role="img"
              aria-label={`${metric.label}: ${formatPercentile(metric.value)}`}
            >
              <span className="percentile-marker percentile-marker--25" aria-hidden="true" />
              <span className="percentile-marker percentile-marker--50" aria-hidden="true" />
              <span className="percentile-marker percentile-marker--75" aria-hidden="true" />
              <span className="percentile-bar__fill" style={{ width: `${metric.value}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
