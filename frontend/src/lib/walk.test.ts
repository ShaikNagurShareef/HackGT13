import { describe, expect, it } from 'vitest'
import { alertText, cumulativeDistances, dueAlert, pointAlong, type WalkAlert } from './walk'

const LINE: [number, number][] = [
  [-84.4, 33.77],
  [-84.39, 33.77], // ~925 m east
  [-84.39, 33.78], // ~1110 m north
]

const ALERTS: WalkAlert[] = [
  { start_m: 300, end_m: 360, names: ['Spring Street'], score: 95, stretches: 1 },
  { start_m: 400, end_m: 520, names: ['10th Street', 'Peachtree Street'], score: 98, stretches: 2 },
]

describe('walk geometry', () => {
  it('accumulates distance and interpolates positions', () => {
    const cum = cumulativeDistances(LINE)

    expect(cum[1]).toBeGreaterThan(900)
    expect(cum[1]).toBeLessThan(950)
    const mid = pointAlong(LINE, cum, cum[1] / 2)
    expect(mid[0]).toBeCloseTo(-84.395, 4)
    expect(pointAlong(LINE, cum, -5)).toEqual(LINE[0])
    expect(pointAlong(LINE, cum, 1e9)).toEqual(LINE[2])
  })
})

describe('dueAlert (VOX-02)', () => {
  it('fires 60 m before a stretch, once', () => {
    const none = { spoken: new Set<number>(), lastSpokenS: null }

    expect(dueAlert(ALERTS, 200, 150, none)).toBeNull()
    expect(dueAlert(ALERTS, 245, 190, none)).toBe(0)
    expect(dueAlert(ALERTS, 250, 195, { spoken: new Set([0]), lastSpokenS: null })).toBeNull()
  })

  it('waits at least 45 s of walk time between alerts', () => {
    const justSpoke = { spoken: new Set([0]), lastSpokenS: 190 }

    expect(dueAlert(ALERTS, 345, 220, justSpoke)).toBeNull()
    expect(dueAlert(ALERTS, 345, 240, justSpoke)).toBe(1)
  })

  it('never fires for a stretch already passed', () => {
    expect(dueAlert(ALERTS, 600, 500, { spoken: new Set(), lastSpokenS: null })).toBeNull()
  })
})

describe('alertText (EC-45, copy rules)', () => {
  it('describes single and merged stretches calmly', () => {
    expect(alertText(ALERTS[0])).toBe('In 60 meters, Spring Street has high traffic risk. Take extra care crossing.')
    expect(alertText(ALERTS[1])).toContain('Next 120 meters has 2 high-risk stretches')
    for (const a of ALERTS) expect(alertText(a)).not.toMatch(/safe|danger/i)
  })
})
