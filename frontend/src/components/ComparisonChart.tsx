import type { ComparisonResult, MetricComparison } from '../types/player'
import { formatDecimal } from '../utils/formatters'

interface Props {
  result: ComparisonResult
}

function safeValue(value: number) {
  return Number.isFinite(value) ? value : 0
}

function formatMetricValue(value: number) {
  if (!Number.isFinite(value)) {
    return 'N/A'
  }

  return formatDecimal(value)
}

function winnerLabel(metric: MetricComparison) {
  if (metric.winner === 'a') {
    return 'Player A leads'
  }

  if (metric.winner === 'b') {
    return 'Player B leads'
  }

  return 'Draw'
}

export default function ComparisonChart({ result }: Props) {
  return (
    <section className="comparison-panel" aria-labelledby="metric-comparison-heading">
      <h2 className="section-title" id="metric-comparison-heading">Metric Comparison</h2>
      <div className="comparison-metrics">
        {result.metrics.map((metric) => {
          const valueA = safeValue(metric.value_a)
          const valueB = safeValue(metric.value_b)
          const maxValue = Math.max(valueA, valueB, 0)
          const widthA = maxValue > 0 ? (valueA / maxValue) * 100 : 0
          const widthB = maxValue > 0 ? (valueB / maxValue) * 100 : 0

          return (
            <article
              className="comparison-row"
              key={metric.metric_name}
              aria-label={`${metric.label}: ${result.player_a.name} ${formatMetricValue(metric.value_a)}, ${result.player_b.name} ${formatMetricValue(metric.value_b)}, ${winnerLabel(metric)}`}
            >
              <div className="comparison-row__header">
                <h3>{metric.label}</h3>
                <strong>{winnerLabel(metric)}</strong>
              </div>
              <div className="comparison-bars">
                <div className="comparison-bar-row">
                  <span>{result.player_a.name}</span>
                  <div className="comparison-bar" aria-hidden="true">
                    <span className="comparison-bar__fill comparison-bar__fill--a" style={{ width: `${widthA}%` }} />
                  </div>
                  <strong>{formatMetricValue(metric.value_a)}</strong>
                </div>
                <div className="comparison-bar-row">
                  <span>{result.player_b.name}</span>
                  <div className="comparison-bar" aria-hidden="true">
                    <span className="comparison-bar__fill comparison-bar__fill--b" style={{ width: `${widthB}%` }} />
                  </div>
                  <strong>{formatMetricValue(metric.value_b)}</strong>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
