import { afterEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_STATE } from '../state/urlState'
import { shareLink, shareableUrl } from './share'

const view = {
  ...DEFAULT_STATE,
  from: { lat: 33.7766, lon: -84.3963, label: 'Your location' },
  to: { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' },
  seg: 12,
  hour: 22,
}

describe('shareableUrl', () => {
  it('keeps the trip, drops transient view state, and never labels a shared start as "Your location"', () => {
    const url = shareableUrl(view, 'https://pathpro.tech', '/')
    expect(url).toContain('https://pathpro.tech/?from=33.77660%2C-84.39630%2CStart+point')
    expect(url).toContain('to=33.78100%2C-84.38630%2CMidtown+MARTA')
    expect(url).not.toContain('seg=')
    expect(url).not.toContain('h=')
  })
})

describe('shareLink', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses the Web Share sheet when available', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { share })
    await expect(shareLink('https://x', 'PathPro route', 'text')).resolves.toBe('shared')
    expect(share).toHaveBeenCalledWith({ title: 'PathPro route', text: 'text', url: 'https://x' })
  })

  it('treats a dismissed share sheet as cancelled, not failed', async () => {
    const abort = Object.assign(new Error('cancel'), { name: 'AbortError' })
    vi.stubGlobal('navigator', { share: vi.fn().mockRejectedValue(abort) })
    await expect(shareLink('https://x', 't', 'x')).resolves.toBe('cancelled')
  })

  it('falls back to copying the link', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    await expect(shareLink('https://x', 't', 'x')).resolves.toBe('copied')
    expect(writeText).toHaveBeenCalledWith('https://x')
  })

  it('reports failure when neither is possible', async () => {
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error('no')) } })
    await expect(shareLink('https://x', 't', 'x')).resolves.toBe('failed')
    vi.stubGlobal('navigator', {})
    await expect(shareLink('https://x', 't', 'x')).resolves.toBe('failed')
  })
})
