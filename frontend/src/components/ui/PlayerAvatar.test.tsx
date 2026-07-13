import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PlayerAvatar from './PlayerAvatar'

describe('PlayerAvatar', () => {
  it('renders a provided player image with useful alt text', () => {
    render(<PlayerAvatar name="Mohamed Salah" imageUrl="https://images.example.test/salah.jpg" position="FWD" />)

    const image = screen.getByRole('img', { name: 'Mohamed Salah player portrait' }) as HTMLImageElement
    expect(image.src).toBe('https://images.example.test/salah.jpg')
    expect(image.getAttribute('referrerpolicy')).toBe('no-referrer')
  })

  it('renders deterministic initials when an image URL is absent', () => {
    render(<PlayerAvatar name="Mohamed Salah" />)

    expect(screen.getByRole('img', { name: 'Mohamed Salah avatar' })).toBeTruthy()
    expect(screen.getByText('MS')).toBeTruthy()
  })

  it('switches to fallback initials when the external image fails', () => {
    render(<PlayerAvatar name="Harry Kane" imageUrl="https://images.example.test/broken.jpg" />)

    fireEvent.error(screen.getByRole('img', { name: 'Harry Kane player portrait' }))

    expect(screen.getByRole('img', { name: 'Harry Kane avatar' })).toBeTruthy()
    expect(screen.getByText('HK')).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Harry Kane player portrait' })).toBeNull()
  })

  it('does not expose fallback initials twice to assistive technology', () => {
    render(<PlayerAvatar name="Kylian Mbappe" />)

    const fallback = screen.getByRole('img', { name: 'Kylian Mbappe avatar' })
    expect(fallback.querySelector('[aria-hidden="true"]')?.textContent).toBe('KM')
  })
})