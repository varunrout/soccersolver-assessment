import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import PlayerCard from './PlayerCard'
import type { PlayerSummary } from '../types/player'
import { formatMarketValue } from '../utils/formatters'

const player: PlayerSummary = {
  player_id: 'mo-salah',
  name: 'Mohamed Salah',
  position: 'FWD',
  club: 'Liverpool',
  league: 'Premier League',
  market_value_eur: 120_000_000,
}

describe('PlayerCard', () => {
  it('links to the player profile route and renders real summary fields', () => {
    render(
      <MemoryRouter>
        <PlayerCard player={player} />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: /view mohamed salah profile/i })

    expect(link.getAttribute('href')).toBe('/player/mo-salah')
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
    expect(screen.getByText('FWD')).toBeTruthy()
    expect(screen.getByText('Liverpool')).toBeTruthy()
    expect(screen.getByText('Premier League')).toBeTruthy()
    expect(screen.getByText('€120m')).toBeTruthy()
  })
})

describe('formatMarketValue', () => {
  it('formats millions with consistent precision', () => {
    expect(formatMarketValue(120_000_000)).toBe('€120m')
    expect(formatMarketValue(35_500_000)).toBe('€35.5m')
  })

  it('formats thousands', () => {
    expect(formatMarketValue(850_000)).toBe('€850k')
  })

  it('returns N/A for zero and invalid negative values', () => {
    expect(formatMarketValue(0)).toBe('N/A')
    expect(formatMarketValue(-1)).toBe('N/A')
  })
})
