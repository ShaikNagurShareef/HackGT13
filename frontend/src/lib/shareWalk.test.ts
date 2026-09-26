import { describe, expect, it } from 'vitest'
import { MAX_ROUTE_POINTS, downsampleRoute, followIdFromPath, followUrl, formatAgo } from './shareWalk'

describe('follow links', () => {
  it('recognises /follow/<id> paths, with or without a deploy base and trailing slash', () => {
    expect(followIdFromPath('/follow/AbC_12-xyzXYZ0123456789')).toBe('AbC_12-xyzXYZ0123456789')
    expect(followIdFromPath('/PathPro/follow/AbC_12-xyzXYZ0123456789/')).toBe('AbC_12-xyzXYZ0123456789')
    expect(followIdFromPath('/')).toBeNull()
    expect(followIdFromPath('/follow/')).toBeNull()
    expect(followIdFromPath('/follow/has spaces')).toBeNull()
    expect(followIdFromPath('/follow/a/b')).toBeNull()
  })

  it('builds the full follow URL, marking demo links', () => {
    expect(followUrl('https://pathpro.tech', 'abc123', false)).toBe('https://pathpro.tech/follow/abc123')
    expect(followUrl('https://pathpro.tech', 'abc123', true)).toBe('https://pathpro.tech/follow/abc123?demo=1')
  })
})

describe('downsampleRoute', () => {
  it('keeps short routes as they are', () => {
    const route: [number, number][] = [
      [-84.39, 33.77],
      [-84.38, 33.78],
    ]

    expect(downsampleRoute(route)).toEqual(route)
  })

  it('thins long routes to the server limit and keeps both ends', () => {
    const route = Array.from({ length: 5001 }, (_, i): [number, number] => [-84.4 + i * 1e-5, 33.77])

    const thinned = downsampleRoute(route)

    expect(thinned.length).toBeLessThanOrEqual(MAX_ROUTE_POINTS)
    expect(thinned[0]).toEqual(route[0])
    expect(thinned[thinned.length - 1]).toEqual(route[route.length - 1])
  })
})

describe('formatAgo', () => {
  it.each([
    [0, 'just now'],
    [4_000, 'just now'],
    [12_400, '12 s ago'],
    [59_000, '59 s ago'],
    [60_000, '1 min ago'],
    [185_000, '3 min ago'],
    [2 * 3_600_000, '2 h ago'],
    [-5_000, 'just now'],
  ])('%i ms -> %s', (ms, text) => {
    expect(formatAgo(ms)).toBe(text)
  })
})
