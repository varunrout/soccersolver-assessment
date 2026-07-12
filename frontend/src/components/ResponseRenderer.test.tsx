import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { ChartResponse, ResponseUnion, TableResponse } from '../types/chat'
import type { ComparisonResult, PlayerDetail } from '../types/player'
import ResponseRenderer from './ResponseRenderer'

const salah: PlayerDetail = {
  player_id: 'e342ad68',
  name: 'Mohamed Salah',
  position: 'FWD',
  club: 'Liverpool',
  league: 'Premier League',
  market_value_eur: 104_000_000,
  age: 29,
  goals: 23,
  assists: 13,
  minutes_played: 2762,
  shots: 134,
  passes: 1118,
  xg: 23.7,
  xa: 9.7,
}

const kane: PlayerDetail = {
  ...salah,
  player_id: '21a66f6a',
  name: 'Harry Kane',
  club: 'Tottenham',
}

const comparison: ComparisonResult = {
  player_a: salah,
  player_b: kane,
  metrics: [
    { metric_name: 'goals_p90', label: 'Goals per 90', value_a: 0.749, value_b: 0.473, winner: 'a' },
    { metric_name: 'xg_p90', label: 'xG per 90', value_a: 0.772, value_b: 0.546, winner: 'draw' },
  ],
  market_context: {
    value_a: 104_000_000,
    value_b: 104_000_000,
    league_avg_a: 22_376_812,
    league_avg_b: null,
  },
}

function renderResponse(response: ResponseUnion) {
  return render(
    <MemoryRouter>
      <ResponseRenderer response={response} />
    </MemoryRouter>,
  )
}

describe('ResponseRenderer text', () => {
  it('renders clarification text', () => {
    renderResponse({ type: 'text', message: 'Which metric should I rank by?', is_error: false })

    expect(screen.getByText('Which metric should I rank by?')).toBeTruthy()
  })

  it('renders error text as an explicit alert', () => {
    renderResponse({ type: 'text', message: 'I could not find that player.', is_error: true })

    expect(screen.getByRole('alert').textContent).toContain('Unable to complete request')
    expect(screen.getByText('I could not find that player.')).toBeTruthy()
  })
})

describe('ResponseRenderer table', () => {
  it('renders ordered headers, rows, null fallback, and nested values safely', () => {
    const response: TableResponse = {
      type: 'table',
      title: 'Top players',
      columns: ['rank', 'name', 'meta', 'available'],
      rows: [
        { rank: 1, name: 'Mohamed Salah', meta: null, available: true },
        { rank: 2, name: 'Harry Kane', meta: { club: 'Tottenham' }, available: false },
      ],
    }
    renderResponse(response)

    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['rank', 'name', 'meta', 'available'])
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
    expect(screen.getByText('—')).toBeTruthy()
    expect(screen.getByText('{"club":"Tottenham"}')).toBeTruthy()
    expect(screen.getByText('True')).toBeTruthy()
    expect(screen.getByText('False')).toBeTruthy()
  })

  it('renders empty rows fallback', () => {
    renderResponse({ type: 'table', title: 'No rows', columns: ['name'], rows: [] })

    expect(screen.getByText('No results to display.')).toBeTruthy()
  })

  it('uses unique heading IDs for repeated table titles', () => {
    const response: TableResponse = {
      type: 'table',
      title: 'Repeated title',
      columns: ['name'],
      rows: [{ name: 'Mohamed Salah' }],
    }

    render(
      <>
        <ResponseRenderer response={response} />
        <ResponseRenderer response={response} />
      </>,
    )

    const ids = screen.getAllByRole('heading', { name: 'Repeated title' }).map((heading) => heading.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

describe('ResponseRenderer chart', () => {
  it('renders radar response with accessible values', () => {
    const response: ChartResponse = {
      type: 'chart',
      title: 'Mohamed Salah vs peers',
      chart_type: 'radar',
      labels: ['Goals', 'Assists'],
      datasets: [
        { label: 'Mohamed Salah', data: [100, 97.1] },
        { label: 'Peer average', data: [50, 50] },
      ],
    }
    renderResponse(response)

    expect(screen.getByRole('img', { name: /mohamed salah vs peers radar chart/i })).toBeTruthy()
    expect(screen.getByRole('table', { name: /chart values/i })).toBeTruthy()
    expect(screen.getByText('Goals')).toBeTruthy()
    expect(screen.getByText('97.1')).toBeTruthy()
  })

  it('handles non-finite and mismatched malformed chart data without crashing', () => {
    const response: ChartResponse = {
      type: 'chart',
      title: 'Malformed chart',
      chart_type: 'bar',
      labels: ['One', 'Two'],
      datasets: [{ label: 'Dataset', data: [Number.NaN] }],
    }
    renderResponse(response)

    expect(screen.getByText('Malformed chart')).toBeTruthy()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('uses unique heading IDs for repeated chart titles', () => {
    const response: ChartResponse = {
      type: 'chart',
      title: 'Repeated chart',
      chart_type: 'bar',
      labels: ['Goals'],
      datasets: [{ label: 'Mohamed Salah', data: [100] }],
    }

    render(
      <>
        <ResponseRenderer response={response} />
        <ResponseRenderer response={response} />
      </>,
    )

    const ids = screen.getAllByRole('heading', { name: 'Repeated chart' }).map((heading) => heading.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

describe('ResponseRenderer comparison', () => {
  it('renders comparison players, metrics, winners, market context and null peer averages', () => {
    renderResponse({ type: 'comparison', result: comparison })

    expect(screen.getByRole('link', { name: 'Mohamed Salah' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Harry Kane' })).toBeTruthy()
    expect(screen.getByText('Goals per 90')).toBeTruthy()
    expect(screen.getByText('Player A leads')).toBeTruthy()
    expect(screen.getByText('Draw')).toBeTruthy()
    const marketSection = screen.getByRole('heading', { name: 'Market Context' }).closest('section')
    expect(marketSection).not.toBeNull()
    expect(within(marketSection as HTMLElement).getByText('Not available')).toBeTruthy()
  })
})

describe('ResponseRenderer defensive fallback', () => {
  it('does not crash for unknown response types', () => {
    renderResponse({ type: 'mystery' } as unknown as ResponseUnion)

    expect(screen.getByText('This response could not be displayed.')).toBeTruthy()
  })
})
