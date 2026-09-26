import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { report, routes } from '../../test/fixtures'
import { RouteSheet, type RouteSheetProps } from './RouteSheet'
import { TripHeader } from './TripHeader'

function setup(over: Partial<RouteSheetProps> = {}) {
  const props: RouteSheetProps = {
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
  render(<RouteSheet {...props} />)
  return props
}

describe('RouteSheet (RTE-04, mobile route sheet)', () => {
  it('headlines the PathPro route with time, risk cut, time cost, and arrival', () => {
    setup()
    const pp = screen.getByTestId('route-pp')

    expect(pp).toHaveTextContent('PathPro route')
    expect(pp).toHaveTextContent('23 min · 49% less traffic risk')
    expect(pp).toHaveTextContent('+4 min vs fastest · arrive 10:52 PM')
    expect(pp).toHaveAttribute('aria-pressed', 'true')
    expect(pp).toHaveTextContent('83')
    expect(pp).not.toHaveTextContent('High') // both routes are often "High"; the risk cut leads instead
    expect(screen.getByTestId('route-fast')).toHaveTextContent('18 min')
    expect(screen.getByRole('region', { name: 'Route comparison' })).toHaveTextContent('Both routes use Fifth Street Northwest')
    expect(screen.getByRole('note')).toHaveTextContent('Always stay alert')
  })

  it('selects a row, starts, listens, previews, and shares', async () => {
    const user = userEvent.setup()
    const p = setup({ startNote: "You're 2.1 km from the start, so Start previews the walk." })

    await user.click(screen.getByTestId('route-fast'))
    await user.click(screen.getByRole('button', { name: 'Start' }))
    await user.click(screen.getByRole('button', { name: /Listen/ }))
    await user.click(screen.getByRole('button', { name: /Preview walk/ }))
    await user.click(screen.getByRole('button', { name: /Share/ }))

    expect(p.onSelect).toHaveBeenCalledWith('fast')
    expect(p.onStart).toHaveBeenCalled()
    expect(p.onListen).toHaveBeenCalled()
    expect(p.onPreview).toHaveBeenCalled()
    expect(p.onShare).toHaveBeenCalled()
    expect(screen.getByText(/2.1 km from the start/)).toBeInTheDocument()
  })

  it('"Why?" expands the sheet to the explanation (grounded text, template otherwise)', async () => {
    const user = userEvent.setup()
    setup()
    const sheet = screen.getByRole('region', { name: 'Route comparison' })

    expect(sheet).toHaveAttribute('data-state', 'peek')
    await user.click(screen.getByRole('button', { name: 'Why?' }))
    expect(sheet).toHaveAttribute('data-state', 'expanded')
    expect(screen.getByTestId('route-explanation')).toHaveTextContent('by avoiding Peachtree Place Northwest')
  })

  it('keeps the evidence in the expanded state: avoided, reports, unavoidable, hot list', async () => {
    const user = userEvent.setup()
    const withReports = routes({ reports: [report(), report({ seg_id: 12, label: 'Sidewalk blocked' })] })
    const p = setup({ routes: withReports, explanation: 'LLM text', shareStatus: 'Link copied' })

    await waitFor(() => expect(screen.getByTestId('route-explanation')).toHaveTextContent('LLM text'))
    expect(screen.getByRole('status')).toHaveTextContent('Link copied')
    const avoided = screen.getByLabelText('High-risk stretches the PathPro route avoids')
    await user.click(within(avoided).getByRole('button', { name: /Peachtree Place Northwest/ }))
    const hot = screen.getByLabelText('Highest-risk stretches on the fastest route')
    await user.click(within(hot).getByRole('button', { name: /Fifth Street Northwest/ }))

    expect(p.onFocusSegment).toHaveBeenCalledWith(12)
    expect(p.onSelectSegment).toHaveBeenCalledWith(11)
    expect(screen.getByTestId('route-reports')).toHaveTextContent('2 community reports on this route')
  })

  it('renders the single-route case positively (RTE-03)', () => {
    setup({ routes: routes({ pathpro: null, time_cost_min: null, exposure_reduction_pct: null, unavoidable: [] }) })

    expect(screen.getByTestId('route-fast')).toHaveTextContent('already the lower-risk option')
    expect(screen.queryByTestId('route-pp')).toBeNull()
    expect(screen.queryByRole('button', { name: /Preview walk/ })).toBeInTheDocument()
  })
})

describe('TripHeader', () => {
  it('shows a compact From/To with swap and back', async () => {
    const user = userEvent.setup()
    const h = { onEditFrom: vi.fn(), onEditTo: vi.fn(), onSwap: vi.fn(), onBack: vi.fn() }
    render(
      <TripHeader
        from={{ lat: 1, lon: 2, label: 'Your location' }}
        to={{ lat: 3, lon: 4, label: 'Midtown MARTA' }}
        {...h}
      />,
    )

    await user.click(screen.getByRole('button', { name: /From.*Your location/ }))
    await user.click(screen.getByRole('button', { name: /To.*Midtown MARTA/ }))
    await user.click(screen.getByRole('button', { name: 'Swap start and destination' }))
    await user.click(screen.getByRole('button', { name: 'Back to map' }))

    expect(h.onEditFrom).toHaveBeenCalled()
    expect(h.onEditTo).toHaveBeenCalled()
    expect(h.onSwap).toHaveBeenCalled()
    expect(h.onBack).toHaveBeenCalled()
  })

  it('invites choosing a start when there is none', () => {
    render(<TripHeader from={null} to={{ lat: 3, lon: 4, label: 'X' }} onEditFrom={vi.fn()} onEditTo={vi.fn()} onSwap={vi.fn()} onBack={vi.fn()} />)
    expect(screen.getByRole('button', { name: /From.*Choose a start/ })).toBeInTheDocument()
  })
})
