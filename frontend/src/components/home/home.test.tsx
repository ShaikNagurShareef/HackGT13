import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { RoutineSuggestion } from '../../lib/routines'
import { LegendChip } from './LegendChip'
import { LocationNotice } from './LocationNotice'
import { MapControls } from './MapControls'
import { SearchPill } from './SearchPill'
import { StatusChip } from './StatusChip'
import { isStrongSuggestion, suggestionHeadline } from '../../lib/suggestion'
import { SuggestionCard } from './SuggestionCard'
import { WelcomeToast } from './WelcomeToast'

const HOME = { lat: 33.785, lon: -84.402, label: 'Home' }
const back: RoutineSuggestion = { from: null, to: HOME, reason: 'Heading back?', kind: 'return', score: 2 }

describe('home chrome', () => {
  it('search pill opens search', async () => {
    const onOpen = vi.fn()
    render(<SearchPill onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('button', { name: 'Where to?' }))
    expect(onOpen).toHaveBeenCalled()
  })

  it('map controls open options and locate, reflecting GPS state', async () => {
    const onLayers = vi.fn()
    const onLocate = vi.fn()
    const { rerender } = render(<MapControls onLayers={onLayers} onLocate={onLocate} geoStatus="prompt" />)

    await userEvent.click(screen.getByRole('button', { name: 'Map options' }))
    await userEvent.click(screen.getByRole('button', { name: 'Show my location' }))
    expect(onLayers).toHaveBeenCalled()
    expect(onLocate).toHaveBeenCalled()

    rerender(<MapControls onLayers={onLayers} onLocate={onLocate} geoStatus="locating" />)
    expect(screen.getByRole('button', { name: 'Show my location' })).toHaveAttribute('aria-busy', 'true')
    rerender(<MapControls onLayers={onLayers} onLocate={onLocate} geoStatus="denied" />)
    expect(screen.getByRole('button', { name: 'Location is off' })).toBeInTheDocument()
  })

  it('legend chip expands to the full legend', async () => {
    render(<LegendChip reports />)
    const chip = screen.getByRole('button', { name: /Lower.*High traffic risk/ })

    expect(screen.queryByRole('region', { name: 'Risk legend' })).toBeNull()
    await userEvent.click(chip)
    expect(chip).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('region', { name: 'Risk legend' })).toHaveTextContent('Community report')
  })

  it('status chip appears only for deviations', async () => {
    const onClick = vi.fn()
    const { rerender } = render(<StatusChip label={null} onClick={onClick} />)
    expect(screen.queryByRole('button')).toBeNull()

    rerender(<StatusChip label="☂ Wet · 10 PM" onClick={onClick} />)
    await userEvent.click(screen.getByRole('button', { name: /Wet · 10 PM/ }))
    expect(onClick).toHaveBeenCalled()
  })

  it('welcome toast states the scope and dismisses', async () => {
    const onDismiss = vi.fn()
    const { rerender } = render(<WelcomeToast dataThrough="2026-09-19" safetyAvailable={false} onDismiss={onDismiss} />)

    const toast = screen.getByRole('region', { name: 'Welcome to PathPro' })
    expect(toast).toHaveTextContent('See traffic risk before you walk into it.')
    expect(toast).toHaveTextContent('Traffic risk from crash history. Crash data through 2026-09-19.')
    rerender(<WelcomeToast dataThrough="2026-09-19" safetyAvailable onDismiss={onDismiss} />)
    expect(toast).toHaveTextContent(
      'Traffic risk, plus personal-safety signals: lighting, foot traffic, help points, and reported crimes against persons.',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(onDismiss).toHaveBeenCalled()
  })

  it('location notice explains the fallback and offers to pick a start', async () => {
    const onPick = vi.fn()
    render(<LocationNotice message="You're outside Atlanta — PathPro covers the City of Atlanta. Pick a starting point." onPickStart={onPick} />)

    expect(screen.getByRole('status')).toHaveTextContent("You're outside Atlanta")
    await userEvent.click(screen.getByRole('button', { name: 'Pick a start' }))
    expect(onPick).toHaveBeenCalled()
  })
})

describe('SuggestionCard (learned routines)', () => {
  it('offers a one-tap lower-risk trip and can be dismissed', async () => {
    const onGo = vi.fn()
    const onDismiss = vi.fn()
    render(<SuggestionCard suggestion={back} etaMin={18} onGo={onGo} onDismiss={onDismiss} />)

    const card = screen.getByRole('region', { name: 'Suggested trip' })
    expect(card).toHaveTextContent('Heading back to Home?')
    expect(card).toHaveTextContent('~18 min · lower-risk route one tap away')
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss suggestion' }))
    expect(onGo).toHaveBeenCalledWith(back)
    expect(onDismiss).toHaveBeenCalled()
  })

  it('only strong routine or return matches earn the home card', () => {
    expect(isStrongSuggestion(back)).toBe(true)
    expect(isStrongSuggestion({ ...back, kind: 'routine', score: 1.4 })).toBe(true)
    expect(isStrongSuggestion({ ...back, kind: 'routine', score: 0.4 })).toBe(false)
    expect(isStrongSuggestion({ ...back, kind: 'saved', score: 0.5 })).toBe(false)
    expect(isStrongSuggestion(undefined)).toBe(false)
  })

  it('words each kind of suggestion', () => {
    expect(suggestionHeadline({ ...back, kind: 'routine' })).toBe('Heading to Home?')
    expect(suggestionHeadline({ ...back, kind: 'saved' })).toBe('Go to Home?')
  })
})
