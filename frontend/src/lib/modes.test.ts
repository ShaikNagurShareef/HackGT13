import { describe, expect, it } from 'vitest'
import type { ModeInfo } from '../api/schemas'
import {
  MODE_LABELS,
  TRAVEL_MODES,
  UNAVAILABLE_NOTE,
  arrivalRadiusM,
  continueHeadline,
  estimateMinutes,
  formatTripMinutes,
  isRideMode,
  isTravelMode,
  modeOptions,
  modeUnavailableMessage,
  networkLegendTitle,
  resolveMode,
  speedMps,
  tabDurations,
  travelingTo,
  tripNoun,
} from './modes'

const BIKE: ModeInfo = { key: 'bike', label: 'Bike', available: true, speed_kmh: 18, network: 'ride', static_prefix: 'ride_' }

describe('travel modes', () => {
  it('lists Walk · Bike · E-bike · Scooter in tab order', () => {
    expect(TRAVEL_MODES).toEqual(['walk', 'bike', 'ebike', 'scooter'])
    expect(TRAVEL_MODES.map((m) => MODE_LABELS[m])).toEqual(['Walk', 'Bike', 'E-bike', 'Scooter'])
    expect(isTravelMode('ebike')).toBe(true)
    expect(isTravelMode('bus')).toBe(false)
    expect(isRideMode('walk')).toBe(false)
    expect(isRideMode('scooter')).toBe(true)
  })

  it('always offers all four tabs: walk available, unlisted modes shown as unavailable (never hidden)', () => {
    const options = modeOptions([])

    expect(options.map((o) => o.key)).toEqual(['walk', 'bike', 'ebike', 'scooter'])
    expect(options.map((o) => o.available)).toEqual([true, false, false, false])
    expect(options[1]).toMatchObject({ network: 'ride', static_prefix: 'ride_' })
    expect(UNAVAILABLE_NOTE).toBe('Coming soon in this area')
  })

  it('uses the server entry for listed modes and keeps walk available', () => {
    const options = modeOptions([BIKE, { ...BIKE, key: 'walk', label: 'Walk', available: false, network: 'walk', static_prefix: '' }])

    expect(options[1]).toBe(BIKE)
    expect(options[0].available).toBe(true)
  })

  it('falls back to Walk when the requested mode is unavailable', () => {
    const options = modeOptions([BIKE])

    expect(resolveMode('bike', options)).toBe('bike')
    expect(resolveMode('scooter', options)).toBe('walk')
    expect(modeUnavailableMessage('scooter')).toBe("Scooter routes aren't available in this area yet. Showing the walk instead.")
  })

  it('reads speeds from the server, with sensible fallbacks', () => {
    expect(speedMps('bike', [BIKE])).toBeCloseTo(5)
    expect(speedMps('walk', [])).toBeCloseTo(1.3)
    expect(speedMps('ebike', [])).toBeGreaterThan(speedMps('bike', []))
  })

  it('formats durations per mode ("12 min ride")', () => {
    expect(formatTripMinutes(720, 'bike')).toBe('12 min ride')
    expect(formatTripMinutes(720, 'walk')).toBe('12 min walk')
    expect(formatTripMinutes(10, 'scooter')).toBe('1 min ride')
    expect(tripNoun('ebike')).toBe('ride')
    expect(tripNoun('walk')).toBe('walk')
    expect(estimateMinutes(4500, 'bike', [BIKE])).toBe(15)
    expect(estimateMinutes(0, 'bike', [BIKE])).toBe(1)
  })

  it('writes mode-aware navigation copy and arrival radius', () => {
    expect(continueHeadline('Spring Street', 'walk')).toBe('Continue on Spring Street')
    expect(continueHeadline('Spring Street', 'bike')).toBe('Keep riding on Spring Street')
    expect(continueHeadline(null, 'scooter')).toBe('Keep riding on the PathPro route')
    expect(arrivalRadiusM('walk')).toBe(30)
    expect(arrivalRadiusM('bike')).toBe(40)
    expect(travelingTo('walk', 'Midtown')).toBe('Walking to Midtown')
    expect(travelingTo('scooter', 'Midtown')).toBe('Riding to Midtown')
  })

  it('titles the street legend for the network on the map', () => {
    expect(networkLegendTitle('walk')).toBe('Traffic risk to pedestrians')
    expect(networkLegendTitle('ebike')).toBe('Traffic risk to people on bikes & scooters')
  })

  it('gives each tab a fetched duration, an estimate, or nothing when unavailable', () => {
    const options = modeOptions([BIKE])
    const tabs = tabDurations(options, { walk: 1500 }, 4500)

    expect(tabs.walk).toEqual({ minutes: 25, estimated: false })
    expect(tabs.bike).toEqual({ minutes: 15, estimated: true })
    expect(tabs.scooter).toBeNull()
    expect(tabDurations(options, {}, null).bike).toBeNull()
  })
})
