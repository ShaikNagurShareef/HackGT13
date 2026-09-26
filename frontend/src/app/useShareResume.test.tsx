import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Route } from '../api/schemas'
import { clearShareSession, loadShareSession, saveShareSession, type StoredShareSession } from '../lib/shareSession'
import { route } from '../test/fixtures'
import { sharedWalk } from '../test/walkFixtures'
import type { Place } from '../state/urlState'
import { useShareResume, type ShareResumeDeps } from './useShareResume'

const NOW = Date.parse('2026-09-27T02:45:00Z')
const MIDTOWN: Place = { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 }
const AQUARIUM: Place = { label: 'Georgia Aquarium', lat: 33.7634, lon: -84.3951 }
const STORED: StoredShareSession = {
  walk_id: 'w1',
  owner_token: 'secret-token',
  follow_path: '/follow/w1',
  expires_at: '2026-09-27T08:30:00Z',
  destination: MIDTOWN,
}

type Props = { destination: Place | null; route: Route | null; active?: boolean; demo?: boolean }

function setup(initial: Props) {
  const start = vi.fn()
  const onNotice = vi.fn()
  const deps = (p: Props): ShareResumeDeps => ({
    demo: p.demo ?? false,
    destination: p.destination,
    route: p.route,
    nav: { active: p.active ?? false, start },
    onNotice,
  })
  const hook = renderHook((p: Props) => useShareResume(deps(p)), { initialProps: initial })
  return { ...hook, start, onNotice }
}

describe('useShareResume', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(NOW)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.sessionStorage.clear()
  })

  it('offers to resume a live walk saved in this tab', () => {
    saveShareSession(STORED)

    const { result } = setup({ destination: MIDTOWN, route: null })

    expect(result.current.pending).toEqual(STORED)
    expect(result.current.resumed).toBeNull()
  })

  it('offers nothing when no walk was being shared', () => {
    const { result } = setup({ destination: MIDTOWN, route: null })

    expect(result.current.pending).toBeNull()
  })

  it('offers nothing in demo mode', () => {
    saveShareSession(STORED)

    const { result } = setup({ destination: MIDTOWN, route: null, demo: true })

    expect(result.current.pending).toBeNull()
  })

  it('offers nothing when the saved walk has expired', () => {
    saveShareSession({ ...STORED, expires_at: '2026-09-27T02:00:00Z' })

    const { result } = setup({ destination: MIDTOWN, route: null })

    expect(result.current.pending).toBeNull()
  })

  it('resumes navigation to the same destination when the route is ready', () => {
    saveShareSession(STORED)
    const { result, start } = setup({ destination: MIDTOWN, route: route() })

    act(() => result.current.resume())

    expect(start).toHaveBeenCalledWith('gps')
    expect(result.current.pending).toBeNull()
    expect(result.current.resumed).toEqual(STORED)
  })

  it('waits for the route to load, then resumes navigation', () => {
    saveShareSession(STORED)
    const { result, rerender, start } = setup({ destination: MIDTOWN, route: null })

    act(() => result.current.resume())
    expect(start).not.toHaveBeenCalled()
    expect(result.current.resumed).toEqual(STORED)

    rerender({ destination: MIDTOWN, route: route() })
    expect(start).toHaveBeenCalledTimes(1)
    rerender({ destination: MIDTOWN, route: route(), active: true })
    expect(start).toHaveBeenCalledTimes(1)
  })

  it('keeps posting position only when navigation cannot be restored for that destination', () => {
    saveShareSession(STORED)
    const { result, rerender, start } = setup({ destination: AQUARIUM, route: route() })

    act(() => result.current.resume())
    rerender({ destination: AQUARIUM, route: route() })

    expect(start).not.toHaveBeenCalled()
    expect(result.current.resumed).toEqual(STORED)
  })

  it('does not start navigation if the resumed walk ended before the route arrived', () => {
    saveShareSession(STORED)
    const { result, rerender, start } = setup({ destination: MIDTOWN, route: null })

    act(() => result.current.resume())
    clearShareSession('w1')
    rerender({ destination: MIDTOWN, route: route() })

    expect(start).not.toHaveBeenCalled()
  })

  it('says so when the saved walk expired before resuming', () => {
    saveShareSession(STORED)
    const { result, onNotice, start } = setup({ destination: MIDTOWN, route: route() })
    vi.setSystemTime(Date.parse('2026-09-27T09:00:00Z'))

    act(() => result.current.resume())

    expect(start).not.toHaveBeenCalled()
    expect(result.current.resumed).toBeNull()
    expect(onNotice).toHaveBeenCalledWith('Your live link expired. Share again to start a new one.')
  })

  it('stop sharing marks the walk ended at its last shared position and forgets it', async () => {
    saveShareSession(STORED)
    const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
      const walk = sharedWalk()
      const data = init?.method === 'PUT' ? { ...walk, status: 'ended', route: undefined } : walk
      return new Response(JSON.stringify({ success: true, data }), { headers: { 'content-type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetcher)
    const { result, onNotice } = setup({ destination: MIDTOWN, route: route() })

    act(() => result.current.stopSharing())

    expect(result.current.pending).toBeNull()
    expect(loadShareSession()).toBeNull()
    expect(onNotice).toHaveBeenCalledWith('Stopped sharing your walk.')
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    const [, init] = fetcher.mock.calls[1] as unknown as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({ owner_token: 'secret-token', lat: 33.7775, lon: -84.395, status: 'ended' })
  })

  it('still forgets the walk when ending it fails', async () => {
    saveShareSession(STORED)
    const fetcher = vi.fn().mockRejectedValue(new TypeError('offline'))
    vi.stubGlobal('fetch', fetcher)
    const { result } = setup({ destination: MIDTOWN, route: null })

    act(() => result.current.stopSharing())
    await waitFor(() => expect(fetcher).toHaveBeenCalled())

    expect(loadShareSession()).toBeNull()
    expect(result.current.pending).toBeNull()
  })
})
