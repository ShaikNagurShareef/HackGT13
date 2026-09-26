import { describe, expect, it } from 'vitest'
import { routes } from '../test/fixtures'
import { arrivalAt, summarizeRoutes, templateSummary } from './routeSummary'

describe('arrivalAt', () => {
  it('adds the walk duration to the departure', () => {
    expect(arrivalAt('2026-09-25T22:30:00-04:00', 1362).toISOString()).toBe('2026-09-26T02:52:42.000Z')
  })
})

describe('summarizeRoutes (route sheet headline)', () => {
  it('leads with the PathPro route: time, risk cut, time cost, and arrival', () => {
    const s = summarizeRoutes(routes())

    expect(s.primary).toEqual({
      kind: 'pp',
      label: 'PathPro route',
      title: '23 min · 49% less traffic risk',
      sub: '+4 min vs fastest · arrive 10:52 PM',
    })
    expect(s.secondary).toEqual({
      kind: 'fast',
      label: 'Fastest route',
      title: '18 min',
      sub: '1.3 km high-risk · arrive 10:48 PM',
    })
  })

  it('says "about the same time" when the detour rounds to zero', () => {
    const s = summarizeRoutes(routes({ time_cost_min: 0.3 }))
    expect(s.primary.sub).toBe('About the same time as fastest · arrive 10:52 PM')
  })

  it('shows a single lower-risk fastest route when PathPro has no alternative', () => {
    const s = summarizeRoutes(routes({ pathpro: null, time_cost_min: null, exposure_reduction_pct: null }))

    expect(s.primary.kind).toBe('fast')
    expect(s.primary.label).toBe('Route')
    expect(s.primary.title).toBe('18 min · already the lower-risk option')
    expect(s.primary.sub).toBe('arrive 10:48 PM')
    expect(s.secondary).toBeNull()
  })
})

describe('templateSummary', () => {
  it('names the avoided stretch and the PathPro route', () => {
    expect(templateSummary(routes())).toBe(
      'The PathPro route adds 4.3 min and cuts traffic-risk exposure 49% by avoiding Peachtree Place Northwest.',
    )
  })

  it('handles the single-route case', () => {
    const single = routes({ pathpro: null })
    expect(templateSummary(single)).toContain('busiest stretch is Fifth Street Northwest')
    const bare = routes({ pathpro: null, fastest: { ...routes().fastest, top_segments: [] } })
    expect(templateSummary(bare)).toBe('The fastest route is already the lower-risk option.')
  })
})
