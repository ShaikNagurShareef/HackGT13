import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FAIRNESS_NOTE, DEFAULT_SAFETY_LAYERS } from '../../lib/safety'
import { helpPoint, safetyHex, safetyMeta } from '../../test/fixtures'
import { AboutSafety } from './AboutSafety'
import { RoutePreferencePicker } from './RoutePreferencePicker'
import { SafetyLayerToggles } from './SafetyLayerToggles'
import { SafetyLegend } from './SafetyLegend'
import { SafetyHelpList } from './SafetyHelpList'
import { SafetyLegendChip } from './SafetyLegendChip'
import { SafetyPickCard } from './SafetyPickCard'
import { SafetyRouteNote } from './SafetyRouteNote'

const ALL_ON = { crimes: true, lit: true, busy: true, help: true }

describe('SafetyLegend', () => {
  it('shows the day part for the Risk Tides hour, the crime bands in words, and the fairness note', () => {
    render(<SafetyLegend meta={safetyMeta()} hour={21} layers={DEFAULT_SAFETY_LAYERS} tooWide={false} />)
    const legend = screen.getByRole('region', { name: 'Personal safety legend' })

    expect(legend).toHaveTextContent('Evening · 5 PM–10 PM')
    expect(legend).toHaveTextContent('Reported crimes against persons, last 12 months')
    for (const label of ['Fewer reports', 'Typical', 'More reports']) expect(legend).toHaveTextContent(label)
    expect(legend).toHaveTextContent(FAIRNESS_NOTE)
    expect(legend).toHaveTextContent('Blue-light emergency phone')
  })

  it('lists sources with safe links and the data date', () => {
    const meta = safetyMeta({
      sources: [
        { name: 'Atlanta Police Department Open Data', url: 'https://opendata.atlantapd.org/', license: 'Public records' },
        { name: 'Sketchy link', url: 'javascript:alert(1)', license: 'n/a' },
      ],
    })
    render(<SafetyLegend meta={meta} hour={9} layers={DEFAULT_SAFETY_LAYERS} tooWide={false} />)

    expect(screen.getByRole('link', { name: 'Atlanta Police Department Open Data' })).toHaveAttribute('href', 'https://opendata.atlantapd.org/')
    expect(screen.queryByRole('link', { name: 'Sketchy link' })).toBeNull()
    expect(screen.getByText(/data through 2026-09-19/)).toBeInTheDocument()
  })

  it('drops the crime key (and its note) when that layer is off, and keys the overlays that are on', () => {
    render(<SafetyLegend meta={safetyMeta()} hour={9} layers={{ ...ALL_ON, crimes: false }} tooWide={false} compact />)
    const legend = screen.getByRole('region', { name: 'Personal safety legend' })

    expect(legend).not.toHaveTextContent('More reports')
    expect(legend).not.toHaveTextContent(FAIRNESS_NOTE)
    expect(legend).toHaveTextContent('Well-lit streets')
    expect(legend).toHaveTextContent('Busier streets')
    expect(screen.queryByText(/Sources/)).toBeNull()
  })

  it('asks to zoom in when the map is too wide to load', () => {
    render(<SafetyLegend meta={null} hour={9} layers={DEFAULT_SAFETY_LAYERS} tooWide />)
    expect(screen.getByRole('status')).toHaveTextContent('Zoom in to see the personal safety layer.')
  })
})

describe('SafetyLayerToggles', () => {
  it('toggles each layer with an accessible switch', async () => {
    const onChange = vi.fn()
    render(<SafetyLayerToggles layers={DEFAULT_SAFETY_LAYERS} onChange={onChange} hasLit hasBusy />)

    const crimes = screen.getByRole('checkbox', { name: 'Reported crimes against persons' })
    expect(crimes).toBeChecked()
    await userEvent.click(crimes)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Well-lit streets' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Help points' }))

    expect(onChange).toHaveBeenNthCalledWith(1, { ...DEFAULT_SAFETY_LAYERS, crimes: false })
    expect(onChange).toHaveBeenNthCalledWith(2, { ...DEFAULT_SAFETY_LAYERS, lit: true })
    expect(onChange).toHaveBeenNthCalledWith(3, { ...DEFAULT_SAFETY_LAYERS, help: false })
  })

  it('hides lighting and foot-traffic toggles when the data has none', () => {
    render(<SafetyLayerToggles layers={DEFAULT_SAFETY_LAYERS} onChange={vi.fn()} hasLit={false} hasBusy={false} />)
    expect(screen.queryByRole('checkbox', { name: 'Well-lit streets' })).toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'Busier streets' })).toBeNull()
  })
})

