import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Area } from '../api/schemas'
import { meta, segment } from '../test/fixtures'
import { About } from './About'
import { AreaCard } from './AreaCard'
import { ConditionsChip, DepartPicker, Legend, TrustNote } from './Controls'
import { FactorBars, ScoreDial, SegmentSheet } from './SegmentSheet'
import { Timeline, hourAt, positionOf } from './Timeline'

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

  it('offers "Ask about this street" only when Ask PathPro is available', async () => {
    const onAsk = vi.fn()
    const { rerender } = render(<SegmentSheet detail={segment()} explanation="Because." onClose={vi.fn()} onAbout={vi.fn()} onAsk={onAsk} />)

    await userEvent.click(screen.getByRole('button', { name: 'Ask about this street' }))
    expect(onAsk).toHaveBeenCalledTimes(1)

    rerender(<SegmentSheet detail={segment()} explanation="Because." onClose={vi.fn()} onAbout={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Ask about this street' })).toBeNull()
  })
})

describe('AreaCard (CITY-02)', () => {
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
    in_street_coverage: true,
    condition_used: { cond: 'dry', source: 'override', label: 'Dry' },
    at: '2026-09-25T22:30:00-04:00',
  }

  it('offers "Ask about this area" only when Ask PathPro is available', async () => {
    const onAsk = vi.fn()
    const { rerender } = render(<AreaCard area={area} onClose={vi.fn()} onAbout={vi.fn()} onAsk={onAsk} />)

    await userEvent.click(screen.getByRole('button', { name: 'Ask about this area' }))
    expect(onAsk).toHaveBeenCalledTimes(1)

    rerender(<AreaCard area={area} onClose={vi.fn()} onAbout={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Ask about this area' })).toBeNull()
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
    expect(legend).not.toHaveTextContent('Community report')
  })

  it('adds a community report entry to the legend when reports are on', () => {
    render(<Legend reports />)
    expect(screen.getByRole('region', { name: 'Risk legend' })).toHaveTextContent('Community report')
  })
})

describe('About (TRUST-01..03)', () => {
  it('about shows holdout metrics, limitations, and tap-to-call', async () => {
    const onClose = vi.fn()
    render(<About meta={meta()} onClose={onClose} />)

    const dialog = screen.getByRole('dialog', { name: 'How PathPro works' })
    expect(dialog).toHaveTextContent('46%')
    expect(dialog).toHaveTextContent('37%–56%')
    expect(screen.getByRole('link', { name: 'Georgia Tech Police 404-894-2500' })).toHaveAttribute('href', 'tel:4048942500')
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
