function formatCompact(value: number, divisor: number, suffix: string) {
  const amount = value / divisor
  const formatted = Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1)

  return `\u20ac${formatted}${suffix}`
}

export function formatMarketValue(value: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return 'N/A'
  }

  if (value >= 1_000_000) {
    return formatCompact(value, 1_000_000, 'm')
  }

  if (value >= 1_000) {
    return formatCompact(value, 1_000, 'k')
  }

  return 'N/A'
}

export function formatInteger(value: number): string {
  if (!Number.isFinite(value)) {
    return 'N/A'
  }

  return Math.round(value).toLocaleString('en-GB')
}

export function formatDecimal(value: number): string {
  if (!Number.isFinite(value)) {
    return 'N/A'
  }

  return value.toLocaleString('en-GB', {
    maximumFractionDigits: 2,
    minimumFractionDigits: Number.isInteger(value) ? 0 : 1,
  })
}
