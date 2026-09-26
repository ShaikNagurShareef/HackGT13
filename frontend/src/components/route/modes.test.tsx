import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ModeInfo } from '../../api/schemas'
import { modeOptions } from '../../lib/modes'
import { route, routes } from '../../test/fixtures'
import { Legend } from '../Controls'
import { NavigationView } from '../nav/NavigationView'
import { OptionsContent, type OptionsContentProps } from '../options/OptionsContent'
import { HandoffCard } from './HandoffCard'
import { ModeTabs } from './ModeTabs'
import { RouteSheet, type RouteSheetProps } from './RouteSheet'

const BIKE: ModeInfo = { key: 'bike', label: 'Bike', available: true, speed_kmh: 15, network: 'ride', static_prefix: 'ride_' }
const OPTIONS = modeOptions([BIKE])
const NORTH_AVE = { name: 'North Ave', lat: 33.7716, lon: -84.3872 }
const ARTS_CENTER = { name: 'Arts Center', lat: 33.7893, lon: -84.3876 }

describe('ModeTabs', () => {
  it('shows Walk · Bike · E-bike · Scooter with durations; unavailable modes are disabled, not hidden', async () => {
    const onSelect = vi.fn()
    render(
      <ModeTabs
        options={OPTIONS}
        selected="walk"
        onSelect={onSelect}
        durations={{ walk: { minutes: 34, estimated: false }, bike: { minutes: 12, estimated: true } }}
      />,
    )
    const group = screen.getByRole('group', { name: 'Travel mode' })
    const walk = within(group).getByRole('button', { name: /Walk/ })
    const bike = within(group).getByRole('button', { name: /^Bike/ })
    const scooter = within(group).getByRole('button', { name: /Scooter/ })

    expect(walk).toHaveAttribute('aria-pressed', 'true')
    expect(walk).toHaveTextContent('34 min')
    expect(bike).toHaveTextContent('~12 min')
    expect(scooter).toHaveAttribute('aria-disabled', 'true')
    expect(scooter).toHaveAccessibleDescription('Coming soon in this area')
    expect(within(group).getByRole('button', { name: /E-bike/ })).toHaveAttribute('aria-disabled', 'true')

    await userEvent.click(bike)
    await userEvent.click(scooter)
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('bike')
    expect(screen.getByRole('status')).toHaveTextContent('Scooter: Coming soon in this area')
  })

  it('has a compact icon-only form for search, still labelled', () => {
    render(<ModeTabs options={OPTIONS} selected="bike" onSelect={vi.fn()} compact />)

    expect(screen.getByRole('button', { name: 'Bike' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Walk' })).toHaveAttribute('aria-pressed', 'false')
  })
})

describe('HandoffCard (MARTA hand-off and ride suggestion)', () => {
  it('offers MARTA with both walks and plans the walk to the station on tap', async () => {
    const onPlanStation = vi.fn()
    const onTryMode = vi.fn()
    render(
      <HandoffCard
        marta={{ board: { station: NORTH_AVE, walkMin: 8 }, alight: { station: ARTS_CENTER, walkMin: 6 } }}
        ride={{ mode: 'bike', minutes: 14 }}
        onPlanStation={onPlanStation}
        onTryMode={onTryMode}
      />,
    )
    const card = screen.getByRole('region', { name: 'Faster options' })

    expect(card).toHaveTextContent('Faster with MARTA: walk 8 min to North Ave station')
    expect(card).toHaveTextContent('…then from Arts Center station, 6 min walk')
    await userEvent.click(within(card).getByRole('button', { name: /Faster with MARTA/ }))
    await userEvent.click(within(card).getByRole('button', { name: 'Try Bike: ~14 min' }))
    expect(onPlanStation).toHaveBeenCalledWith({ lat: 33.7716, lon: -84.3872, label: 'North Ave station' })
    expect(onTryMode).toHaveBeenCalledWith('bike')
  })

  it('renders nothing without a suggestion', () => {
    const { container } = render(<HandoffCard marta={null} ride={null} onPlanStation={vi.fn()} onTryMode={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})

function sheetProps(over: Partial<RouteSheetProps> = {}): RouteSheetProps {
  return {
    routes: routes(),
    selected: 'pp',
    onSelect: vi.fn(),
    explanation: null,
    onStart: vi.fn(),
    onPreview: vi.fn(),
    startNote: null,
    onListen: vi.fn(),
    onShare: vi.fn(),
    shareStatus: null,
    onFocusSegment: vi.fn(),
    onSelectSegment: vi.fn(),
    ...over,
  }
}

describe('RouteSheet in a ride mode', () => {
  it('headlines the ride and previews the ride', () => {
    const ride = routes({ mode: 'bike', exposure_reduction_pct: 38, pathpro: route({ duration_s: 840 }) })
    render(<RouteSheet {...sheetProps({ routes: ride })} />)

    expect(screen.getByTestId('route-pp')).toHaveTextContent('14 min ride · 38% less traffic risk')
    expect(screen.getByRole('button', { name: /Preview ride/ })).toBeInTheDocument()
    expect(screen.getByTestId('route-pp')).not.toHaveTextContent(/\bsafe/i)
  })

  it('shows the hand-off card in the peek when given', () => {
    render(
      <RouteSheet
        {...sheetProps({
          handoff: { marta: null, ride: { mode: 'bike', minutes: 14 }, onPlanStation: vi.fn(), onTryMode: vi.fn() },
        })}
      />,
    )
    expect(screen.getByRole('button', { name: 'Try Bike: ~14 min' })).toBeInTheDocument()
  })
})

describe('mode-aware chrome', () => {
  it('navigation badges a ride preview', () => {
    render(
      <NavigationView
        instruction={null}
        mode="preview"
        travel="scooter"
        remainingS={600}
        remainingM={2000}
        arrival="10:40 PM"
        arrived={false}
        destination="Midtown"
        onEnd={vi.fn()}
        onDone={vi.fn()}
      />,
    )
    expect(screen.getByText('Preview ride')).toBeInTheDocument()
  })

  it('titles the legend for the network on the map', () => {
    render(<Legend title="Traffic risk to people on bikes & scooters" />)
    expect(screen.getByRole('region', { name: 'Risk legend' })).toHaveTextContent('Traffic risk to people on bikes & scooters')
  })

  it('options: the walk-only preference hides for rides and personal safety is labelled walking', () => {
    const props: OptionsContentProps = {
      cond: 'live',
      condLabel: 'Live',
      onCond: vi.fn(),
      depart: 'now',
      onDepart: vi.fn(),
      cityAvailable: false,
      mapMode: 'streets',
      onMapMode: vi.fn(),
      safety: {
        legend: { meta: null, hour: 21, layers: { lit: true, busy: false, help: false, crimes: false }, tooWide: false },
        onLayers: vi.fn(),
        hasLit: true,
        hasBusy: true,
        helpPoints: [],
        onPickHelp: vi.fn(),
        prefer: 'lower_traffic_risk',
        onPrefer: vi.fn(),
      },
      showReportsLegend: false,
      onClearHistory: vi.fn(),
      travelMode: 'bike',
    }
    render(<OptionsContent {...props} />)

    expect(screen.queryByRole('group', { name: 'Route preference' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Personal safety (walking)' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Risk legend' })).toHaveTextContent('Traffic risk to people on bikes & scooters')
  })
})
