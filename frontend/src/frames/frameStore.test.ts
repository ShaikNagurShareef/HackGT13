import { describe, expect, it, vi } from 'vitest'
import { FrameSet, FrameStore, frameUrl, median } from './frameStore'

function buffer(n: number): Uint8Array {
  const out = new Uint8Array(24 * n)
  for (let h = 0; h < 24; h++) for (let i = 0; i < n; i++) out[h * n + i] = h * 4 + i
  return out
}

describe('FrameSet', () => {
  it('slices hours without copying', () => {
    const frames = new FrameSet(buffer(3), 3)

    expect(Array.from(frames.hour(2))).toEqual([8, 9, 10])
    expect(frames.hour(2).buffer).toBe(frames.buffer.buffer)
    expect(Array.from(frames.hour(26))).toEqual([8, 9, 10])
  })

  it('rejects a buffer that does not match 24 x N', () => {
    expect(() => new FrameSet(new Uint8Array(10), 3)).toThrow(/frame size/)
  })

  it('computes per-hour medians', () => {
    expect(new FrameSet(buffer(3), 3).medians()[5]).toBe(21)
    expect(median(new Uint8Array([10, 90, 50]))).toBe(50)
  })
})

describe('FrameStore', () => {
  it('fetches once per frame set and caches', async () => {
    const fetcher = vi.fn(async () => buffer(2).buffer as ArrayBuffer)
    const store = new FrameStore('/static/v1', 2, fetcher)

    const [a, b] = await Promise.all([store.get('friday', 'wet'), store.get('friday', 'wet')])

    expect(a).toBe(b)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledWith('/static/v1/frames_friday_wet.bin')
  })

  it('evicts failed fetches so a retry can succeed', async () => {
    const fetcher = vi
      .fn<(url: string) => Promise<ArrayBuffer>>()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(buffer(2).buffer as ArrayBuffer)
    const store = new FrameStore('/s', 2, fetcher)

    await expect(store.get('weekday', 'dry')).rejects.toThrow('offline')
    await expect(store.get('weekday', 'dry')).resolves.toBeInstanceOf(FrameSet)
  })

  it('builds frame urls', () => {
    expect(frameUrl('/static/x', 'sunday', 'dry')).toBe('/static/x/frames_sunday_dry.bin')
  })
})
