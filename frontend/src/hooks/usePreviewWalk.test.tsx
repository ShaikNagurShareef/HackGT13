import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { stubAudio, stubSpeech } from '../test/audio'
import { route } from '../test/fixtures'
import { usePreviewWalk } from './usePreviewWalk'

describe('usePreviewWalk (VOX-05)', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('moves along the route, raises the alert banner once, and finishes', () => {
    vi.useFakeTimers()
    const speakSpy = vi.fn()
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak: speakSpy })
    vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; constructor(text: string) { this.text = text } })
    const r = route()
    const { result } = renderHook(() => usePreviewWalk(r, true))

    expect(result.current.position).toBeNull()
    act(() => result.current.start())
    act(() => void vi.advanceTimersByTime(1500))
    expect(result.current.active).toBe(true)
    expect(result.current.progress).toBeGreaterThan(0)
    expect(result.current.position).not.toBeNull()

    act(() => void vi.advanceTimersByTime(60_000))
    expect(result.current.banner).toContain('Spring Street')
    expect(speakSpy).toHaveBeenCalledTimes(1)
    expect(result.current.progress).toBe(1)
    expect(result.current.active).toBe(false)
  })

  it('stops on demand', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => usePreviewWalk(route(), false))
    act(() => result.current.start())
    act(() => result.current.stop())
    expect(result.current.active).toBe(false)
    expect(result.current.banner).toBeNull()
  })

  it('plays the prefetched clip for an alert when voice is on, and stays silent when it is off', () => {
    vi.useFakeTimers()
    const speakSpy = stubSpeech()
    const audio = stubAudio()
    const clipFor = (i: number) => (i === 0 ? 'blob:clip-0' : null)
    const r = route()
    const on = renderHook(() => usePreviewWalk(r, true, undefined, clipFor))
    const off = renderHook(() => usePreviewWalk(r, false, undefined, clipFor))

    act(() => on.result.current.start())
    act(() => off.result.current.start())
    act(() => void vi.advanceTimersByTime(60_000))

    expect(on.result.current.banner).toContain('Spring Street')
    expect(audio.sources).toEqual(['blob:clip-0'])
    expect(speakSpy).not.toHaveBeenCalled()
  })
})
