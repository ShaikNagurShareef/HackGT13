import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCheckIn, type CheckInInput } from './useCheckIn'

const MIN = 60_000
const START = Date.UTC(2026, 8, 26, 22, 30)

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function setup(over: Partial<CheckInInput> = {}) {
  const initial: CheckInInput = { enabled: true, etaS: 12 * 60, finished: false, ...over }
  return renderHook((props: CheckInInput) => useCheckIn(props), { initialProps: initial })
}

describe('useCheckIn', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(START)
  })
  afterEach(() => vi.useRealTimers())

  it('asks ten minutes after the expected arrival, not before', async () => {
    const { result } = setup()

    await advance(22 * MIN - 1000)
    expect(result.current.due).toBe(false)
    await advance(1000)
    expect(result.current.due).toBe(true)
  })

  it('"I\'m fine" snoozes for ten minutes', async () => {
    const { result } = setup()
    await advance(22 * MIN)

    act(() => result.current.snooze())
    expect(result.current.due).toBe(false)
    await advance(10 * MIN - 1000)
    expect(result.current.due).toBe(false)
    await advance(1000)
    expect(result.current.due).toBe(true)
  })

  it('is cancelled on arrival or when the walk ends', async () => {
    const { result, rerender } = setup()
    await advance(22 * MIN)
    expect(result.current.due).toBe(true)

    rerender({ enabled: true, etaS: 12 * 60, finished: true })
    expect(result.current.due).toBe(false)
    await advance(60 * MIN)
    expect(result.current.due).toBe(false)
  })

  it('never asks when disabled (preview walks)', async () => {
    const { result } = setup({ enabled: false })

    await advance(120 * MIN)

    expect(result.current.due).toBe(false)
  })

  it('keeps the schedule from when navigation started, not later ETA updates', async () => {
    const { result, rerender } = setup()
    await advance(5 * MIN)

    rerender({ enabled: true, etaS: 60 * 60, finished: false })
    await advance(17 * MIN)

    expect(result.current.due).toBe(true)
  })
})
