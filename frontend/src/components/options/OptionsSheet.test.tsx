import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { OptionsSheet, type OptionsSheetProps } from './OptionsSheet'

function setup(over: Partial<OptionsSheetProps> = {}) {
  const props: OptionsSheetProps = {
    cond: 'live',
    condLabel: 'Live · dry',
    onCond: vi.fn(),
    depart: 'now',
    onDepart: vi.fn(),
    cityAvailable: true,
    cityMode: false,
    onCityMode: vi.fn(),
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
    expect(p.onCityMode).toHaveBeenCalledWith(true)
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
})
