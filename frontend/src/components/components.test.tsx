import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { meta, routes, segment } from '../test/fixtures'
import { About, FirstRun } from './About'
import { ComparisonCard, templateSummary } from './ComparisonCard'
import { ConditionsChip, DepartPicker, Legend, TrustNote } from './Controls'
import { FactorBars, ScoreDial, SegmentSheet } from './SegmentSheet'
import { Timeline, hourAt, positionOf } from './Timeline'

describe('ComparisonCard (RTE-04)', () => {
  it('shows time cost next to benefit and both routes', () => {
    render(<ComparisonCard routes={routes()} explanation={null} onClear={vi.fn()} onSelectSegment={vi.fn()} />)

    const card = screen.getByRole('region', { name: 'Route comparison' })
    expect(card).toHaveTextContent('+4.3 min, 49% less traffic-risk exposure')
    expect(within(screen.getByTestId('route-pp')).getByText('83')).toBeInTheDocument()
    expect(within(screen.getByTestId('route-fast')).getByText('93')).toBeInTheDocument()
    expect(card).toHaveTextContent('Both routes use Fifth Street Northwest')
    expect(screen.getByRole('note')).toHaveTextContent('Always stay alert')
  })

  it('uses the grounded explanation when present, template otherwise', () => {
    const { rerender } = render(
      <ComparisonCard routes={routes()} explanation={null} onClear={vi.fn()} onSelectSegment={vi.fn()} />,
    )
    expect(screen.getByTestId('route-explanation')).toHaveTextContent('by avoiding Peachtree Place Northwest')

    rerender(<ComparisonCard routes={routes()} explanation="LLM text" onClear={vi.fn()} onSelectSegment={vi.fn()} />)
    expect(screen.getByTestId('route-explanation')).toHaveTextContent('LLM text')
  })

  it('renders the single-route case positively (RTE-03)', () => {
    const single = routes({ pathpulse: null, time_cost_min: null, exposure_reduction_pct: null, unavoidable: [] })
    render(<ComparisonCard routes={single} explanation={null} onClear={vi.fn()} onSelectSegment={vi.fn()} />)

    expect(screen.getAllByText('The fastest route is already the lower-risk option.')).toHaveLength(1)
    expect(screen.queryByTestId('route-pp')).toBeNull()
    expect(templateSummary(single)).toContain('busiest stretch is Fifth Street Northwest')
  })

  it('selects a hot segment and clears', async () => {
    const onSelect = vi.fn()
    const onClear = vi.fn()
    render(<ComparisonCard routes={routes()} explanation={null} onClear={onClear} onSelectSegment={onSelect} />)

    const hotList = screen.getByLabelText('Highest-risk stretches on the fastest route')
    await userEvent.click(within(hotList).getByRole('button', { name: /Peachtree Place Northwest/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Clear route' }))

    expect(onSelect).toHaveBeenCalledWith(12)
    expect(onClear).toHaveBeenCalled()
  })

  it('lists avoided stretches, listen, and preview-walk controls (RTE-06, VOX-01/05)', async () => {
    const onFocus = vi.fn()
    const onListen = vi.fn()
    const onStart = vi.fn()
    render(
      <ComparisonCard
        routes={routes()}
        explanation={null}
        onClear={vi.fn()}
        onSelectSegment={vi.fn()}
        onFocusSegment={onFocus}
        onListen={onListen}
        walk={{ active: false, progress: 0, banner: 'In 60 meters, Spring Street has high traffic risk.', onStart, onStop: vi.fn() }}
      />,
    )

    const avoided = screen.getByLabelText('High-risk stretches the PathPulse route avoids')
    expect(avoided).toHaveTextContent('Avoids 1 high-risk stretch')
    await userEvent.click(within(avoided).getByRole('button', { name: /Peachtree Place Northwest/ }))
    await userEvent.click(screen.getByRole('button', { name: /Listen/ }))
    await userEvent.click(screen.getByRole('button', { name: /Preview walk/ }))

    expect(onFocus).toHaveBeenCalledWith(12)
    expect(onListen).toHaveBeenCalled()
    expect(onStart).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Spring Street')
  })
})

describe('SegmentSheet (EXP-01..05)', () => {
  it('factor bars sum to the displayed score', () => {
    render(<FactorBars detail={segment()} />)

    const points = screen.getAllByRole('listitem').slice(0, -1).map((li) => li.querySelector('.factor-points')?.textContent ?? '0')
    const sum = points.reduce((s, p) => s + Number(p.replace('−', '-').replace('+', '')), 0)
    expect(sum).toBe(96)
  })

  it('shows dial, confidence, history, and the methodology link', async () => {
    const onAbout = vi.fn()
    render(<SegmentSheet detail={segment({ confidence: 'limited' })} explanation="Because." onClose={vi.fn()} onAbout={onAbout} />)

    expect(screen.getByRole('img', { name: 'Traffic risk 96 of 100, High' })).toBeInTheDocument()
    expect(screen.getByText('Limited data')).toBeInTheDocument()
    expect(screen.getByText('107')).toBeInTheDocument()
    expect(screen.getAllByText('16%')).toHaveLength(2)
    expect(screen.getByText(/estimate based mostly on street characteristics/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'How is this calculated?' }))
    expect(onAbout).toHaveBeenCalled()
  })

  it('shows a loading line until the explanation arrives', () => {
    render(<SegmentSheet detail={segment()} explanation={null} onClose={vi.fn()} onAbout={vi.fn()} />)
    expect(screen.getByTestId('segment-explanation')).toHaveTextContent('Loading explanation…')
  })

  it('clamps the dial', () => {
    render(<ScoreDial score={140} band="High" />)
    expect(screen.getByRole('img')).toHaveAccessibleName('Traffic risk 140 of 100, High')
  })
})

describe('Timeline (TIDE-01..05)', () => {
  const props = {
    hour: 22,
    onHour: vi.fn(),
    playing: false,
    onTogglePlay: vi.fn(),
    medians: Array.from({ length: 24 }, (_, h) => h * 2),
    lights: Array.from({ length: 24 }, (_, h) => (h > 19 || h < 7 ? 'dark' : 'day')),
    condLabel: 'Wet',
    day: 'friday' as const,
    onDay: vi.fn(),
  }

  it('maps slider positions from 6 AM', () => {
    expect(hourAt(0)).toBe(6)
    expect(hourAt(23)).toBe(5)
    expect(positionOf(22)).toBe(16)
  })

  it('announces hour, condition, and citywide median', () => {
    render(<Timeline {...props} />)
    expect(screen.getByRole('slider', { name: 'Hour of day' })).toHaveAttribute(
      'aria-valuetext',
      '10 PM, wet, citywide median risk 44',
    )
  })

  it('changes hour, day, and play state', async () => {
    const onHour = vi.fn()
    const onDay = vi.fn()
    const onTogglePlay = vi.fn()
    render(<Timeline {...props} onHour={onHour} onDay={onDay} onTogglePlay={onTogglePlay} playing />)

    fireEvent.change(screen.getByRole('slider'), { target: { value: '0' } })
    await userEvent.click(screen.getByRole('button', { name: 'Saturday' }))
    await userEvent.click(screen.getByRole('button', { name: 'Pause Risk Tides' }))

    expect(onHour).toHaveBeenCalledWith(6)
    expect(onDay).toHaveBeenCalledWith('saturday')
    expect(onTogglePlay).toHaveBeenCalled()
  })
})

describe('Controls', () => {
  it('switches conditions and departure', async () => {
    const onCond = vi.fn()
    const onDepart = vi.fn()
    render(
      <>
        <ConditionsChip cond="live" label="Rain · live forecast" onChange={onCond} />
        <DepartPicker value="now" onChange={onDepart} />
      </>,
    )

    expect(screen.getByRole('button', { name: 'Live' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: /Wet/ }))
    await userEvent.click(screen.getByRole('button', { name: '+15 min' }))
    fireEvent.change(screen.getByLabelText('Custom departure (Atlanta time)'), { target: { value: '2026-09-26T01:00' } })

    expect(onCond).toHaveBeenCalledWith('wet')
    expect(onDepart).toHaveBeenNthCalledWith(1, '+15m')
    expect(onDepart).toHaveBeenNthCalledWith(2, '2026-09-26T01:00')
  })

  it('renders a fixed numeric legend and trust note', () => {
    render(
      <>
        <Legend />
        <TrustNote />
      </>,
    )
    const legend = screen.getByRole('region', { name: 'Risk legend' })
    for (const label of ['Lower', 'Moderate', 'Elevated', 'High']) expect(legend).toHaveTextContent(label)
    expect(screen.getByRole('note')).toHaveTextContent('Traffic risk estimate')
  })
})

describe('About and first run (TRUST-01..03)', () => {
  it('first run states the traffic-only scope and dismisses', async () => {
    const onDone = vi.fn()
    render(<FirstRun dataThrough="2026-09-19" onDone={onDone} />)

    expect(screen.getByRole('dialog')).toHaveTextContent('Traffic risk only — not crime or personal safety')
    expect(screen.getByRole('dialog')).toHaveTextContent('Crash data through 2026-09-19')
    await userEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(onDone).toHaveBeenCalled()
  })

  it('about shows holdout metrics, limitations, and tap-to-call', async () => {
    const onClose = vi.fn()
    render(<About meta={meta()} onClose={onClose} />)

    const dialog = screen.getByRole('dialog', { name: 'How PathPulse works' })
    expect(dialog).toHaveTextContent('46%')
    expect(dialog).toHaveTextContent('37%–56%')
    expect(screen.getByRole('link', { name: 'Georgia Tech Police 404-894-2500' })).toHaveAttribute('href', 'tel:4048942500')
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })
})
