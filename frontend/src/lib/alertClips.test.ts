import { describe, expect, it, vi } from 'vitest'
import { CLIP_CONCURRENCY, MAX_ALERT_CLIPS, prefetchClips } from './alertClips'

const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0))

describe('prefetchClips', () => {
  it('fetches a bounded number of clips, a few at a time, in order', async () => {
    let inFlight = 0
    let peak = 0
    const fetchClip = vi.fn(async () => {
      inFlight++
      peak = Math.max(peak, inFlight)
      await tick()
      inFlight--
      return new Blob(['mp3'])
    })
    const got: number[] = []

    await prefetchClips(30, fetchClip, new AbortController().signal, (i) => got.push(i))

    expect(fetchClip).toHaveBeenCalledTimes(MAX_ALERT_CLIPS)
    expect(peak).toBe(CLIP_CONCURRENCY)
    expect([...got].sort((a, b) => a - b)).toEqual([...Array(MAX_ALERT_CLIPS).keys()])
  })

  it('stops after the first failure: the device voice covers the rest', async () => {
    const fetchClip = vi.fn(async (i: number) => {
      await tick()
      if (i === 1) throw new Error('503')
      return new Blob(['mp3'])
    })
    const got: number[] = []

    await prefetchClips(10, fetchClip, new AbortController().signal, (i) => got.push(i))

    expect(fetchClip.mock.calls.length).toBeLessThanOrEqual(CLIP_CONCURRENCY + 1)
    expect(got).toEqual([0])
  })

  it('delivers nothing once aborted', async () => {
    const controller = new AbortController()
    const fetchClip = vi.fn(async () => {
      controller.abort()
      return new Blob(['mp3'])
    })
    const onClip = vi.fn()

    await prefetchClips(5, fetchClip, controller.signal, onClip)

    expect(onClip).not.toHaveBeenCalled()
    expect(fetchClip.mock.calls.length).toBeLessThanOrEqual(CLIP_CONCURRENCY)
  })

  it('does nothing for a route without alerts', async () => {
    const fetchClip = vi.fn()
    await prefetchClips(0, fetchClip, new AbortController().signal, vi.fn())
    expect(fetchClip).not.toHaveBeenCalled()
  })
})
