import { describe, expect, it } from 'vitest'
import {
  CHECKIN_GRACE_MS,
  CHECKIN_SNOOZE_MS,
  cancelCheckIn,
  isCheckInDue,
  msUntilCheckIn,
  scheduleCheckIn,
  snoozeCheckIn,
} from './checkin'

const START = Date.UTC(2026, 8, 26, 22, 30)
const MIN = 60_000

describe('check-in timing', () => {
  it('is due ten minutes after the expected arrival', () => {
    const checkIn = scheduleCheckIn(START, 720)

    expect(CHECKIN_GRACE_MS).toBe(10 * MIN)
    expect(checkIn.dueAt).toBe(START + 12 * MIN + 10 * MIN)
    expect(isCheckInDue(checkIn, START + 21 * MIN)).toBe(false)
    expect(isCheckInDue(checkIn, START + 22 * MIN)).toBe(true)
    expect(msUntilCheckIn(checkIn, START)).toBe(22 * MIN)
    expect(msUntilCheckIn(checkIn, START + 30 * MIN)).toBe(0)
  })

  it('snoozes for ten minutes from now', () => {
    const now = START + 25 * MIN

    const snoozed = snoozeCheckIn(now)

    expect(CHECKIN_SNOOZE_MS).toBe(10 * MIN)
    expect(snoozed.dueAt).toBe(now + 10 * MIN)
    expect(isCheckInDue(snoozed, now + 9 * MIN)).toBe(false)
    expect(isCheckInDue(snoozed, now + 10 * MIN)).toBe(true)
  })

  it('is never due once cancelled (arrived or walk ended)', () => {
    const cancelled = cancelCheckIn()

    expect(cancelled.dueAt).toBeNull()
    expect(isCheckInDue(cancelled, START + 999 * MIN)).toBe(false)
    expect(msUntilCheckIn(cancelled, START)).toBeNull()
  })

  it('treats a missing or negative ETA as zero', () => {
    expect(scheduleCheckIn(START, -30).dueAt).toBe(START + 10 * MIN)
    expect(scheduleCheckIn(START, Number.NaN).dueAt).toBe(START + 10 * MIN)
  })
})
