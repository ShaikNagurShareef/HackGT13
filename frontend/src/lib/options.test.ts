import { describe, expect, it } from 'vitest'
import { departLabel, statusLabel } from './options'

const DEFAULTS = { cond: 'live' as const, depart: 'now', hour: null, cityMode: false }

describe('statusLabel (home status chip)', () => {
  it('is hidden when everything is at its default', () => {
    expect(statusLabel(DEFAULTS)).toBeNull()
  })

  it('summarises only the deviations', () => {
    expect(statusLabel({ ...DEFAULTS, cond: 'wet', depart: '2026-09-25T22:00' })).toBe('☂ Wet · 10 PM')
    expect(statusLabel({ ...DEFAULTS, cond: 'dry' })).toBe('Dry')
    expect(statusLabel({ ...DEFAULTS, depart: '+15m' })).toBe('In 15 min')
    expect(statusLabel({ ...DEFAULTS, hour: 22, cityMode: true })).toBe('Tides 10 PM · City Pulse')
  })
})

describe('statusLabel (personal safety)', () => {
  it('names the safety map mode and a non-default route preference', () => {
    expect(statusLabel({ ...DEFAULTS, safetyMode: true })).toBe('Personal safety')
    expect(statusLabel({ ...DEFAULTS, prefer: 'lit_and_busy' })).toBe('Well-lit & busier')
    expect(statusLabel({ ...DEFAULTS, prefer: 'lower_traffic_risk' })).toBeNull()
  })
})

describe('departLabel', () => {
  it('reads relative and Atlanta wall-clock departures', () => {
    expect(departLabel('now')).toBe('Now')
    expect(departLabel('+1h')).toBe('In 1 h')
    expect(departLabel('+90m')).toBe('In 90 min')
    expect(departLabel('2026-09-25T22:30')).toBe('10:30 PM')
    expect(departLabel('2026-09-26T09:00:00')).toBe('9 AM')
    expect(departLabel('garbage')).toBe('Now')
  })
})

describe('statusLabel (travel mode)', () => {
  it('names a ride mode and drops the walk-only preference', () => {
    expect(statusLabel({ ...DEFAULTS, mode: 'bike' })).toBe('Bike')
    expect(statusLabel({ ...DEFAULTS, mode: 'ebike', prefer: 'lit_and_busy' })).toBe('E-bike')
    expect(statusLabel({ ...DEFAULTS, mode: 'walk' })).toBeNull()
  })
})
