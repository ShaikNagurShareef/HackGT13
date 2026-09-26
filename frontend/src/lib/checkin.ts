/**
 * Local check-in while navigating: if the walker hasn't arrived ten minutes after the expected
 * arrival, PathPro asks "Everything OK?". Pure timing only; nothing leaves the device.
 */

export const CHECKIN_GRACE_MS = 10 * 60_000
export const CHECKIN_SNOOZE_MS = 10 * 60_000
const MS_PER_S = 1000

/** When the next check-in is due (epoch ms), or null once cancelled. */
export interface CheckIn {
  readonly dueAt: number | null
}

export function scheduleCheckIn(startedAtMs: number, etaS: number): CheckIn {
  const eta = Number.isFinite(etaS) ? Math.max(0, etaS) : 0
  return { dueAt: startedAtMs + eta * MS_PER_S + CHECKIN_GRACE_MS }
}

export function snoozeCheckIn(nowMs: number): CheckIn {
  return { dueAt: nowMs + CHECKIN_SNOOZE_MS }
}

export function cancelCheckIn(): CheckIn {
  return { dueAt: null }
}

export function isCheckInDue(checkIn: CheckIn, nowMs: number): boolean {
  return checkIn.dueAt != null && nowMs >= checkIn.dueAt
}

export function msUntilCheckIn(checkIn: CheckIn, nowMs: number): number | null {
  return checkIn.dueAt == null ? null : Math.max(0, checkIn.dueAt - nowMs)
}
