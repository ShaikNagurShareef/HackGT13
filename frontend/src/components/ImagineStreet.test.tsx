import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { resetRuntimeForTests } from '../api/runtime'
import { segment } from '../test/fixtures'
import { IMAGINE_BUTTON, IMAGINE_LABEL, ImagineStreet } from './ImagineStreet'
import { SegmentSheet } from './SegmentSheet'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const BANNED = /\b(safe|safer|safest|unsafe|dangerous|bad area|guaranteed)\b/i

const imagined = {
  success: true,
  data: {
    seg_id: 4,
    image_url: '/imagine/segment/4.png',
    prompt_summary: 'Redesign ideas from its top traffic-risk factors (speed limit).',
    fixes: ['high-visibility crosswalks', 'curb extensions'],
    label: 'AI illustration of evidence-based street fixes by Grok Imagine — not a real photo',
    cached: false,
  },
}

function jsonFetch(body: unknown) {
  return vi.fn(async () => new Response(JSON.stringify(body), JSON_HEADERS))
}

describe('ImagineStreet (Grok Imagine)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
  })

  it('copy stays within the traffic-risk wording rules', () => {
    expect(IMAGINE_BUTTON).toBe('Imagine this street redesigned')
    expect(IMAGINE_LABEL).toBe('AI illustration of evidence-based street fixes by Grok Imagine — not a real photo')
    expect(IMAGINE_BUTTON).not.toMatch(BANNED)
    expect(IMAGINE_LABEL).not.toMatch(BANNED)
  })

  it('requests the illustration and shows it with alt text and the visible label', async () => {
    const fetcher = jsonFetch(imagined)
    vi.stubGlobal('fetch', fetcher)
    render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    await userEvent.click(screen.getByRole('button', { name: IMAGINE_BUTTON }))

    const img = await screen.findByRole('img', { name: /AI illustration of Row 1 St redesigned with high-visibility crosswalks, curb extensions/ })
    expect(img).toHaveAttribute('src', '/api/imagine/segment/4.png')
    expect(screen.getByText(IMAGINE_LABEL)).toBeVisible()
    expect(screen.getByText(/top traffic-risk factors/)).toBeInTheDocument()
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/imagine/segment')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ seg_id: 4 })
    expect(screen.queryByRole('button', { name: IMAGINE_BUTTON })).not.toBeInTheDocument()
  })

  it('shows a busy state while the illustration is generated', async () => {
    let resolve: (r: Response) => void = () => undefined
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((r) => (resolve = r))))
    render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    await userEvent.click(screen.getByRole('button', { name: IMAGINE_BUTTON }))

    const busy = screen.getByRole('button', { name: /Imagining/ })
    expect(busy).toHaveAttribute('aria-busy', 'true')
    expect(busy).toHaveAttribute('aria-disabled', 'true')
    resolve(new Response(JSON.stringify(imagined), JSON_HEADERS))
    expect(await screen.findByText(IMAGINE_LABEL)).toBeInTheDocument()
  })

  it('reports a friendly message when the service is unavailable and allows a retry', async () => {
    const body = { success: false, error: { code: 'IMAGINE_UNAVAILABLE', message: 'Street illustrations are unavailable right now.' } }
    vi.stubGlobal('fetch', jsonFetch(body))
    render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    await userEvent.click(screen.getByRole('button', { name: IMAGINE_BUTTON }))

    expect(await screen.findByRole('status')).toHaveTextContent('Street illustrations are unavailable right now.')
    expect(screen.getByRole('button', { name: IMAGINE_BUTTON })).toBeEnabled()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('is hidden in the offline demo', () => {
    resetRuntimeForTests('', true)
    const { container } = render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    expect(container).toBeEmptyDOMElement()
  })

  it('shows how many planned fixes Gemini confirmed in the picture', async () => {
    const check = { by: 'gemini', fixes_shown: ['curb extensions'], fixes_total: 2 }
    vi.stubGlobal('fetch', jsonFetch({ ...imagined, data: { ...imagined.data, check } }))
    render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    await userEvent.click(screen.getByRole('button', { name: IMAGINE_BUTTON }))

    const line = await screen.findByText('Checked by Gemini: shows 1 of 2 planned fixes')
    expect(line).toBeVisible()
    expect(line.textContent).not.toMatch(BANNED)
  })

  it('adds no check line when the picture was not checked', async () => {
    vi.stubGlobal('fetch', jsonFetch({ ...imagined, data: { ...imagined.data, check: null } }))
    render(<ImagineStreet segId={4} streetName="Row 1 St" />)

    await userEvent.click(screen.getByRole('button', { name: IMAGINE_BUTTON }))

    expect(await screen.findByText(IMAGINE_LABEL)).toBeInTheDocument()
    expect(screen.queryByText(/Checked by Gemini/)).not.toBeInTheDocument()
  })

  it('rejects a check from anyone but Gemini', async () => {
    const check = { by: 'someone', fixes_shown: [], fixes_total: 2 }
    vi.stubGlobal('fetch', jsonFetch({ ...imagined, data: { ...imagined.data, check } }))

    await expect(api.imagineSegment(4)).rejects.toMatchObject({ code: 'BAD_RESPONSE' })
  })

  it('the api client validates the response with zod', async () => {
    vi.stubGlobal('fetch', jsonFetch({ success: true, data: { ...imagined.data, image_url: 42 } }))

    await expect(api.imagineSegment(4)).rejects.toMatchObject({ code: 'BAD_RESPONSE' })
  })
})

describe('SegmentSheet imagine button', () => {
  it('offers the redesign illustration on walk streets only', () => {
    const { rerender } = render(<SegmentSheet detail={segment()} explanation="Because." onClose={vi.fn()} onAbout={vi.fn()} />)
    expect(screen.getByRole('button', { name: IMAGINE_BUTTON })).toBeInTheDocument()

    rerender(<SegmentSheet detail={segment()} explanation="Because." onClose={vi.fn()} onAbout={vi.fn()} rideNetwork />)
    expect(screen.queryByRole('button', { name: IMAGINE_BUTTON })).not.toBeInTheDocument()
  })
})
