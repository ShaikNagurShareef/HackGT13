import { describe, expect, it } from 'vitest'
import type { Area } from '../api/schemas'
import { segment } from '../test/fixtures'
import { AREA_ASK_LABEL, ROUTE_ASK_LABEL, screenAskTarget, segmentAskTarget } from './askContext'

const area: Area = {
  cell: '8844c0a305fffff',
  lat: 33.77,
  lon: -84.39,
  score: 70,
  band: 'Elevated',
  confidence: 'medium',
  baseline_points: 50,
  factors: [],
  remainder_points: 20,
  crashes: 12,
  ped_crashes: 2,
  period: '2020-2024',
  in_street_coverage: false,
  condition_used: { cond: 'dry', source: 'override', label: 'Dry' },
  at: '2026-09-25T22:30:00-04:00',
}
const nothing = { detail: null, area: null, routeKey: null, cond: 'live', mode: 'walk' } as const

describe('screenAskTarget (the agent button asks about what is on screen)', () => {
  it('asks about the open street sheet, exactly like the street pill', () => {
    const detail = segment()
    const target = screenAskTarget({ ...nothing, detail, routeKey: 'rk-1', cond: 'wet', mode: 'bike' })

    expect(target).toEqual(segmentAskTarget(detail, 'wet', 'bike'))
    expect(target).toEqual({
      context: { kind: 'segment', seg_id: 11, t: '2026-09-25T22:30:00-04:00', cond: 'wet', mode: 'bike' },
      label: 'Fifth Street Northwest · 10 PM',
    })
  })

  it('asks about the displayed route when no street sheet is open', () => {
    expect(screenAskTarget({ ...nothing, routeKey: 'rk-123' })).toEqual({
      context: { kind: 'route', route_key: 'rk-123' },
      label: ROUTE_ASK_LABEL,
    })
  })

  it('asks about an open City Pulse area card', () => {
    expect(screenAskTarget({ ...nothing, area, cond: 'dry' })).toEqual({
      context: { kind: 'area', cell: '8844c0a305fffff', t: '2026-09-25T22:30:00-04:00', cond: 'dry' },
      label: AREA_ASK_LABEL,
    })
  })

  it('prefers the area card when it covers the route or street (it is what is on screen)', () => {
    expect(screenAskTarget({ ...nothing, area, routeKey: 'rk-123' })?.context.kind).toBe('area')
    expect(screenAskTarget({ ...nothing, area, detail: segment() })?.context.kind).toBe('area')
  })

  it('has no context when nothing is on screen (the server uses the current conditions)', () => {
    expect(screenAskTarget(nothing)).toBeNull()
  })
})
