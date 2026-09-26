import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Area } from '../api/schemas'
import type { Routines } from '../hooks/useRoutines'
import { meta, routes, segment } from '../test/fixtures'
import { DesktopLayer, type DesktopLayerProps } from './DesktopLayer'
import { DetailLayer } from './DetailLayer'
import { HomeScreen } from './HomeScreen'
import { Panels, type PanelsProps } from './Panels'
import { RouteScreen } from './RouteScreen'

const noop = () => {}

describe('HomeScreen', () => {
  it('shows the search pill, a routine card, the status chip, the welcome, and the legend chip', async () => {
    const onGo = vi.fn()
    render(
      <HomeScreen
        suggestion={{ from: null, to: { lat: 1, lon: 2, label: 'Home' }, reason: 'Heading back?', kind: 'return', score: 2 }}
        etaMin={18}
        onGo={onGo}
        onDismissSuggestion={noop}
        onOpenSearch={noop}
        statusLabel="☂ Wet · 10 PM"
        onOpenOptions={noop}
        welcomeDataThrough="2026-09-19"
        onDismissWelcome={noop}
        reportsLegend={false}
      />,
    )

    expect(screen.getByRole('button', { name: 'Where to?' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Suggested trip' })).toHaveTextContent('Heading back to Home?')
    expect(screen.getByRole('button', { name: /Wet · 10 PM/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Welcome to PathPro' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onGo).toHaveBeenCalled()
  })

  it('shows only the pill and legend by default', () => {
    render(
      <HomeScreen
        suggestion={null}
        etaMin={null}
        onGo={noop}
        onDismissSuggestion={noop}
        onOpenSearch={noop}
        statusLabel={null}
        onOpenOptions={noop}
        welcomeDataThrough={null}
        onDismissWelcome={noop}
        reportsLegend={false}
      />,
    )
    expect(screen.getAllByRole('button')).toHaveLength(2)
  })
})

describe('RouteScreen', () => {
  const header = { from: null, to: { lat: 1, lon: 2, label: 'Midtown MARTA' }, onEditFrom: noop, onEditTo: noop, onSwap: noop, onBack: noop }

  it('asks for a start with a friendly notice while routes are pending', async () => {
    const onPickStart = vi.fn()
    render(<RouteScreen header={header} notice="You're outside Atlanta — PathPro covers the City of Atlanta. Pick a starting point." onPickStart={onPickStart} loading sheet={null} />)

    expect(screen.getByRole('region', { name: 'Finding routes' })).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Pick a start' }))
    expect(onPickStart).toHaveBeenCalled()
  })

  it('renders the route sheet when routes arrive', () => {
    const sheet = {
      routes: routes(),
      selected: 'pp' as const,
      onSelect: noop,
      explanation: null,
      onStart: noop,
      onPreview: noop,
      startNote: null,
      onListen: noop,
      onShare: noop,
      shareStatus: null,
      onFocusSegment: noop,
      onSelectSegment: noop,
    }
    render(<RouteScreen header={header} notice={null} onPickStart={noop} loading={false} sheet={sheet} />)
    expect(screen.getByRole('region', { name: 'Route comparison' })).toBeInTheDocument()
  })
})

describe('DetailLayer', () => {
  afterEach(() => vi.restoreAllMocks())

  const area: Area = {
    cell: '8844c0a305fffff',
    lat: 33.77,
    lon: -84.39,
    score: 70,
    band: 'Elevated',
    confidence: 'medium',
    baseline_points: 50,
    factors: [],
    remainder_points: 20,
    crashes: 12,
    ped_crashes: 2,
    period: '2020-2024',
    in_street_coverage: false,
    condition_used: { cond: 'dry', source: 'override', label: 'Dry' },
    at: '2026-09-25T22:30:00-04:00',
  }

  it('shows a City Pulse area card', () => {
    render(<DetailLayer area={area} detail={null} cond="dry" onCloseArea={noop} onCloseDetail={noop} onAbout={noop} onReported={noop} />)
    expect(screen.getByRole('region', { name: 'Area traffic risk' })).toBeInTheDocument()
  })

  it('shows a street sheet with its explanation, falling back to a local summary', async () => {
    vi.spyOn(api, 'explainSegment').mockRejectedValue(new Error('down'))
    vi.spyOn(api, 'segmentHourly').mockRejectedValue(new Error('down'))
    vi.spyOn(api, 'segmentReports').mockResolvedValue([])
    vi.stubGlobal('matchMedia', () => ({ matches: true }))
    render(<DetailLayer area={null} detail={segment()} cond="wet" onCloseArea={noop} onCloseDetail={noop} onAbout={noop} onReported={noop} />)

    await waitFor(() => expect(screen.getByTestId('segment-explanation')).toHaveTextContent('Fifth Street Northwest scores 96'))
    vi.unstubAllGlobals()
  })

  it('renders nothing without a selection', () => {
    const { container } = render(<DetailLayer area={null} detail={null} cond="wet" onCloseArea={noop} onCloseDetail={noop} onAbout={noop} onReported={noop} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('Panels', () => {
  const routines: Routines = { suggestions: [], recents: [], saved: {}, record: vi.fn(), setSaved: vi.fn(), clear: vi.fn() }
  const actions = {
    closePanel: vi.fn(),
    setPanel: vi.fn(),
    searchNote: () => null,
    startFromMyLocation: vi.fn(),
    pickPlace: vi.fn(),
    planSuggestion: vi.fn(),
    editSaved: vi.fn(),
  } as unknown as PanelsProps['actions']
  const options: PanelsProps['options'] = {
    cond: 'live',
    condLabel: 'Live',
    onCond: noop,
    depart: 'now',
    onDepart: noop,
    cityAvailable: false,
    cityMode: false,
    onCityMode: noop,
    timeline: { hour: 1, onHour: noop, playing: false, onTogglePlay: noop, medians: [], lights: [], condLabel: 'Dry', day: 'weekday', onDay: noop },
    showReportsLegend: false,
  }
  const base = { meta: meta(), actions, routines, canUseLocation: true, welcome: false, onDismissWelcome: noop, options }

  it('renders one sheet at a time', async () => {
    const { rerender } = render(<Panels {...base} panel={null} />)
    expect(screen.queryByRole('dialog')).toBeNull()

    rerender(<Panels {...base} panel={{ kind: 'search', field: 'to' }} />)
    await userEvent.click(screen.getByRole('button', { name: 'Klaus Building' }))
    expect(actions.pickPlace).toHaveBeenCalledWith('to', { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' })

    rerender(<Panels {...base} panel={{ kind: 'options' }} />)
    await userEvent.click(screen.getByRole('button', { name: 'About PathPro' }))
    expect(actions.setPanel).toHaveBeenCalledWith({ kind: 'about' })

    rerender(<Panels {...base} panel={{ kind: 'about' }} />)
    expect(screen.getByRole('dialog', { name: 'How PathPro works' })).toBeInTheDocument()
  })
})

describe('DesktopLayer (≥1024 px)', () => {
  const timeline = { hour: 22, onHour: noop, playing: false, onTogglePlay: noop, medians: [], lights: [], condLabel: 'Wet', day: 'friday' as const, onDay: noop }
  const base: DesktopLayerProps = {
    screen: 'home',
    home: {
      suggestion: null,
      etaMin: null,
      onGo: noop,
      onDismissSuggestion: noop,
      search: { field: 'to', suggestions: [], saved: {}, recents: [], canUseLocation: false, onUseLocation: noop, onPick: noop, onPickSuggestion: noop, onEditSaved: noop },
      options: { cond: 'live', condLabel: 'Live', onCond: noop, depart: 'now', onDepart: noop, cityAvailable: false, cityMode: false, onCityMode: noop, showReportsLegend: false, onClearHistory: noop },
      onAbout: noop,
    },
    route: { header: { from: null, to: { lat: 1, lon: 2, label: 'Midtown MARTA' }, onEditFrom: noop, onEditTo: noop, onSwap: noop, onBack: noop }, notice: null, onPickStart: noop, loading: true, sheet: null },
    destination: 'Midtown MARTA',
    timeline,
    welcomeDataThrough: '2026-09-19',
    onDismissWelcome: noop,
  }

  it('home: sidebar, docked Risk Tides, and the welcome toast', () => {
    render(<DesktopLayer {...base} />)
    expect(screen.getByRole('complementary', { name: 'PathPro' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Risk Tides timeline' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Welcome to PathPro' })).toBeInTheDocument()
  })

  it('route: the trip panel moves into the sidebar; navigation hides Risk Tides', () => {
    const { rerender } = render(<DesktopLayer {...base} screen="route" />)
    expect(screen.getByRole('region', { name: 'Trip' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Welcome to PathPro' })).toBeNull()

    rerender(<DesktopLayer {...base} screen="nav" />)
    expect(screen.getByText(/Walking to Midtown MARTA/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Risk Tides timeline' })).toBeNull()
  })
})
