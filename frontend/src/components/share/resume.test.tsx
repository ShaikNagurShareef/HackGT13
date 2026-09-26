import { act, cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { loadShareSession, saveShareSession, type StoredShareSession } from '../../lib/shareSession'
import type { GeoFix } from '../../lib/origin'
import { sharedWalk } from '../../test/walkFixtures'
import { ResumeSharePrompt } from './ResumeSharePrompt'
import { ResumedShareBar } from './ResumedShareBar'
import { ShareWalkControl } from './ShareWalkControl'

const NOW = Date.parse('2026-09-27T02:45:00Z')
const DEST = { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 }
const STORED: StoredShareSession = {
  walk_id: 'w1',
  owner_token: 'secret-token',
  follow_path: '/follow/w1',
  expires_at: '2026-09-27T08:30:00Z',
  destination: DEST,
}
const FIX: GeoFix = { lat: 33.7775, lon: -84.395, accuracy: 9, heading: null, at: NOW }
const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }

function walkServer() {
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
    const sent = JSON.parse(String(init?.body ?? '{}')) as { status?: 'walking' }
    const data = { ...sharedWalk({ status: sent.status ?? 'walking' }), route: undefined }
    return new Response(JSON.stringify({ success: true, data }), JSON_HEADERS)
  })
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function puts(fetcher: ReturnType<typeof walkServer>): Array<Record<string, unknown>> {
  return fetcher.mock.calls
    .filter(([, init]) => init?.method === 'PUT')
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)
}

describe('ResumeSharePrompt', () => {
  it('asks whether to resume sharing the walk to the destination', async () => {
    const onResume = vi.fn()
    const onStop = vi.fn()
    const { container } = render(<ResumeSharePrompt destination="Midtown MARTA" onResume={onResume} onStop={onStop} />)

    expect(screen.getByRole('region', { name: /You were sharing your walk to Midtown MARTA\. Resume sharing\?/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }))
    await userEvent.click(screen.getByRole('button', { name: 'Stop sharing' }))

    expect(onResume).toHaveBeenCalledTimes(1)
    expect(onStop).toHaveBeenCalledTimes(1)
    expect((await axe(container)).violations).toEqual([])
  })
})

describe('ShareWalkControl without a start button', () => {
  it('shows only the notice when sharing cannot be started from here', () => {
    render(
      <ShareWalkControl
        phase="idle"
        notice="Stopped sharing your walk."
        canStart={false}
        onStart={vi.fn()}
        onResend={vi.fn()}
        onStop={vi.fn()}
        onDismissNotice={vi.fn()}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Share my walk' })).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Stopped sharing your walk.')
  })
})

describe('ResumedShareBar', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(NOW)
    vi.stubGlobal('navigator', { share: vi.fn().mockResolvedValue(undefined) })
  })
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.sessionStorage.clear()
  })

  it('keeps posting the GPS position for the resumed walk (no ETA without navigation)', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    render(<ResumedShareBar destination={DEST} position={FIX} />)

    expect(await screen.findByText('Sharing live')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(puts(fetcher)[0]).toEqual({ owner_token: 'secret-token', lat: 33.7775, lon: -84.395, accuracy_m: 9, status: 'walking' })
  })

  it('stops sharing on request and forgets the session', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(<ResumedShareBar destination={DEST} position={FIX} />)

    await user.click(await screen.findByRole('button', { name: 'Stop' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(puts(fetcher).at(-1)).toMatchObject({ status: 'ended' })
    expect(loadShareSession()).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Stopped sharing your walk.')
    expect(screen.queryByRole('button', { name: 'Share my walk' })).toBeNull()
  })

  it('reports arrival when the walker reaches the destination', async () => {
    saveShareSession(STORED)
    const fetcher = walkServer()

    render(<ResumedShareBar destination={DEST} position={{ ...FIX, lat: DEST.lat, lon: DEST.lon }} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })

    expect(puts(fetcher).map((b) => b.status)).toContain('arrived')
    expect(loadShareSession()).toBeNull()
  })

  it('renders nothing when there is no walk to resume', () => {
    walkServer()

    const { container } = render(<ResumedShareBar destination={DEST} position={FIX} />)

    expect(container).toBeEmptyDOMElement()
  })
})
