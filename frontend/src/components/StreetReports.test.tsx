import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { report } from '../test/fixtures'
import { StreetReports } from './StreetReports'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
type Handler = (init?: RequestInit) => unknown

function serve(handlers: Record<string, Handler>) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${url}`
    const handler = handlers[key]
    if (!handler) throw new Error(`unexpected ${key}`)
    return new Response(JSON.stringify(handler(init)), JSON_HEADERS)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

const UNAVAILABLE = { success: false, error: { code: 'REPORTS_UNAVAILABLE', message: 'Community reports are unavailable' } }

describe('StreetReports', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists existing reports and offers keyboard-accessible category chips', async () => {
    serve({ 'GET /api/segments/11/reports': () => ({ success: true, data: [report({ confirmations: 3 })] }) })

    render(<StreetReports segId={11} />)

    const section = await screen.findByRole('region', { name: 'Report a street issue' })
    const list = within(section).getByRole('list', { name: 'Community reports on this street' })
    expect(list).toHaveTextContent('Construction detour')
    expect(list).toHaveTextContent('3 walkers')
    const chips = within(section).getAllByRole('button')
    expect(chips).toHaveLength(6)
    for (const chip of chips) expect(chip).toHaveAttribute('aria-pressed', 'false')
    expect(section).toHaveTextContent('never change traffic-risk scores')
  })

  it('posts a category, thanks the walker politely, and updates the list', async () => {
    const fetcher = serve({
      'GET /api/segments/11/reports': () => ({ success: true, data: [] }),
      'POST /api/reports': () => ({ success: true, data: report({ category: 'signal_out', label: 'Crossing signal out', confirmations: 1 }) }),
    })
    const onReported = vi.fn()
    render(<StreetReports segId={11} onReported={onReported} />)

    const chip = await screen.findByRole('button', { name: 'Crossing signal out' })
    chip.focus()
    await userEvent.keyboard('{Enter}')

    // The polite live region is always mounted so screen readers announce the change.
    await vi.waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Thanks — other walkers will see this for 14 days.'),
    )
    expect(screen.getByRole('button', { name: 'Crossing signal out' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('list', { name: 'Community reports on this street' })).toHaveTextContent('1 walker')
    const post = fetcher.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === 'POST')
    const postInit = post?.[1] as RequestInit | undefined
    expect(JSON.parse(String(postInit?.body))).toEqual({ seg_id: 11, category: 'signal_out' })
    expect(onReported).toHaveBeenCalled()
  })

  it('hides entirely when reports are unavailable', async () => {
    const fetcher = serve({ 'GET /api/segments/11/reports': () => UNAVAILABLE })

    const { container } = render(<StreetReports segId={11} />)

    await vi.waitFor(() => expect(fetcher).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('hides if posting finds the service unavailable', async () => {
    serve({
      'GET /api/segments/11/reports': () => ({ success: true, data: [] }),
      'POST /api/reports': () => UNAVAILABLE,
    })
    const { container } = render(<StreetReports segId={11} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Flooding or standing water' }))

    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  })

  it('shows other posting errors without hiding the section', async () => {
    serve({
      'GET /api/segments/11/reports': () => ({ success: true, data: [] }),
      'POST /api/reports': () => ({ success: false, error: { code: 'RATE_LIMITED', message: 'Too many requests. Try again in a minute.' } }),
    })
    render(<StreetReports segId={11} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Sidewalk blocked' }))

    await vi.waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Too many requests'))
    expect(screen.getByRole('button', { name: 'Sidewalk blocked' })).toHaveAttribute('aria-pressed', 'false')
  })
})
