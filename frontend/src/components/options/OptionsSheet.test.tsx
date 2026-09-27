import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_SAFETY_LAYERS, FAIRNESS_NOTE } from '../../lib/safety'
import { helpPoint, safetyMeta } from '../../test/fixtures'
import { OptionsSheet, type OptionsSheetProps } from './OptionsSheet'

function setup(over: Partial<OptionsSheetProps> = {}) {
  const props: OptionsSheetProps = {
    cond: 'live',
    condLabel: 'Live · dry',
    onCond: vi.fn(),
    depart: 'now',
    onDepart: vi.fn(),
    cityAvailable: true,
    mapMode: 'streets',
    onMapMode: vi.fn(),
    safety: null,
    timeline: {
      hour: 22,
      onHour: vi.fn(),
      playing: false,
      onTogglePlay: vi.fn(),
      medians: Array.from({ length: 24 }, (_, h) => h),
      lights: [],
      condLabel: 'Wet',
      day: 'friday',
      onDay: vi.fn(),
    },
    showReportsLegend: false,
    onAbout: vi.fn(),
    onClearHistory: vi.fn(),
    onClose: vi.fn(),
    ...over,
  }
  render(<OptionsSheet {...props} />)
  return props
}

describe('OptionsSheet', () => {
  it('groups conditions, departure, map mode, Risk Tides, and the legend', async () => {
    const user = userEvent.setup()
    const p = setup()

    expect(screen.getByRole('dialog', { name: 'Map options' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Wet/ }))
    await user.click(screen.getByRole('button', { name: '+15 min' }))
    await user.click(screen.getByRole('button', { name: 'City Pulse' }))
    fireEvent.change(screen.getByRole('slider', { name: 'Hour of day' }), { target: { value: '0' } })

    expect(p.onCond).toHaveBeenCalledWith('wet')
    expect(p.onDepart).toHaveBeenCalledWith('+15m')
    expect(p.onMapMode).toHaveBeenCalledWith('city')
    expect(p.timeline.onHour).toHaveBeenCalledWith(6)
    expect(screen.getByRole('region', { name: 'Risk legend' })).toBeInTheDocument()
  })

  it('hides City Pulse when the bundle has no hex cells', () => {
    setup({ cityAvailable: false })
    expect(screen.queryByRole('button', { name: 'City Pulse' })).toBeNull()
  })

  it('keeps walking patterns on the phone and clears them on request', async () => {
    const user = userEvent.setup()
    const p = setup()

    expect(screen.getByText('Your walking patterns stay on this phone.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear history' }))
    expect(p.onClearHistory).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('History cleared')
  })

  it('opens About and closes with the button or Escape', async () => {
    const user = userEvent.setup()
    const p = setup()

    await user.click(screen.getByRole('button', { name: 'About PathPro' }))
    await user.click(screen.getByRole('button', { name: 'Close options' }))
    await user.keyboard('{Escape}')
    expect(p.onAbout).toHaveBeenCalled()
    expect(p.onClose).toHaveBeenCalledTimes(2)
  })

  it('hides the personal safety mode and route preference when the server has no safety layer', () => {
    setup()
    expect(screen.queryByRole('button', { name: 'Personal safety' })).toBeNull()
    expect(screen.queryByRole('group', { name: 'Route preference' })).toBeNull()
  })
})

describe('OptionsSheet with the personal safety layer', () => {
  const safety = () => ({
    legend: { meta: safetyMeta(), hour: 21, layers: DEFAULT_SAFETY_LAYERS, tooWide: false },
    onLayers: vi.fn(),
    hasLit: true,
    hasBusy: false,
    helpPoints: [helpPoint()],
    onPickHelp: vi.fn(),
    prefer: 'lower_traffic_risk' as const,
    onPrefer: vi.fn(),
  })

  it('offers Personal safety as a third map mode and a route preference', async () => {
    const user = userEvent.setup()
    const p = setup({ safety: safety() })

    await user.click(screen.getByRole('button', { name: 'Personal safety' }))
    await user.click(screen.getByRole('button', { name: /Well-lit & busier/ }))

    expect(p.onMapMode).toHaveBeenCalledWith('safety')
    expect(p.safety?.onPrefer).toHaveBeenCalledWith('lit_and_busy')
    expect(screen.getByRole('region', { name: 'Risk legend' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Reported crimes against persons' })).toBeNull()
  })

  it('in safety mode shows the layer toggles and the safety legend with its fairness note', async () => {
    const user = userEvent.setup()
    const p = setup({ mapMode: 'safety', safety: safety() })

    expect(screen.getByRole('button', { name: 'Personal safety' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('region', { name: 'Personal safety legend' })).toHaveTextContent(FAIRNESS_NOTE)
    expect(screen.queryByRole('region', { name: 'Risk legend' })).toBeNull()
    expect(screen.queryByRole('checkbox', { name: 'Busier streets' })).toBeNull()
    await user.click(screen.getByRole('checkbox', { name: 'Well-lit streets' }))
    expect(p.safety?.onLayers).toHaveBeenCalledWith({ ...DEFAULT_SAFETY_LAYERS, lit: true })
    await user.click(screen.getByRole('button', { name: 'Blue-light emergency phone · Tech Green' }))
    expect(p.safety?.onPickHelp).toHaveBeenCalledWith({ kind: 'help', point: helpPoint() })
  })

  it('offers Ask PathPro next to About when the server has it, and hides it otherwise', async () => {
    const onAsk = vi.fn()
    setup({ onAsk })
    await userEvent.click(screen.getByRole('button', { name: 'Ask PathPro' }))
    expect(onAsk).toHaveBeenCalled()
  })

  it('hides Ask PathPro without a handler (demo mode)', () => {
    setup()
    expect(screen.queryByRole('button', { name: 'Ask PathPro' })).toBeNull()
  })
})
