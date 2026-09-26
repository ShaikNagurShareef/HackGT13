import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { GeoFix, GeoStatus } from '../lib/origin'
import { DEFAULT_STATE, type Place, type ViewState } from '../state/urlState'
import { useTripPlanner } from './useTripPlanner'

const BBOX = [-84.55, 33.64, -84.28, 33.88]
const MIDTOWN: Place = { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' }
const KLAUS: Place = { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' }
const HERE: GeoFix = { lat: 33.7766, lon: -84.3963, accuracy: 10, heading: null, at: 0 }
const YOU = { lat: 33.7766, lon: -84.3963, label: 'Your location' }

interface Props {
  view: ViewState
  status: GeoStatus
  position: GeoFix | null
  bbox?: ReadonlyArray<number> | null
}

function setup(initial: Props) {
  const update = vi.fn()
  const request = vi.fn()
  const hook = renderHook(
    ({ view, status, position, bbox = BBOX }: Props) =>
      useTripPlanner({ view, update, geo: { status, position, request, error: null }, bbox }),
    { initialProps: initial },
  )
  return { ...hook, update, request }
}

describe('useTripPlanner', () => {
  it('starts from "Your location" when GPS is inside coverage', () => {
    const { result, update } = setup({ view: DEFAULT_STATE, status: 'granted', position: HERE })

    result.current.pickDestination(MIDTOWN)

    expect(result.current.origin.status).toBe('ready')
    expect(update).toHaveBeenCalledWith({ from: YOU, to: MIDTOWN, seg: null })
  })

  it('keeps a chosen start', () => {
    const { result, update } = setup({ view: { ...DEFAULT_STATE, from: KLAUS }, status: 'granted', position: HERE })

    result.current.pickDestination(MIDTOWN)

    expect(update).toHaveBeenCalledWith({ to: MIDTOWN, seg: null })
  })

  it('asks politely for location when a destination is picked without GPS, then fills the start', () => {
    const { result, update, request, rerender } = setup({ view: DEFAULT_STATE, status: 'prompt', position: null })

    result.current.pickDestination(MIDTOWN)
    expect(update).toHaveBeenCalledWith({ to: MIDTOWN, seg: null })
    expect(request).toHaveBeenCalled()

    rerender({ view: { ...DEFAULT_STATE, to: MIDTOWN }, status: 'granted', position: HERE })
    expect(update).toHaveBeenLastCalledWith({ from: YOU })
  })

  it('does not route from outside Atlanta', () => {
    const far = { ...HERE, lat: 34.2, lon: -84.1 }
    const { result, update } = setup({ view: { ...DEFAULT_STATE, to: MIDTOWN }, status: 'granted', position: far })

    expect(result.current.origin.status).toBe('outside')
    expect(update).not.toHaveBeenCalled()
  })

  it('swaps, picks a start, and clears the trip', () => {
    const view = { ...DEFAULT_STATE, from: KLAUS, to: MIDTOWN, seg: 4 }
    const { result, update } = setup({ view, status: 'denied', position: null })

    result.current.swap()
    expect(update).toHaveBeenLastCalledWith({ from: MIDTOWN, to: KLAUS, seg: null })
    result.current.pickOrigin(MIDTOWN)
    expect(update).toHaveBeenLastCalledWith({ from: MIDTOWN, seg: null })
    result.current.clear()
    expect(update).toHaveBeenLastCalledWith({ from: null, to: null, seg: null })
  })

  it('waits for the coverage area before trusting a GPS start', () => {
    const { result, update } = setup({ view: { ...DEFAULT_STATE, to: MIDTOWN }, status: 'granted', position: HERE, bbox: null })

    expect(result.current.origin).toEqual({ place: null, status: 'locating' })
    expect(update).not.toHaveBeenCalled()
  })
})
