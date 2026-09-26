import { describe, expect, it } from 'vitest'
import { RAMP, bandFor, colorFor, cssColor, relativeLuminance, widthFor } from './bands'

describe('bandFor', () => {
  it.each([
    [0, 'Lower'],
    [24, 'Lower'],
    [25, 'Moderate'],
    [49.4, 'Moderate'],
    [50, 'Elevated'],
    [74, 'Elevated'],
    [75, 'High'],
    [100, 'High'],
    [140, 'High'],
    [-3, 'Lower'],
  ])('maps %s to %s', (score, band) => {
    expect(bandFor(score)).toBe(band)
  })
})

describe('ramp', () => {
  it('has 101 entries of valid RGB', () => {
    expect(RAMP).toHaveLength(101)
    for (const [r, g, b] of RAMP) {
      for (const v of [r, g, b]) expect(v).toBeGreaterThanOrEqual(0)
      for (const v of [r, g, b]) expect(v).toBeLessThanOrEqual(255)
    }
  })

  it('is luminance-ordered so it reads in grayscale (EC-54)', () => {
    const lum = RAMP.map(relativeLuminance)
    for (let i = 1; i < lum.length; i++) expect(lum[i]).toBeGreaterThanOrEqual(lum[i - 1] - 1e-3)
  })

  it('clamps out-of-range scores', () => {
    expect(colorFor(-10)).toEqual(RAMP[0])
    expect(colorFor(250)).toEqual(RAMP[100])
    expect(cssColor(50)).toMatch(/^rgb\(\d+ \d+ \d+\)$/)
  })

  it('widens lines with risk', () => {
    expect(widthFor(0)).toBe(1.5)
    expect(widthFor(100)).toBe(5)
    expect(widthFor(80)).toBeGreaterThan(widthFor(20))
  })
})
