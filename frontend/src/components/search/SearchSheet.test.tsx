import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RoutineSuggestion } from '../../lib/routines'
import { SearchSheet, type SearchSheetProps } from './SearchSheet'

const HOME = { lat: 33.785, lon: -84.402, label: 'Home Park apt' }
const TECH_SQ = { lat: 33.7765, lon: -84.3893, label: 'Tech Square' }
const SUGGESTION: RoutineSuggestion = {
  from: null,
  to: TECH_SQ,
  reason: 'You usually walk here on Fridays around 10 PM',
  kind: 'routine',
  score: 1.2,
}

function jsonFetch(data: unknown) {
  return vi.fn(async () => new Response(JSON.stringify({ success: true, data }), { headers: { 'content-type': 'application/json' } }))
}

function setup(over: Partial<SearchSheetProps> = {}) {
  const props: SearchSheetProps = {
    field: 'to',
    welcome: false,
    onDismissWelcome: vi.fn(),
    note: null,
    suggestions: [SUGGESTION],
    saved: { home: HOME },
    recents: [{ lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' }],
    canUseLocation: false,
    onUseLocation: vi.fn(),
    onPick: vi.fn(),
    onPickSuggestion: vi.fn(),
    onEditSaved: vi.fn(),
    onClose: vi.fn(),
    ...over,
  }
  render(<SearchSheet {...props} />)
  return props
}

describe('SearchSheet (SRCH-01..04, Google-Maps-style search)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('opens as a dialog with an autofocused input and the four sections', () => {
    setup()

    expect(screen.getByRole('dialog', { name: 'Where to?' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Search places' })).toHaveFocus()
    for (const title of ['Suggested for now', 'Saved', 'Recent', 'Popular near Georgia Tech']) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    }
    expect(screen.getByText('You usually walk here on Fridays around 10 PM')).toBeInTheDocument()
  })

  it('picks from suggestions, saved, recents, and popular places', async () => {
    const user = userEvent.setup()
    const p = setup()

    await user.click(screen.getByRole('button', { name: /Tech Square.*Fridays/ }))
    await user.click(screen.getByRole('button', { name: /^Home:/ }))
    await user.click(within(screen.getByRole('list', { name: 'Recent' })).getByRole('button', { name: /Midtown MARTA/ }))
    await user.click(within(screen.getByRole('list', { name: 'Popular near Georgia Tech' })).getByRole('button', { name: 'Klaus Building' }))

    expect(p.onPickSuggestion).toHaveBeenCalledWith(SUGGESTION)
    expect(p.onPick).toHaveBeenNthCalledWith(1, HOME)
    expect(p.onPick).toHaveBeenNthCalledWith(2, expect.objectContaining({ label: 'Midtown MARTA' }))
    expect(p.onPick).toHaveBeenNthCalledWith(3, { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' })
  })

  it('sets an empty Work, edits Home with the icon or a long press', async () => {
    const user = userEvent.setup()
    const p = setup()

    await user.click(screen.getByRole('button', { name: 'Set Work' }))
    await user.click(screen.getByRole('button', { name: 'Change Home' }))
    fireEvent.contextMenu(screen.getByRole('button', { name: /^Home:/ }))

    expect(p.onEditSaved).toHaveBeenNthCalledWith(1, 'work')
    expect(p.onEditSaved).toHaveBeenNthCalledWith(2, 'home')
    expect(p.onEditSaved).toHaveBeenNthCalledWith(3, 'home')
  })

  it('autocompletes from the gazetteer and geocoder, flags out-of-coverage, and picks with Enter', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', jsonFetch([{ label: 'Stone Mountain Park', address: 'Stone Mountain, GA', lat: 33.8, lon: -84.1, in_coverage: false }]))
    const p = setup()
    const input = screen.getByRole('combobox', { name: 'Search places' })

    await user.type(input, 'north ave')
    expect(await screen.findByRole('option', { name: /North Ave MARTA/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Saved' })).toBeNull()
    await waitFor(() => expect(screen.getByText('Outside routing coverage')).toBeInTheDocument())
    await user.keyboard('{Enter}')

    expect(p.onPick).toHaveBeenCalledWith(expect.objectContaining({ label: 'North Ave MARTA' }))
  })

  it('says so when nothing matches (EC-03) and closes on Escape', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', jsonFetch([]))
    const p = setup()

    await user.type(screen.getByRole('combobox', { name: 'Search places' }), 'zzzz')
    expect(await screen.findByText('No match nearby. Try a building or street name.')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(p.onClose).toHaveBeenCalled()
  })

  it('choosing a start offers "Your location" and hides saved/suggestions', async () => {
    const user = userEvent.setup()
    const p = setup({ field: 'from', canUseLocation: true, note: "You're outside Atlanta — PathPro covers the City of Atlanta. Pick a starting point." })

    expect(screen.getByRole('dialog', { name: 'Choose a start' })).toBeInTheDocument()
    expect(screen.getByText(/You're outside Atlanta/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Suggested for now' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Your location' }))
    expect(p.onUseLocation).toHaveBeenCalled()
  })

  it('states the personal-safety scope in the welcome when the layer is available', () => {
    setup({ welcome: true, safetyAvailable: true })
    expect(screen.getByText(/Traffic risk, plus personal-safety signals/)).toBeInTheDocument()
  })

  it('shows a one-line welcome for first-time visitors', async () => {
    const user = userEvent.setup()
    const p = setup({ welcome: true, field: 'home' })

    expect(screen.getByRole('dialog', { name: 'Set Home' })).toBeInTheDocument()
    expect(screen.getByText(/Traffic risk from crash history\./)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Dismiss welcome' }))
    expect(p.onDismissWelcome).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Close search' }))
    expect(p.onClose).toHaveBeenCalled()
  })
})
