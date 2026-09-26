import { useEffect, useState } from 'react'
import { ApiError, api, type Condition } from '../api/client'
import type { SegmentDetail, TravelMode } from '../api/schemas'
import { useLatest } from './useLatest'

/** Street detail for the selected segment (EXP-01..05). */
export function useSegmentDetail(
  seg: number | null,
  at: string,
  cond: Condition,
  onError: (message: string) => void,
  /** Ride modes: segment ids index the ride network. */
  mode: TravelMode = 'walk',
): SegmentDetail | null {
  const [detail, setDetail] = useState<SegmentDetail | null>(null)
  const latest = useLatest(onError)

  useEffect(() => {
    if (seg == null) return
    let cancelled = false
    api
      .segment(seg, at, cond, mode)
      .then((d) => !cancelled && setDetail(d))
      .catch((e: unknown) => !cancelled && latest.current(e instanceof ApiError ? e.message : 'Could not load details.'))
    return () => {
      cancelled = true
    }
  }, [seg, at, cond, mode, latest])

  return seg == null || detail?.seg_id !== seg ? null : detail
}
