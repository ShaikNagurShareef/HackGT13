import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { MAX_ALERT_CLIPS, type AlertKind } from '../lib/alertClips'
import { stubBlobUrls } from '../test/audio'
import { useAlertClips } from './useAlertClips'

const KEY = 'aaaaaaaaaaaaaaaa'
const OTHER = 'bbbbbbbbbbbbbbbb'

interface Props {
  routeKey: string | null
  kind: AlertKind
  count: number
  active: boolean
}

const setup = (initial: Props) => renderHook((p: Props) => useAlertClips(p), { initialProps: initial })

describe('useAlertClips (Grok Voice navigation alerts)', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.history.replaceState(null, '', '/')
  })

  it('prefetches a bounded set of clips once navigation starts, and keeps them for a restart', async () => {
    stubBlobUrls()
    const fetchClip = vi.spyOn(api, 'ttsAlert').mockResolvedValue(new Blob(['mp3']))
    const { result, rerender } = setup({ routeKey: KEY, kind: 'fast', count: 20, active: false })

    expect(fetchClip).not.toHaveBeenCalled()
    rerender({ routeKey: KEY, kind: 'fast', count: 20, active: true })
    await waitFor(() => expect(fetchClip).toHaveBeenCalledTimes(MAX_ALERT_CLIPS))
    expect(fetchClip).toHaveBeenCalledWith(KEY, 0, 'fast', expect.any(AbortSignal))
    await waitFor(() => expect(result.current(MAX_ALERT_CLIPS - 1)).toMatch(/^blob:clip-/))
    expect(result.current(MAX_ALERT_CLIPS)).toBeNull()

    rerender({ routeKey: KEY, kind: 'fast', count: 20, active: false })
    rerender({ routeKey: KEY, kind: 'fast', count: 20, active: true })
    expect(fetchClip).toHaveBeenCalledTimes(MAX_ALERT_CLIPS)
    expect(result.current(0)).toMatch(/^blob:clip-/)
  })

  it('revokes every clip URL when the route changes and on unmount', async () => {
    const urls = stubBlobUrls()
    vi.spyOn(api, 'ttsAlert').mockResolvedValue(new Blob(['mp3']))
    const { result, rerender, unmount } = setup({ routeKey: KEY, kind: 'pp', count: 2, active: true })
    await waitFor(() => expect(result.current(1)).not.toBeNull())
    const first = [result.current(0), result.current(1)]

    rerender({ routeKey: OTHER, kind: 'pp', count: 2, active: true })
    expect(urls.revoke.mock.calls.map(([u]) => u).sort()).toEqual([...first].sort())
    await waitFor(() => expect(result.current(1)).not.toBeNull())
    expect(first).not.toContain(result.current(0))

    unmount()
    expect(urls.revoke).toHaveBeenCalledTimes(4)
  })

  it('keeps the device voice in demo mode: no network at all', async () => {
    window.history.replaceState(null, '', '/?demo=1')
    const fetchClip = vi.spyOn(api, 'ttsAlert')
    const { result } = setup({ routeKey: KEY, kind: 'pp', count: 3, active: true })

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(fetchClip).not.toHaveBeenCalled()
    expect(result.current(0)).toBeNull()
  })

  it('has nothing to fetch without a route key', () => {
    const fetchClip = vi.spyOn(api, 'ttsAlert')
    const { result } = setup({ routeKey: null, kind: 'pp', count: 3, active: true })

    expect(fetchClip).not.toHaveBeenCalled()
    expect(result.current(0)).toBeNull()
  })
})
