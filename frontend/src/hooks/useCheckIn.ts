import { useCallback, useEffect, useState } from 'react'
import { msUntilCheckIn, scheduleCheckIn, snoozeCheckIn, type CheckIn } from '../lib/checkin'

export interface CheckInInput {
  /** GPS navigation only: a preview walk is a simulation. */
  enabled: boolean
  /** Expected walk time when navigation started; later ETA changes do not move the check-in. */
  etaS: number
  /** Arrived or walk ended: the check-in is cancelled. */
  finished: boolean
}

export interface CheckInState {
  due: boolean
  /** "I'm fine": ask again in ten minutes. */
  snooze: () => void
}

/** Asks "Everything OK?" when the walker hasn't arrived by ETA + 10 min. Entirely on-device. */
export function useCheckIn({ enabled, etaS, finished }: CheckInInput): CheckInState {
  const [checkIn, setCheckIn] = useState<CheckIn>(() => scheduleCheckIn(Date.now(), etaS))
  const [dueFor, setDueFor] = useState<CheckIn | null>(null)
  const active = enabled && !finished

  useEffect(() => {
    if (!active) return
    const wait = msUntilCheckIn(checkIn, Date.now())
    if (wait == null) return
    const id = window.setTimeout(() => setDueFor(checkIn), wait)
    return () => window.clearTimeout(id)
  }, [active, checkIn])

  const snooze = useCallback(() => setCheckIn(snoozeCheckIn(Date.now())), [])
  // "Due" belongs to one schedule: snoozing replaces the schedule, which clears it.
  return { due: active && dueFor === checkIn, snooze }
}
