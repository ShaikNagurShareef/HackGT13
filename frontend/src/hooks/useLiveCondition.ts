import { useEffect, useState } from 'react'
import { api, type Condition } from '../api/client'

export interface LiveCondition {
  wet: boolean
  label: string | null
}

const UNAVAILABLE = 'Live weather unavailable — using dry conditions.'

/** Current Atlanta weather for "Live" mode; falls back to dry with an honest label. */
export function useLiveCondition(cond: Condition): LiveCondition {
  const [live, setLive] = useState<LiveCondition>({ wet: false, label: null })

  useEffect(() => {
    if (cond !== 'live') return
    let cancelled = false
    api
      .liveConditions()
      .then((c) => !cancelled && setLive({ wet: c.cond === 'wet', label: c.label }))
      .catch(() => !cancelled && setLive({ wet: false, label: UNAVAILABLE }))
    return () => {
      cancelled = true
    }
  }, [cond])

  return live
}
