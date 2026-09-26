import { describe, expect, it } from 'vitest'
import { DEFAULT_STATE, parseState, serializeState, type ViewState } from './urlState'

describe('url state', () => {
  it('round-trips a full view', () => {
    const view: ViewState = {
      from: { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' },
      to: { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' },
      depart: '2026-09-25T22:30',
      cond: 'wet',
      hour: 22,
      day: 'friday',
      seg: 1234,
      demo: true,
      prefer: 'lit_and_busy',
      mode: 'ebike',
    }

    expect(parseState(serializeState(view))).toEqual(view)
  })

  it('defaults cleanly and serializes defaults to empty', () => {
    expect(parseState('')).toEqual(DEFAULT_STATE)
    expect(serializeState(DEFAULT_STATE)).toBe('')
  })

  it('rejects malformed or hostile values', () => {
    const s = parseState('?from=abc,def&cond=hail&h=99&seg=-4&t=<script>&day=funday')

    expect(s.from).toBeNull()
    expect(s.cond).toBe('live')
    expect(s.hour).toBeNull()
    expect(s.seg).toBeNull()
    expect(s.depart).toBe('now')
    expect(s.day).toBeNull()
  })

  it('caps place labels', () => {
    const s = parseState(`?to=33.78,-84.38,${'x'.repeat(200)}`)

    expect(s.to?.label.length).toBe(80)
  })

  it('keeps the route preference short in the URL and ignores unknown values', () => {
    expect(serializeState({ ...DEFAULT_STATE, prefer: 'lit_and_busy' })).toBe('?pref=lit')
    expect(parseState('?pref=lit').prefer).toBe('lit_and_busy')
    expect(parseState('?pref=crime').prefer).toBe('lower_traffic_risk')
  })

  it('keeps the travel mode in the URL (walk is the default) and ignores unknown modes', () => {
    expect(serializeState({ ...DEFAULT_STATE, mode: 'bike' })).toBe('?mode=bike')
    expect(parseState('?mode=scooter').mode).toBe('scooter')
    expect(parseState('?mode=car').mode).toBe('walk')
    expect(DEFAULT_STATE.mode).toBe('walk')
  })
})
