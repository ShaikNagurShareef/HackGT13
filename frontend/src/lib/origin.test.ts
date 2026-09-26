import { describe, expect, it } from 'vitest'
import { YOUR_LOCATION, originMessage, resolveOrigin } from './origin'

const BBOX = [-84.55, 33.64, -84.28, 33.88]
const GT = { lat: 33.7766, lon: -84.3963, accuracy: 12, heading: null, at: 0 }

describe('resolveOrigin', () => {
  it('uses the GPS fix as "Your location" inside coverage', () => {
    expect(resolveOrigin({ status: 'granted', position: GT }, BBOX)).toEqual({
      place: { lat: 33.7766, lon: -84.3963, label: YOUR_LOCATION },
      status: 'ready',
    })
  })

  it('reports outside coverage instead of routing from there', () => {
    const decatur = { ...GT, lat: 33.95, lon: -84.1 }
    expect(resolveOrigin({ status: 'granted', position: decatur }, BBOX)).toEqual({ place: null, status: 'outside' })
  })

  it('maps permission states without a fix', () => {
    expect(resolveOrigin({ status: 'locating', position: null }, BBOX).status).toBe('locating')
    expect(resolveOrigin({ status: 'granted', position: null }, BBOX).status).toBe('locating')
    expect(resolveOrigin({ status: 'denied', position: null }, BBOX).status).toBe('denied')
    expect(resolveOrigin({ status: 'unavailable', position: null }, BBOX).status).toBe('unavailable')
    expect(resolveOrigin({ status: 'prompt', position: null }, BBOX).status).toBe('ask')
  })
})

describe('originMessage', () => {
  it('explains each fallback in friendly, scoped words', () => {
    expect(originMessage('outside')).toBe(
      "You're outside Atlanta — PathPro covers the City of Atlanta. Pick a starting point.",
    )
    expect(originMessage('denied')).toMatch(/Location is off.*Pick a starting point/)
    expect(originMessage('unavailable')).toMatch(/Pick a starting point/)
    expect(originMessage('locating')).toBe('Finding your location…')
    expect(originMessage('ready')).toBeNull()
    expect(originMessage('ask')).toMatch(/Pick a starting point/)
  })
})
