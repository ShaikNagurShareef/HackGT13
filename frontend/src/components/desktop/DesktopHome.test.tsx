import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DesktopHome, type DesktopHomeProps } from './DesktopHome'

function setup(over: Partial<DesktopHomeProps> = {}) {
  const props: DesktopHomeProps = {
    suggestion: null,
    etaMin: null,
    onGo: vi.fn(),
    onDismissSuggestion: vi.fn(),
    search: {
      field: 'to',
      suggestions: [],
      saved: {},
      recents: [],
      canUseLocation: false,
      onUseLocation: vi.fn(),
      onPick: vi.fn(),
      onPickSuggestion: vi.fn(),
      onEditSaved: vi.fn(),
    },
    options: {
      cond: 'live',
      condLabel: 'Live · dry',
      onCond: vi.fn(),
      depart: 'now',
      onDepart: vi.fn(),
      cityAvailable: true,
      cityMode: false,
      onCityMode: vi.fn(),
      showReportsLegend: false,
      onClearHistory: vi.fn(),
    },
    onAbout: vi.fn(),
    ...over,
  }
  render(<DesktopHome {...props} />)
  return props
}

describe('DesktopHome (persistent sidebar)', () => {
  it('leads with the brand and tagline, then an inline search with its sections', () => {
    setup()
    const sidebar = screen.getByRole('complementary', { name: 'PathPro' })

    expect(within(sidebar).getByRole('heading', { level: 1, name: 'PathPro' })).toBeInTheDocument()
    expect(sidebar).toHaveTextContent('See traffic risk before you walk into it.')
    expect(within(sidebar).getByRole('combobox', { name: 'Search places' })).toBeInTheDocument()
    expect(within(sidebar).getByRole('heading', { name: 'Popular near Georgia Tech' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('picks a place inline', async () => {
    const p = setup()
    await userEvent.click(screen.getByRole('button', { name: 'Tech Square' }))
    expect(p.search.onPick).toHaveBeenCalledWith({ lat: 33.7765, lon: -84.3893, label: 'Tech Square' })
  })

  it('keeps conditions, departure, map mode, legend, privacy, and About in view (no Risk Tides: it docks on the map)', async () => {
    const p = setup()

    await userEvent.click(screen.getByRole('button', { name: /Wet/ }))
    await userEvent.click(screen.getByRole('button', { name: '+1 h' }))
    await userEvent.click(screen.getByRole('button', { name: 'City Pulse' }))
    await userEvent.click(screen.getByRole('button', { name: 'Clear history' }))
    await userEvent.click(screen.getByRole('button', { name: 'About PathPro' }))

    expect(p.options.onCond).toHaveBeenCalledWith('wet')
    expect(p.options.onDepart).toHaveBeenCalledWith('+1h')
    expect(p.options.onCityMode).toHaveBeenCalledWith(true)
    expect(p.options.onClearHistory).toHaveBeenCalled()
    expect(p.onAbout).toHaveBeenCalled()
    expect(screen.getByRole('region', { name: 'Risk legend' })).toBeInTheDocument()
    expect(screen.queryByRole('slider', { name: 'Hour of day' })).toBeNull()
  })

  it('shows a learned routine at the top', () => {
    setup({ suggestion: { from: null, to: { lat: 1, lon: 2, label: 'Home' }, reason: 'Heading back?', kind: 'return', score: 2 }, etaMin: 12 })
    expect(screen.getByRole('region', { name: 'Suggested trip' })).toHaveTextContent('Heading back to Home?')
  })
})