describe('RoutePreferencePicker', () => {
  it('offers lower traffic risk (default) or well-lit and busier, and says crime is never used', async () => {
    const onChange = vi.fn()
    render(<RoutePreferencePicker value="lower_traffic_risk" onChange={onChange} />)
    const group = screen.getByRole('group', { name: 'Route preference' })

    expect(within(group).getByRole('button', { name: 'Lower traffic risk' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(group).getByRole('button', { name: /Well-lit & busier/ }))
    expect(onChange).toHaveBeenCalledWith('lit_and_busy')
    expect(screen.getByText(/Reported crimes are never used to choose routes/)).toBeInTheDocument()
  })
})

describe('SafetyPickCard', () => {
  it('describes a tapped area with the fairness note', async () => {
    const onClose = vi.fn()
    render(<SafetyPickCard pick={{ kind: 'hex', hex: safetyHex() }} dayLabel="Evening" onClose={onClose} />)
    const card = screen.getByRole('region', { name: 'This area · Evening' })

    expect(card).toHaveTextContent('6 reported crimes against persons in the last 12 months (typical for the city)')
    expect(card).toHaveTextContent('78% well-lit')
    expect(card).toHaveTextContent(FAIRNESS_NOTE)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('names a help point and keeps 911 one tap away', () => {
    render(<SafetyPickCard pick={{ kind: 'help', point: helpPoint() }} dayLabel={null} onClose={vi.fn()} />)
    const card = screen.getByRole('region', { name: 'Help point' })

    expect(card).toHaveTextContent('Blue-light emergency phone · Tech Green')
    expect(within(card).getByRole('link', { name: 'Call 911' })).toHaveAttribute('href', 'tel:911')
  })
})

describe('SafetyLegendChip (phone home)', () => {
  it('starts open so the fairness note is visible, and collapses on tap', async () => {
    render(<SafetyLegendChip meta={safetyMeta()} hour={21} layers={DEFAULT_SAFETY_LAYERS} tooWide={false} />)
    const toggle = screen.getByRole('button', { name: /Personal safety legend/ })

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(FAIRNESS_NOTE)).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-controls', screen.getByRole('region', { name: 'Personal safety legend' }).id)
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText(FAIRNESS_NOTE)).toBeNull()
  })
})

describe('SafetyHelpList (keyboard and screen-reader access to help points)', () => {
  it('lists help points in view, blue-light phones first, and opens one', async () => {
    const onPick = vi.fn()
    const police = helpPoint({ kind: 'police', name: 'GT Police' })
    const phone = helpPoint()
    render(<SafetyHelpList points={[police, phone]} onPick={onPick} />)
    const list = screen.getByRole('list', { name: 'Help points in view' })
    const buttons = within(list).getAllByRole('button')

    expect(buttons.map((b) => b.textContent)).toEqual(['Blue-light emergency phone · Tech Green', 'Police station · GT Police'])
    await userEvent.click(buttons[1])
    expect(onPick).toHaveBeenCalledWith({ kind: 'help', point: police })
  })

  it('caps the list and says how many more are on the map', () => {
    const points = Array.from({ length: 10 }, (_, i) => helpPoint({ name: `Phone ${i}` }))
    render(<SafetyHelpList points={points} onPick={vi.fn()} />)
    expect(screen.getAllByRole('button')).toHaveLength(6)
    expect(screen.getByText('4 more on the map')).toBeInTheDocument()
  })

  it('renders nothing when no help points are in view', () => {
    const { container } = render(<SafetyHelpList points={[]} onPick={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('SafetyRouteNote (phone route screen)', () => {
  it('says the shading is informational and opens the legend', async () => {
    const onOpen = vi.fn()
    render(<SafetyRouteNote onOpenLegend={onOpen} />)

    expect(screen.getByText(/never used to choose routes/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Legend' }))
    expect(onOpen).toHaveBeenCalled()
  })
})

describe('AboutSafety', () => {
  it('explains how the layer works, its limits, sources, and that routing never uses crime', () => {
    render(<AboutSafety meta={safetyMeta()} />)

    expect(screen.getByRole('heading', { name: 'Personal safety layer — how it works and its limits' })).toBeInTheDocument()
    expect(screen.getByText(FAIRNESS_NOTE)).toBeInTheDocument()
    expect(screen.getByText(/never used to choose or rank routes/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'OpenStreetMap' })).toBeInTheDocument()
    expect(screen.getByText(/Aggravated assault, Robbery/)).toBeInTheDocument()
  })
})
